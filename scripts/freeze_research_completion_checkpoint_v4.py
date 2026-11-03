#!/usr/bin/env python3
"""Freeze and verify the external-source-aware research checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V3_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v3.py"
)
V3_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v3_for_v4",
    V3_MODULE_PATH,
)
assert V3_SPEC is not None and V3_SPEC.loader is not None
V3 = importlib.util.module_from_spec(V3_SPEC)
V3_SPEC.loader.exec_module(V3)

OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v4"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v3"
)
EXTERNAL_SOURCE_REPLAY = Path(
    "docs/evidence/external_source_replay_v1"
)

PACKS = dict(V3.PACKS)
PACKS["external_source_replay"] = EXTERNAL_SOURCE_REPLAY

CLAIM_STATES = dict(V3.CLAIM_STATES)
CLAIM_STATES["external_source_replay"] = "PARTIALLY_SUPPORTED"


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V3.load_manifests()
    manifest_path = REPO_ROOT / EXTERNAL_SOURCE_REPLAY / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"missing required evidence pack: {EXTERNAL_SOURCE_REPLAY}"
        )
    manifests["external_source_replay"] = V3.V2.V1.load_json(manifest_path)
    return manifests


def validate_external_source_replay(manifest: dict[str, Any]) -> None:
    require_equal = V3.V2.V1.require_equal
    require_equal(
        manifest["schema_version"],
        "flipguard_external_source_replay_evidence_v1",
        "external source replay schema",
    )
    require_equal(
        manifest["status"],
        "SUPPORTED_WITH_SCOPE_LIMIT",
        "external source replay status",
    )
    require_equal(
        manifest["workflow_conclusion"],
        "success",
        "external source workflow conclusion",
    )
    require_equal(
        manifest["policies"],
        {
            "direct_policy_v2": V3.V2.V1.DIRECT_POLICY_DIGEST,
            "policy_retuning": 0,
            "security_policy_v2": V3.V2.V1.SECURITY_POLICY_DIGEST,
        },
        "external source replay policies",
    )
    require_equal(
        manifest["encrypted_execution"],
        {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "external source replay encrypted accounting",
    )
    require_equal(
        manifest["paper_claim_allowed"],
        False,
        "external source replay paper gate",
    )

    summary = V3.V2.V1.load_json(
        REPO_ROOT / EXTERNAL_SOURCE_REPLAY / "summary.json"
    )
    require_equal(
        summary["official_source_byte_replay"],
        "SUPPORTED",
        "official source byte replay",
    )
    require_equal(
        summary["deterministic_exporter_replay"],
        "SUPPORTED",
        "external deterministic exporter replay",
    )
    require_equal(
        summary["static_graph_contract_replay"],
        "SUPPORTED",
        "external static graph replay",
    )
    require_equal(
        summary["encrypted_execution_ledger_replay"],
        "NOT_EVALUATED",
        "external encrypted-ledger replay",
    )
    require_equal(summary["source_datasets"], 2, "source dataset count")
    require_equal(
        summary["deterministic_exporters"],
        3,
        "deterministic exporter count",
    )
    require_equal(
        summary["static_graph_contracts"],
        3,
        "static graph contract count",
    )
    require_equal(summary["checks_failed"], 0, "external failed checks")


def validate_semantics(
    manifests: dict[str, dict[str, Any]],
) -> None:
    V3.validate_semantics(
        {name: manifests[name] for name in V3.PACKS}
    )
    validate_external_source_replay(manifests["external_source_replay"])
    for claim, state in CLAIM_STATES.items():
        if state not in V3.V2.V1.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")
    V3.V2.V1.require_equal(
        CLAIM_STATES["external_source_replay"],
        "PARTIALLY_SUPPORTED",
        "external source replay remains scope-limited",
    )
    V3.V2.V1.require_equal(
        CLAIM_STATES["artifact_reproducibility"],
        "PARTIALLY_SUPPORTED",
        "artifact reproducibility remains qualified",
    )
    V3.V2.V1.require_equal(
        CLAIM_STATES["security"],
        "PARTIALLY_SUPPORTED",
        "security remains qualified",
    )


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": V3.V2.V1.sha256_path(
                root / "manifest.json"
            ),
            "tree_sha256": V3.V2.V1.tree_digest(root),
            "checksum_index": V3.V2.V1.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V3.V2.validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V3.verify(PREVIOUS_CHECKPOINT)
    manifest = V3.V2.V1.load_json(PREVIOUS_CHECKPOINT / "manifest.json")
    return {
        "path": PREVIOUS_CHECKPOINT.relative_to(REPO_ROOT).as_posix(),
        "schema_version": manifest["schema_version"],
        "manifest_sha256": V3.V2.V1.sha256_path(
            PREVIOUS_CHECKPOINT / "manifest.json"
        ),
        "tree_sha256": V3.V2.V1.tree_digest(PREVIOUS_CHECKPOINT),
        "verification": "VERIFIED_WITH_HISTORICAL_SOURCE_BINDINGS",
        "status": "IMMUTABLE_PREDECESSOR",
    }


def freeze(
    output: Path,
    freezer_commit: str,
    *,
    claim_matrix_digest: str | None = None,
    novelty_audit_digest: str | None = None,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite research checkpoint: {output}"
        )
    manifests = load_manifests()
    validate_semantics(manifests)
    pack_records = build_pack_records(manifests)
    predecessor = previous_checkpoint_record()
    claim_matrix = (
        REPO_ROOT / "docs/research/flipguard_v2_claim_evidence_matrix.md"
    )
    novelty_audit = (
        REPO_ROOT
        / "docs/research/step_7f1_primary_source_novelty_audit.md"
    )

    output.mkdir(parents=True)
    claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v4",
        "paper_claim_allowed": False,
        "block_reason": (
            "Paper admission remains manual. Exact-modulus estimates retain "
            "distribution-model caveats; external replay covers official "
            "source bytes, exporters, and static graph contracts but not "
            "ignored encrypted execution ledgers. Release tagging and "
            "external archival also remain incomplete."
        ),
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        V3.V2.V1.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v4",
        "evidence_id": "research_completion_checkpoint_v4",
        "classification": "POST_CONFIRMATORY_RESEARCH_CHECKPOINT",
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": claim_state_document["block_reason"],
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds clean-runner replay from byte-pinned official MNIST "
                "and BSDS500 inputs without modifying checkpoint V3."
            ),
        },
        "policies": {
            "direct_policy_v2": V3.V2.V1.DIRECT_POLICY_DIGEST,
            "security_policy_v2": V3.V2.V1.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "security_assurance_boundary": {
            "static_v2_admitted_object_counterexamples": 0,
            "estimator_models": 2,
            "exact_q_qp_objects_per_model": 18,
            "attack_failures": 0,
            "status": "PARTIALLY_SUPPORTED",
            "caveat": (
                "Xs is exact per coefficient; Xe sigma matches but its "
                "explicit Lattigo truncation bound is not modeled."
            ),
        },
        "artifact_replay_boundary": {
            "portable_checkpoint_replay": "SUPPORTED",
            "official_source_byte_replay": "SUPPORTED",
            "deterministic_exporter_replay": "SUPPORTED",
            "static_graph_contract_replay": "SUPPORTED",
            "encrypted_execution_ledger_replay": "NOT_EVALUATED",
            "source_datasets": 2,
            "deterministic_exporters": 3,
            "static_graph_contracts": 3,
            "status": "PARTIALLY_SUPPORTED",
        },
        "claim_state_registry": {
            "path": "claim_states.json",
            "sha256": V3.V2.V1.sha256_path(
                output / "claim_states.json"
            ),
        },
        "claim_matrix": {
            "path": claim_matrix.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                claim_matrix_digest
                or V3.V2.V1.sha256_path(claim_matrix)
            ),
        },
        "novelty_audit": {
            "path": novelty_audit.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                novelty_audit_digest
                or V3.V2.V1.sha256_path(novelty_audit)
            ),
        },
        "packs": pack_records,
        "evidence_tree_hygiene": {
            "generated_python_artifacts": 0,
            "policy": "REJECT_PYCACHE_PYC_PYO",
        },
        "remaining_manual_gates": [
            "paper claim admission",
            "ignored encrypted execution-ledger replay",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(
        V3.V2.V1.canonical_json(manifest)
    )
    readme = """# FlipGuard Research Completion Checkpoint V4

This non-overwriting checkpoint binds the 19 packs in checkpoint V3 and the
external source replay pack. It performs no CKKS execution, changes no frozen
policy, and promotes no paper claim.

Byte-pinned official MNIST and BSDS500 inputs, three deterministic exporters,
and three static graph contracts replay successfully on a clean GitHub runner.
Ignored encrypted execution ledgers were not replayed, so external source and
artifact reproducibility claims remain scope-limited.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    V3.V2.V1.write_checksums(output)


def verify(output: Path) -> None:
    V3.V2.V1.verify_checksums(output)
    V3.V2.validate_evidence_tree_hygiene(output)
    manifest = V3.V2.V1.load_json(output / "manifest.json")
    V3.V2.V1.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v4",
        "checkpoint schema",
    )
    V3.V2.V1.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "checkpoint paper gate",
    )
    manifests = load_manifests()
    validate_semantics(manifests)
    V3.V2.V1.require_equal(
        build_pack_records(manifests),
        manifest["packs"],
        "linked evidence records",
    )
    V3.V2.V1.require_equal(
        previous_checkpoint_record(),
        manifest["lineage"]["previous_checkpoint"],
        "checkpoint lineage",
    )
    V3.V2.V1.require_equal(
        manifest["artifact_replay_boundary"][
            "official_source_byte_replay"
        ],
        "SUPPORTED",
        "checkpoint official-source replay",
    )
    V3.V2.V1.require_equal(
        manifest["artifact_replay_boundary"][
            "encrypted_execution_ledger_replay"
        ],
        "NOT_EVALUATED",
        "checkpoint encrypted-ledger boundary",
    )
    claim_matrix = REPO_ROOT / manifest["claim_matrix"]["path"]
    V3.V2.V1.verify_bound_source(
        claim_matrix,
        manifest["claim_matrix"]["sha256"],
        manifest["freezer_commit"],
        "claim matrix binding",
    )
    novelty_audit = REPO_ROOT / manifest["novelty_audit"]["path"]
    V3.V2.V1.verify_bound_source(
        novelty_audit,
        manifest["novelty_audit"]["sha256"],
        manifest["freezer_commit"],
        "novelty audit binding",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-research-checkpoint-v4-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["freezer_commit"],
            claim_matrix_digest=manifest["claim_matrix"]["sha256"],
            novelty_audit_digest=manifest["novelty_audit"]["sha256"],
        )
        V3.V2.V1.compare_trees(output, rebuilt)


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
            "research_completion_checkpoint_v4=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v4=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
