#!/usr/bin/env python3
"""Freeze and verify the native-EVA-aware research checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V6_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v6.py"
)
V6_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v6_for_v7",
    V6_MODULE_PATH,
)
assert V6_SPEC is not None and V6_SPEC.loader is not None
V6 = importlib.util.module_from_spec(V6_SPEC)
V6_SPEC.loader.exec_module(V6)

BASE = V6.BASE
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v7"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v6"
)
EVA_NATIVE = Path("docs/evidence/eva_native_runtime_replay_v1")

PACKS = dict(V6.PACKS)
PACKS["eva_native_runtime_replay"] = EVA_NATIVE

CLAIM_STATES = dict(V6.CLAIM_STATES)
CLAIM_STATES.update(
    {
        "native_eva_seal_runtime_execution": "SUPPORTED",
        "native_eva_seal_decision_certification": "BLOCKED",
        "native_eva_seal_locked_audit": "NOT_EVALUATED",
        "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
        "general_external_compiler_interoperability": (
            "PARTIALLY_SUPPORTED"
        ),
        "encrypted_external_candidate_certification": "BLOCKED",
    }
)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V6.load_manifests()
    path = REPO_ROOT / EVA_NATIVE / "manifest.json"
    if not path.is_file():
        raise ValueError(f"missing required evidence pack: {EVA_NATIVE}")
    manifests["eva_native_runtime_replay"] = BASE.load_json(path)
    return manifests


def validate_eva_native(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_eva_native_runtime_evidence_v1",
        "native EVA evidence schema",
    )
    BASE.require_equal(
        manifest["status"],
        "PARTIAL_SCIENTIFIC_RESULT",
        "native EVA evidence status",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "native EVA paper gate"
    )
    BASE.require_equal(
        manifest["direct_policy_digest"],
        BASE.DIRECT_POLICY_DIGEST,
        "native EVA direct policy",
    )
    BASE.require_equal(
        manifest["security_policy_digest"],
        BASE.SECURITY_POLICY_DIGEST,
        "native EVA security policy",
    )
    BASE.require_equal(
        manifest["log_representation"],
        "TRAILING_SPACE_TAB_NORMALIZED_TEXT_V1",
        "native EVA log representation",
    )
    summary = BASE.load_json(REPO_ROOT / EVA_NATIVE / "summary.json")
    BASE.require_equal(
        summary["claim_states"]["native_eva_seal_execution"],
        "SUPPORTED",
        "native EVA execution claim",
    )
    BASE.require_equal(
        summary["claim_states"][
            "native_eva_seal_decision_certification"
        ],
        "BLOCKED",
        "native EVA certification claim",
    )
    BASE.require_equal(
        summary["validation"]["status"],
        "REJECTED",
        "native EVA validation result",
    )
    counts = summary["validation"]["counts"]
    BASE.require_equal(
        counts["observations"], 42, "native EVA validation observations"
    )
    BASE.require_equal(
        counts["decision_flips"], 11, "native EVA validation flips"
    )
    BASE.require_equal(
        counts["error_violations"], 36, "native EVA validation violations"
    )
    BASE.require_equal(
        counts["execution_failures"],
        0,
        "native EVA execution failures",
    )
    BASE.require_equal(
        summary["locked_audit"]["status"],
        "NOT_EVALUATED",
        "native EVA locked audit",
    )
    BASE.require_equal(
        summary["accounting"]["retuning"], 0, "native EVA retuning"
    )
    BASE.require_equal(
        summary["policy_modifications"],
        0,
        "native EVA policy modifications",
    )
    BASE.require_equal(
        summary["security_interpretation"]["runtime_security_claim"],
        "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "native EVA runtime security boundary",
    )


def validate_semantics(manifests: dict[str, dict[str, Any]]) -> None:
    V6.validate_semantics(
        {name: manifests[name] for name in V6.PACKS}
    )
    validate_eva_native(manifests["eva_native_runtime_replay"])
    for claim, state in CLAIM_STATES.items():
        if state not in BASE.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": BASE.sha256_path(root / "manifest.json"),
            "tree_sha256": BASE.tree_digest(root),
            "checksum_index": BASE.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V6.verify(PREVIOUS_CHECKPOINT)
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
    paths = V6.research_source_paths()
    paths.update(
        {
            "related_work": (
                REPO_ROOT / "docs/research/flipguard_v2_related_work.md"
            ),
            "eva_native_runtime_protocol": (
                REPO_ROOT
                / "docs/research/step_7g11_eva_native_runtime_protocol.md"
            ),
        }
    )
    return paths


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
        "Paper admission remains manual. A pinned EVA v1.0.1 program ran "
        "successfully for 42 validation observations on native SEAL v3.6.4, "
        "but decision validation was REJECTED with 11 flips and 36 budget "
        "violations, so locked audit was not evaluated. Native SEAL uses a "
        "different secret/error distribution and disabled runtime security "
        "enforcement; cross-runtime numerical equivalence and a SAFE external "
        "candidate with locked audit remain unevaluated. Release tagging and "
        "external archival are also incomplete."
    )
    claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v7",
        "paper_claim_allowed": False,
        "block_reason": block_reason,
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        BASE.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v7",
        "evidence_id": "research_completion_checkpoint_v7",
        "classification": (
            "POST_CONFIRMATORY_NATIVE_EXTERNAL_RUNTIME_CHECKPOINT"
        ),
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": block_reason,
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds the pinned native EVA/SEAL execution pack. It records "
                "successful encrypted execution and fail-closed decision "
                "rejection without modifying checkpoint V6 or either policy."
            ),
        },
        "policies": {
            "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
            "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "external_compiler_boundary": {
            "eva_compiler_parameter_replays": 1,
            "eva_schedule_bound_imports": 1,
            "eva_lattigo_corrected_smoke_rejected": 1,
            "native_eva_seal_validation_instances": 1,
            "native_eva_seal_validation_observations": 42,
            "native_eva_seal_execution_failures": 0,
            "native_eva_seal_validation_safe": 0,
            "native_eva_seal_validation_rejected": 1,
            "native_eva_seal_decision_flips": 11,
            "native_eva_seal_budget_violations": 36,
            "native_eva_seal_locked_audits": 0,
            "pre_execution_recoveries": 2,
            "pre_execution_recovery_encrypted_executions": 0,
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
            "cross-runtime numerical equivalence study",
            "runtime-specific security estimation",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V7

This non-overwriting checkpoint binds checkpoint V6 plus the pinned native
Microsoft EVA v1.0.1 / SEAL v3.6.4 execution pack. It changes no frozen
policy and promotes no paper claim.

All 42 encrypted validation observations executed, but the candidate was
decision-REJECTED with 11 flips and 36 error-budget violations. Locked audit
was therefore not evaluated. The result supports native execution, not
decision certification, runtime security equivalence, or broad external
compiler interoperability.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path) -> None:
    BASE.verify_checksums(output)
    V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v7",
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
    boundary = manifest["external_compiler_boundary"]
    expected = {
        "native_eva_seal_validation_observations": 42,
        "native_eva_seal_execution_failures": 0,
        "native_eva_seal_validation_safe": 0,
        "native_eva_seal_validation_rejected": 1,
        "native_eva_seal_decision_flips": 11,
        "native_eva_seal_budget_violations": 36,
        "native_eva_seal_locked_audits": 0,
        "policy_modifications": 0,
    }
    for field, value in expected.items():
        BASE.require_equal(
            boundary[field], value, f"checkpoint boundary {field}"
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
        prefix="flipguard-research-checkpoint-v7-",
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
            "research_completion_checkpoint_v7=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v7=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
