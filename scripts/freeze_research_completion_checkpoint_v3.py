#!/usr/bin/env python3
"""Freeze and verify the estimator- and replay-aware research checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V2_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v2.py"
)
V2_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v2_for_v3",
    V2_MODULE_PATH,
)
assert V2_SPEC is not None and V2_SPEC.loader is not None
V2 = importlib.util.module_from_spec(V2_SPEC)
V2_SPEC.loader.exec_module(V2)

OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v3"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v2"
)
EXACT_ESTIMATOR = Path(
    "docs/evidence/exact_security_estimator_v1"
)
INDEPENDENT_REPLAY = Path(
    "docs/evidence/independent_machine_replay_v1"
)

PACKS = dict(V2.PACKS)
PACKS["exact_security_estimator"] = EXACT_ESTIMATOR
PACKS["independent_machine_replay"] = INDEPENDENT_REPLAY

CLAIM_STATES = dict(V2.CLAIM_STATES)
CLAIM_STATES.update(
    {
        "exact_modulus_security_sensitivity": "PARTIALLY_SUPPORTED",
        "portable_checkpoint_replay": "SUPPORTED",
        "external_source_replay": "NOT_EVALUATED",
    }
)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V2.load_manifests()
    for name, relative in (
        ("exact_security_estimator", EXACT_ESTIMATOR),
        ("independent_machine_replay", INDEPENDENT_REPLAY),
    ):
        manifest_path = REPO_ROOT / relative / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"missing required evidence pack: {relative}")
        manifests[name] = V2.V1.load_json(manifest_path)
    return manifests


def validate_exact_estimator(manifest: dict[str, Any]) -> None:
    V2.V1.require_equal(
        manifest["schema_version"],
        "flipguard_exact_security_estimator_evidence_v1",
        "exact estimator schema",
    )
    V2.V1.require_equal(
        manifest["security_policy_modified"],
        False,
        "exact estimator policy modification",
    )
    V2.V1.require_equal(
        manifest["security_claim"],
        "PARTIALLY_SUPPORTED",
        "exact estimator security claim",
    )
    V2.V1.require_equal(
        manifest["status"],
        "SUPPORTED_WITH_MODEL_CAVEATS",
        "exact estimator status",
    )
    V2.V1.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "exact estimator paper gate",
    )

    summary = V2.V1.load_json(
        REPO_ROOT / EXACT_ESTIMATOR / "summary.json"
    )
    V2.V1.require_equal(
        summary["status"],
        "SUPPORTED_WITH_MODEL_CAVEATS",
        "exact estimator summary status",
    )
    V2.V1.require_equal(
        summary["objects_per_model"],
        18,
        "exact estimator objects per model",
    )
    V2.V1.require_equal(
        len(summary["models"]),
        2,
        "exact estimator model count",
    )
    V2.V1.require_equal(
        summary["exact_distribution_claim_allowed"],
        False,
        "exact distribution claim gate",
    )
    for model in summary["models"]:
        V2.V1.require_equal(
            model["objects"],
            18,
            f"{model['model_id']} object count",
        )
        V2.V1.require_equal(
            model["attack_failures"],
            0,
            f"{model['model_id']} attack failures",
        )
        V2.V1.require_equal(
            model["static_admitted_estimator_failures"],
            0,
            f"{model['model_id']} admitted failures",
        )
        V2.V1.require_equal(
            model["static_admitted_estimator_incomplete"],
            0,
            f"{model['model_id']} admitted incomplete",
        )
        V2.V1.require_equal(
            model["static_admission_concordance"],
            "SUPPORTED_FOR_STATIC_ADMITTED_OBJECTS",
            f"{model['model_id']} static concordance",
        )


def validate_independent_replay(manifest: dict[str, Any]) -> None:
    V2.V1.require_equal(
        manifest["schema_version"],
        "flipguard_independent_machine_replay_evidence_v1",
        "independent replay schema",
    )
    V2.V1.require_equal(
        manifest["status"],
        "SUPPORTED_WITH_DECLARED_EXTERNAL_INPUT_BOUNDARY",
        "independent replay status",
    )
    V2.V1.require_equal(
        manifest["workflow_conclusion"],
        "success",
        "independent replay workflow conclusion",
    )
    V2.V1.require_equal(
        manifest["policies"],
        {
            "direct_policy_v2": V2.V1.DIRECT_POLICY_DIGEST,
            "policy_retuning": 0,
            "security_policy_v2": V2.V1.SECURITY_POLICY_DIGEST,
        },
        "independent replay policies",
    )
    V2.V1.require_equal(
        manifest["encrypted_execution"],
        {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "independent replay encrypted accounting",
    )
    scope = manifest["source_replay_scope"]
    V2.V1.require_equal(
        scope["committed_checkpoint_replay_independent_of_raw_results"],
        True,
        "committed checkpoint replay",
    )
    V2.V1.require_equal(
        scope["status"],
        "NOT_EVALUATED_ON_CLEAN_CLONE",
        "external source replay status",
    )
    V2.V1.require_equal(
        len(scope["missing"]),
        8,
        "independent replay missing inputs",
    )
    V2.V1.require_equal(
        len(scope["portable_go_test_exclusions"]),
        5,
        "independent replay Go exclusions",
    )
    V2.V1.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "independent replay paper gate",
    )

    summary = V2.V1.load_json(
        REPO_ROOT / INDEPENDENT_REPLAY / "summary.json"
    )
    V2.V1.require_equal(
        summary["checks_passed"],
        11,
        "independent replay passed checks",
    )
    V2.V1.require_equal(
        summary["checks_failed"],
        0,
        "independent replay failed checks",
    )
    V2.V1.require_equal(
        summary["external_source_replay"],
        "NOT_EVALUATED_ON_CLEAN_CLONE",
        "independent replay external-source boundary",
    )


def validate_semantics(
    manifests: dict[str, dict[str, Any]],
) -> None:
    V2.validate_semantics(
        {name: manifests[name] for name in V2.PACKS}
    )
    validate_exact_estimator(manifests["exact_security_estimator"])
    validate_independent_replay(manifests["independent_machine_replay"])
    for claim, state in CLAIM_STATES.items():
        if state not in V2.V1.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")
    V2.V1.require_equal(
        CLAIM_STATES["security"],
        "PARTIALLY_SUPPORTED",
        "security claim remains qualified",
    )
    V2.V1.require_equal(
        CLAIM_STATES["artifact_reproducibility"],
        "PARTIALLY_SUPPORTED",
        "artifact reproducibility remains qualified",
    )
    V2.V1.require_equal(
        CLAIM_STATES["external_source_replay"],
        "NOT_EVALUATED",
        "external source replay claim",
    )


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": V2.V1.sha256_path(root / "manifest.json"),
            "tree_sha256": V2.V1.tree_digest(root),
            "checksum_index": V2.V1.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V2.validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V2.verify(PREVIOUS_CHECKPOINT)
    manifest = V2.V1.load_json(PREVIOUS_CHECKPOINT / "manifest.json")
    return {
        "path": PREVIOUS_CHECKPOINT.relative_to(REPO_ROOT).as_posix(),
        "schema_version": manifest["schema_version"],
        "manifest_sha256": V2.V1.sha256_path(
            PREVIOUS_CHECKPOINT / "manifest.json"
        ),
        "tree_sha256": V2.V1.tree_digest(PREVIOUS_CHECKPOINT),
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
        "schema_version": "flipguard_claim_state_registry_v3",
        "paper_claim_allowed": False,
        "block_reason": (
            "Paper admission remains manual. Exact-modulus estimates retain "
            "distribution-model caveats, and external raw-input replay, "
            "release tagging, and external archival remain incomplete."
        ),
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        V2.V1.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v3",
        "evidence_id": "research_completion_checkpoint_v3",
        "classification": "POST_CONFIRMATORY_RESEARCH_CHECKPOINT",
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": claim_state_document["block_reason"],
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds complete exact-modulus estimator sensitivity and "
                "independent clean-runner replay without modifying V2."
            ),
        },
        "policies": {
            "direct_policy_v2": V2.V1.DIRECT_POLICY_DIGEST,
            "security_policy_v2": V2.V1.SECURITY_POLICY_DIGEST,
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
            "external_raw_source_replay": "NOT_EVALUATED",
            "missing_external_inputs": 8,
            "portable_go_test_exclusions": 5,
            "status": "PARTIALLY_SUPPORTED",
        },
        "claim_state_registry": {
            "path": "claim_states.json",
            "sha256": V2.V1.sha256_path(output / "claim_states.json"),
        },
        "claim_matrix": {
            "path": claim_matrix.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                claim_matrix_digest
                or V2.V1.sha256_path(claim_matrix)
            ),
        },
        "novelty_audit": {
            "path": novelty_audit.relative_to(REPO_ROOT).as_posix(),
            "sha256": (
                novelty_audit_digest
                or V2.V1.sha256_path(novelty_audit)
            ),
        },
        "packs": pack_records,
        "evidence_tree_hygiene": {
            "generated_python_artifacts": 0,
            "policy": "REJECT_PYCACHE_PYC_PYO",
        },
        "remaining_manual_gates": [
            "paper claim admission",
            "external raw-input source replay",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(V2.V1.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V3

This non-overwriting checkpoint binds the 17 packs in checkpoint V2, the
complete two-model exact-modulus security sensitivity pack, the independent
clean-runner replay pack, and the immutable V2 lineage record. It performs no
CKKS execution and promotes no paper claim.

Exact-modulus estimates support Security V2 admission for the evaluated
objects, subject to the declared estimator/distribution boundary. Portable
checkpoint replay is supported; raw source replay is not evaluated because
the ignored external inputs are absent from the clean clone.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    V2.V1.write_checksums(output)


def verify(output: Path) -> None:
    V2.V1.verify_checksums(output)
    V2.validate_evidence_tree_hygiene(output)
    manifest = V2.V1.load_json(output / "manifest.json")
    V2.V1.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v3",
        "checkpoint schema",
    )
    V2.V1.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "checkpoint paper gate",
    )
    manifests = load_manifests()
    validate_semantics(manifests)
    V2.V1.require_equal(
        build_pack_records(manifests),
        manifest["packs"],
        "linked evidence records",
    )
    V2.V1.require_equal(
        previous_checkpoint_record(),
        manifest["lineage"]["previous_checkpoint"],
        "checkpoint lineage",
    )
    V2.V1.require_equal(
        manifest["security_assurance_boundary"]["attack_failures"],
        0,
        "checkpoint estimator attack failures",
    )
    V2.V1.require_equal(
        manifest["artifact_replay_boundary"][
            "external_raw_source_replay"
        ],
        "NOT_EVALUATED",
        "checkpoint external source replay",
    )
    claim_matrix = REPO_ROOT / manifest["claim_matrix"]["path"]
    V2.V1.verify_bound_source(
        claim_matrix,
        manifest["claim_matrix"]["sha256"],
        manifest["freezer_commit"],
        "claim matrix binding",
    )
    novelty_audit = REPO_ROOT / manifest["novelty_audit"]["path"]
    V2.V1.verify_bound_source(
        novelty_audit,
        manifest["novelty_audit"]["sha256"],
        manifest["freezer_commit"],
        "novelty audit binding",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-research-checkpoint-v3-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["freezer_commit"],
            claim_matrix_digest=manifest["claim_matrix"]["sha256"],
            novelty_audit_digest=manifest["novelty_audit"]["sha256"],
        )
        V2.V1.compare_trees(output, rebuilt)


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
            "research_completion_checkpoint_v3=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v3=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
