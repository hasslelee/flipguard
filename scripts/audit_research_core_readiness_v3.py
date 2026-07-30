#!/usr/bin/env python3
"""Freeze a checkpoint-V8-aware readiness audit without paper admission."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str) -> Any:
    path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2 = load_module(
    "audit_research_core_readiness_v2_for_v3",
    "scripts/audit_research_core_readiness_v2.py",
)
V8 = load_module(
    "freeze_research_completion_checkpoint_v8_for_readiness_v3",
    "scripts/freeze_research_completion_checkpoint_v8.py",
)
BASE = V8.BASE

CHECKPOINT = REPO_ROOT / "docs/evidence/research_completion_checkpoint_v8"
MATCHED_PACK = V2.MATCHED_PACK
PREVIOUS_READINESS = (
    REPO_ROOT / "docs/evidence/research_core_readiness_v2"
)
OUTPUT_DEFAULT = REPO_ROOT / "docs/evidence/research_core_readiness_v3"

RESEARCH_SOURCES = {
    **V2.RESEARCH_SOURCES,
    "eva_native_scale_sensitivity_protocol": (
        REPO_ROOT
        / "docs/research/step_7g12_eva_native_scale_sensitivity_protocol.md"
    ),
}

REQUIRED_CORE_CLAIMS = dict(V2.REQUIRED_CORE_CLAIMS)
EXCLUDED_CLAIMS = dict(V2.EXCLUDED_CLAIMS)
EXCLUDED_CLAIMS.pop("native_eva_seal_decision_certification")
EXCLUDED_CLAIMS.pop("native_eva_seal_locked_audit")
EXCLUDED_CLAIMS.pop("encrypted_external_candidate_certification")
EXCLUDED_CLAIMS.update(
    {
        "original_scale20_candidate_decision_certification": "BLOCKED",
        "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
        "general_external_autotuner_integration": "NOT_EVALUATED",
    }
)
SUPPORTED_CONTEXT_CLAIMS = dict(V2.SUPPORTED_CONTEXT_CLAIMS)
SUPPORTED_CONTEXT_CLAIMS.update(
    {
        "native_eva_seal_decision_certification": (
            "PARTIALLY_SUPPORTED"
        ),
        "native_eva_seal_locked_audit": "PARTIALLY_SUPPORTED",
        "encrypted_external_candidate_certification": (
            "PARTIALLY_SUPPORTED"
        ),
        "external_precision_sensitivity": "PARTIALLY_SUPPORTED",
    }
)


def previous_readiness_record() -> dict[str, Any]:
    BASE.verify_checksums(PREVIOUS_READINESS)
    manifest = BASE.load_json(PREVIOUS_READINESS / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_core_readiness_evidence_v2",
        "previous readiness schema",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "previous readiness paper gate",
    )
    return {
        "path": PREVIOUS_READINESS.relative_to(REPO_ROOT).as_posix(),
        "schema_version": manifest["schema_version"],
        "manifest_sha256": BASE.sha256_path(
            PREVIOUS_READINESS / "manifest.json"
        ),
        "tree_sha256": BASE.tree_digest(PREVIOUS_READINESS),
        "status": "IMMUTABLE_PREDECESSOR",
    }


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    V8.verify(CHECKPOINT)
    V2.V1.MATCHED.verify(MATCHED_PACK)
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
    BASE.require_equal(
        checkpoint["policies"]["policy_retuning"],
        0,
        "checkpoint policy retuning",
    )
    states = registry["states"]
    groups = [
        set(REQUIRED_CORE_CLAIMS),
        set(EXCLUDED_CLAIMS),
        set(SUPPORTED_CONTEXT_CLAIMS),
    ]
    if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
        raise ValueError("readiness claim partitions overlap")
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
        matched["encrypted_executions_added"],
        0,
        "matched encrypted executions",
    )
    boundary = checkpoint["external_compiler_boundary"]
    expected_boundary = {
        "native_eva_scale_arms": 3,
        "native_eva_validation_observations": 126,
        "native_eva_validation_safe_arms": 2,
        "native_eva_validation_rejected_arms": 1,
        "native_eva_selected_scale": 30,
        "native_eva_locked_audit_observations": 48,
        "native_eva_locked_audit_flips": 0,
        "native_eva_locked_audit_violations": 0,
        "policy_modifications": 0,
        "retuning": 0,
    }
    for key, expected in expected_boundary.items():
        BASE.require_equal(
            boundary[key], expected, f"external boundary {key}"
        )
    return checkpoint, registry


def build_summary() -> dict[str, Any]:
    checkpoint, registry = validate_inputs()
    return {
        "schema_version": "flipguard_research_core_readiness_summary_v3",
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
        "native_external_runtime_result": {
            "runtime_execution": "SUPPORTED",
            "development_only": True,
            "fixed_scale_arms": [20, 30, 40],
            "validation_observations": 126,
            "validation_key_runs": 9,
            "arm_statuses": {
                "20": "REJECTED",
                "30": "SAFE",
                "40": "SAFE",
            },
            "selected_scale": 30,
            "selection_rule": "FIRST_SAFE_IN_PREDECLARED_ORDER",
            "locked_audit_observations": 48,
            "locked_audit_status": "SAFE",
            "locked_audit_flips": 0,
            "locked_audit_violations": 0,
            "retuning": 0,
            "policy_modifications": 0,
            "original_scale20_status": "REJECTED",
            "repeated_scale20_status": "REJECTED",
            "interpretation": (
                "one post-rejection seed-0 external-compiler sensitivity "
                "supports scoped native candidate certification and locked "
                "replay, not general autotuner or runtime-security claims"
            ),
        },
        "mandatory_scope_limits": [
            "finite observed validation and audit evidence is not a domain-wide analytical guarantee",
            "the natural-data decision-margin synthesis effect is blocked",
            "the CKKS primitive residual envelope is not instantiated",
            "native EVA scale sensitivity is post-rejection seed-0 development evidence on one model",
            "native SEAL and Lattigo runtime distributions are not security-equivalent",
            "cross-runtime numerical equivalence is not evaluated",
            "general external-autotuner behavior is not evaluated",
            "structural support is limited to declared graph adapters and scalar-replicated packing",
            "latency inference clusters by 10 dataset-model units and remains bounded to the frozen host and arms",
            "Security V2 exact-estimator sensitivity does not model Lattigo's explicit Gaussian truncation bound",
        ],
        "optional_extensions_not_required_for_scoped_core": [
            "independent public autotuner candidate with locked audit",
            "instantiated CKKS primitive residual bounds",
            "packed CNN or arbitrary graph support",
            "cross-runtime matched numerical study",
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
            "total_current_bound_packs": len(checkpoint["packs"]) + 1,
        },
        "paper_work_prohibited": True,
        "paper_claim_allowed": False,
        "manual_scope_review_required": True,
        "readiness_interpretation": (
            "the scoped empirical systems study remains ready for manual "
            "direction review with explicit limitations; the native EVA "
            "sensitivity closes one development context gap but does not "
            "authorize manuscript work or expand the core scope"
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
    predecessor = previous_readiness_record()
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
        "schema_version": "flipguard_research_core_readiness_evidence_v3",
        "evidence_id": "research_core_readiness_v3",
        "classification": "STATIC_NATIVE_EVA_SCALE_AWARE_SCOPE_GATE",
        "analysis_commit": analysis_commit,
        "research_core_status": summary["research_core_status"],
        "lineage": {
            "previous_readiness": predecessor,
            "change": (
                "Re-evaluates scoped readiness against checkpoint V8 and "
                "the development-only native EVA first-SAFE locked audit."
            ),
        },
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
            "manual research-direction review is required; the native EVA "
            "SAFE audit is one development sensitivity, while cross-runtime "
            "equivalence, runtime security, and general external-autotuner "
            "behavior remain unevaluated; manuscript work is prohibited"
        ),
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Core Readiness V3

This static gate keeps the declared empirical systems core at
`READY_WITH_SCOPED_LIMITATIONS`. It verifies checkpoint V8 and recognizes the
development-only native EVA scale-30 SAFE validation and untouched audit.

The status is not paper admission. Runtime-security equivalence, cross-runtime
numerical equivalence, and general external-autotuner behavior remain outside
the supported scope. Manuscript work remains prohibited.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    BASE.verify_checksums(output)
    V8.V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_core_readiness_evidence_v3",
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
        "readiness encrypted executions",
    )
    BASE.require_equal(
        manifest["policy_modifications"], 0, "policy modifications"
    )
    BASE.require_equal(
        manifest["lineage"]["previous_readiness"],
        previous_readiness_record(),
        "readiness lineage",
    )
    summary = BASE.load_json(output / "summary.json")
    BASE.require_equal(summary, build_summary(), "recomputed readiness summary")
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
        prefix="flipguard-research-readiness-v3-", dir="/tmp"
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
            "research_core_readiness_v3=VERIFIED "
            f"status={manifest['research_core_status']} "
            "paper_claim_allowed=false"
        )
        return
    if not args.analysis_commit:
        raise ValueError("--analysis-commit is required when freezing")
    freeze(output, args.analysis_commit)
    print(f"research_core_readiness_v3=FROZEN output={output}")


if __name__ == "__main__":
    main()
