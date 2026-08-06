#!/usr/bin/env python3
"""Run one exact official ELASM LinearRegression plan with raw output capture."""

from __future__ import annotations

import argparse
import builtins
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np


def digest_array(value: np.ndarray) -> str:
    return f"sha256:{hashlib.sha256(np.asarray(value, dtype=np.float64).tobytes(order='C')).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--mode", choices=("eva", "elasm"), required=True)
    parser.add_argument("--waterline", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--context-root", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-npz", required=True, type=Path)
    args = parser.parse_args()
    if not 15 <= args.waterline <= 50 or args.seed != 20260805:
        raise ValueError("ELASM V7 frozen plan or seed changed")
    root = args.runtime_root.resolve()
    context = args.context_root.resolve()
    if context.exists() or args.output_json.exists() or args.output_npz.exists():
        raise FileExistsError("refusing to overwrite ELASM V7 plan material")

    random.seed(args.seed)
    np.random.seed(args.seed)
    x = np.asarray([random.uniform(-1, 1) for _ in range(4096)], dtype=np.float64)
    y = np.asarray([2.0 * point + 1.0 + random.uniform(-0.01, 0.01) for point in x], dtype=np.float64)
    w = 1.0
    c = 0.0
    for _ in range(2):
        error = w * x + c - y
        grad_w = float(np.sum(error * x)) / 2048.0
        grad_b = float(np.sum(error)) / 2048.0
        w += -0.01 * grad_w
        c += -0.01 * grad_b

    import hecate as hc

    builtins.input = lambda _prompt="": ""
    total_started = time.perf_counter_ns()
    started = time.perf_counter_ns()
    hevm = hc.HEVM(path=str(context))
    context_keygen_ms = (time.perf_counter_ns() - started) / 1_000_000
    examples = root / "examples"
    const_path = examples / "traced/_hecate_LinearRegression.cst"
    plan_path = examples / f"optimized/{args.mode}/LinearRegression.{args.waterline}._hecate_LinearRegression.hevm"
    started = time.perf_counter_ns()
    hevm.load(str(const_path), str(plan_path))
    load_preprocess_ms = (time.perf_counter_ns() - started) / 1_000_000
    started = time.perf_counter_ns()
    hevm.setInput(0, x)
    hevm.setInput(1, y)
    encrypt_ms = (time.perf_counter_ns() - started) / 1_000_000
    started = time.perf_counter_ns()
    hevm.run()
    execute_ms = (time.perf_counter_ns() - started) / 1_000_000
    started = time.perf_counter_ns()
    result = np.asarray(hevm.getOutput(), dtype=np.float64)
    decrypt_ms = (time.perf_counter_ns() - started) / 1_000_000
    total_ms = (time.perf_counter_ns() - total_started) / 1_000_000
    if result.shape[0] != 2:
        raise ValueError(f"unexpected ELASM result shape: {result.shape}")
    rms = float(np.sqrt(np.mean(np.power(result[0] - w, 2) + np.power(result[1] - c, 2))))
    args.output_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_npz, encrypted_w=result[0], encrypted_c=result[1])
    record = {
        "schema_version": "flipguard_external_v7_elasm_plan_result_v1",
        "mode": args.mode,
        "waterline": args.waterline,
        "seed": args.seed,
        "input_x_sha256": digest_array(x),
        "input_y_sha256": digest_array(y),
        "plaintext_w": w,
        "plaintext_c": c,
        "encrypted_w_slot0": float(result[0, 0]),
        "encrypted_c_slot0": float(result[1, 0]),
        "encrypted_w_min": float(np.min(result[0])),
        "encrypted_w_max": float(np.max(result[0])),
        "encrypted_c_min": float(np.min(result[1])),
        "encrypted_c_max": float(np.max(result[1])),
        "rms_error": rms,
        "raw_output_shape": list(result.shape),
        "raw_output_npz": args.output_npz.name,
        "timing_ms": {
            "context_keygen": context_keygen_ms,
            "load_preprocess": load_preprocess_ms,
            "encryption": encrypt_ms,
            "evaluation": execute_ms,
            "decryption": decrypt_ms,
            "total": total_ms,
        },
    }
    args.output_json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
