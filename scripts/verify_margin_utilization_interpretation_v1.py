#!/usr/bin/env python3
"""Verify the frozen margin-utilization interpretation overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("docs/evidence/margin_utilization_interpretation_v1"),
    )
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest["evidence_id"] != "margin_utilization_interpretation_v1"
        or manifest["frozen_evidence_modified"]
        or manifest["encrypted_execution_performed"]
        or manifest["primary_rho"] != 0.5
        or manifest["primary_rows"] != 100
        or manifest["development_rows"] != 20
        or manifest["confirmatory_rows"] != 80
    ):
        raise ValueError("margin interpretation manifest state changed")
    for name, record in manifest["files"].items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise ValueError(f"{name}: content changed")

    with (root / "workload_utilization_summary.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 100:
        raise ValueError("primary utilization row count changed")
    if any(row["observation_binding"] != "aggregate_extrema_not_sample_bound" for row in rows):
        raise ValueError("aggregate extrema were presented as sample-bound")

    structural = json.loads(
        (root / "structural_rejection_interpretation.json").read_text()
    )
    if not math.isclose(
        structural["validation"]["margin_utilization_ratio"],
        0.4706530094839232,
        rel_tol=0,
        abs_tol=1e-15,
    ) or not math.isclose(
        structural["locked_audit"]["margin_utilization_ratio"],
        0.5613686443055665,
        rel_tol=0,
        abs_tol=1e-15,
    ):
        raise ValueError("structural utilization interpretation changed")
    if (
        structural["locked_audit"]["observed_decision_preserved"] is not True
        or structural["locked_audit"]["reserve_policy_pass"] is not False
        or structural["locked_audit"]["policy_reject_without_flip"] is not True
        or structural["policy_change_authorized"] is not False
    ):
        raise ValueError("structural negative classification changed")

    with (root / "alpha_sensitivity_summary.csv").open(newline="") as handle:
        alpha_rows = list(csv.DictReader(handle))
    if len(alpha_rows) != 5 or any(
        int(row["natural_candidate_state_changes"]) != 0
        or int(row["bounded_oracle_selection_changes"]) != 0
        or int(row["direct_initial_literal_changes"]) != 0
        or row["optimality_evidence"] != "False"
        for row in alpha_rows
    ):
        raise ValueError("alpha invariance interpretation changed")

    expected = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{sha256(path).removeprefix('sha256:')}  {path.name}\n"
            )
    if (root / "SHA256SUMS").read_text() != "".join(expected):
        raise ValueError("SHA256SUMS mismatch")
    print(
        "margin_utilization_interpretation=VERIFIED "
        "primary_rows=100 structural_policy_reject_without_flip=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
