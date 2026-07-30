#!/usr/bin/env python3
"""Freeze and verify the decision-activation-aware research checkpoint."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V1_MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v1.py"
)
V1_SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v1_for_v2",
    V1_MODULE_PATH,
)
assert V1_SPEC is not None and V1_SPEC.loader is not None
V1 = importlib.util.module_from_spec(V1_SPEC)
V1_SPEC.loader.exec_module(V1)

OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v2"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v1"
)
DECISION_ACTIVATION = Path(
    "docs/evidence/decision_contract_activation_control_v1"
)

PACKS = dict(V1.PACKS)
PACKS["decision_contract_activation"] = DECISION_ACTIVATION

CLAIM_STATES = dict(V1.CLAIM_STATES)
CLAIM_STATES["finite_domain_decision_contract_activation"] = "SUPPORTED"

EXPECTED_ACTIVATION_ACCOUNTING = {
    "arms": 4,
    "audit_encrypted_sample_evaluations": 384,
    "audit_key_runs": 12,
    "locked_audit_pass": 4,
    "selection_encrypted_sample_evaluations": 1344,
    "selection_key_runs": 42,
    "selection_repairs": 10,
    "selection_trials": 14,
}


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V1.load_manifests()
    activation_path = REPO_ROOT / DECISION_ACTIVATION / "manifest.json"
    if not activation_path.is_file():
        raise ValueError(
            f"missing required evidence pack: {DECISION_ACTIVATION}"
        )
    manifests["decision_contract_activation"] = V1.load_json(
        activation_path
    )
    return manifests


def validate_evidence_tree_hygiene(root: Path) -> None:
    prohibited = []
    for path in root.rglob("*"):
        if path.name == "__pycache__":
            prohibited.append(path)
        elif path.is_file() and path.suffix in {".pyc", ".pyo"}:
            prohibited.append(path)
    if prohibited:
        rendered = ", ".join(
            path.relative_to(root).as_posix()
            for path in sorted(prohibited)
        )
        raise ValueError(f"generated Python artifacts in evidence tree: {rendered}")


def validate_activation(manifest: dict[str, Any]) -> None:
    V1.require_equal(
        manifest["schema_version"],
        "flipguard_decision_contract_activation_evidence_v1",
        "activation schema",
    )
    V1.require_equal(
        manifest["classification"],
        "FINITE_DOMAIN_DEVELOPMENT_CONTROL",
        "activation classification",
    )
    V1.require_equal(
        manifest["direct_policy_digest"],
        V1.DIRECT_POLICY_DIGEST,
        "activation direct policy",
    )
    V1.require_equal(
        manifest["security_policy_digest"],
        V1.SECURITY_POLICY_DIGEST,
        "activation security policy",
    )
    V1.require_equal(
        manifest["accounting"],
        EXPECTED_ACTIVATION_ACCOUNTING,
        "activation accounting",
    )
    V1.require_equal(
        manifest["claims"],
        {
            "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
            "finite_domain_encrypted_control": "SUPPORTED",
            "natural_data_decision_contract_synthesis_effect": "BLOCKED",
            "paper_claim_allowed": False,
        },
        "activation claim boundary",
    )
    V1.require_equal(
        manifest["frozen_evidence_modified"],
        False,
        "activation frozen-evidence flag",
    )
    V1.require_equal(
        len(manifest["recoveries"]),
        2,
        "activation recovery count",
    )
    recovery_codes = {
        recovery["reason_code"] for recovery in manifest["recoveries"]
    }
    V1.require_equal(
        recovery_codes,
        {
            "NON_NUMERIC_ROW_ID",
            "INCOMPLETE_CANONICAL_CSV_SCHEMA",
        },
        "activation recovery reasons",
    )
    for index, recovery in enumerate(manifest["recoveries"], start=1):
        V1.require_equal(
            recovery["classification"],
            "SUPERSEDED_IMPLEMENTATION_RECOVERY",
            f"activation recovery {index} classification",
        )
        V1.require_equal(
            recovery["encrypted_key_runs"],
            0,
            f"activation recovery {index} key runs",
        )
        V1.require_equal(
            recovery["encrypted_rerun_justified"],
            True,
            f"activation recovery {index} rerun justification",
        )

    summary = V1.load_json(
        REPO_ROOT / DECISION_ACTIVATION / "summary.json"
    )
    V1.require_equal(summary["status"], "SUPPORTED", "activation status")
    V1.require_equal(
        summary["natural_data_decision_contract_synthesis_effect"],
        "BLOCKED",
        "natural-data effect",
    )
    V1.require_equal(
        summary["finite_domain_decision_contract_synthesis_effect"],
        "SUPPORTED",
        "finite-domain effect",
    )
    V1.require_equal(
        summary["finite_domain_encrypted_control"],
        "SUPPORTED",
        "encrypted activation control",
    )
    V1.require_equal(
        summary["initial_scales"],
        {
            "narrow_decision_contract": 21,
            "narrow_graph_fixed": 20,
            "wide_decision_contract": 20,
            "wide_graph_fixed": 20,
        },
        "activation initial scales",
    )
    V1.require_equal(
        summary["selected_scales"],
        {
            "narrow_decision_contract": 33,
            "narrow_graph_fixed": 32,
            "wide_decision_contract": 28,
            "wide_graph_fixed": 28,
        },
        "activation selected scales",
    )
    for key in (
        "locked_audit_flips",
        "locked_audit_retuning",
        "locked_audit_violations",
        "policy_modifications",
    ):
        V1.require_equal(summary[key], 0, f"activation {key}")
    V1.require_equal(
        summary["paper_claim_allowed"],
        False,
        "activation paper gate",
    )


def validate_semantics(
    manifests: dict[str, dict[str, Any]],
) -> None:
    V1.validate_semantics(
        {name: manifests[name] for name in V1.PACKS}
    )
    validate_activation(manifests["decision_contract_activation"])
    for claim, state in CLAIM_STATES.items():
        if state not in V1.ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")
    V1.require_equal(
        CLAIM_STATES["decision_contract_candidate_synthesis_effect"],
        "BLOCKED",
        "natural-data decision-contract claim",
    )
    V1.require_equal(
        CLAIM_STATES["finite_domain_decision_contract_activation"],
        "SUPPORTED",
        "finite-domain activation claim",
    )


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in PACKS.items():
        root = REPO_ROOT / relative
        validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": V1.sha256_path(root / "manifest.json"),
            "tree_sha256": V1.tree_digest(root),
            "checksum_index": V1.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    validate_evidence_tree_hygiene(PREVIOUS_CHECKPOINT)
    V1.verify(PREVIOUS_CHECKPOINT)
    manifest = V1.load_json(PREVIOUS_CHECKPOINT / "manifest.json")
    return {
        "path": PREVIOUS_CHECKPOINT.relative_to(REPO_ROOT).as_posix(),
        "schema_version": manifest["schema_version"],
        "manifest_sha256": V1.sha256_path(
            PREVIOUS_CHECKPOINT / "manifest.json"
        ),
        "tree_sha256": V1.tree_digest(PREVIOUS_CHECKPOINT),
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
        "schema_version": "flipguard_claim_state_registry_v2",
        "paper_claim_allowed": False,
        "block_reason": (
            "Paper admission remains manual; exact lattice estimation, "
            "release tagging, external archival, and independent-machine "
            "replay remain incomplete."
        ),
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        V1.canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v2",
        "evidence_id": "research_completion_checkpoint_v2",
        "classification": "POST_CONFIRMATORY_RESEARCH_CHECKPOINT",
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": claim_state_document["block_reason"],
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds the finite-domain decision-contract activation "
                "control without modifying checkpoint V1."
            ),
        },
        "policies": {
            "direct_policy_v2": V1.DIRECT_POLICY_DIGEST,
            "security_policy_v2": V1.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "formal_population": {
            "development_seed": 0,
            "confirmatory_seeds": [1, 2, 3, 4],
            "primary_dataset_model_workloads": 10,
            "deterministic_partitions": 5,
            "workload_partition_instances": 50,
            "independent_training_seed_extension_instances": 9,
            "decision_activation_control_role": (
                "FINITE_DOMAIN_DEVELOPMENT_CONTROL"
            ),
            "decision_activation_control_arms": 4,
        },
        "decision_contract_claim_boundary": {
            "natural_data_candidate_synthesis_effect": "BLOCKED",
            "finite_domain_activation": "SUPPORTED",
            "promotion_from_control_to_natural_data": "PROHIBITED",
        },
        "decision_activation_accounting": EXPECTED_ACTIVATION_ACCOUNTING,
        "research_negatives_preserved": {
            "structural_locked_audit": (
                "24/25 PASS; one numerical REJECT with zero flips and "
                "one budget violation"
            ),
            "natural_decision_contract_synthesis_effect": (
                "BLOCKED in 10/10 seed-0 natural workloads"
            ),
            "instantiated_analytical_certificates": "0/50",
        },
        "recovery_history_preserved": {
            "decision_activation_pre_encryption_recoveries": 2,
            "encrypted_key_runs_in_recoveries": 0,
            "classification": "SUPERSEDED_IMPLEMENTATION_RECOVERY",
        },
        "scope": {
            "supported": (
                "declared scalar-replicated tabular, polynomial/MLP, "
                "Sobel, Harris, and CNN-lite graph adapters"
            ),
            "not_supported": [
                "arbitrary CKKS graphs",
                "packed full-image CNN execution",
                "universal model support",
                "global optimum",
                "domain-wide analytical decision preservation",
                "natural-data decision-margin-driven configuration change",
            ],
        },
        "claim_state_registry": {
            "path": "claim_states.json",
            "sha256": V1.sha256_path(output / "claim_states.json"),
        },
        "claim_matrix": {
            "path": claim_matrix.relative_to(REPO_ROOT).as_posix(),
            "sha256": claim_matrix_digest or V1.sha256_path(claim_matrix),
        },
        "novelty_audit": {
            "path": novelty_audit.relative_to(REPO_ROOT).as_posix(),
            "sha256": novelty_audit_digest or V1.sha256_path(novelty_audit),
        },
        "packs": pack_records,
        "evidence_tree_hygiene": {
            "generated_python_artifacts": 0,
            "policy": "REJECT_PYCACHE_PYC_PYO",
        },
        "remaining_manual_gates": [
            "paper claim admission",
            "exact lattice-estimator execution",
            "release tag",
            "external archive",
            "independent-machine deterministic replay",
        ],
    }
    (output / "manifest.json").write_bytes(V1.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V2

This non-overwriting checkpoint binds the 16 packs in checkpoint V1, the
finite-domain decision-contract activation control, and the immutable V1
lineage record. It performs no CKKS execution and promotes no paper claim.

The activation control supports a scoped finite-domain mechanism claim. The
natural-data candidate-synthesis effect remains BLOCKED, and the control is
not used to reinterpret the primary or confirmatory populations.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    V1.write_checksums(output)


def verify(output: Path) -> None:
    V1.verify_checksums(output)
    validate_evidence_tree_hygiene(output)
    manifest = V1.load_json(output / "manifest.json")
    V1.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v2",
        "checkpoint schema",
    )
    V1.require_equal(
        manifest["paper_claim_allowed"],
        False,
        "checkpoint paper gate",
    )
    manifests = load_manifests()
    validate_semantics(manifests)
    V1.require_equal(
        build_pack_records(manifests),
        manifest["packs"],
        "linked evidence records",
    )
    V1.require_equal(
        previous_checkpoint_record(),
        manifest["lineage"]["previous_checkpoint"],
        "checkpoint lineage",
    )
    V1.require_equal(
        manifest["decision_contract_claim_boundary"],
        {
            "natural_data_candidate_synthesis_effect": "BLOCKED",
            "finite_domain_activation": "SUPPORTED",
            "promotion_from_control_to_natural_data": "PROHIBITED",
        },
        "decision-contract claim boundary",
    )
    V1.require_equal(
        manifest["decision_activation_accounting"],
        EXPECTED_ACTIVATION_ACCOUNTING,
        "decision activation accounting",
    )
    claim_matrix = REPO_ROOT / manifest["claim_matrix"]["path"]
    V1.verify_bound_source(
        claim_matrix,
        manifest["claim_matrix"]["sha256"],
        manifest["freezer_commit"],
        "claim matrix binding",
    )
    novelty_audit = REPO_ROOT / manifest["novelty_audit"]["path"]
    V1.verify_bound_source(
        novelty_audit,
        manifest["novelty_audit"]["sha256"],
        manifest["freezer_commit"],
        "novelty audit binding",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-research-checkpoint-v2-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(
            rebuilt,
            manifest["freezer_commit"],
            claim_matrix_digest=manifest["claim_matrix"]["sha256"],
            novelty_audit_digest=manifest["novelty_audit"]["sha256"],
        )
        V1.compare_trees(output, rebuilt)


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
            "research_completion_checkpoint_v2=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v2=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
