#!/usr/bin/env python3
"""Freeze and verify the EVA scale-sensitivity-aware checkpoint V8."""

from __future__ import annotations

import argparse
import importlib.util
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V7_PATH = REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v7.py"
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v7_for_v8", V7_PATH
)
assert SPEC is not None and SPEC.loader is not None
V7 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V7)

BASE = V7.BASE
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v8"
)
PREVIOUS_CHECKPOINT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v7"
)
EVA_SCALE = Path("docs/evidence/eva_native_scale_sensitivity_v1")

PACKS = dict(V7.PACKS)
PACKS["eva_native_scale_sensitivity"] = EVA_SCALE

CLAIM_STATES = dict(V7.CLAIM_STATES)
CLAIM_STATES.update(
    {
        "native_eva_seal_decision_certification": (
            "PARTIALLY_SUPPORTED"
        ),
        "native_eva_seal_locked_audit": "PARTIALLY_SUPPORTED",
        "encrypted_external_candidate_certification": (
            "PARTIALLY_SUPPORTED"
        ),
        "external_precision_sensitivity": "PARTIALLY_SUPPORTED",
        "original_scale20_candidate_decision_certification": "BLOCKED",
        "cross_runtime_numerical_equivalence": "NOT_EVALUATED",
        "general_external_compiler_interoperability": (
            "PARTIALLY_SUPPORTED"
        ),
        "general_external_autotuner_integration": "NOT_EVALUATED",
    }
)


def load_manifests() -> dict[str, dict[str, Any]]:
    manifests = V7.load_manifests()
    path = REPO_ROOT / EVA_SCALE / "manifest.json"
    if not path.is_file():
        raise ValueError(f"missing required evidence pack: {EVA_SCALE}")
    manifests["eva_native_scale_sensitivity"] = BASE.load_json(path)
    return manifests


def validate_scale_sensitivity(manifest: dict[str, Any]) -> None:
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_eva_native_scale_sensitivity_evidence_v1",
        "EVA scale evidence schema",
    )
    BASE.require_equal(manifest["status"], "PASS", "EVA scale status")
    BASE.require_equal(
        manifest["outcome"],
        "SELECTED_AUDIT_PASS",
        "EVA scale outcome",
    )
    BASE.require_equal(
        manifest["paper_claim_allowed"], False, "EVA scale paper gate"
    )
    BASE.require_equal(
        manifest["direct_policy_digest"],
        BASE.DIRECT_POLICY_DIGEST,
        "EVA scale direct policy",
    )
    BASE.require_equal(
        manifest["security_policy_digest"],
        BASE.SECURITY_POLICY_DIGEST,
        "EVA scale security policy",
    )
    summary = BASE.load_json(REPO_ROOT / EVA_SCALE / "summary.json")
    by_scale = {
        int(arm["input_scale_bits"]): arm for arm in summary["arms"]
    }
    BASE.require_equal(
        sorted(by_scale), [20, 30, 40], "EVA scale arm population"
    )
    expected_status = {20: "REJECTED", 30: "SAFE", 40: "SAFE"}
    for scale, status in expected_status.items():
        BASE.require_equal(
            by_scale[scale]["validation"]["status"],
            status,
            f"EVA scale {scale} validation",
        )
    BASE.require_equal(
        summary["selected"]["input_scale_bits"], 30, "EVA selected scale"
    )
    audit = summary["locked_audit"]
    BASE.require_equal(audit["status"], "SAFE", "EVA scale audit status")
    BASE.require_equal(
        audit["counts"]["observations"], 48, "EVA scale audit observations"
    )
    BASE.require_equal(
        audit["counts"]["decision_flips"], 0, "EVA scale audit flips"
    )
    BASE.require_equal(
        audit["counts"]["error_violations"],
        0,
        "EVA scale audit violations",
    )
    BASE.require_equal(audit["retuning"], 0, "EVA scale audit retuning")
    accounting = summary["accounting"]
    BASE.require_equal(
        accounting["candidate_trials"], 3, "EVA scale candidate trials"
    )
    BASE.require_equal(
        accounting["validation_encrypted_sample_evaluations"],
        126,
        "EVA scale validation evaluations",
    )
    BASE.require_equal(
        accounting["locked_audit_encrypted_sample_evaluations"],
        48,
        "EVA scale audit evaluations",
    )
    BASE.require_equal(
        summary["policy_modifications"], 0, "EVA scale policy changes"
    )
    original = summary["original_scale20_comparison"]
    BASE.require_equal(
        original["literal_identity"],
        "SEMANTICALLY_IDENTICAL",
        "EVA scale-20 semantic identity",
    )
    BASE.require_equal(
        original["original_validation"]["status"],
        "REJECTED",
        "original EVA scale-20 status",
    )
    BASE.require_equal(
        original["sensitivity_validation"]["status"],
        "REJECTED",
        "sensitivity EVA scale-20 status",
    )
    BASE.require_equal(
        summary["security_interpretation"]["runtime_security_claim"],
        "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "EVA scale runtime security boundary",
    )


def validate_semantics(manifests: dict[str, dict[str, Any]]) -> None:
    V7.validate_semantics(
        {name: manifests[name] for name in V7.PACKS}
    )
    validate_scale_sensitivity(
        manifests["eva_native_scale_sensitivity"]
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
        V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(root)
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": BASE.sha256_path(root / "manifest.json"),
            "tree_sha256": BASE.tree_digest(root),
            "checksum_index": BASE.verify_checksum_index(root),
        }
    return records


def previous_checkpoint_record() -> dict[str, Any]:
    V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(
        PREVIOUS_CHECKPOINT
    )
    V7.verify(PREVIOUS_CHECKPOINT)
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
    paths = V7.research_source_paths()
    paths["eva_native_scale_sensitivity_protocol"] = (
        REPO_ROOT
        / "docs/research/step_7g12_eva_native_scale_sensitivity_protocol.md"
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
        "Paper admission remains manual. The post-rejection seed-0 EVA "
        "scale sensitivity found a scale-30 native SEAL candidate that "
        "passed 42 validation and 48 untouched locked-audit evaluations, "
        "but this is one development workload selected from three fixed "
        "arms. Native SEAL uses a different runtime distribution with "
        "security enforcement disabled; cross-runtime numerical equivalence, "
        "general external-autotuner behavior, release tagging, and external "
        "archival remain incomplete."
    )
    claims = {
        "schema_version": "flipguard_claim_state_registry_v8",
        "paper_claim_allowed": False,
        "block_reason": block_reason,
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        BASE.canonical_json(claims)
    )
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v8",
        "evidence_id": "research_completion_checkpoint_v8",
        "classification": (
            "POST_CONFIRMATORY_NATIVE_EVA_SCALE_SENSITIVITY_CHECKPOINT"
        ),
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": block_reason,
        "lineage": {
            "previous_checkpoint": predecessor,
            "change": (
                "Adds the predeclared native EVA scale-sensitivity pack. "
                "The scale-30 first-SAFE literal passed untouched audit; "
                "the original and repeated scale-20 candidates remain "
                "REJECTED. Neither frozen policy was modified."
            ),
        },
        "policies": {
            "direct_policy_v2": BASE.DIRECT_POLICY_DIGEST,
            "security_policy_v2": BASE.SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "external_compiler_boundary": {
            "native_eva_scale_arms": 3,
            "native_eva_validation_key_runs": 9,
            "native_eva_validation_observations": 126,
            "native_eva_validation_safe_arms": 2,
            "native_eva_validation_rejected_arms": 1,
            "native_eva_selected_scale": 30,
            "native_eva_locked_audit_key_runs": 3,
            "native_eva_locked_audit_observations": 48,
            "native_eva_locked_audit_flips": 0,
            "native_eva_locked_audit_violations": 0,
            "native_eva_locked_audit_failures": 0,
            "original_scale20_status": "REJECTED",
            "repeated_scale20_status": "REJECTED",
            "scale20_semantic_identity": "SEMANTICALLY_IDENTICAL",
            "development_only": True,
            "runtime_security_claim": (
                "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
            ),
            "policy_modifications": 0,
            "retuning": 0,
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
            "independent external autotuner candidate with locked audit",
            "cross-runtime numerical equivalence study",
            "runtime-specific security estimation",
            "release tag",
            "external archive",
        ],
    }
    (output / "manifest.json").write_bytes(BASE.canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V8

This non-overwriting checkpoint binds checkpoint V7 plus the predeclared
native EVA scale-sensitivity pack. Scale 30 passed validation and untouched
locked audit, while both scale-20 fresh-key runs remain decision-REJECTED.

The sensitivity is one seed-0 development workload. It changes no frozen
policy and authorizes no manuscript or broad external-autotuner claim.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    BASE.write_checksums(output)


def verify(output: Path = OUTPUT_DEFAULT) -> None:
    BASE.verify_checksums(output)
    V7.V6.V5.V4.V3.V2.validate_evidence_tree_hygiene(output)
    manifest = BASE.load_json(output / "manifest.json")
    BASE.require_equal(
        manifest["schema_version"],
        "flipguard_research_completion_checkpoint_v8",
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
        "native_eva_scale_arms": 3,
        "native_eva_validation_key_runs": 9,
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
        prefix="flipguard-research-checkpoint-v8-", dir="/tmp"
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
            "research_completion_checkpoint_v8=VERIFIED "
            f"packs={len(PACKS)} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v8=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
