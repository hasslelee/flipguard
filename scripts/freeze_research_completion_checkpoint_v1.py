#!/usr/bin/env python3
"""Freeze and verify the post-confirmatory research checkpoint index."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/research_completion_checkpoint_v1"
)

DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)

PACKS = {
    "conditional_analytical_readiness": Path(
        "docs/evidence/conditional_analytical_readiness_v2"
    ),
    "direct_synthesis_ablation": Path(
        "docs/evidence/direct_synthesis_ablation_v1"
    ),
    "final_confirmatory": Path(
        "docs/evidence/final_confirmatory_suite_v1"
    ),
    "independent_training_seed": Path(
        "docs/evidence/independent_training_seed_extension_v1"
    ),
    "no_safe_confirmatory": Path(
        "docs/evidence/no_safe_controls_confirmatory_v1"
    ),
    "non_tabular_harris": Path(
        "docs/evidence/non_tabular_harris_holdout_v1"
    ),
    "non_tabular_mnist_cnn_lite": Path(
        "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1"
    ),
    "non_tabular_sobel": Path(
        "docs/evidence/non_tabular_sobel_holdout_v1"
    ),
    "paired_latency": Path(
        "docs/evidence/paired_latency_final_v1"
    ),
    "policy_sensitivity": Path(
        "docs/evidence/policy_sensitivity_v1"
    ),
    "security_attestation": Path(
        "docs/evidence/security_v2_static_attestation_formal_v2"
    ),
    "security_bounded_catalog": Path(
        "docs/evidence/security_v2_bounded_oracle_v1"
    ),
    "structural_extension": Path(
        "docs/evidence/structural_extension_v1"
    ),
    "structural_failure_analysis": Path(
        "docs/evidence/structural_audit_failure_analysis_v1"
    ),
    "tabular_certification_observed": Path(
        "docs/evidence/tabular_certification_observed_v1"
    ),
    "validation_identity": Path(
        "docs/evidence/validation_identity_comparison_v2"
    ),
}

CLAIM_STATES = {
    "adaptive_repair": "SUPPORTED",
    "artifact_reproducibility": "PARTIALLY_SUPPORTED",
    "conditional_error_envelope_propagation": "SUPPORTED",
    "decision_contract_candidate_synthesis_effect": "BLOCKED",
    "decision_integrity_certification": "PARTIALLY_SUPPORTED",
    "direct_synthesis": "SUPPORTED",
    "instantiated_ckks_analytical_certificate": "BLOCKED",
    "latency_only_no_certification_comparator": "SUPPORTED",
    "latency_speedup": "PARTIALLY_SUPPORTED",
    "locked_audit_fixed_heldout_partitions": "SUPPORTED",
    "planner_baseline": "PARTIALLY_SUPPORTED",
    "security": "PARTIALLY_SUPPORTED",
    "security_compliant_bounded_catalog_comparison": "SUPPORTED",
    "structural_generalization": "PARTIALLY_SUPPORTED",
    "training_model_seed_generalization": "PARTIALLY_SUPPORTED",
    "trial_reduction": "SUPPORTED",
}

ALLOWED_STATES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "BLOCKED",
    "NOT_EVALUATED",
    "SUPERSEDED",
    "PILOT_ONLY",
}


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def git_blob(commit: str, path: Path) -> bytes:
    relative = path.relative_to(REPO_ROOT).as_posix()
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def verify_bound_source(
    path: Path,
    expected_digest: str,
    source_commit: str,
    label: str,
) -> str:
    if sha256_path(path) == expected_digest:
        return "CURRENT_TREE"
    historical_digest = sha256_bytes(git_blob(source_commit, path))
    require_equal(
        historical_digest,
        expected_digest,
        f"{label} historical Git binding",
    )
    return "FREEZER_COMMIT"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_path(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def require_equal(
    actual: Any,
    expected: Any,
    label: str,
) -> None:
    if actual != expected:
        raise ValueError(
            f"{label}={actual!r}; expected {expected!r}"
        )


def verify_checksum_index(root: Path) -> str:
    checksum_path = root / "SHA256SUMS"
    if not checksum_path.is_file():
        return "NOT_PRESENT_TREE_DIGEST_ONLY"
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, relative_text = line.split("  ", 1)
        relative = Path(relative_text.removeprefix("./"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"{checksum_path}: unsafe checksum path {relative_text}"
            )
        target = root / relative
        if not target.is_file():
            raise ValueError(
                f"{checksum_path}: missing {relative.as_posix()}"
            )
        require_equal(
            sha256_path(target),
            f"sha256:{digest}",
            f"{checksum_path}:{relative.as_posix()}",
        )
    return "VERIFIED"


def load_manifests(
    packs: dict[str, Path] = PACKS,
) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for name, relative in packs.items():
        root = REPO_ROOT / relative
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"missing required evidence pack: {relative}")
        manifests[name] = load_json(manifest_path)
    return manifests


def validate_semantics(
    manifests: dict[str, dict[str, Any]],
) -> None:
    final = manifests["final_confirmatory"]
    require_equal(final["paper_claim_allowed"], False, "final paper gate")
    require_equal(
        final["direct_policy"]["digest"],
        DIRECT_POLICY_DIGEST,
        "final direct policy digest",
    )
    require_equal(
        final["security_policy"]["digest"],
        SECURITY_POLICY_DIGEST,
        "final security policy digest",
    )
    require_equal(
        final["catalog_accounting"],
        {
            "confirmatory_catalog_candidates": 560,
            "development_catalog_candidates": 140,
            "raw_catalog_executions": 1100,
            "security_admitted_catalog_candidates": 700,
            "security_excluded_catalog_candidates": 400,
        },
        "formal catalog accounting",
    )
    require_equal(
        final["formal_trial_accounting"][
            "formal_trial_reduction_all"
        ],
        0.9,
        "all-instance formal trial reduction",
    )
    require_equal(
        final["formal_trial_accounting"][
            "formal_trial_reduction_confirmatory"
        ],
        0.9,
        "confirmatory formal trial reduction",
    )

    ablation = manifests["direct_synthesis_ablation"]
    require_equal(
        ablation["direct_policy_digest"],
        DIRECT_POLICY_DIGEST,
        "ablation direct policy digest",
    )
    require_equal(
        ablation["security_policy_digest"],
        SECURITY_POLICY_DIGEST,
        "ablation security policy digest",
    )
    require_equal(
        ablation["claim_states"],
        {
            "adaptive_repair": "SUPPORTED",
            "decision_contract_candidate_synthesis_effect": "BLOCKED",
            "development_locked_audit": "SUPPORTED",
            "latency_only_no_certification_comparator": "SUPPORTED",
        },
        "ablation claim states",
    )

    independent = manifests["independent_training_seed"]
    require_equal(independent["instances"], 9, "independent instances")
    require_equal(
        independent["training_seed_generalization"],
        "PARTIALLY_SUPPORTED",
        "training-seed claim",
    )
    require_equal(
        independent["direct_policy_digest"],
        DIRECT_POLICY_DIGEST,
        "independent direct policy digest",
    )
    require_equal(
        independent["security_policy_digest"],
        SECURITY_POLICY_DIGEST,
        "independent security policy digest",
    )

    structural = manifests["structural_extension"]
    require_equal(
        structural["claim_state"],
        "PARTIALLY_SUPPORTED",
        "structural claim",
    )
    expected_structural_counts = {
        "structural_instances": 25,
        "selection_selected": 25,
        "selection_failed": 0,
        "selection_no_safe": 0,
        "locked_audit_pass": 24,
        "locked_audit_rejected": 1,
        "locked_audit_failed": 0,
        "retuning": 0,
        "flip_count": 0,
        "violation_count": 1,
        "policy_modification_after_audit": 0,
    }
    for key, expected in expected_structural_counts.items():
        require_equal(
            structural["counts"][key],
            expected,
            f"structural {key}",
        )

    for name in ("non_tabular_sobel", "non_tabular_harris"):
        manifest = manifests[name]
        require_equal(
            manifest["policies"]["direct_policy_v2"],
            DIRECT_POLICY_DIGEST,
            f"{name} direct policy digest",
        )
        require_equal(
            manifest["policies"]["security_policy_v2"],
            SECURITY_POLICY_DIGEST,
            f"{name} security policy digest",
        )
        require_equal(
            manifest["summary"]["status"],
            "SUPPORTED",
            f"{name} status",
        )
        require_equal(
            manifest["summary"]["locked_audit"]["retuning"],
            0,
            f"{name} retuning",
        )
        require_equal(
            manifest["summary"]["locked_audit"]["violations"],
            0,
            f"{name} audit violations",
        )

    cnn = manifests["non_tabular_mnist_cnn_lite"]
    require_equal(cnn["claim_status"], "SUPPORTED", "CNN-lite status")
    require_equal(
        cnn["structural_generalization"],
        "PARTIALLY_SUPPORTED",
        "CNN-lite structural claim",
    )
    require_equal(
        cnn["direct_policy_digest"],
        DIRECT_POLICY_DIGEST,
        "CNN-lite direct policy digest",
    )
    require_equal(
        cnn["security_policy_digest"],
        SECURITY_POLICY_DIGEST,
        "CNN-lite security policy digest",
    )

    analytical = manifests["conditional_analytical_readiness"]
    require_equal(
        analytical["claims"]["conditional_propagation_lemma"],
        "SUPPORTED",
        "conditional propagation claim",
    )
    require_equal(
        analytical["claims"][
            "instantiated_ckks_analytical_certificate"
        ],
        "BLOCKED",
        "instantiated analytical claim",
    )
    require_equal(
        analytical["accounting"]["primary_candidates"],
        50,
        "analytical primary candidates",
    )
    require_equal(
        analytical["accounting"]["proof_eligible_candidates"],
        0,
        "analytical proof-eligible candidates",
    )
    require_equal(
        analytical["accounting"]["encrypted_executions"],
        0,
        "analytical encrypted executions",
    )

    identity = manifests["validation_identity"]
    require_equal(
        identity["identity_class_counts"],
        {"SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER": 50},
        "validation identity classes",
    )
    require_equal(
        identity["encrypted_rerun_required_workloads"],
        0,
        "validation identity reruns",
    )

    for claim, state in CLAIM_STATES.items():
        if state not in ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid claim state {state}")


def build_pack_records(
    manifests: dict[str, dict[str, Any]],
    packs: dict[str, Path] = PACKS,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, relative in packs.items():
        root = REPO_ROOT / relative
        manifest_path = root / "manifest.json"
        records[name] = {
            "path": relative.as_posix(),
            "schema_version": manifests[name].get("schema_version"),
            "manifest_sha256": sha256_path(manifest_path),
            "tree_sha256": tree_digest(root),
            "checksum_index": verify_checksum_index(root),
        }
    return records


def pack_paths_from_manifest(
    records: dict[str, dict[str, Any]],
) -> dict[str, Path]:
    packs: dict[str, Path] = {}
    for name, record in records.items():
        if not isinstance(name, str) or not name:
            raise ValueError("checkpoint contains an invalid pack name")
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"checkpoint contains unsafe pack path: {relative}"
            )
        if relative.parts[:2] != ("docs", "evidence"):
            raise ValueError(
                f"checkpoint pack is outside docs/evidence: {relative}"
            )
        packs[name] = relative
    return packs


def write_checksums(output: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output).as_posix()}\n"
        )
    (output / "SHA256SUMS").write_text(
        "".join(lines),
        encoding="ascii",
    )


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
    claim_matrix = (
        REPO_ROOT / "docs/research/flipguard_v2_claim_evidence_matrix.md"
    )
    novelty_audit = (
        REPO_ROOT
        / "docs/research/step_7f1_primary_source_novelty_audit.md"
    )
    output.mkdir(parents=True)
    claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v1",
        "paper_claim_allowed": False,
        "block_reason": (
            "Paper admission, external archival, release tagging, and "
            "independent-machine replay remain separate manual gates."
        ),
        "states": CLAIM_STATES,
    }
    (output / "claim_states.json").write_bytes(
        canonical_json(claim_state_document)
    )
    manifest = {
        "schema_version": (
            "flipguard_research_completion_checkpoint_v1"
        ),
        "evidence_id": "research_completion_checkpoint_v1",
        "classification": "POST_CONFIRMATORY_RESEARCH_CHECKPOINT",
        "freezer_commit": freezer_commit,
        "paper_claim_allowed": False,
        "research_checkpoint_status": "PARTIALLY_SUPPORTED",
        "block_reason": claim_state_document["block_reason"],
        "policies": {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "formal_population": {
            "development_seed": 0,
            "confirmatory_seeds": [1, 2, 3, 4],
            "primary_dataset_model_workloads": 10,
            "deterministic_partitions": 5,
            "workload_partition_instances": 50,
            "independent_training_seed_extension_instances": 9,
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
            ],
        },
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
        "claim_state_registry": {
            "path": "claim_states.json",
            "sha256": sha256_path(output / "claim_states.json"),
        },
        "claim_matrix": {
            "path": claim_matrix.relative_to(REPO_ROOT).as_posix(),
            "sha256": claim_matrix_digest or sha256_path(claim_matrix),
        },
        "novelty_audit": {
            "path": novelty_audit.relative_to(REPO_ROOT).as_posix(),
            "sha256": novelty_audit_digest or sha256_path(novelty_audit),
        },
        "packs": pack_records,
        "remaining_manual_gates": [
            "paper claim admission",
            "release tag",
            "external archive",
            "independent-machine deterministic replay",
        ],
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# FlipGuard Research Completion Checkpoint V1

This non-overwriting index binds the authoritative post-confirmatory evidence
packs and their current claim boundaries. It performs no CKKS execution and
does not promote any paper claim.

The checkpoint preserves scientific negative results, including the 24/25
structural locked-audit result, the missing natural-data decision-contract
synthesis effect, and the absence of instantiated CKKS analytical proofs.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)


def verify_checksums(output: Path) -> None:
    checksum_path = output / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="ascii").splitlines()
    expected_paths: set[str] = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        target = output / relative
        if not target.is_file():
            raise ValueError(f"missing checkpoint file: {relative}")
        require_equal(
            sha256_path(target),
            f"sha256:{digest}",
            f"checkpoint checksum {relative}",
        )
        expected_paths.add(relative)
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(
        actual_paths,
        expected_paths,
        "checkpoint file set",
    )


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = sorted(
        path.relative_to(expected)
        for path in expected.rglob("*")
        if path.is_file()
    )
    actual_files = sorted(
        path.relative_to(actual)
        for path in actual.rglob("*")
        if path.is_file()
    )
    require_equal(actual_files, expected_files, "rebuilt file set")
    for relative in expected_files:
        require_equal(
            (actual / relative).read_bytes(),
            (expected / relative).read_bytes(),
            f"rebuilt file {relative.as_posix()}",
        )


def verify(output: Path) -> str:
    verify_checksums(output)
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["paper_claim_allowed"],
        False,
        "checkpoint paper gate",
    )
    frozen_pack_paths = pack_paths_from_manifest(manifest["packs"])
    manifests = load_manifests(frozen_pack_paths)
    validate_semantics(manifests)
    current_records = build_pack_records(manifests, frozen_pack_paths)
    require_equal(
        current_records,
        manifest["packs"],
        "linked evidence records",
    )
    claim_states = output / manifest["claim_state_registry"]["path"]
    require_equal(
        sha256_path(claim_states),
        manifest["claim_state_registry"]["sha256"],
        "claim state registry binding",
    )
    frozen_claim_states = load_json(claim_states)
    require_equal(
        frozen_claim_states["paper_claim_allowed"],
        False,
        "claim registry paper gate",
    )
    for claim, state in frozen_claim_states["states"].items():
        if state not in ALLOWED_STATES:
            raise ValueError(f"{claim}: invalid frozen claim state {state}")
    claim_matrix = REPO_ROOT / manifest["claim_matrix"]["path"]
    verify_bound_source(
        claim_matrix,
        manifest["claim_matrix"]["sha256"],
        manifest["freezer_commit"],
        "claim matrix binding",
    )
    novelty_audit = REPO_ROOT / manifest["novelty_audit"]["path"]
    verify_bound_source(
        novelty_audit,
        manifest["novelty_audit"]["sha256"],
        manifest["freezer_commit"],
        "novelty audit binding",
    )
    current_claim_state_document = {
        "schema_version": "flipguard_claim_state_registry_v1",
        "paper_claim_allowed": False,
        "block_reason": (
            "Paper admission, external archival, release tagging, and "
            "independent-machine replay remain separate manual gates."
        ),
        "states": CLAIM_STATES,
    }
    can_rebuild = (
        frozen_pack_paths == PACKS and
        sha256_bytes(canonical_json(current_claim_state_document)) ==
        manifest["claim_state_registry"]["sha256"]
    )
    if can_rebuild:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-",
            dir="/tmp",
        ) as temporary:
            rebuilt = Path(temporary) / "rebuilt"
            freeze(
                rebuilt,
                manifest["freezer_commit"],
                claim_matrix_digest=manifest["claim_matrix"]["sha256"],
                novelty_audit_digest=manifest["novelty_audit"]["sha256"],
            )
            compare_trees(output, rebuilt)
        return "DETERMINISTIC_REBUILD"
    return "HISTORICAL_MANIFEST_BOUND"


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
        verification_mode = verify(output)
        print(
            "research_completion_checkpoint_v1=VERIFIED "
            f"packs={len(load_json(output / 'manifest.json')['packs'])} "
            f"mode={verification_mode} paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(output, args.freezer_commit)
    print(
        "research_completion_checkpoint_v1=FROZEN "
        f"packs={len(PACKS)} output={output}"
    )


if __name__ == "__main__":
    main()
