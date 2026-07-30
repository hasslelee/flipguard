#!/usr/bin/env python3
"""Freeze and verify the post-hoc structural audit failure analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = Path(
    "results/thesis_grade_protocol/structural_audit_failure_analysis_v1"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/structural_audit_failure_analysis_v1"
)
SELECTION_RESULT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3/results/"
    "directv1_full_structural_poly3_inputmodel_floor18_keys3_"
    "seed4_banknote_mlp_square_poly3.json"
)
AUDIT_RESULT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3/locked_audit/"
    "full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3/"
    "results/directv1_full_structural_poly3_inputmodel_floor18_keys3_"
    "seed4_banknote_mlp_square_poly3_locked_audit_keys3.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def generate(output: Path) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    analysis_root = REPO_ROOT / ANALYSIS_ROOT
    analysis = read_json(analysis_root / "margin_error_analysis.json")
    if (
        analysis.get("analysis_type")
        != "EXPLANATORY_POST_HOC_STATIC_NO_POLICY_CHANGE"
        or analysis.get("failure_class")
        != "VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN"
        or analysis.get("observation_accounting", {}).get(
            "violating_observations"
        )
        != 1
        or analysis.get("observation_accounting", {}).get(
            "one_key_repeat_only"
        )
        is not True
        or analysis.get("claim_effect", {}).get("structural_generalization")
        != "PARTIALLY_SUPPORTED"
        or analysis.get("claim_effect", {}).get("policy_change_authorized")
        is not False
    ):
        raise ValueError("structural failure analysis classification changed")

    output.mkdir(parents=True)
    analysis_files = [
        "failing_samples.csv",
        "key_repeat_breakdown.csv",
        "margin_error_analysis.json",
        "summary.md",
        "SHA256SUMS",
    ]
    for name in analysis_files:
        copy_file(analysis_root / name, output / "analysis" / name)

    bound_sources = {
        "selection_result": SELECTION_RESULT,
        "audit_result": AUDIT_RESULT,
        "analyzer": Path("scripts/analyze_structural_audit_failure.py"),
    }
    source_records: dict[str, dict[str, Any]] = {}
    for name, relative in bound_sources.items():
        source = REPO_ROOT / relative
        destination = output / "sources" / f"{name}{source.suffix}"
        copy_file(source, destination)
        source_records[name] = {
            "path": str(relative),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "snapshot": str(destination.relative_to(output)),
        }

    readme = """# Structural audit failure analysis evidence

This pack freezes a static, explanatory post-hoc analysis of the single
`mlp_square_poly3` locked-audit numerical rejection. No encrypted execution,
candidate repair, reselection, or policy change was performed.

The aggregate execution result proves one violating sample-key observation
among 621 observations. The original execution artifact did not persist the
per-sample CKKS scores, so the exact row and key repeat are explicitly marked
`NOT_RECORDED_IN_EXECUTION_ARTIFACT`.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    internal_files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}
    )
    manifest = {
        "schema_version": 1,
        "evidence_id": "structural_audit_failure_analysis_v1",
        "status": "PARTIAL_SCIENTIFIC_RESULT",
        "analysis_type": "EXPLANATORY_POST_HOC_STATIC_NO_POLICY_CHANGE",
        "failure_class": "VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN",
        "claim_state": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "policy_modification_authorized": False,
        "encrypted_rerun_performed": False,
        "exact_sample_identity_available": False,
        "exact_key_repeat_identity_available": False,
        "analysis_builder_parent_commit": git_head(),
        "source_records": source_records,
        "digests": analysis["digests"],
        "observation_accounting": analysis["observation_accounting"],
        "no_flip_explanation": analysis["no_flip_explanation"],
        "files": {
            str(path.relative_to(output)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in internal_files
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_files = sorted(internal_files + [output / "manifest.json"])
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
            for path in checksum_files
        ),
        encoding="utf-8",
    )


def verify(output: Path) -> None:
    manifest = read_json(output / "manifest.json")
    if (
        manifest.get("status") != "PARTIAL_SCIENTIFIC_RESULT"
        or manifest.get("analysis_type")
        != "EXPLANATORY_POST_HOC_STATIC_NO_POLICY_CHANGE"
        or manifest.get("policy_modification_authorized") is not False
        or manifest.get("encrypted_rerun_performed") is not False
        or manifest.get("exact_sample_identity_available") is not False
        or manifest.get("exact_key_repeat_identity_available") is not False
        or manifest.get("observation_accounting", {}).get(
            "violating_observations"
        )
        != 1
    ):
        raise ValueError("structural analysis evidence state changed")
    for relative, expected in manifest["files"].items():
        path = output / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: analysis evidence changed")
    for record in manifest["source_records"].values():
        source = REPO_ROOT / record["path"]
        snapshot = output / record["snapshot"]
        if (
            not source.is_file()
            or source.stat().st_size != record["bytes"]
            or sha256(source) != record["sha256"]
            or sha256(snapshot) != record["sha256"]
        ):
            raise ValueError(f"{source}: analysis source binding changed")
    expected_lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        expected_lines.append(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
        )
    if (output / "SHA256SUMS").read_text(encoding="utf-8") != "".join(
        expected_lines
    ):
        raise ValueError("analysis evidence SHA256SUMS changed")
    print(
        "structural_failure_analysis_evidence=VERIFIED "
        "violating_observations=1 exact_row=NOT_RECORDED"
    )


def main() -> int:
    args = parse_args()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output)
        return 0
    if output.exists():
        if not args.force:
            raise ValueError(f"{output} exists; use --force")
        shutil.rmtree(output)
    generate(output)
    verify(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
