#!/usr/bin/env python3
"""Freeze and verify the EVA-aware research completion checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V5_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v5.py"
)
V5_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v5_for_v6",
    V5_MODULE_PATH,
)
assert V5_SPEC is not None and V5_SPEC.loader is not None
V5 = importlib.util.module_from_spec(V5_SPEC)
V5_SPEC.loader.exec_module(V5)

BASE = V5.BASE
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v6"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v5"
)
EVA_PARAMETER = Path("docs/evidence/eva_external_adapter_replay_v1")
EVA_SCHEDULE = Path(
    "docs/evidence/eva_schedule_bound_adapter_replay_v1"
)

PACKS = dict(V5.PACKS)
PACKS.update(
    {
        "eva_compiler_parameter_replay": EVA_PARAMETER,
        "eva_schedule_bound_replay": EVA_SCHEDULE,
    }
)

CLAIM_STATES = dict(V5.CLAIM_STATES)
CLAIM_STATES.update(
    {
        "actual_eva_compiler_parameter_output": "SUPPORTED",
        "schedule_bound_external_candidate_import": "SUPPORTED",
        "general_external_compiler_interoperability": (
            "PARTIALLY_SUPPORTED"
        ),
        "encrypted_external_candidate_certification": "BLOCKED",
        "locked_audit_external_schedule_replay": "NOT_EVALUATED",
        "native_eva_seal_runtime_execution": "NOT_EVALUATED",
    }
)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V5.load_manifests()
    for name, relative in PACKS.items():
        if name in manifests:
            continue
        path = REPO_ROOT / relative / "manifest.json"
        if not path.is_file():
            raise ValueError(f"missing required evidence pack: {relative}")
        manifests[name] = BASE.load_json(path)
    return manifests


def validate_eva_parameter(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_eva_external_adapter_evidence_v1",
        "EVA parameter evidence schema",
    )
    BASE.require_equal(
        manifest["status"],
        "BLOCKED_GRAPH_COMPATIBILITY",
        "EVA parameter replay status",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "EVA parameter paper gate"
    )
    summary = manifest["summary"]
    BASE.require_equal(
        summary["compiler_replay"], "PASS", "EVA compiler replay"
    )
    BASE.require_equal(
        summary["security_v2_admission"],
        "PASS",
        "EVA parameter security admission",
    )
    BASE.require_equal(
        summary["encrypted_candidate_trials"],
        0,
        "EVA parameter encrypted trials",
    )
    BASE.require_equal(
        summary["retuning"], 0, "EVA parameter replay retuning"
    )


def validate_eva_schedule(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_eva_schedule_bound_adapter_evidence_v1",
        "EVA schedule evidence schema",
    )
    BASE.require_equal(
        manifest["status"],
        "PARTIAL_SCIENTIFIC_RESULT",
        "EVA schedule evidence status",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "EVA schedule paper gate"
    )
    BASE.require_equal(
        manifest["direct_policy_digest"],
        BASE.DIRECT_POLICY_DIGEST,
        "EVA schedule direct policy",
    )
    BASE.require_equal(
        manifest["security_policy_digest"],
        BASE.SECURITY_POLICY_DIGEST,
        "EVA schedule security policy",
    )
    summary = BASE.load_json(REPO_ROOT / EVA_SCHEDULE / "summary.json")
    BASE.require_equal(
        summary["corrected_smoke"]["status"],
        "REJECTED",
        "EVA corrected smoke result",
    )
    BASE.require_equal(
        summary["corrected_smoke"]["security_admission"],
        "PASS",
        "EVA corrected smoke security",
    )
    BASE.require_equal(
        summary["corrected_smoke"]["reason_code"],
        "LATTIGO_RUNTIME_NUMERICAL_REJECT_AFTER_EXACT_SCHEDULE_REPLAY",
        "EVA corrected smoke reason",
    )
    BASE.require_equal(
        summary["formal_validation"]["status"],
        "NOT_EVALUATED",
        "EVA formal validation gate",
    )
    BASE.require_equal(
        summary["locked_audit"]["status"],
        "NOT_EVALUATED",
        "EVA locked audit gate",
    )
    BASE.require_equal(
        summary["accounting"]["retuning"], 0, "EVA schedule retuning"
    )
    BASE.require_equal(
        summary["claim_states"][
            "schedule_bound_external_candidate_import"
        ],
        "SUPPORTED",
        "EVA schedule import claim",
    )
    BASE.require_equal(
        summary["claim_states"][
            "encrypted_external_candidate_certification"
        ],
        "BLOCKED",
        "EVA encrypted certification claim",
    )


def validate_semantics(manifests: dict[str, dict[str, Any]]) -> None:
    V5.validate_semantics(
        {name: manifests[name] for name in V5.PACKS}
    )
    validate_eva_parameter(manifests["eva_compiler_parameter_replay"])
    validate_eva_schedule(manifests["eva_schedule_bound_replay"])
    for claim, state in CLAIM_STATES.items():
        if state not in BASE.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V5.V4.V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": BASE.sha256_path(root / "manifest.json"),
            "tree_sha256": BASE.tree_digest(root),
            "checksum_index": BASE.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V5.V4.V3.V2.validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V5.verify(PREVIOUS_CHECKPOINT)
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
        "eva_schedule_protocol": (
            REPO_ROOT
            / "docs/research/step_7g10_eva_schedule_bound_adapter_protocol.md"
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
        "Paper admission remains manual. EVA's exact compiler parameter "
        "output and bound execution schedule are reproducible, but the "
        "corrected one-row Lattigo smoke is decision-REJECTED; formal "
        "validation and locked audit are therefore not evaluated. No SAFE "
        "actual third-party candidate has completed locked audit. Native "
        "EVA/SEAL inference, release tagging, and external archival remain "
        "incomplete."
    )
    claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v6",
        "paper_claim_allowed": False,
        "block_reason": block_reason,
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        BASE.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v6",
        "evidence_id": "research_completion_checkpoint_v6",
        "classification": (
            "POST_CONFIRMATORY_EXTERNAL_COMPILER_EVIDENCE_CHECKPOINT"
        ),
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": block_reason,
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds the source-replayed EVA compiler parameter pack and "
                "the schedule-bound Lattigo numerical rejection pack without "
                "modifying checkpoint V5 or either frozen policy."
            ),
        },
        "policies": {
            "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
            "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "external_compiler_boundary": {
            "eva_compiler_parameter_replays": 1,
            "eva_parameter_security_v2_pass": 1,
            "eva_schedule_bound_imports": 1,
            "eva_corrected_smoke_safe": 0,
            "eva_corrected_smoke_rejected": 1,
            "eva_formal_validations": 0,
            "eva_locked_audits": 0,
            "native_eva_seal_executions": 0,
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
            "native external-runtime comparison",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V6

This non-overwriting checkpoint binds checkpoint V5 plus the source-replayed
Microsoft EVA parameter and schedule-bound replay packs. It performs no CKKS
execution, changes no frozen policy, and promotes no paper claim.

The exact EVA parameter literal passes Security V2. Its bound schedule can be
executed through the frozen Lattigo gate, but the corrected development smoke
is decision-REJECTED. Formal validation, locked audit, and native EVA/SEAL
inference are not evaluated.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path) -> None:
    BASE.verify_checksums(output)
    V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v6",
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
    BASE.require_equal(
        boundary["eva_corrected_smoke_rejected"],
        1,
        "checkpoint EVA rejection",
    )
    BASE.require_equal(
        boundary["eva_formal_validations"],
        0,
        "checkpoint EVA formal-validation boundary",
    )
    BASE.require_equal(
        boundary["eva_locked_audits"],
        0,
        "checkpoint EVA audit boundary",
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
        prefix="flipguard-research-checkpoint-v6-",
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
            "research_completion_checkpoint_v6=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v6=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
