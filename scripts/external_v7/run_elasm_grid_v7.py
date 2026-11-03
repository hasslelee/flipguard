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


def plan_sequence() -> list[tuple[str, int]]:
    return [(mode, waterline) for mode in ("eva", "elasm") for waterline in range(15, 51)]


def load_resume_records(output: Path, resume: bool) -> list[dict[str, str]]:
    if not output.exists():
        if resume:
            raise FileNotFoundError(f"resume output does not exist: {output}")
        output.mkdir(parents=True)
        return []
    if not resume:
        raise FileExistsError(f"refusing to overwrite {output}")
    if (output / "manifest.json").exists():
        raise ValueError(f"refusing to resume finalized ELASM grid: {output}")

    records_path = output / "records.csv"
    if not records_path.is_file():
        raise FileNotFoundError(f"resume records missing: {records_path}")
    with records_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"resume record schema drift: {reader.fieldnames}")
        records = list(reader)

    plans = plan_sequence()
    if len(records) > len(plans):
        raise ValueError(f"resume prefix exceeds frozen plan count: {len(records)}")
    for index, row in enumerate(records):
        expected_mode, expected_waterline = plans[index]
        actual = (row["mode"], int(row["waterline"]))
        if actual != (expected_mode, expected_waterline):
            raise ValueError(
                "noncanonical resume prefix at row "
                f"{index + 1}: expected {expected_mode}_{expected_waterline:02d}, "
                f"found {actual[0]}_{actual[1]:02d}"
            )
        run_dir = output / f"{expected_mode}_{expected_waterline:02d}"
        for required_name in ("compile.stdout", "compile.stderr"):
            if not (run_dir / required_name).is_file():
                raise FileNotFoundError(run_dir / required_name)
        if row["compile_status"] == "PASS":
            for required_name in ("optimized.mlir", "plan.hevm", "constants.cst"):
                if not (run_dir / required_name).is_file():
                    raise FileNotFoundError(run_dir / required_name)
        if row["encrypted_end_to_end"] == "true":
            for required_name in (
                "execute.stdout",
                "execute.stderr",
                "result.json",
                "decrypted_outputs.npz",
            ):
                if not (run_dir / required_name).is_file():
                    raise FileNotFoundError(run_dir / required_name)
    return records


def quarantine_interrupted_run(run_dir: Path, interrupted_root: Path) -> None:
    interrupted_root.mkdir(parents=True, exist_ok=True)
    destination = interrupted_root / run_dir.name
    if destination.exists():
        raise FileExistsError(f"interrupted run destination already exists: {destination}")
    shutil.move(str(run_dir), str(destination))


def remove_ephemeral_context(context_root: Path, key_context_root: Path) -> None:
    if context_root.parent.resolve() != key_context_root.resolve():
        raise ValueError(f"refusing unsafe key-context cleanup: {context_root}")
    if context_root.exists():
        shutil.rmtree(context_root)
    if context_root.exists():
        raise RuntimeError(f"ephemeral key context still exists: {context_root}")


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
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interrupted-root", type=Path)
    args = parser.parse_args()
    source = args.source_root.resolve()
    runtime = args.runtime_root.resolve()
    output = args.output_root.resolve()
    if args.resume != (args.interrupted_root is not None):
        raise ValueError("--resume and --interrupted-root must be provided together")
    for checkout in (source, runtime):
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, check=True, text=True, capture_output=True).stdout.strip()
        if commit != PINNED_COMMIT:
            raise ValueError(f"ELASM source drift at {checkout}: {commit}")
    if args.seed != 20260805:
        raise ValueError("ELASM V7 seed changed")
    records = load_resume_records(output, args.resume)
    resumed_prefix_rows = len(records)
    args.status_file.write_text(str(resumed_prefix_rows) + "\n", encoding="ascii")
    examples = runtime / "examples"
    optimizer = runtime / "build/bin/hecate-opt"
    trace = examples / "traced/LinearRegression.mlir"
    test_source = source / "examples/tests/LinearRegression.py"
    for required in (optimizer, trace, test_source, runtime / "config.json"):
        if not required.is_file():
            raise FileNotFoundError(required)

    key_context_root = runtime / "key_contexts"
    interrupted_root = args.interrupted_root.resolve() if args.interrupted_root else None
    plans = plan_sequence()
    for mode in ("eva", "elasm"):
        optimized = examples / "optimized" / mode
        optimized.mkdir(parents=True, exist_ok=True)
    for plan_index, (mode, waterline) in enumerate(plans):
        if plan_index < resumed_prefix_rows:
            continue
        optimized = examples / "optimized" / mode
        run_dir = output / f"{mode}_{waterline:02d}"
        if run_dir.exists():
            if plan_index != resumed_prefix_rows or interrupted_root is None:
                raise FileExistsError(f"unexpected non-prefix run directory: {run_dir}")
            quarantine_interrupted_run(run_dir, interrupted_root)
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
            context_root = key_context_root / f"{mode}_{waterline:02d}"
            execution_command = [
                "python3", str(Path(__file__).with_name("run_elasm_plan_v7.py")),
                "--runtime-root", str(runtime), "--mode", mode, "--waterline", str(waterline),
                "--seed", str(args.seed), "--context-root", str(context_root),
                "--output-json", str(result_json), "--output-npz", str(result_npz),
            ]
            try:
                execution_exit, execution_wall = run(
                    execution_command, examples, run_dir / "execute.stdout", run_dir / "execute.stderr"
                )
            finally:
                remove_ephemeral_context(context_root, key_context_root)
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
        "ephemeral_key_context_retained": False,
        "resumed_prefix_rows": resumed_prefix_rows,
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
