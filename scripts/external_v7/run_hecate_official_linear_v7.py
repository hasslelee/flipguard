#!/usr/bin/env python3
"""Execute frozen official HECATE LinearRegression plans with raw outputs."""

from __future__ import annotations

import argparse
import builtins
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

import numpy as np


EXPECTED_COMMIT = "aedca73dac27b86044721781b9fca8d12e665876"
SEED = 20260806
MODES = ("eva", "elasm")
WATERLINE = 40
LOOP_COUNT = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def array_digest(value: np.ndarray) -> str:
    material = np.asarray(value, dtype=np.float64).tobytes(order="C")
    return f"sha256:{hashlib.sha256(material).hexdigest()}"


def run(command: list[str], cwd: Path, stdout: Path, stderr: Path) -> tuple[int, float]:
    started = time.monotonic()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        result = subprocess.run(
            command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, check=False
        )
    return result.returncode, time.monotonic() - started


def reference(seed: int) -> tuple[np.ndarray, np.ndarray, float, float]:
    generator = random.Random(seed)
    x = np.asarray([generator.uniform(-1, 1) for _ in range(4096)], dtype=np.float64)
    y = np.asarray(
        [2.0 * point + 1.0 + generator.uniform(-0.01, 0.01) for point in x],
        dtype=np.float64,
    )
    weight = 1.0
    bias = 0.0
    for _ in range(LOOP_COUNT):
        error = weight * x + bias - y
        weight += -0.01 * float(np.sum(error * x)) / 2048.0
        bias += -0.01 * float(np.sum(error)) / 2048.0
    return x, y, weight, bias


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0])
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()
    if commit != EXPECTED_COMMIT:
        raise ValueError(f"HECATE source drift: {commit}")
    required = [
        root / "build/bin/hecate-opt",
        root / "build/lib/libHecateFrontend.so",
        root / "build/lib/libSEAL_HEVM.so",
        root / "profiled_SEAL_CPU.json",
        root / "examples/benchmarks/2_ML/LinearRegression.py",
        root / "examples/tests/2_ML/LinearRegression.py",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    output.mkdir(parents=True)
    os.environ["HECATE"] = str(root)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [
            str(root / "python/hecate"),
            str(root / "python/hetorch"),
            str(root / "python/poly"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    sys.path[:0] = [
        str(root / "python/hecate"),
        str(root / "python/hetorch"),
        str(root / "python/poly"),
    ]
    library_path = os.pathsep.join(
        [str(root / "build/lib"), os.environ.get("LD_LIBRARY_PATH", "")]
    )
    os.environ["LD_LIBRARY_PATH"] = library_path

    examples = root / "examples"
    trace_dir = examples / "traced"
    (trace_dir / "cst").mkdir(parents=True, exist_ok=True)
    trace_command = [
        "python3", str(root / "examples/benchmarks/2_ML/LinearRegression.py"),
        "LinearRegression", "--opt", "eva", "--waterline", str(WATERLINE),
        "--library", "SEAL", "--device", "CPU", "--loop_count", str(LOOP_COUNT),
        "--input", "false",
    ]
    trace_exit, trace_seconds = run(
        trace_command, examples, output / "trace.stdout", output / "trace.stderr"
    )
    if trace_exit != 0:
        raise RuntimeError("official HECATE trace failed")
    trace = trace_dir / "LinearRegression.mlir"
    const = trace_dir / "cst/_hecate_LinearRegression.cst"
    if not trace.is_file() or not const.is_file():
        raise FileNotFoundError("official HECATE trace outputs missing")
    shutil.copy2(trace, output / "LinearRegression.mlir")
    shutil.copy2(const, output / "_hecate_LinearRegression.cst")

    x, y, plain_weight, plain_bias = reference(SEED)
    np.savez_compressed(output / "frozen_input.npz", x=x, y=y)
    rows: list[dict[str, object]] = []
    for index, mode in enumerate(MODES, start=1):
        mode_dir = output / mode
        mode_dir.mkdir()
        optimized_dir = examples / "optimized" / mode
        optimized_dir.mkdir(parents=True, exist_ok=True)
        mlir = optimized_dir / f"LinearRegression.{WATERLINE}.mlir"
        compile_command = [
            str(root / "build/bin/hecate-opt"), f"--{mode}",
            f"--ckks-config={root / 'profiled_SEAL_CPU.json'}",
            f"--waterline={WATERLINE}", "--enable-debug-printer", str(trace),
            "--mlir-disable-threading", "-o", str(mlir),
        ]
        compile_exit, compile_seconds = run(
            compile_command, examples, mode_dir / "compile.stdout", mode_dir / "compile.stderr"
        )
        if compile_exit != 0:
            rows.append({
                "mode": mode, "compile_status": "FAIL", "compile_wall_seconds": compile_seconds,
                "encrypted_status": "NOT_RUN", "keygen_ms": "", "load_ms": "", "encryption_ms": "",
                "evaluation_ms": "", "decryption_ms": "", "total_ms": "", "rms_error": "",
                "max_absolute_error": "", "evidence_level": 1,
            })
            args.status_file.write_text(f"{index}\n", encoding="ascii")
            continue
        hevm_path = optimized_dir / f"LinearRegression.{WATERLINE}._hecate_LinearRegression.hevm"
        if not hevm_path.is_file():
            raise FileNotFoundError(hevm_path)
        shutil.copy2(mlir, mode_dir / "optimized.mlir")
        shutil.copy2(hevm_path, mode_dir / "plan.hevm")

        import hecate as hc

        hc.setLibnHW([mode, WATERLINE, "LinearRegression", "SEAL", "CPU"])
        context = output / "key_contexts" / mode
        if context.exists():
            raise FileExistsError(context)
        builtins.input = lambda _prompt="": ""
        total_start = time.perf_counter_ns()
        started = time.perf_counter_ns()
        hevm = hc.HEVM(path=str(context))
        keygen_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        hevm.load(str(const), str(hevm_path))
        load_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        hevm.setInput(0, x)
        hevm.setInput(1, y)
        encryption_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        hevm.run()
        evaluation_ms = (time.perf_counter_ns() - started) / 1_000_000
        started = time.perf_counter_ns()
        encrypted = np.asarray(hevm.getOutput(), dtype=np.float64)
        decryption_ms = (time.perf_counter_ns() - started) / 1_000_000
        total_ms = (time.perf_counter_ns() - total_start) / 1_000_000
        if encrypted.shape[0] != 2:
            raise ValueError(f"unexpected HECATE output shape: {encrypted.shape}")
        error_w = encrypted[0] - plain_weight
        error_b = encrypted[1] - plain_bias
        combined = np.concatenate([error_w, error_b])
        rms = float(np.sqrt(np.mean(np.square(combined))))
        maximum = float(np.max(np.abs(combined)))
        np.savez_compressed(
            mode_dir / "decrypted_outputs.npz", encrypted_weight=encrypted[0], encrypted_bias=encrypted[1]
        )
        result = {
            "schema_version": "flipguard_external_hecate_official_result_v1",
            "mode": mode,
            "waterline": WATERLINE,
            "loop_count": LOOP_COUNT,
            "seed": SEED,
            "input_x_sha256": array_digest(x),
            "input_y_sha256": array_digest(y),
            "plaintext_weight": plain_weight,
            "plaintext_bias": plain_bias,
            "encrypted_weight_slot0": float(encrypted[0, 0]),
            "encrypted_bias_slot0": float(encrypted[1, 0]),
            "raw_output_shape": list(encrypted.shape),
            "rms_error": rms,
            "max_absolute_error": maximum,
            "timing_ms": {
                "key_generation": keygen_ms, "load_preprocess": load_ms,
                "encryption": encryption_ms, "evaluation": evaluation_ms,
                "decryption": decryption_ms, "total": total_ms,
            },
            "decision_rule": "NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD",
            "decision_gate_state": "NOT_EVALUATED",
        }
        (mode_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        rows.append({
            "mode": mode, "compile_status": "PASS", "compile_wall_seconds": compile_seconds,
            "encrypted_status": "PASS", "keygen_ms": keygen_ms, "load_ms": load_ms,
            "encryption_ms": encryption_ms, "evaluation_ms": evaluation_ms,
            "decryption_ms": decryption_ms, "total_ms": total_ms, "rms_error": rms,
            "max_absolute_error": maximum, "evidence_level": 3,
        })
        args.status_file.write_text(f"{index}\n", encoding="ascii")

    write_csv(output / "records.csv", rows)
    manifest = {
        "schema_version": "flipguard_external_hecate_official_v7",
        "provider": "CoreLab HECATE current source",
        "source_commit": EXPECTED_COMMIT,
        "workload": "official_LinearRegression",
        "modes": list(MODES),
        "hecate_mode_flag_present": False,
        "waterline": WATERLINE,
        "loop_count": LOOP_COUNT,
        "seed": SEED,
        "plans_generated": sum(row["compile_status"] == "PASS" for row in rows),
        "encrypted_end_to_end_runs": sum(row["encrypted_status"] == "PASS" for row in rows),
        "decision_output_available": False,
        "maximum_evidence_level": max(int(row["evidence_level"]) for row in rows),
        "optimizer_sha256": sha256_file(root / "build/bin/hecate-opt"),
        "runtime_sha256": sha256_file(root / "build/lib/libSEAL_HEVM.so"),
        "trace_sha256": sha256_file(output / "LinearRegression.mlir"),
        "input_sha256": sha256_file(output / "frozen_input.npz"),
        "source_modifications": 0,
        "outlier_removal": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sums = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if "key_contexts" in path.parts or path.name == "SHA256SUMS":
            continue
        sums.append(f"{sha256_file(path).removeprefix('sha256:')}  {path.relative_to(output)}")
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["encrypted_end_to_end_runs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
