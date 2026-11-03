#!/usr/bin/env python3
"""Freeze and verify the clean CoreLab ELASM V6 attempt without overstating it."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "external/v6"
RAW = RUNTIME / "outputs/corelab/elasm-linear-regression-grid-v1"
DEFAULT_OUTPUT = ROOT / "docs/evidence/external_end_to_end_clean_v6/provider_candidate_manifests/corelab_elasm"
RUN_IDS = [
    "0009-elasm-source-checkout",
    "0010-elasm-pin-checkout",
    "0013-seal4-source-checkout",
    "0014-elasm-clean-build",
    "0015-elasm-runtime-trace",
    "0016-elasm-full-grid",
    "0017-elasm-full-grid-retry1",
    "0018-elasm-runtime-trace-retry1",
    "0019-elasm-full-grid-retry2",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, text=True, capture_output=True
    ).stdout.strip()


def copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"required CoreLab V6 artifact is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def write_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def generate(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite CoreLab ELASM V6 evidence: {output}")
    records_path = RAW / "records.csv"
    if not records_path.is_file():
        raise ValueError("the partial ELASM grid ledger is missing")
    with records_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 39:
        raise ValueError(f"expected the preserved 39-row attempt, found {len(rows)}")
    if any(row["compile_status"] != "PASS" for row in rows):
        raise ValueError("the preserved ELASM compile ledger changed")
    if any(row["execution_status"] != "FAIL" for row in rows):
        raise ValueError("unexpected encrypted execution success in the blocked attempt")
    if any(row["evidence_level"] != "2" for row in rows):
        raise ValueError("the blocked ELASM rows must remain evidence level 2")

    output.mkdir(parents=True)
    copy(records_path, output / "partial_grid/records.csv")
    # Generated plans are compact and contain no key material. Preserve the exact
    # partial official-pipeline output, including the interrupted final directory.
    shutil.copytree(RAW, output / "partial_grid/generated_plans", dirs_exist_ok=True)

    runs: dict[str, dict[str, Any]] = {}
    for run_id in RUN_IDS:
        status = RUNTIME / "status/corelab" / run_id / "run_manifest.json"
        copy(status, output / "stage_manifests" / f"{run_id}.json")
        runs[run_id] = load(status)
        time_log = RUNTIME / "logs/corelab" / run_id / "time.log"
        if time_log.is_file():
            copy(time_log, output / "time_logs" / f"{run_id}.txt")
        stderr = RUNTIME / "logs/corelab" / run_id / "stderr.log"
        if runs[run_id]["return_code"] != 0 and stderr.is_file():
            copy(stderr, output / "failures" / f"{run_id}.stderr.txt")

    for name in ("0016-elasm-full-grid", "0017-elasm-full-grid-retry1"):
        if "git" not in (output / "failures" / f"{name}.stderr.txt").read_text(encoding="utf-8"):
            raise ValueError(f"{name} no longer records the container Git failure")
    numpy_failures = sum(
        "No module named 'numpy'" in path.read_text(encoding="utf-8", errors="replace")
        for path in RAW.glob("*/execute.stderr")
    )
    if numpy_failures < len(rows):
        raise ValueError("not every recorded ELASM execution failure has the common numpy cause")

    source_manifest = {
        "elasm": {
            "repository": "https://github.com/corelab-src/elasm",
            "commit": git_head(RUNTIME / "sources/elasm"),
            "tree_sha256": runs["0010-elasm-pin-checkout"]["source_sha256"],
            "license_sha256": sha256(RUNTIME / "sources/elasm/LICENSE"),
        },
        "seal": {
            "repository": "https://github.com/microsoft/SEAL",
            "commit": git_head(RUNTIME / "sources/seal-4.0.0"),
            "tree_sha256": runs["0013-seal4-source-checkout"]["source_sha256"],
            "license_sha256": sha256(RUNTIME / "sources/seal-4.0.0/LICENSE"),
        },
    }
    (output / "source_manifest.json").write_text(
        json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failure_records = {
        "0016-elasm-full-grid": "CONTAINER_GIT_WORKTREE_POINTER_UNRESOLVED_BEFORE_PLAN_EXECUTION",
        "0017-elasm-full-grid-retry1": "CONTAINER_GIT_WORKTREE_POINTER_UNRESOLVED_BEFORE_PLAN_EXECUTION",
        "0019-elasm-full-grid-retry2": "RUNNER_DEPENDENCY_NUMPY_MISSING_BEFORE_KEYGEN_ALL_RECORDED_PLANS",
        "recovery_budget": "THREE_GRID_ATTEMPTS_EXHAUSTED",
        "termination": "COMMON_PRE_KEYGEN_FAILURE_DETECTED_AND_REMAINING_DUPLICATE_FAILURES_AVOIDED",
    }
    (output / "failure_records.json").write_text(
        json.dumps(failure_records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    modes = Counter(row["mode"] for row in rows)
    summary = {
        "schema_version": "flipguard_external_end_to_end_clean_v6_corelab_elasm_evidence_v1",
        "provider": "CoreLab ELASM",
        "status": "REPRODUCTION_BLOCKED",
        "maximum_evidence_level": 2,
        "official_pipeline_state": "PARTIAL_OFFICIAL_PIPELINE",
        "clean_build": {
            "status": runs["0014-elasm-clean-build"]["state"],
            "elapsed_seconds": runs["0014-elasm-clean-build"]["elapsed_seconds"],
            "binary_sha256": runs["0014-elasm-clean-build"]["binary_sha256"],
        },
        "grid": {
            "predeclared_plans": 72,
            "recorded_plan_attempts": len(rows),
            "plans_generated": sum(row["compile_status"] == "PASS" for row in rows),
            "plans_executed": 0,
            "encrypted_end_to_end_runs": 0,
            "fresh_key_runs": 0,
            "actual_output_rows": 0,
            "mode_counts": dict(sorted(modes.items())),
            "decision_output_available": False,
            "gate_state": "NOT_EVALUATED",
            "security_state": "SECURITY_NOT_EVALUATED",
        },
        "failure": {
            "common_failure_count": numpy_failures,
            "common_failure": "RUNNER_DEPENDENCY_NUMPY_MISSING_BEFORE_KEYGEN",
            "independent_grid_attempts": 3,
            "recovery_budget_exhausted": True,
        },
        "predecessor_agreement": {
            "state": "NOT_EVALUATED_NO_V6_ENCRYPTED_OUTPUT",
            "prior_storage_pressure_may_have_affected_result": "NO",
        },
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": "flipguard_external_end_to_end_clean_v6_provider_pack_v1",
        "provider": "CoreLab ELASM",
        "source_commit": git_head(ROOT),
        "runtime_root": "external/v6",
        "new_keys_generated": False,
        "old_results_reused": False,
        "summary_sha256": sha256(output / "summary.json"),
        "source_manifest_sha256": sha256(output / "source_manifest.json"),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_sums(output)
    verify(output)


def verify(output: Path) -> None:
    manifest = load(output / "manifest.json")
    summary = load(output / "summary.json")
    if manifest["schema_version"] != "flipguard_external_end_to_end_clean_v6_provider_pack_v1":
        raise ValueError("CoreLab ELASM V6 provider-pack schema changed")
    if summary["maximum_evidence_level"] != 2 or summary["status"] != "REPRODUCTION_BLOCKED":
        raise ValueError("CoreLab ELASM evidence level or state changed")
    grid = summary["grid"]
    if grid["encrypted_end_to_end_runs"] != 0 or grid["plans_executed"] != 0:
        raise ValueError("blocked ELASM attempt cannot be counted as encrypted execution")
    if grid["gate_state"] != "NOT_EVALUATED" or grid["decision_output_available"]:
        raise ValueError("blocked ELASM attempt cannot be counted as a decision-bearing provider")
    expected = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(output).as_posix()}")
    if (output / "SHA256SUMS").read_text(encoding="ascii") != "\n".join(expected) + "\n":
        raise ValueError("CoreLab ELASM V6 SHA256SUMS mismatch")
    print(
        "external_v6_corelab_elasm=PASS level=2 "
        f"plans={grid['plans_generated']} encrypted={grid['encrypted_end_to_end_runs']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.verify:
        verify(output)
    else:
        generate(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
