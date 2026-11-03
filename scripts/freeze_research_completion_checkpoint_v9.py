#!/usr/bin/env python3
"""Freeze checkpoint V9 with the cross-runtime replay readiness gate."""

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


V8 = load_module(
    "freeze_research_completion_checkpoint_v8_for_v9",
    "scripts/freeze_research_completion_checkpoint_v8.py",
)
CROSS = load_module(
    "audit_eva_cross_runtime_replay_readiness_v1_for_checkpoint_v9",
    "scripts/audit_eva_cross_runtime_replay_readiness_v1.py",
)
BASE = V8.BASE
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v9"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v8"
)
CROSS_PACK = Path("docs/evidence/eva_cross_runtime_replay_readiness_v1")

PACKS = dict(V8.PACKS)
PACKS["eva_cross_runtime_replay_readiness"] = CROSS_PACK
CLAIM_STATES = dict(V8.CLAIM_STATES)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V8.load_manifests()
    path = REPO_ROOT / CROSS_PACK / "manifest.json"
    BASE.require_equal(path.is_file(), True, "cross-runtime readiness pack")
    manifests["eva_cross_runtime_replay_readiness"] = BASE.load_json(path)
    return manifests


def validate_cross_runtime_readiness(manifest: dict[str, Any]) -> None:
    CROSS.verify(REPO_ROOT / CROSS_PACK)
    summary = BASE.load_json(REPO_ROOT / CROSS_PACK / "summary.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_eva_cross_runtime_replay_readiness_evidence_v1",
        "cross-runtime readiness schema",
    )
    BASE.require_equal(
        manifest["status"],
        "NOT_READY_INTEGRITY_PRESERVING_REPLAY",
        "cross-runtime readiness status",
    )
    BASE.require_equal(
        manifest["encrypted_execution_allowed"],
        False,
        "cross-runtime encrypted execution gate",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "cross-runtime paper gate",
    )
    BASE.require_equal(
        summary["cross_runtime_numerical_equivalence"],
        "NOT_EVALUATED",
        "cross-runtime claim state",
    )
    BASE.require_equal(
        summary["policy_modifications"], 0, "cross-runtime policy changes"
    )
    BASE.require_equal(
        summary["encrypted_executions_added"],
        0,
        "cross-runtime encrypted executions",
    )


def validate_semantics(manifests: dict[str, dict[str, Any]]) -> None:
    V8.validate_semantics(
        {name: manifests[name] for name in V8.PACKS}
    )
    validate_cross_runtime_readiness(
        manifests["eva_cross_runtime_replay_readiness"]
    )
    for claim, state in CLAIM_STATES.items():
        if state not in BASE.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V8.V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": BASE.sha256_path(root / "manifest.json"),
            "tree_sha256": BASE.tree_digest(root),
            "checksum_index": BASE.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V8.V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(
        PREVIOUS_CHECKPOINT
    )
    V8.verify(PREVIOUS_CHECKPOINT)
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
    paths = V8.research_source_paths()
    paths["cross_runtime_evidence_boundary"] = (
        REPO_ROOT
        / "docs/research/step_7g13_cross_runtime_evidence_boundary.md"
    )
    return paths


def cross_runtime_gate_summary() -> dict[str, Any]:
    summary = BASE.load_json(REPO_ROOT / CROSS_PACK / "summary.json")
    state = summary["state"]
    return {
        "status": summary["status"],
        "encrypted_execution_allowed": summary[
            "encrypted_execution_allowed"
        ],
        "cross_runtime_numerical_equivalence": summary[
            "cross_runtime_numerical_equivalence"
        ],
        "selected_native_scale": state["selected_native_candidate"][
            "input_scale_bits"
        ],
        "selected_native_exact_qp_captured": state[
            "selected_native_candidate"
        ]["exact_qp_captured_in_selected_run"],
        "lattigo_implemented_scale": state["lattigo_adapter"][
            "implemented_input_scale_bits"
        ],
        "matched_population_available": state["pairing"][
            "matched_row_key_population_available"
        ],
        "blockers": state["blockers"],
        "policy_modifications": summary["policy_modifications"],
        "encrypted_executions_added": summary[
            "encrypted_executions_added"
        ],
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
        "Paper admission remains manual. The scoped native EVA scale-30 "
        "candidate passed development validation and untouched audit, but the "
        "selected run did not bind exact Q/P, the Lattigo adapter and provider "
        "gate bind the scale-20 schedule, and no matched row/key population or "
        "runtime-specific native security analysis exists. Cross-runtime "
        "equivalence and general external-autotuner behavior remain "
        "NOT_EVALUATED; release tagging and external archival remain open."
    )
    claims = {
        "schema_version": "flipguard_claim_state_registry_v9",
        "paper_claim_allowed": False,
        "block_reason": block_reason,
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        BASE.canonical_json(claims)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v9",
        "evidence_id": "research_completion_checkpoint_v9",
        "classification": (
            "POST_CONFIRMATORY_CROSS_RUNTIME_READINESS_CHECKPOINT"
        ),
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": block_reason,
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds a fail-closed cross-runtime replay readiness pack. It "
                "records exact identity, adapter, population, and security "
                "blockers without adding encrypted execution or modifying "
                "either frozen policy."
            ),
        },
        "policies": {
            "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
            "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "external_compiler_boundary": V8.BASE.load_json(
            PREVIOUS_CHECKPOINT / "manifest.json"
        )["external_compiler_boundary"],
        "cross_runtime_replay_readiness": cross_runtime_gate_summary(),
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
            "independent external autotuner candidate with locked audit",
            "cross-runtime exact materialization and schedule adapter",
            "cross-runtime matched numerical study",
            "runtime-specific security estimation",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V9

This non-overwriting checkpoint binds checkpoint V8 plus the static EVA
cross-runtime replay readiness pack. The new pack does not add encrypted
execution. It prevents a matched Lattigo-SEAL claim until exact selected-run
Q/P, a scale-30 digest-bound adapter, matched rows/keys, and separate security
interpretations are available.

The scoped native EVA validation and audit result remains preserved.
`cross_runtime_numerical_equivalence=NOT_EVALUATED`.
`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> None:
    BASE.verify_checksums(output)
    V8.V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v9",
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
        manifest["cross_runtime_replay_readiness"],
        cross_runtime_gate_summary(),
        "cross-runtime readiness summary",
    )
    gate = manifest["cross_runtime_replay_readiness"]
    BASE.require_equal(
        gate["encrypted_execution_allowed"],
        False,
        "cross-runtime execution gate",
    )
    BASE.require_equal(
        gate["cross_runtime_numerical_equivalence"],
        "NOT_EVALUATED",
        "cross-runtime claim state",
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
        prefix="flipguard-research-checkpoint-v9-", dir="/tmp"
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
            "research_completion_checkpoint_v9=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v9=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
