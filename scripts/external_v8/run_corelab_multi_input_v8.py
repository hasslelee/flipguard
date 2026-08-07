#!/usr/bin/env python3
"""Run the frozen 72-plan CoreLab EVA/ELASM grid on 200 unique inputs."""

from __future__ import annotations

import argparse
import builtins
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time

import numpy as np


PINNED_COMMIT = "3c37c11b29ca480525bb6681e0254bdf90029425"
SEED_DOMAIN = "flipguard-v8-corelab-linear-regression-200-inputs-20260807"
INPUT_COUNT = 200
POINTS = 4096
FIELDS = (
    "mode", "waterline", "plan_status", "input_id", "input_x_sha256", "input_y_sha256",
    "plaintext_w", "plaintext_c", "encrypted_w_slot0", "encrypted_c_slot0",
    "max_abs_w_error", "max_abs_c_error", "rms_error", "context_keygen_ms",
    "load_preprocess_ms", "encrypt_ms", "evaluate_ms", "decrypt_ms", "total_ms",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def digest_array(value: np.ndarray) -> str:
    return "sha256:" + hashlib.sha256(np.asarray(value, dtype=np.float64).tobytes(order="C")).hexdigest()


def make_input(index: int) -> tuple[np.ndarray, np.ndarray, float, float]:
    seed = int.from_bytes(hashlib.sha256(f"{SEED_DOMAIN}:{index:04d}".encode("ascii")).digest()[:8], "big")
    generator = random.Random(seed)
    x = np.asarray([generator.uniform(-1, 1) for _ in range(POINTS)], dtype=np.float64)
    y = np.asarray([2.0 * point + 1.0 + generator.uniform(-0.01, 0.01) for point in x], dtype=np.float64)
    w, c = 1.0, 0.0
    for _ in range(2):
        error = w * x + c - y
        w += -0.01 * float(np.sum(error * x)) / 2048.0
        c += -0.01 * float(np.sum(error)) / 2048.0
    return x, y, w, c


def input_manifest(output: Path) -> list[dict[str, str]]:
    path = output / "input_manifest.csv"
    expected = []
    for index in range(INPUT_COUNT):
        x, y, w, c = make_input(index)
        expected.append({
            "input_id": f"corelab_v8_{index:04d}",
            "input_x_sha256": digest_array(x),
            "input_y_sha256": digest_array(y),
            "plaintext_w": format(w, ".17g"),
            "plaintext_c": format(c, ".17g"),
        })
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            actual = list(csv.DictReader(handle))
        if actual != expected:
            raise RuntimeError("INTEGRITY_BLOCK: CoreLab V8 input manifest drift")
    else:
        with path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=tuple(expected[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(expected)
    return expected


def run_plan(runtime: Path, v7: Path, output: Path, mode: str, waterline: int, inputs: list[dict[str, str]]) -> dict[str, object]:
    plan_id = f"{mode}_{waterline:02d}"
    final = output / "plans" / f"{plan_id}.json"
    if final.exists():
        result = json.loads(final.read_text(encoding="utf-8"))
        if len(result.get("records", [])) != INPUT_COUNT:
            raise RuntimeError(f"INTEGRITY_BLOCK: incomplete resumed CoreLab plan {plan_id}")
        return result
    source = v7 / plan_id
    plan = source / "plan.hevm"
    constants = source / "constants.cst"
    if not plan.is_file() or not constants.is_file():
        return {"plan_id": plan_id, "mode": mode, "waterline": waterline, "status": "PLAN_UNAVAILABLE", "records": []}

    import hecate as hc

    context = output / "ephemeral_key_contexts" / plan_id
    if context.exists():
        shutil.rmtree(context)
    builtins.input = lambda _prompt="": ""
    started = time.perf_counter_ns()
    hevm = hc.HEVM(path=str(context))
    keygen_ms = (time.perf_counter_ns() - started) / 1e6
    started = time.perf_counter_ns()
    hevm.load(str(constants), str(plan))
    load_ms = (time.perf_counter_ns() - started) / 1e6
    records = []
    try:
        for index, bound in enumerate(inputs):
            x, y, plain_w, plain_c = make_input(index)
            if digest_array(x) != bound["input_x_sha256"] or digest_array(y) != bound["input_y_sha256"]:
                raise RuntimeError("INTEGRITY_BLOCK: CoreLab generated input digest mismatch")
            total_started = time.perf_counter_ns()
            started = time.perf_counter_ns(); hevm.setInput(0, x); hevm.setInput(1, y)
            encrypt_ms = (time.perf_counter_ns() - started) / 1e6
            started = time.perf_counter_ns(); hevm.run()
            evaluate_ms = (time.perf_counter_ns() - started) / 1e6
            started = time.perf_counter_ns(); actual = np.asarray(hevm.getOutput(), dtype=np.float64)
            decrypt_ms = (time.perf_counter_ns() - started) / 1e6
            if actual.shape[0] != 2 or not np.all(np.isfinite(actual)):
                raise RuntimeError(f"CoreLab non-finite/unexpected output at {plan_id}/{index}")
            w_error = np.abs(actual[0] - plain_w)
            c_error = np.abs(actual[1] - plain_c)
            records.append({
                "mode": mode, "waterline": waterline, "plan_status": "PASS",
                "input_id": bound["input_id"], "input_x_sha256": bound["input_x_sha256"],
                "input_y_sha256": bound["input_y_sha256"], "plaintext_w": plain_w,
                "plaintext_c": plain_c, "encrypted_w_slot0": float(actual[0, 0]),
                "encrypted_c_slot0": float(actual[1, 0]), "max_abs_w_error": float(np.max(w_error)),
                "max_abs_c_error": float(np.max(c_error)),
                "rms_error": float(math.sqrt(np.mean(w_error**2 + c_error**2))),
                "context_keygen_ms": keygen_ms, "load_preprocess_ms": load_ms,
                "encrypt_ms": encrypt_ms, "evaluate_ms": evaluate_ms, "decrypt_ms": decrypt_ms,
                "total_ms": (time.perf_counter_ns() - total_started) / 1e6,
            })
    finally:
        del hevm
        if context.exists():
            shutil.rmtree(context)
    result = {
        "schema_version": "flipguard_focused_external_v8_corelab_plan_v1",
        "plan_id": plan_id, "mode": mode, "waterline": waterline, "status": "PASS",
        "unique_inputs": INPUT_COUNT, "fresh_contexts": 1, "records": records,
        "plan_sha256": sha256(plan), "constants_sha256": sha256(constants),
    }
    partial = final.with_suffix(".json.partial")
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    partial.replace(final)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--v7-output-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    v7 = args.v7_output_root.resolve()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not (runtime / ".git").is_dir():
        raise RuntimeError("missing pinned CoreLab runtime checkout")
    import subprocess
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=runtime, check=True, text=True, capture_output=True).stdout.strip()
    if head != PINNED_COMMIT or subprocess.run(["git", "status", "--short"], cwd=runtime, check=True, text=True, capture_output=True).stdout.strip():
        raise RuntimeError("INTEGRITY_BLOCK: CoreLab runtime source binding changed")
    inputs = input_manifest(output)
    plan_results = []
    for mode in ("eva", "elasm"):
        for waterline in range(15, 51):
            plan_results.append(run_plan(runtime, v7, output, mode, waterline, inputs))
            (output / "progress.json").write_text(json.dumps({"plans_completed": len(plan_results), "plans_total": 72, "current": f"{mode}_{waterline:02d}"}, sort_keys=True) + "\n", encoding="utf-8")
    rows = [row for plan in plan_results for row in plan["records"]]
    records_path = output / "records.csv"
    if not records_path.exists():
        with records_path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
    manifest = {
        "schema_version": "flipguard_focused_external_v8_corelab_result_v1",
        "status": "PASS" if rows else "FAILED",
        "provider": "CoreLab EVA/ELASM", "provider_commit": head,
        "workload": "official_LinearRegression_multi_input_v8",
        "decision_semantics": "NUMERICAL_ONLY_NO_NATURAL_DECISION_OUTPUT",
        "plans_attempted": 72,
        "plans_completed": sum(plan["status"] == "PASS" for plan in plan_results),
        "plans_unavailable": sum(plan["status"] != "PASS" for plan in plan_results),
        "unique_inputs_per_completed_plan": INPUT_COUNT,
        "raw_plan_input_rows": len(rows),
        "fresh_contexts": sum(plan["status"] == "PASS" for plan in plan_results),
        "max_rms_error": max((float(row["rms_error"]) for row in rows), default=None),
        "input_manifest_sha256": sha256(output / "input_manifest.csv"),
        "records_sha256": sha256(records_path),
        "source_modifications": 0,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksums = [f"{sha256(path)[7:]}  {path.relative_to(output).as_posix()}" for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
