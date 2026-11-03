#!/usr/bin/env python3
"""Freeze a fail-closed research-core readiness audit without paper admission."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

V5_PATH = REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v5.py"
V5_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v5_for_readiness", V5_PATH
)
assert V5_SPEC is not None and V5_SPEC.loader is not None
V5 = importlib.util.module_from_spec(V5_SPEC)
V5_SPEC.loader.exec_module(V5)

MATCHED_PATH = REPO_ROOT / "scripts/analyze_hit_direct_matched_workload.py"
MATCHED_SPEC = importlib.util.spec_from_file_location(
    "analyze_hit_direct_matched_workload_for_readiness", MATCHED_PATH
)
assert MATCHED_SPEC is not None and MATCHED_SPEC.loader is not None
MATCHED = importlib.util.module_from_spec(MATCHED_SPEC)
MATCHED_SPEC.loader.exec_module(MATCHED)

BASE = V5.BASE
CHECKPOINT = REPO_ROOT / "docs/evidence/research_completion_checkpoint_v5"
MATCHED_PACK = REPO_ROOT / "docs/evidence/hit_direct_matched_workload_v1"
OUTPUT_DEFAULT = REPO_ROOT / "docs/evidence/research_core_readiness_v1"

RESEARCH_SOURCES = {
    "claim_matrix": (
        REPO_ROOT / "docs/research/flipguard_v2_claim_evidence_matrix.md"
    ),
    "novelty_audit": (
        REPO_ROOT
        / "docs/research/step_7f1_primary_source_novelty_audit.md"
    ),
    "provider_boundary": (
        REPO_ROOT
        / "docs/research/step_7g5_external_provider_evidence_boundary.md"
    ),
}

REQUIRED_CORE_CLAIMS = {
    "direct_synthesis": "SUPPORTED",
    "adaptive_repair": "SUPPORTED",
    "decision_integrity_certification": "PARTIALLY_SUPPORTED",
    "trial_reduction": "SUPPORTED",
    "security_compliant_bounded_catalog_comparison": "SUPPORTED",
    "latency_speedup": "PARTIALLY_SUPPORTED",
    "security": "PARTIALLY_SUPPORTED",
    "locked_audit_fixed_heldout_partitions": "SUPPORTED",
    "training_model_seed_generalization": "PARTIALLY_SUPPORTED",
    "structural_generalization": "PARTIALLY_SUPPORTED",
    "artifact_reproducibility": "PARTIALLY_SUPPORTED",
}

EXCLUDED_CLAIMS = {
    "decision_contract_candidate_synthesis_effect": "BLOCKED",
    "instantiated_ckks_analytical_certificate": "BLOCKED",
    "encrypted_external_candidate_certification": "BLOCKED",
    "general_external_autotuner_integration": "NOT_EVALUATED",
    "hit_candidate_quality": "NOT_EVALUATED",
}

SUPPORTED_CONTEXT_CLAIMS = {
    "finite_domain_decision_contract_activation": "SUPPORTED",
    "conditional_error_envelope_propagation": "SUPPORTED",
    "exact_modulus_security_sensitivity": "PARTIALLY_SUPPORTED",
    "provider_class_interoperability": "PARTIALLY_SUPPORTED",
    "lossless_external_literal_import": "SUPPORTED",
    "latency_only_no_certification_comparator": "SUPPORTED",
    "planner_baseline": "PARTIALLY_SUPPORTED",
}


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    V5.verify(CHECKPOINT)
    MATCHED.verify(MATCHED_PACK)
    checkpoint = BASE.load_json(CHECKPOINT / "manifest.json")
    registry = BASE.load_json(CHECKPOINT / "claim_states.json")
    matched = BASE.load_json(MATCHED_PACK / "manifest.json")

    BASE.require_equal(
        checkpoint["paper_claim_allowed"],
        False,
        "checkpoint paper admission",
    )
    BASE.require_equal(
        registry["paper_claim_allowed"],
        False,
        "claim registry paper admission",
    )
    states = registry["states"]
    for claim, expected in REQUIRED_CORE_CLAIMS.items():
        BASE.require_equal(states.get(claim), expected, f"core claim {claim}")
    for claim, expected in EXCLUDED_CLAIMS.items():
        BASE.require_equal(
            states.get(claim), expected, f"excluded claim {claim}"
        )
    for claim, expected in SUPPORTED_CONTEXT_CLAIMS.items():
        BASE.require_equal(
            states.get(claim), expected, f"context claim {claim}"
        )
    BASE.require_equal(
        matched["claim_states"]["matched_workload_provider_comparison"],
        "PARTIALLY_SUPPORTED",
        "matched provider comparison",
    )
    BASE.require_equal(
        matched["claim_states"]["unpaired_latency_claim"],
        "BLOCKED",
        "matched unpaired latency boundary",
    )
    BASE.require_equal(
        matched["encrypted_executions_added"],
        0,
        "matched encrypted executions",
    )
    BASE.require_equal(
        matched["policy_modifications"],
        0,
        "matched policy modifications",
    )
    return checkpoint, registry


def build_summary() -> dict[str, Any]:
    checkpoint, registry = validate_inputs()
    return {
        "schema_version": "flipguard_research_core_readiness_summary_v1",
        "research_core_status": "READY_WITH_SCOPED_LIMITATIONS",
        "core_scope": (
            "empirical finite-set decision-integrity admission for declared "
            "CKKS graph adapters, bounded failure-aware direct synthesis, "
            "abstention, Security V2 filtering, and no-retuning locked replay"
        ),
        "required_core_claims": {
            claim: {
                "state": registry["states"][claim],
                "gate": "PASS",
            }
            for claim in REQUIRED_CORE_CLAIMS
        },
        "supported_context_claims": {
            claim: {
                "state": registry["states"][claim],
                "gate": "PASS_WITH_DECLARED_SCOPE",
            }
            for claim in SUPPORTED_CONTEXT_CLAIMS
        },
        "excluded_claims": {
            claim: {
                "state": registry["states"][claim],
                "paper_admission": "EXCLUDE",
            }
            for claim in EXCLUDED_CLAIMS
        },
        "mandatory_scope_limits": [
            "finite observed validation and audit evidence is not a domain-wide analytical guarantee",
            "the natural-data decision-margin synthesis effect is blocked",
            "the CKKS primitive residual envelope is not instantiated",
            "external-provider certification has no SAFE public-tool candidate with locked audit",
            "structural support is limited to declared graph adapters and scalar-replicated packing",
            "latency inference clusters by 10 dataset-model units and remains bounded to the frozen host and arms",
            "Security V2 exact-estimator sensitivity does not model Lattigo's explicit Gaussian truncation bound",
        ],
        "optional_extensions_not_required_for_scoped_core": [
            "SAFE public third-party selector or autotuner candidate with locked audit",
            "instantiated CKKS primitive residual bounds",
            "packed CNN or arbitrary graph support",
            "additional independent datasets, training seeds, backends, and hosts",
            "release tag and external archive",
        ],
        "evidence": {
            "checkpoint_path": CHECKPOINT.relative_to(REPO_ROOT).as_posix(),
            "checkpoint_manifest_sha256": BASE.sha256_path(
                CHECKPOINT / "manifest.json"
            ),
            "checkpoint_packs": len(checkpoint["packs"]),
            "matched_provider_path": MATCHED_PACK.relative_to(
                REPO_ROOT
            ).as_posix(),
            "matched_provider_manifest_sha256": BASE.sha256_path(
                MATCHED_PACK / "manifest.json"
            ),
            "total_bound_packs": len(checkpoint["packs"]) + 1,
        },
        "paper_work_prohibited": True,
        "paper_claim_allowed": False,
        "manual_scope_review_required": True,
        "readiness_interpretation": (
            "the scoped empirical systems study has the required evidence "
            "to enter manual direction review; excluded claims remain blocked "
            "and this artifact does not authorize manuscript work"
        ),
    }


def freeze(
    output: Path,
    analysis_commit: str,
    *,
    research_source_digests: dict[str, str] | None = None,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite research readiness evidence: {output}"
        )
    summary = build_summary()
    source_records = {
        name: {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                research_source_digests[name]
                if research_source_digests is not None
                else BASE.sha256_path(path)
            ),
        }
        for name, path in RESEARCH_SOURCES.items()
    }
    output.mkdir(parents=True)
    (output / "summary.json").write_bytes(BASE.canonical_json(summary))
    manifest = {
        "schema_version": "flipguard_research_core_readiness_evidence_v1",
        "evidence_id": "research_core_readiness_v1",
        "classification": "STATIC_POST_CONFIRMATORY_SCOPE_GATE",
        "analysis_commit": analysis_commit,
        "research_core_status": summary["research_core_status"],
        "research_sources": source_records,
        "checkpoint_manifest_sha256": summary["evidence"][
            "checkpoint_manifest_sha256"
        ],
        "matched_provider_manifest_sha256": summary["evidence"][
            "matched_provider_manifest_sha256"
        ],
        "summary_sha256": BASE.sha256_path(output / "summary.json"),
        "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
        "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
        "encrypted_executions_added": 0,
        "policy_modifications": 0,
        "paper_work_prohibited": True,
        "paper_claim_allowed": False,
        "manual_scope_review_required": True,
        "block_reason": (
            "manual research-direction review is required; blocked and "
            "not-evaluated claims remain excluded, and manuscript work is "
            "still prohibited"
        ),
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Core Readiness V1

This static gate classifies the declared empirical systems core as
`READY_WITH_SCOPED_LIMITATIONS`. It verifies checkpoint V5 and the no-rerun
HIT/direct matched-workload diagnostic.

The status is not paper admission. Blocked or unevaluated claims remain
excluded, manual direction review is required, and manuscript work remains
prohibited.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    BASE.verify_checksums(output)
    V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_core_readiness_evidence_v1",
        "readiness schema",
    )
    BASE.require_equal(
        manifest["research_core_status"],
        "READY_WITH_SCOPED_LIMITATIONS",
        "research core status",
    )
    BASE.require_equal(
        manifest["paper_work_prohibited"], True, "paper work prohibition"
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "paper admission"
    )
    BASE.require_equal(
        manifest["encrypted_executions_added"],
        0,
        "encrypted executions added",
    )
    BASE.require_equal(
        manifest["policy_modifications"], 0, "policy modifications"
    )
    expected = build_summary()
    summary = BASE.load_json(output / "summary.json")
    BASE.require_equal(summary, expected, "recomputed readiness summary")
    BASE.require_equal(
        manifest["summary_sha256"],
        BASE.sha256_path(output / "summary.json"),
        "summary digest",
    )
    source_digests = {
        name: record["sha256"]
        for name, record in manifest["research_sources"].items()
    }
    for name, path in RESEARCH_SOURCES.items():
        BASE.verify_bound_source(
            path,
            source_digests[name],
            manifest["analysis_commit"],
            f"{name} binding",
        )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-research-readiness-", dir="/tmp"
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["analysis_commit"],
            research_source_digests=source_digests,
        )
        BASE.compare_trees(output, rebuilt)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--analysis-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        manifest = verify(output)
        print(
            "research_core_readiness=VERIFIED "
            f"status={manifest['research_core_status']} "
            "paper_claim_allowed=false"
        )
        return
    if not args.analysis_commit:
        raise ValueError("--analysis-commit is required when freezing")
    freeze(output, args.analysis_commit)
    print(f"research_core_readiness=FROZEN output={output}")


if __name__ == "__main__":
    main()
