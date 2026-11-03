#!/usr/bin/env python3
"""Freeze a V7-aware research-core readiness audit without paper admission."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

V1_PATH = REPO_ROOT / "scripts/audit_research_core_readiness.py"
V1_SPEC = importlib.util.spec_from_file_location(
    "audit_research_core_readiness_v1_for_v2", V1_PATH
)
assert V1_SPEC is not None and V1_SPEC.loader is not None
V1 = importlib.util.module_from_spec(V1_SPEC)
V1_SPEC.loader.exec_module(V1)

V7_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v7.py"
)
V7_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v7_for_readiness_v2",
    V7_PATH,
)
assert V7_SPEC is not None and V7_SPEC.loader is not None
V7 = importlib.util.module_from_spec(V7_SPEC)
V7_SPEC.loader.exec_module(V7)

BASE = V7.BASE
CHECKPOINT = REPO_ROOT / "docs/evidence/research_completion_checkpoint_v7"
MATCHED_PACK = V1.MATCHED_PACK
PREVIOUS_READINESS = (
    REPO_ROOT / "docs/evidence/research_core_readiness_v1"
)
OUTPUT_DEFAULT = REPO_ROOT / "docs/evidence/research_core_readiness_v2"

RESEARCH_SOURCES = {
    **V1.RESEARCH_SOURCES,
    "related_work": (
        REPO_ROOT / "docs/research/flipguard_v2_related_work.md"
    ),
    "eva_native_runtime_protocol": (
        REPO_ROOT / "docs/research/step_7g11_eva_native_runtime_protocol.md"
    ),
}

REQUIRED_CORE_CLAIMS = dict(V1.REQUIRED_CORE_CLAIMS)

EXCLUDED_CLAIMS = {
    **V1.EXCLUDED_CLAIMS,
    "native_eva_seal_decision_certification": "BLOCKED",
    "native_eva_seal_locked_audit": "NOT_EVALUATED",
    "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
}

SUPPORTED_CONTEXT_CLAIMS = {
    **V1.SUPPORTED_CONTEXT_CLAIMS,
    "actual_eva_compiler_parameter_output": "SUPPORTED",
    "schedule_bound_external_candidate_import": "SUPPORTED",
    "native_eva_seal_runtime_execution": "SUPPORTED",
    "general_external_compiler_interoperability": (
        "PARTIALLY_SUPPORTED"
    ),
}


def previous_readiness_record() -> dict[str, Any]:
    V1.verify(PREVIOUS_READINESS)
    manifest = BASE.load_json(PREVIOUS_READINESS / "manifest.json")
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
    V7.verify(CHECKPOINT)
    V1.MATCHED.verify(MATCHED_PACK)
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
    boundary = checkpoint["external_compiler_boundary"]
    BASE.require_equal(
        boundary["native_eva_seal_validation_observations"],
        42,
        "native EVA observations",
    )
    BASE.require_equal(
        boundary["native_eva_seal_validation_rejected"],
        1,
        "native EVA rejection",
    )
    BASE.require_equal(
        boundary["native_eva_seal_locked_audits"],
        0,
        "native EVA locked audits",
    )
    return checkpoint, registry


def build_summary() -> dict[str, Any]:
    checkpoint, registry = validate_inputs()
    return {
        "schema_version": "flipguard_research_core_readiness_summary_v2",
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
            "validation_observations": 42,
            "execution_failures": 0,
            "validation_status": "REJECTED",
            "decision_flips": 11,
            "error_budget_violations": 36,
            "locked_audit": "NOT_EVALUATED",
            "policy_modifications": 0,
            "interpretation": (
                "native execution feasibility is supported; decision "
                "certification and broad interoperability are not"
            ),
        },
        "mandatory_scope_limits": [
            "finite observed validation and audit evidence is not a domain-wide analytical guarantee",
            "the natural-data decision-margin synthesis effect is blocked",
            "the CKKS primitive residual envelope is not instantiated",
            "the native EVA candidate was decision-REJECTED and did not enter locked audit",
            "native SEAL and Lattigo runtime distributions are not security-equivalent",
            "cross-runtime numerical equivalence is not evaluated",
            "structural support is limited to declared graph adapters and scalar-replicated packing",
            "latency inference clusters by 10 dataset-model units and remains bounded to the frozen host and arms",
            "Security V2 exact-estimator sensitivity does not model Lattigo's explicit Gaussian truncation bound",
        ],
        "optional_extensions_not_required_for_scoped_core": [
            "SAFE public third-party selector or autotuner candidate with locked audit",
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
            "the scoped empirical systems study has the required evidence "
            "to enter manual direction review; native external execution is "
            "an informative negative certification control, excluded claims "
            "remain blocked, and this artifact does not authorize manuscript "
            "work"
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
        "schema_version": "flipguard_research_core_readiness_evidence_v2",
        "evidence_id": "research_core_readiness_v2",
        "classification": "STATIC_NATIVE_EVA_AWARE_SCOPE_GATE",
        "analysis_commit": analysis_commit,
        "research_core_status": summary["research_core_status"],
        "lineage": {
            "previous_readiness": predecessor,
            "change": (
                "Re-evaluates scoped readiness against checkpoint V7 and "
                "the fail-closed native EVA/SEAL decision rejection."
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
            "manual research-direction review is required; native EVA "
            "decision certification is blocked, locked audit and cross-runtime "
            "equivalence are not evaluated, and manuscript work is prohibited"
        ),
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Core Readiness V2

This static gate classifies the declared empirical systems core as
`READY_WITH_SCOPED_LIMITATIONS`. It verifies checkpoint V7, the native
EVA/SEAL decision rejection, and the no-rerun HIT/direct matched-workload
diagnostic.

The status is not paper admission. Native external execution succeeded, but
decision certification is blocked and locked audit was not evaluated.
Excluded claims remain excluded, manual direction review is required, and
manuscript work remains prohibited.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    BASE.verify_checksums(output)
    V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_core_readiness_evidence_v2",
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
    BASE.require_equal(
        manifest["lineage"]["previous_readiness"],
        previous_readiness_record(),
        "readiness lineage",
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
        prefix="flipguard-research-readiness-v2-", dir="/tmp"
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
            "research_core_readiness_v2=VERIFIED "
            f"status={manifest['research_core_status']} "
            "paper_claim_allowed=false"
        )
        return
    if not args.analysis_commit:
        raise ValueError("--analysis-commit is required when freezing")
    freeze(output, args.analysis_commit)
    print(f"research_core_readiness_v2=FROZEN output={output}")


if __name__ == "__main__":
    main()
