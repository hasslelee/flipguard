#!/usr/bin/env python3
"""Verify the closed journal multiclass extension overlay."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = load(PACK / "manifest.json")
    summary = load(PACK / "final_summary.json")
    hierarchy = load(PACK / "experiment_hierarchy.json")
    assert manifest["journal_extension_state"] == "FINAL_FROZEN"
    assert manifest["frozen_core_modified"] is False
    assert manifest["policy_retuning"] == 0
    assert manifest["security_replay_encrypted_runs"] == 0
    assert manifest["security_amendment"] == "NOT_REQUIRED"
    assert summary["security_reconciliation"]["class"] == "CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH"
    assert summary["security_reconciliation"]["root_cause"] == "RESULT_SCOPE_AND_AGGREGATION_MISMATCH"
    assert summary["models"]["mlp_100"]["security_policy_admission"] == "SECURITY_V2_PASS"
    assert summary["models"]["lenet5_small"]["security_policy_admission"] == "SECURITY_V2_PASS"
    performance = summary["models"]["mlp_100"]["performance_evidence"]
    assert performance["effect_class"] == "LITERAL_EFFECT_ONLY"
    assert performance["graph_only_over_gap_aware_total_ci95"][0] < 1
    assert performance["graph_only_over_gap_aware_total_ci95"][1] > 1
    assert performance["catalog_over_gap_aware_total_ci95"][0] > 1
    assert performance["records"] == 5400
    assert summary["models"]["lenet5_small"]["catalog_coverage"] == "PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG_7_OF_7"
    assert [tier["name"] for tier in hierarchy["tiers"]] == [
        "Tier 1 - Controlled Primary",
        "Tier 2 - Standard Multiclass Generalization",
        "Tier 3 - Additional Robustness",
    ]
    assert hierarchy["tiers"][0]["contents"]["catalog_candidates"] == 700
    assert hierarchy["tiers"][1]["contents"]["validation_images_per_model"] == 500

    with (PACK / "catalog_support_matrix.csv").open(newline="", encoding="utf-8") as handle:
        catalog = {row["model"]: row for row in csv.DictReader(handle)}
    assert catalog["mlp_100"]["safe"] == "6"
    assert catalog["lenet5_small"]["plan_unsupported"] == "7"

    with (PACK / "evidence_dependencies.csv").open(newline="", encoding="utf-8") as handle:
        dependencies = list(csv.DictReader(handle))
    assert len(dependencies) == 8
    for row in dependencies:
        path = ROOT / row["path"]
        assert path.is_file(), path
        assert digest(path) == row["manifest_sha256"], path

    claim_pack = load(ROOT / "docs/evidence/journal_multiclass_claim_admission_v2/claims.json")
    claims = {row["claim_id"]: row for row in claim_pack["claims"]}
    assert claims["mlp100_paired_latency_amendment"]["paper_admitted"] is True
    assert claims["arbitrary_packed_cnn"]["paper_admitted"] is False
    assert "S29 is faster than S32" in claims["mlp100_paired_latency_amendment"]["prohibited_wording"]

    source_results = load(ROOT / "docs/evidence/journal_multiclass_extension_results_v1/summary.json")
    assert source_results["models"]["mlp_100"]["locked_audit"]["retuning_count"] == 0
    assert source_results["models"]["lenet5_small"]["locked_audit"]["retuning_count"] == 0
    assert source_results["models"]["mlp_100"]["locked_audit"]["argmax_flips"] == 0
    assert source_results["models"]["lenet5_small"]["locked_audit"]["argmax_flips"] == 0

    for line in (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        assert digest(PACK / name) == expected, name
    print("journal_multiclass_extension_final_v1=VERIFIED state=FINAL_FROZEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
