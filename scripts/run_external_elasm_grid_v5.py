#!/usr/bin/env python3
"""Run the frozen ELASM/EVA waterline grid through the official SEAL HEVM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


PINNED_COMMIT = "3c37c11b29ca480525bb6681e0254bdf90029425"
FIELDS = [
    "mode",
    "waterline",
    "compile_status",
    "compile_exit_status",
    "compile_wall_seconds",
    "execution_status",
    "execution_exit_status",
    "execution_wrapper_wall_seconds",
    "reported_hevm_seconds",
    "reported_rms_error",
    "encrypted_end_to_end",
    "decision_output_available",
    "evidence_level",
    "failure_reason",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def run_and_capture(
    command: list[str],
    cwd: Path,
    stdout: Path,
    stderr: Path,
    stdin_bytes: bytes | None = None,
) -> tuple[int, float]:
    started = time.monotonic()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        result = subprocess.run(
            command,
            cwd=cwd,
            input=stdin_bytes,
            stdout=out,
            stderr=err,
            check=False,
        )
    return result.returncode, time.monotonic() - started


def parse_reported_metrics(path: Path) -> tuple[str, str]:
    numeric: list[float] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            numeric.append(float(line.strip()))
        except ValueError:
            continue
    if len(numeric) < 2:
        return "", ""
    return format(numeric[-2], ".17g"), format(numeric[-1], ".17g")


def write_records(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hecate-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--waterline-start", type=int, default=15)
    parser.add_argument("--waterline-end", type=int, default=50)
    parser.add_argument("--modes", nargs="+", default=["eva", "elasm"])
    args = parser.parse_args()

    root = args.hecate_root.resolve()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    if commit != PINNED_COMMIT:
        raise ValueError(f"ELASM source drift: {commit}")
    if args.source_commit != PINNED_COMMIT:
        raise ValueError("declared source commit does not match the frozen pin")
    if args.modes != ["eva", "elasm"]:
        raise ValueError("V5 requires the frozen eva/elasm mode order")
    if (args.waterline_start, args.waterline_end) != (15, 50):
        raise ValueError("V5 requires the complete 15..50 waterline grid")

    examples = root / "examples"
    optimizer = root / "build/bin/hecate-opt"
    trace = examples / "traced/LinearRegression.mlir"
    test_script = examples / "tests/LinearRegression.py"
    for required in (optimizer, trace, test_script, root / "config.json"):
        if not required.is_file():
            raise FileNotFoundError(required)

    records: list[dict[str, object]] = []
    for mode in args.modes:
        optimized_dir = examples / "optimized" / mode
        optimized_dir.mkdir(parents=True, exist_ok=True)
        for waterline in range(args.waterline_start, args.waterline_end + 1):
            run_dir = output / f"{mode}_{waterline:02d}"
            run_dir.mkdir()
            mlir = optimized_dir / f"LinearRegression.{waterline}.mlir"
            compile_cmd = [
                str(optimizer),
                f"--{mode}",
                f"--ckks-config={root / 'config.json'}",
                f"--waterline={waterline}",
                str(trace),
                "-o",
                str(mlir),
            ]
            compile_exit, compile_wall = run_and_capture(
                compile_cmd, examples, run_dir / "compile.stdout", run_dir / "compile.stderr"
            )
            execution_exit = -1
            execution_wall = 0.0
            reported_seconds = ""
            rms = ""
            reason = ""
            if compile_exit == 0:
                bootstrap = (
                    "import random,runpy,sys,numpy as np;"
                    f"random.seed({args.seed});np.random.seed({args.seed});"
                    f"sys.argv=['LinearRegression.py','{mode}','{waterline}'];"
                    f"runpy.run_path({str(test_script)!r},run_name='__main__')"
                )
                execution_exit, execution_wall = run_and_capture(
                    ["python3", "-c", bootstrap],
                    examples,
                    run_dir / "execute.stdout",
                    run_dir / "execute.stderr",
                    # The official HEVM constructor pauses once before it
                    # generates the SEAL context and key material.
                    b"\n",
                )
                if execution_exit == 0:
                    reported_seconds, rms = parse_reported_metrics(run_dir / "execute.stdout")
                    if not reported_seconds or not rms:
                        reason = "OFFICIAL_OUTPUT_METRICS_UNPARSEABLE"
                else:
                    reason = "OFFICIAL_HEVM_EXECUTION_FAILED"
            else:
                reason = "OFFICIAL_OPTIMIZER_FAILED"
            encrypted = compile_exit == 0 and execution_exit == 0 and bool(rms)
            records.append(
                {
                    "mode": mode,
                    "waterline": waterline,
                    "compile_status": "PASS" if compile_exit == 0 else "FAIL",
                    "compile_exit_status": compile_exit,
                    "compile_wall_seconds": format(compile_wall, ".9f"),
                    "execution_status": "PASS" if encrypted else "FAIL",
                    "execution_exit_status": execution_exit,
                    "execution_wrapper_wall_seconds": format(execution_wall, ".9f"),
                    "reported_hevm_seconds": reported_seconds,
                    "reported_rms_error": rms,
                    "encrypted_end_to_end": str(encrypted).lower(),
                    "decision_output_available": "false",
                    "evidence_level": 4 if encrypted else (3 if compile_exit == 0 else 2),
                    "failure_reason": reason,
                }
            )
            write_records(output / "records.csv", records)

    completed = sum(row["encrypted_end_to_end"] == "true" for row in records)
    manifest = {
        "schema_version": "flipguard_external_elasm_grid_v5",
        "provider": "ELASM",
        "provider_commit": commit,
        "workload": "official_LinearRegression",
        "modes": args.modes,
        "waterlines": list(range(args.waterline_start, args.waterline_end + 1)),
        "frozen_input_seed": args.seed,
        "plans_generated": len(records),
        "encrypted_end_to_end_runs": completed,
        "decision_output_available": False,
        "evidence_level": 4 if completed else 3,
        "optimizer_sha256": sha256(optimizer),
        "trace_sha256": sha256(trace),
        "test_script_sha256": sha256(test_script),
        "records_sha256": sha256(output / "records.csv"),
        "source_modifications": 0,
        "outlier_removal": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    checksums = []
    for path in sorted(path for path in output.rglob("*") if path.is_file()):
        if path.name == "SHA256SUMS":
            continue
        checksums.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(output)}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
