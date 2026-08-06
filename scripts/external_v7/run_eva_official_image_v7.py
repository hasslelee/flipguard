#!/usr/bin/env python3
"""Execute EVA's exact official Sobel/Harris graphs and retain raw outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Any


EXPECTED_EVA_COMMIT = "4cd3254c9c51340ae30c451495ce5378135758c0"
EXPECTED_SOURCE_SHA256 = "4b0488a667341a6d29034843c6b23877b7da86ed99e172336885580492498065"
EXPECTED_IMAGE_SHA256 = "6086eba31e344924addcaef28aad5fe211467e66a53c7bdcef3e2a45386cda1f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eva-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--key-contexts", type=int, default=3)
    args = parser.parse_args()
    eva_root = args.eva_root.resolve()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    if args.key_contexts != 3:
        raise ValueError("the frozen V7 official-image contract requires three contexts")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=eva_root, check=True, text=True, capture_output=True
    ).stdout.strip()
    if head != EXPECTED_EVA_COMMIT:
        raise ValueError(f"EVA source commit changed: {head}")
    source = eva_root / "examples/image_processing.py"
    image = eva_root / "examples/baboon.png"
    if sha256(source) != f"sha256:{EXPECTED_SOURCE_SHA256}" or sha256(image) != f"sha256:{EXPECTED_IMAGE_SHA256}":
        raise ValueError("official EVA image source or input digest changed")

    import os

    original_cwd = Path.cwd()
    os.chdir(source.parent)
    try:
        spec = importlib.util.spec_from_file_location("eva_official_image_processing", source)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load official EVA image example")
        official = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(official)
        inputs = official.read_input_image()
    finally:
        os.chdir(original_cwd)

    from eva import evaluate
    from eva.ckks import CKKSCompiler
    from eva.seal import generate_keys

    output.mkdir(parents=True)
    raw_path = output / "per_pixel_outputs.csv"
    fields = [
        "program", "input_id", "key_context", "pixel_index", "row", "column",
        "input_value", "plaintext_output", "decrypted_output", "absolute_error",
        "keygen_ms", "encrypt_ms", "execute_ms", "decrypt_ms", "total_ms",
    ]
    summaries: list[dict[str, Any]] = []
    with raw_path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for program in (official.sobel, official.harris):
            compile_started = time.perf_counter_ns()
            compiled, parameters, signature = CKKSCompiler().compile(program)
            compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000
            (output / f"{program.name}_compiled.dot").write_text(compiled.to_DOT(), encoding="utf-8")
            reference = list(evaluate(compiled, inputs)["image"][:4096])
            context_summaries = []
            all_errors: list[float] = []
            for key_context in range(1, args.key_contexts + 1):
                total_started = time.perf_counter_ns()
                started = time.perf_counter_ns()
                public_context, secret_context = generate_keys(parameters)
                keygen_ms = (time.perf_counter_ns() - started) / 1_000_000
                started = time.perf_counter_ns()
                encrypted_inputs = public_context.encrypt(inputs, signature)
                encrypt_ms = (time.perf_counter_ns() - started) / 1_000_000
                started = time.perf_counter_ns()
                encrypted_outputs = public_context.execute(compiled, encrypted_inputs)
                execute_ms = (time.perf_counter_ns() - started) / 1_000_000
                started = time.perf_counter_ns()
                decrypted = list(secret_context.decrypt(encrypted_outputs, signature)["image"][:4096])
                decrypt_ms = (time.perf_counter_ns() - started) / 1_000_000
                total_ms = (time.perf_counter_ns() - total_started) / 1_000_000
                errors = [abs(float(actual) - float(expected)) for actual, expected in zip(decrypted, reference)]
                all_errors.extend(errors)
                context_summaries.append(
                    {
                        "key_context": key_context,
                        "keygen_ms": keygen_ms,
                        "encrypt_ms": encrypt_ms,
                        "execute_ms": execute_ms,
                        "decrypt_ms": decrypt_ms,
                        "total_ms": total_ms,
                        "mse": sum(error * error for error in errors) / len(errors),
                        "max_absolute_error": max(errors),
                    }
                )
                for index, (input_value, expected, actual, error) in enumerate(
                    zip(inputs["image"], reference, decrypted, errors)
                ):
                    writer.writerow(
                        {
                            "program": program.name,
                            "input_id": "eva_v1.0.1_official_baboon_64x64",
                            "key_context": key_context,
                            "pixel_index": index,
                            "row": index // 64,
                            "column": index % 64,
                            "input_value": input_value,
                            "plaintext_output": expected,
                            "decrypted_output": actual,
                            "absolute_error": error,
                            "keygen_ms": keygen_ms,
                            "encrypt_ms": encrypt_ms,
                            "execute_ms": execute_ms,
                            "decrypt_ms": decrypt_ms,
                            "total_ms": total_ms,
                        }
                    )
            summaries.append(
                {
                    "program": program.name,
                    "compile_ms": compile_ms,
                    "poly_modulus_degree": int(parameters.poly_modulus_degree),
                    "prime_bits": list(parameters.prime_bits),
                    "rotations": list(parameters.rotations),
                    "key_contexts": args.key_contexts,
                    "ordered_observations": 4096,
                    "raw_output_rows": 4096 * args.key_contexts,
                    "mse_all_contexts": sum(error * error for error in all_errors) / len(all_errors),
                    "max_absolute_error": max(all_errors),
                    "contexts": context_summaries,
                }
            )
    manifest = {
        "schema_version": "flipguard_external_v7_eva_official_image_result_v1",
        "provider": "Microsoft EVA",
        "provider_commit": head,
        "workload_id": "eva_official_baboon_sobel_harris_v1",
        "state": "ENCRYPTED_END_TO_END",
        "evidence_level": 3,
        "level_ceiling_reason": "The official example has one input image and declares no decision rule.",
        "decision_gate_state": "NOT_EVALUATED",
        "unique_input_images": 1,
        "programs": summaries,
        "raw_output_rows": sum(item["raw_output_rows"] for item in summaries),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_checksums(output)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
