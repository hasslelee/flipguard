#!/usr/bin/env python3
"""Deterministically verify the journal multiclass claim boundary."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest = load_json(PACK / "manifest.json")
    claims_doc = load_json(PACK / "claims.json")
    claims = {row["claim_id"]: row for row in claims_doc["claims"]}
    expected = {
        "multiclass_argmax_proposition",
        "mlp100_finite_validation_audit",
        "lenet5_small_finite_validation_audit",
        "natural_top_two_gap_literal_effect",
        "frozen_catalog_coverage",
        "mlp100_paired_latency_amendment",
        "standard_model_security_qualification",
        "arbitrary_packed_cnn",
    }
    assert set(claims) == expected
    assert sum(bool(row["paper_admitted"]) for row in claims.values()) == 7
    assert claims["arbitrary_packed_cnn"]["state"] == "BLOCKED"
    assert not claims["arbitrary_packed_cnn"]["paper_admitted"]

    paired = load_json(
        ROOT / "docs/evidence/journal_mlp_paired_latency_v1/analysis/claim_admission.json"
    )
    assert paired["effect_class"] == "LITERAL_EFFECT_ONLY"
    assert paired["literal_effect_paper_admitted"] is True
    assert paired["latency_superiority_paper_admitted"] is False
    pair = paired["graph_only_over_gap_aware_total"]
    assert pair["total_ci_low"] < 1 < pair["total_ci_high"]

    security = load_json(
        ROOT
        / "docs/evidence/journal_multiclass_security_reconciliation_v1/reconciliation.json"
    )
    assert security["classification"] == "CLASS_S1_ESTIMATOR_ADAPTER_MISMATCH"
    assert security["root_cause"] == "RESULT_SCOPE_AND_AGGREGATION_MISMATCH"
    assert security["security_amendment_required"] is False
    assert security["encrypted_replay_required"] is False
    assert security["corrected_static_replay"]["candidate_failures"] == 0

    extension = load_json(
        ROOT / "docs/evidence/journal_multiclass_extension_results_v1/summary.json"
    )
    assert extension["models"]["mlp_100"]["locked_audit"]["status"] == "SAFE"
    assert extension["models"]["lenet5_small"]["locked_audit"]["status"] == "SAFE"
    assert extension["models"]["lenet5_small"]["security_v2_bounded_catalog"]["plan_unsupported"] == 7

    with (PACK / "claim_evidence_dependencies.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        dependencies = list(csv.DictReader(handle))
    assert {row["claim_id"] for row in dependencies} == expected
    for claim in claims.values():
        assert claim["exact_allowed_wording_ko"]
        assert claim["exact_allowed_wording_en"]
        assert claim["scope"] and claim["evidence"]
        assert claim["security_qualification"] and claim["limitation"]
        assert claim["prohibited_wording"]
        for path in claim["evidence"]:
            assert (ROOT / path).exists(), path

    for key, expected_digest in manifest["inputs"].items():
        rel = {
            "checkpoint_manifest": "docs/evidence/journal_multiclass_extension_checkpoint_v1/manifest.json",
            "extension_results_manifest": "docs/evidence/journal_multiclass_extension_results_v1/manifest.json",
            "natural_activation_manifest": "docs/evidence/journal_multiclass_activation_v1/manifest.json",
            "paired_latency_manifest": "docs/evidence/journal_mlp_paired_latency_v1/manifest.json",
            "security_reconciliation_manifest": "docs/evidence/journal_multiclass_security_reconciliation_v1/manifest.json",
        }[key]
        assert "sha256:" + sha256(ROOT / rel) == expected_digest

    checksums = (PACK / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in checksums:
        expected_digest, name = line.split("  ", 1)
        assert sha256(PACK / name) == expected_digest, name

    print("journal_multiclass_claim_admission_v2=VERIFIED admitted=7 blocked=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
