#!/usr/bin/env python3
"""Verify that research prose matches the frozen EVA provider evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = (
    REPO_ROOT / "docs/evidence/eva_native_scale_sensitivity_v1/summary.json"
)
DOCUMENT_PATHS = {
    "claim_matrix": REPO_ROOT
    / "docs/research/flipguard_v2_claim_evidence_matrix.md",
    "provider_boundary": REPO_ROOT
    / "docs/research/step_7g5_external_provider_evidence_boundary.md",
    "related_work": REPO_ROOT
    / "docs/research/flipguard_v2_related_work.md",
    "novelty_audit": REPO_ROOT
    / "docs/research/step_7f1_primary_source_novelty_audit.md",
    "cross_runtime_boundary": REPO_ROOT
    / "docs/research/step_7g13_cross_runtime_evidence_boundary.md",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def validate_evidence(summary: dict[str, Any]) -> None:
    require(summary["status"] == "PASS", "EVA sensitivity pack is not PASS")
    require(
        summary["evaluation_role"]
        == "seed0_development_external_compiler_precision_sensitivity",
        "EVA evaluation role changed",
    )
    require(summary["paper_claim_allowed"] is False, "paper gate changed")
    by_scale = {
        int(arm["input_scale_bits"]): arm["validation"]["status"]
        for arm in summary["arms"]
    }
    require(
        by_scale == {20: "REJECTED", 30: "SAFE", 40: "SAFE"},
        "EVA arm outcomes changed",
    )
    require(
        summary["selected"]["input_scale_bits"] == 30,
        "EVA selected scale changed",
    )
    audit = summary["locked_audit"]
    require(audit["status"] == "SAFE", "EVA locked audit is not SAFE")
    require(
        audit["counts"]["observations"] == 48,
        "EVA locked-audit population changed",
    )
    require(
        audit["counts"]["decision_flips"] == 0,
        "EVA locked-audit flips changed",
    )
    require(
        audit["counts"]["error_violations"] == 0,
        "EVA locked-audit violations changed",
    )
    require(audit["retuning"] == 0, "EVA locked-audit retuning changed")
    require(
        summary["claim_states"]["cross_runtime_numerical_equivalence"]
        == "NOT_EVALUATED",
        "cross-runtime claim boundary changed",
    )
    require(
        summary["security_interpretation"]["runtime_security_claim"]
        == "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "native runtime security boundary changed",
    )


def validate_documents(documents: dict[str, str]) -> None:
    require(set(documents) == set(DOCUMENT_PATHS), "document set changed")
    all_text = "\n".join(documents.values())

    required_global = (
        "scale-20/30/40",
        "cross-runtime",
        "NOT_EVALUATED",
        "paper_claim_allowed=false",
    )
    for marker in required_global:
        require(marker in all_text, f"missing research marker: {marker}")

    claim_matrix = documents["claim_matrix"]
    require(
        "first-SAFE scale 30 passes 48/48 untouched native SEAL audit"
        in claim_matrix,
        "claim matrix omits scoped native locked-audit success",
    )
    require(
        "matched Lattigo-SEAL numerical equivalence remain NOT_EVALUATED"
        in claim_matrix,
        "claim matrix overstates cross-runtime evidence",
    )

    provider = documents["provider_boundary"]
    for marker in (
        "`encrypted_external_candidate_certification=PARTIALLY_SUPPORTED`",
        "`native_eva_seal_locked_audit=PARTIALLY_SUPPORTED`",
        "`cross_runtime_numerical_equivalence=NOT_EVALUATED`",
        "zero flips, zero violations, and zero retuning",
    ):
        require(marker in provider, f"provider boundary missing: {marker}")

    related = documents["related_work"]
    require(
        "scale-30 first-SAFE literal passes 42 validation and 48 untouched"
        in related,
        "related work omits native EVA outcome",
    )
    require(
        "do not establish EVA autotuning quality" in related,
        "related work lacks EVA quality boundary",
    )

    novelty = documents["novelty_audit"]
    require(
        "scale 30 is the first SAFE arm and passes 48/48" in novelty,
        "novelty audit omits scoped EVA success",
    )
    require(
        "no public search-autotuner candidate" in novelty,
        "novelty audit blurs compiler and autotuner evidence",
    )

    cross_runtime = documents["cross_runtime_boundary"]
    for marker in (
        "That outcome direction does not establish equivalence.",
        "`cross_runtime_numerical_equivalence=NOT_EVALUATED`",
        "No Lattigo schedule-bound execution exists for the selected native scale-30",
        "separate security analyses for the concrete Lattigo and SEAL",
    ):
        require(
            marker in cross_runtime,
            f"cross-runtime boundary missing: {marker}",
        )

    forbidden = (
        "no native third-party compiler or selector has produced a SAFE candidate",
        "successful encrypted third-party certification plus locked audit remains open",
        "cross_runtime_numerical_equivalence=SUPPORTED",
        "general_external_autotuner_integration=SUPPORTED",
        "native_eva_seal_decision_certification=SUPPORTED",
        "native_eva_seal_locked_audit=SUPPORTED",
    )
    for marker in forbidden:
        require(marker not in all_text, f"stale or overclaimed prose: {marker}")


def verify() -> None:
    summary = load_json(SUMMARY_PATH)
    validate_evidence(summary)
    documents = {
        name: path.read_text(encoding="utf-8")
        for name, path in DOCUMENT_PATHS.items()
    }
    validate_documents(documents)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    verify()
    print(
        "external provider research boundary v2: PASS "
        "(native scale-30 scoped SAFE audit; cross-runtime NOT_EVALUATED)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
