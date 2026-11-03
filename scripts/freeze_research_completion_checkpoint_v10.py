#!/usr/bin/env python3
"""Freeze the core-complete FlipGuard research checkpoint V10."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("docs/evidence/research_completion_checkpoint_v10")
V9 = Path("docs/evidence/research_completion_checkpoint_v9")
CLAIMS = Path("docs/evidence/paper_claim_admission_v1")
V3 = Path("results/thesis_grade_protocol/paper_artifacts_v3/final")
MARGIN = Path("docs/evidence/margin_utilization_interpretation_v1")
LATENCY = Path(
    "results/thesis_grade_protocol/paired_latency_claim_admission_v1"
)
CORE_PACKS = {
    "security_v2": Path(
        "docs/evidence/security_v2_static_attestation_formal_v2"
    ),
    "direct_confirmatory": Path(
        "docs/evidence/direct_locked_audit_final_source_v1"
    ),
    "direct_development": Path(
        "docs/evidence/direct_locked_audit_seed0_development_v1"
    ),
    "bounded_oracle": Path(
        "docs/evidence/security_v2_bounded_oracle_v1"
    ),
    "no_safe": Path("docs/evidence/no_safe_controls_confirmatory_v1"),
    "paired_latency_admission": LATENCY,
    "structural": Path("docs/evidence/structural_extension_v1"),
    "structural_failure": Path(
        "docs/evidence/structural_audit_failure_analysis_v1"
    ),
    "sobel": Path("docs/evidence/non_tabular_sobel_holdout_v1"),
    "harris": Path("docs/evidence/non_tabular_harris_holdout_v1"),
    "cnn_lite": Path(
        "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1"
    ),
    "training_seed": Path(
        "docs/evidence/independent_training_seed_extension_v1"
    ),
    "margin_interpretation": MARGIN,
    "paper_claim_admission": CLAIMS,
    "paper_artifacts_v3": V3,
}
VERIFIER = Path("scripts/verify_research_completion_checkpoint_v10.py")
DIRECT_POLICY = Path(
    "docs/evidence/security_v2_static_attestation_formal_v2/"
    "direct_synthesis_policy_v2.json"
)
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("ascii")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(bytes.fromhex(sha256(path).removeprefix("sha256:")))
    return f"sha256:{digest.hexdigest()}"


def load(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def record_pack(relative: Path) -> dict[str, Any]:
    root = ROOT / relative
    manifest = root / "manifest.json"
    if not manifest.is_file():
        raise ValueError(f"{relative}: missing manifest")
    return {
        "path": relative.as_posix(),
        "manifest_sha256": sha256(manifest),
        "tree_sha256": tree_sha256(root),
    }


def write_sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(
                f"{sha256(path).removeprefix('sha256:')}  "
                f"{path.relative_to(root).as_posix()}\n"
            )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def freeze(
    output: Path,
    *,
    source_commit: str,
    archive_record: Path,
    clean_clone_record: Path,
) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V10: {output}")
    claims = load(CLAIMS / "manifest.json")
    publication = load(V3 / "publication_status.json")
    structural = load(Path("docs/evidence/structural_extension_v1/manifest.json"))
    direct_policy = load(DIRECT_POLICY)
    release = json.loads(archive_record.read_text(encoding="utf-8"))
    clean_clone = json.loads(clean_clone_record.read_text(encoding="utf-8"))
    if claims["paper_claim_allowed"] is not True:
        raise ValueError("claim admission overlay is not open")
    if publication["status"] != "FINAL_ADMISSIBLE":
        raise ValueError("paper artifacts V3 are not FINAL_ADMISSIBLE")
    if clean_clone["status"] != "PASS" or not clean_clone["deterministic_rebuild"]:
        raise ValueError("clean-clone release verification failed")
    if clean_clone["archive_sha256"] != release["archive_sha256"]:
        raise ValueError("release records disagree")
    if release["source_commit"] != source_commit:
        raise ValueError("release source commit mismatch")

    if direct_policy["policy_sha256"] != DIRECT_POLICY_DIGEST:
        raise ValueError("Direct Policy V2 digest changed")
    counts = structural["counts"]
    if (
        counts["selection_selected"] != 25
        or counts["locked_audit_pass"] != 24
        or counts["locked_audit_rejected"] != 1
        or counts["locked_audit_failed"] != 0
        or counts["retuning"] != 0
    ):
        raise ValueError("structural negative-result accounting changed")

    packs = {name: record_pack(path) for name, path in CORE_PACKS.items()}
    output.mkdir(parents=True)
    auxiliary = [
        {
            "claim": "EVA cross-runtime numerical equivalence",
            "state": "NOT_EVALUATED",
            "blocking": False,
        },
        {
            "claim": "general external-autotuner integration",
            "state": "NOT_EVALUATED",
            "blocking": False,
        },
        {
            "claim": "runtime-specific equivalent security",
            "state": "NOT_EVALUATED",
            "blocking": False,
        },
        {
            "claim": "instantiated analytical CKKS certificate",
            "state": "BLOCKED",
            "blocking": False,
        },
        {
            "claim": "arbitrary packed CNN/full LeNet",
            "state": "NOT_EVALUATED",
            "blocking": False,
        },
    ]
    completion = {
        "schema_version": "flipguard_research_completion_state_v10",
        "core_development_complete": True,
        "paper_artifacts_final_admissible": True,
        "paper_writing_allowed": True,
        "admitted_claim_count": claims["admitted_claim_count"],
        "blocked_claim_count": claims[
            "blocked_or_not_admitted_claim_count"
        ],
        "future_work_count": len(auxiliary),
        "remaining_core_blockers": [],
        "remaining_auxiliary_work": auxiliary,
        "exact_source_commit": source_commit,
        "artifact_manifest_digest": sha256(V3 / "manifest.json"),
        "paper_writing_rule": (
            "Use only claims.json entries with paper_admitted=true."
        ),
    }
    (output / "completion_state.json").write_bytes(
        canonical_json(completion)
    )
    (output / "release_binding.json").write_bytes(
        canonical_json(
            {
                "archive": release,
                "clean_clone_verification": {
                    "sha256": sha256(clean_clone_record),
                    "status": clean_clone["status"],
                    "source_commit": clean_clone["source_commit"],
                    "archive_sha256": clean_clone["archive_sha256"],
                    "deterministic_rebuild": clean_clone[
                        "deterministic_rebuild"
                    ],
                },
            }
        )
    )
    (output / "auxiliary_work.json").write_bytes(canonical_json(auxiliary))
    shutil.copy2(ROOT / VERIFIER, output / VERIFIER.name)
    v9_record = record_pack(V9)
    manifest = {
        "schema_version": "flipguard_research_completion_checkpoint_v10",
        "evidence_id": "research_completion_checkpoint_v10",
        "classification": "CORE_RESEARCH_COMPLETION",
        "source_commit": source_commit,
        "predecessor": v9_record,
        "core_gates": {
            **{name: "PASS" for name in CORE_PACKS},
            "direct_policy_v2": "PASS",
            "clean_clone_artifact_verification": "PASS",
            "release_candidate_archive": "PASS",
        },
        "policies": {
            "direct_policy_id": "flipguard_direct_synthesis_policy_v2",
            "direct_policy_digest": DIRECT_POLICY_DIGEST,
            "direct_policy_artifact": {
                "path": DIRECT_POLICY.as_posix(),
                "sha256": sha256(ROOT / DIRECT_POLICY),
            },
            "security_policy_id": (
                "security_guidelines_cic2025_table5_2_ternary_128_v2"
            ),
            "security_policy_digest": SECURITY_POLICY_DIGEST,
        },
        "packs": packs,
        "release_archive_sha256": release["archive_sha256"],
        "clean_clone_verification": "PASS",
        "new_encrypted_executions": 0,
        "policy_retuning": 0,
        "completion_state": {
            "path": "completion_state.json",
            "sha256": sha256(output / "completion_state.json"),
        },
        "release_binding": {
            "path": "release_binding.json",
            "sha256": sha256(output / "release_binding.json"),
        },
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    (output / "README.md").write_text(
        "# Research Completion Checkpoint V10\n\n"
        "This immutable overlay closes the declared core research scope. "
        "Auxiliary blocked or unevaluated claims remain future work and do "
        "not block writing that is restricted to the admitted claim registry.\n",
        encoding="ascii",
    )
    write_sums(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--archive-record", type=Path, required=True)
    parser.add_argument("--clean-clone-record", type=Path, required=True)
    args = parser.parse_args()
    freeze(
        args.output,
        source_commit=args.source_commit,
        archive_record=args.archive_record,
        clean_clone_record=args.clean_clone_record,
    )
    print(f"research_completion_checkpoint_v10=FROZEN output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
