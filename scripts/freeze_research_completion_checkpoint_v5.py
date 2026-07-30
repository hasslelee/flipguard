#!/usr/bin/env python3
"""Freeze and verify the actual-provider-aware research checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V4_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v4.py"
)
V4_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v4_for_v5",
    V4_MODULE_PATH,
)
assert V4_SPEC is not None and V4_SPEC.loader is not None
V4 = importlib.util.module_from_spec(V4_SPEC)
V4_SPEC.loader.exec_module(V4)

BASE = V4.V3.V2.V1
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v5"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v4"
)

PROVIDER_GATE = Path(
    "docs/evidence/provider_candidate_gate_interoperability_v1"
)
ORION_ADAPTER = Path("docs/evidence/orion_external_adapter_audit_v1")
HIT_ADAPTER = Path("docs/evidence/hit_external_adapter_replay_v1")
HIT_REJECTION = Path(
    "docs/evidence/hit_external_adapter_rejection_analysis_v1"
)

PACKS = dict(V4.PACKS)
PACKS.update(
    {
        "provider_candidate_gate": PROVIDER_GATE,
        "orion_external_adapter": ORION_ADAPTER,
        "hit_external_adapter": HIT_ADAPTER,
        "hit_rejection_analysis": HIT_REJECTION,
    }
)

CLAIM_STATES = dict(V4.CLAIM_STATES)
CLAIM_STATES.update(
    {
        "provider_class_interoperability": "PARTIALLY_SUPPORTED",
        "actual_public_orion_source_provenance": "SUPPORTED",
        "lossless_external_literal_import": "SUPPORTED",
        "encrypted_external_candidate_certification": "BLOCKED",
        "general_external_autotuner_integration": "NOT_EVALUATED",
        "hit_candidate_quality": "NOT_EVALUATED",
    }
)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V4.load_manifests()
    for name, relative in PACKS.items():
        if name in manifests:
            continue
        path = REPO_ROOT / relative / "manifest.json"
        if not path.is_file():
            raise ValueError(f"missing required evidence pack: {relative}")
        manifests[name] = BASE.load_json(path)
    return manifests


def validate_provider_gate(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_provider_candidate_gate_interoperability_evidence_v1",
        "provider gate schema",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "provider gate paper admission",
    )
    BASE.require_equal(
        manifest["counts"]["selected"], 4, "provider selected count"
    )
    BASE.require_equal(
        manifest["counts"]["locked_audit_pass"],
        4,
        "provider audit pass count",
    )
    BASE.require_equal(
        manifest["counts"]["retuning"], 0, "provider retuning count"
    )
    BASE.require_equal(
        manifest["counts"]["implementation_failures"],
        0,
        "provider implementation failures",
    )
    BASE.require_equal(
        manifest["claim_states"]["provider_class_interoperability"],
        "PARTIALLY_SUPPORTED",
        "provider interoperability claim",
    )
    BASE.require_equal(
        manifest["claim_states"]["third_party_autotuner_integration"],
        "NOT_EVALUATED",
        "provider third-party boundary",
    )


def validate_orion(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_orion_external_adapter_evidence_v1",
        "Orion adapter schema",
    )
    BASE.require_equal(
        manifest["classification"],
        "STATIC_FAIL_CLOSED_INTEROPERABILITY_AUDIT",
        "Orion classification",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "Orion paper admission"
    )
    counts = manifest["summary"]["counts"]
    BASE.require_equal(
        counts["actual_public_configurations"],
        3,
        "Orion public configuration count",
    )
    BASE.require_equal(
        counts["blocked_semantic_mismatch"],
        3,
        "Orion blocked configuration count",
    )
    BASE.require_equal(
        counts["candidate_requests_emitted"],
        0,
        "Orion emitted candidate count",
    )
    BASE.require_equal(
        counts["encrypted_executions"], 0, "Orion encrypted executions"
    )
    BASE.require_equal(
        counts["policy_modifications"], 0, "Orion policy modifications"
    )
    BASE.require_equal(
        manifest["claim_states"]["actual_public_orion_source_provenance"],
        "SUPPORTED",
        "Orion source provenance",
    )
    BASE.require_equal(
        manifest["claim_states"]["encrypted_external_candidate_certification"],
        "NOT_EVALUATED",
        "Orion encrypted certification boundary",
    )


def validate_hit(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_hit_external_adapter_evidence_v1",
        "HIT adapter schema",
    )
    BASE.require_equal(
        manifest["classification"],
        "SOURCE_REPLAYED_PUBLIC_PARAMETER_SELECTOR",
        "HIT classification",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "HIT paper admission"
    )
    BASE.require_equal(
        manifest["selection"],
        {
            "candidate_trials": 1,
            "flips": 0,
            "key_runs": 3,
            "outcome": "NO_SAFE",
            "status": "REJECTED",
            "violations": 6,
        },
        "HIT selection result",
    )
    BASE.require_equal(
        manifest["locked_audit"]["key_runs"], 0, "HIT audit key runs"
    )
    BASE.require_equal(
        manifest["locked_audit"]["retuning"], 0, "HIT audit retuning"
    )
    BASE.require_equal(
        manifest["claim_states"]["lossless_cross_version_literal_import"],
        "SUPPORTED",
        "HIT literal import",
    )
    BASE.require_equal(
        manifest["claim_states"]["encrypted_external_candidate_certification"],
        "BLOCKED",
        "HIT encrypted certification",
    )
    BASE.require_equal(
        manifest["claim_states"]["general_external_autotuner_integration"],
        "NOT_EVALUATED",
        "HIT general integration boundary",
    )


def validate_hit_rejection(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_hit_external_rejection_analysis_v1",
        "HIT rejection analysis schema",
    )
    BASE.require_equal(
        manifest["classification"],
        "EXPLANATORY_POST_HOC_NO_RERUN",
        "HIT rejection classification",
    )
    BASE.require_equal(
        manifest["failure_class"],
        "EXTERNAL_SELECTOR_PRECISION_BUDGET_REJECT",
        "HIT rejection failure class",
    )
    BASE.require_equal(
        manifest["encrypted_executions_added"],
        0,
        "HIT rejection encrypted executions",
    )
    BASE.require_equal(
        manifest["policy_modifications"],
        0,
        "HIT rejection policy modifications",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "HIT rejection paper admission",
    )
    summary = BASE.load_json(REPO_ROOT / HIT_REJECTION / "summary.json")
    BASE.require_equal(
        summary["observed_aggregate"]["error_violations"],
        6,
        "HIT analyzed violations",
    )
    BASE.require_equal(
        summary["observed_aggregate"][
            "all_observations_below_guaranteed_flip_boundary"
        ],
        True,
        "HIT no-flip boundary",
    )
    BASE.require_equal(
        summary["localization_limit"]["sample_level_encrypted_scores"],
        "NOT_AVAILABLE_TABULAR_TRIAL_RESULT_V1",
        "HIT sample localization boundary",
    )


def validate_semantics(manifests: dict[str, dict[str, Any]]) -> None:
    V4.validate_semantics(
        {name: manifests[name] for name in V4.PACKS}
    )
    validate_provider_gate(manifests["provider_candidate_gate"])
    validate_orion(manifests["orion_external_adapter"])
    validate_hit(manifests["hit_external_adapter"])
    validate_hit_rejection(manifests["hit_rejection_analysis"])
    for claim, state in CLAIM_STATES.items():
        if state not in BASE.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V4.V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": BASE.sha256_path(root / "manifest.json"),
            "tree_sha256": BASE.tree_digest(root),
            "checksum_index": BASE.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V4.V3.V2.validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V4.verify(PREVIOUS_CHECKPOINT)
    manifest = BASE.load_json(PREVIOUS_CHECKPOINT / "manifest.json")
    return {
        "path": PREVIOUS_CHECKPOINT.relative_to(REPO_ROOT).as_posix(),
        "schema_version": manifest["schema_version"],
        "manifest_sha256": BASE.sha256_path(
            PREVIOUS_CHECKPOINT / "manifest.json"
        ),
        "tree_sha256": BASE.tree_digest(PREVIOUS_CHECKPOINT),
        "verification": "VERIFIED_WITH_HISTORICAL_SOURCE_BINDINGS",
        "status": "IMMUTABLE_PREDECESSOR",
    }


def research_source_paths() -> dict[str, Path]:
    return {
        "claim_matrix": (
            REPO_ROOT
            / "docs/research/flipguard_v2_claim_evidence_matrix.md"
        ),
        "novelty_audit": (
            REPO_ROOT
            / "docs/research/step_7f1_primary_source_novelty_audit.md"
        ),
        "provider_evidence_boundary": (
            REPO_ROOT
            / "docs/research/step_7g5_external_provider_evidence_boundary.md"
        ),
        "provider_sample_ledger_protocol": (
            REPO_ROOT
            / "docs/research/step_7g4_provider_sample_ledger_protocol.md"
        ),
    }


def freeze(
    output: Path,
    freezer_commit: str,
    *,
    source_digests: dict[str, str] | None = None,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite research checkpoint: {output}"
        )
    manifests = load_manifests()
    validate_semantics(manifests)
    pack_records = build_pack_records(manifests)
    predecessor = previous_checkpoint_record()
    sources = research_source_paths()
    source_records = {
        name: {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                source_digests[name]
                if source_digests is not None
                else BASE.sha256_path(path)
            ),
        }
        for name, path in sources.items()
    }

    output.mkdir(parents=True)
    block_reason = (
        "Paper admission remains manual. Actual public-provider evidence "
        "contains one fail-closed Orion import and one decision-REJECTED HIT "
        "literal, not a SAFE third-party candidate with locked audit. Exact "
        "security estimates retain the declared error-distribution caveat; "
        "release tagging and external archival remain incomplete."
    )
    claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v5",
        "paper_claim_allowed": False,
        "block_reason": block_reason,
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        BASE.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v5",
        "evidence_id": "research_completion_checkpoint_v5",
        "classification": "POST_CONFIRMATORY_PROVIDER_EVIDENCE_CHECKPOINT",
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": block_reason,
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds provider-gate interoperability, actual Orion "
                "fail-closed import, AWS HIT source replay rejection, and "
                "no-rerun rejection analysis without modifying checkpoint V4."
            ),
        },
        "policies": {
            "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
            "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "external_provider_boundary": {
            "synthetic_provider_classes_selected": 4,
            "synthetic_provider_locked_audit_pass": 4,
            "actual_orion_configurations": 3,
            "actual_orion_blocked_before_execution": 3,
            "hit_literals_losslessly_imported": 1,
            "hit_security_v2_pass": 1,
            "hit_validation_safe": 0,
            "hit_validation_rejected": 1,
            "hit_locked_audits": 0,
            "policy_modifications": 0,
            "status": "PARTIALLY_SUPPORTED",
        },
        "research_sources": source_records,
        "claim_state_registry": {
            "path": "claim_states.json",
            "sha256": BASE.sha256_path(output / "claim_states.json"),
        },
        "packs": pack_records,
        "evidence_tree_hygiene": {
            "generated_python_artifacts": 0,
            "policy": "REJECT_PYCACHE_PYC_PYO",
        },
        "remaining_manual_gates": [
            "paper claim admission",
            "SAFE actual third-party candidate plus locked audit",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V5

This non-overwriting checkpoint binds the 20 packs in checkpoint V4 plus the
provider-gate, Orion, AWS HIT, and HIT rejection-analysis packs. It performs no
CKKS execution, changes no frozen policy, and promotes no paper claim.

Provider-format plumbing is verified. Actual public-source evidence remains
qualified: Orion configurations fail closed before execution, while the HIT
literal imports losslessly and passes Security V2 but is decision-REJECTED.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path) -> None:
    BASE.verify_checksums(output)
    V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v5",
        "checkpoint schema",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "checkpoint paper gate"
    )
    manifests = load_manifests()
    validate_semantics(manifests)
    BASE.require_equal(
        build_pack_records(manifests),
        manifest["packs"],
        "linked evidence records",
    )
    BASE.require_equal(
        previous_checkpoint_record(),
        manifest["lineage"]["previous_checkpoint"],
        "checkpoint lineage",
    )
    BASE.require_equal(
        manifest["external_provider_boundary"]["hit_validation_rejected"],
        1,
        "checkpoint HIT rejection",
    )
    BASE.require_equal(
        manifest["external_provider_boundary"]["hit_locked_audits"],
        0,
        "checkpoint HIT audit boundary",
    )
    sources = research_source_paths()
    source_digests = {
        name: record["sha256"]
        for name, record in manifest["research_sources"].items()
    }
    for name, path in sources.items():
        BASE.verify_bound_source(
            path,
            source_digests[name],
            manifest["freezer_commit"],
            f"{name} binding",
        )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-research-checkpoint-v5-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["freezer_commit"],
            source_digests=source_digests,
        )
        BASE.compare_trees(output, rebuilt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--freezer-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        verify(output)
        print(
            "research_completion_checkpoint_v5=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v5=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
