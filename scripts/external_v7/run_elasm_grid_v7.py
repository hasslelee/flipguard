#!/usr/bin/env python3
"""Run the frozen 72-plan ELASM/EVA grid with actual decrypted outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


PINNED_COMMIT = "3c37c11b29ca480525bb6681e0254bdf90029425"
FIELDS = [
    "mode", "waterline", "compile_status", "compile_exit_status", "compile_wall_seconds",
    "execution_status", "execution_exit_status", "execution_wrapper_wall_seconds",
    "reported_hevm_seconds", "reported_rms_error", "encrypted_end_to_end",
    "actual_output_available", "decision_output_available", "evidence_level", "failure_reason",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_records(path: Path, records: list[dict[str, object]]) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    temporary.replace(path)


def run(command: list[str], cwd: Path, stdout: Path, stderr: Path) -> tuple[int, float]:
    started = time.monotonic()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        completed = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err, check=False)
    return completed.returncode, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    source = args.source_root.resolve()
    runtime = args.runtime_root.resolve()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    for checkout in (source, runtime):
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, check=True, text=True, capture_output=True).stdout.strip()
        if commit != PINNED_COMMIT:
            raise ValueError(f"ELASM source drift at {checkout}: {commit}")
    if args.seed != 20260805:
        raise ValueError("ELASM V7 seed changed")
    output.mkdir(parents=True)
    examples = runtime / "examples"
    optimizer = runtime / "build/bin/hecate-opt"
    trace = examples / "traced/LinearRegression.mlir"
    test_source = source / "examples/tests/LinearRegression.py"
    for required in (optimizer, trace, test_source, runtime / "config.json"):
        if not required.is_file():
            raise FileNotFoundError(required)

    records: list[dict[str, object]] = []
    for mode in ("eva", "elasm"):
        optimized = examples / "optimized" / mode
        optimized.mkdir(parents=True, exist_ok=True)
        for waterline in range(15, 51):
            run_dir = output / f"{mode}_{waterline:02d}"
            run_dir.mkdir()
            mlir = optimized / f"LinearRegression.{waterline}.mlir"
            compile_command = [
                str(optimizer), f"--{mode}", f"--ckks-config={runtime / 'config.json'}",
                f"--waterline={waterline}", str(trace), "-o", str(mlir),
            ]
            compile_exit, compile_wall = run(
                compile_command, examples, run_dir / "compile.stdout", run_dir / "compile.stderr"
            )
            execution_exit = -1
            execution_wall = 0.0
            rms = ""
            reported = ""
            reason = ""
            actual_output = False
            if compile_exit == 0:
                generated_hevm = optimized / f"LinearRegression.{waterline}._hecate_LinearRegression.hevm"
                generated_const = examples / "traced/_hecate_LinearRegression.cst"
                shutil.copy2(mlir, run_dir / "optimized.mlir")
                shutil.copy2(generated_hevm, run_dir / "plan.hevm")
                shutil.copy2(generated_const, run_dir / "constants.cst")
                result_json = run_dir / "result.json"
                result_npz = run_dir / "decrypted_outputs.npz"
                execution_command = [
                    "python3", str(Path(__file__).with_name("run_elasm_plan_v7.py")),
                    "--runtime-root", str(runtime), "--mode", mode, "--waterline", str(waterline),
                    "--seed", str(args.seed), "--context-root", str(runtime / "key_contexts" / f"{mode}_{waterline:02d}"),
                    "--output-json", str(result_json), "--output-npz", str(result_npz),
                ]
                execution_exit, execution_wall = run(
                    execution_command, examples, run_dir / "execute.stdout", run_dir / "execute.stderr"
                )
                if execution_exit == 0 and result_json.is_file() and result_npz.is_file():
                    result = json.loads(result_json.read_text(encoding="utf-8"))
                    reported = str(result["timing_ms"]["evaluation"] / 1000.0)
                    rms = str(result["rms_error"])
                    actual_output = True
                else:
                    reason = "OFFICIAL_HEVM_EXECUTION_FAILED"
            else:
                reason = "OFFICIAL_OPTIMIZER_FAILED"
            encrypted = compile_exit == 0 and execution_exit == 0 and actual_output
            records.append(
                {
                    "mode": mode,
                    "waterline": waterline,
                    "compile_status": "PASS" if compile_exit == 0 else "FAIL",
                    "compile_exit_status": compile_exit,
                    "compile_wall_seconds": f"{compile_wall:.9f}",
                    "execution_status": "PASS" if encrypted else "FAIL",
                    "execution_exit_status": execution_exit,
                    "execution_wrapper_wall_seconds": f"{execution_wall:.9f}",
                    "reported_hevm_seconds": reported,
                    "reported_rms_error": rms,
                    "encrypted_end_to_end": str(encrypted).lower(),
                    "actual_output_available": str(actual_output).lower(),
                    "decision_output_available": "false",
                    "evidence_level": 3 if encrypted else (2 if compile_exit == 0 else 1),
                    "failure_reason": reason,
                }
            )
            write_records(output / "records.csv", records)
            args.status_file.write_text(str(len(records)) + "\n", encoding="ascii")

    completed = sum(row["encrypted_end_to_end"] == "true" for row in records)
    manifest = {
        "schema_version": "flipguard_external_elasm_grid_v7",
        "provider": "ELASM",
        "provider_commit": PINNED_COMMIT,
        "workload": "official_LinearRegression",
        "modes": ["eva", "elasm"],
        "waterlines": list(range(15, 51)),
        "frozen_input_seed": args.seed,
        "plans_attempted": len(records),
        "plans_generated": sum(row["compile_status"] == "PASS" for row in records),
        "plans_executed": sum(int(row["execution_exit_status"]) != -1 for row in records),
        "encrypted_end_to_end_runs": completed,
        "decision_output_available": False,
        "evidence_level": 3 if completed else 2,
        "optimizer_sha256": sha256(optimizer),
        "trace_sha256": sha256(trace),
        "test_script_sha256": sha256(test_source),
        "records_sha256": sha256(output / "records.csv"),
        "source_modifications": 0,
        "outlier_removal": False,
        "fresh_context_per_plan": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name != "SHA256SUMS":
            checksums.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
