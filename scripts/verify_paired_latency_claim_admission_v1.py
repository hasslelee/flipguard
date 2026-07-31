#!/usr/bin/env python3
"""Verify the derived paired-latency claim-admission overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path(
            "results/thesis_grade_protocol/"
            "paired_latency_claim_admission_v1"
        ),
    )
    args = parser.parse_args()
    root = args.evidence_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest["evidence_id"] != "paired_latency_claim_admission_v1"
        or manifest["new_encrypted_execution_performed"]
        or manifest["frozen_paired_pack_modified"]
        or manifest["raw_records_reused"] != 5400
        or not manifest["paper_admitted"]
        or manifest["claim_state"] != "PARTIALLY_SUPPORTED"
        or re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]) is None
    ):
        raise ValueError("paired claim-admission manifest changed")
    for name, record in manifest["files"].items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise ValueError(f"{name}: paired admission file changed")

    confirmatory = json.loads(
        (root / "seeds1_4_confirmatory_summary.json").read_text()
    )
    development = json.loads(
        (root / "seed0_development_summary.json").read_text()
    )
    combined = json.loads(
        (root / "combined_descriptive_summary.json").read_text()
    )
    if (
        confirmatory["workload_partition_instances"] != 40
        or development["workload_partition_instances"] != 10
        or combined["workload_partition_instances"] != 50
        or confirmatory["dataset_model_clusters"] != 10
        or confirmatory["failure_count"] != 0
        or confirmatory["catalog_over_direct"][
            "cluster_bootstrap_95_ci_total"
        ]["low"]
        <= 1
    ):
        raise ValueError("population separation or latency admission changed")

    claim = json.loads((root / "claim_admission.json").read_text())
    if (
        claim["claim_state"] != "PARTIALLY_SUPPORTED"
        or claim["paper_admitted"] is not True
        or not all(claim["conditions"].values())
        or claim["raw_pair_independence_claim"] is not False
    ):
        raise ValueError("paired claim state changed")

    with (root / "workload_partition_summary.csv").open(newline="") as handle:
        workloads = list(csv.DictReader(handle))
    with (root / "dataset_model_cluster_summary.csv").open(newline="") as handle:
        clusters = list(csv.DictReader(handle))
    if len(workloads) != 100 or len(clusters) != 30:
        raise ValueError("derived population row count changed")

    expected = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{sha256(path).removeprefix('sha256:')}  {path.name}\n"
            )
    if (root / "SHA256SUMS").read_text() != "".join(expected):
        raise ValueError("paired admission SHA256SUMS mismatch")
    total = confirmatory["catalog_over_direct"][
        "geometric_mean_total_latency_ratio"
    ]
    interval = confirmatory["catalog_over_direct"][
        "cluster_bootstrap_95_ci_total"
    ]
    print(
        "paired_latency_claim_admission=VERIFIED "
        f"confirmatory_ratio={total:.6f} "
        f"ci95=[{interval['low']:.6f},{interval['high']:.6f}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
