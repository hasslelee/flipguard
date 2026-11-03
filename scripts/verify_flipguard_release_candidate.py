#!/usr/bin/env python3
"""Verify RC1 from a clean detached clone without encrypted execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "flipguard-thesis-artifact-v1.0.0-rc1"

STATIC_VERIFIERS = [
    ["python3", "scripts/verify_margin_utilization_interpretation_v1.py"],
    ["python3", "scripts/verify_validation_identity_comparison_evidence.py"],
    ["python3", "scripts/verify_paired_latency_claim_admission_v1.py"],
    ["python3", "scripts/verify_paper_claim_admission.py"],
    ["python3", "scripts/verify_flipguard_v3_paper_artifacts.py", "--rebuild"],
]
CHECKSUM_PACKS = [
    "docs/evidence/eva_selected_exact_materialization_v1",
    "docs/evidence/exact_security_estimator_v1",
    "docs/evidence/security_v2_static_attestation_formal_v2",
    "docs/evidence/final_confirmatory_suite_v1",
    "docs/evidence/direct_locked_audit_final_source_v1",
    "docs/evidence/direct_locked_audit_seed0_development_v1",
    "docs/evidence/security_v2_bounded_oracle_v1",
    "docs/evidence/no_safe_controls_confirmatory_v1",
    "docs/evidence/structural_extension_v1",
    "docs/evidence/structural_audit_failure_analysis_v1",
    "docs/evidence/non_tabular_sobel_holdout_v1",
    "docs/evidence/non_tabular_harris_holdout_v1",
    "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1",
    "docs/evidence/independent_training_seed_extension_v1",
    "docs/evidence/margin_utilization_interpretation_v1",
    "results/thesis_grade_protocol/paired_latency_claim_admission_v1",
    "docs/evidence/paper_claim_admission_v1",
    "results/thesis_grade_protocol/paper_artifacts_v3/final",
]


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


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return result


def verify_frozen_pack(root: Path) -> dict[str, Any]:
    checksum_index = root / "SHA256SUMS"
    checked = 0
    mode = "SHA256SUMS"
    if checksum_index.is_file():
        for line in checksum_index.read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            path = root / relative
            if not path.is_file() or sha256(path) != f"sha256:{digest}":
                raise ValueError(f"{path}: frozen checksum mismatch")
            checked += 1
    else:
        mode = "MANIFEST_FILES"
        manifest = json.loads((root / "manifest.json").read_text())
        for relative, record in manifest.get("files", {}).items():
            path = root / relative
            expected = record if isinstance(record, str) else record["sha256"]
            if not path.is_file() or sha256(path) != expected:
                raise ValueError(f"{path}: frozen manifest digest mismatch")
            checked += 1
    if checked == 0:
        raise ValueError(f"{root}: no frozen file bindings")
    return {
        "path": str(root),
        "mode": mode,
        "files_checked": checked,
        "status": "PASS",
    }


def archive_release_id(archive: Path, temporary: Path) -> str:
    listing = run(["tar", "--zstd", "-tf", str(archive)], cwd=temporary)
    members = listing.stdout.splitlines()
    roots = {
        member.split("/", 1)[0]
        for member in members
        if member and not member.startswith("/")
    }
    if len(roots) != 1:
        raise ValueError("archive does not have exactly one release root")
    release_id = roots.pop()
    if not release_id or release_id in {".", ".."}:
        raise ValueError("archive release ID is invalid")
    return release_id


def verify_archive(archive: Path, temporary: Path) -> dict[str, Any]:
    release_id = archive_release_id(archive, temporary)
    listing = run(["tar", "--zstd", "-tf", str(archive)], cwd=temporary)
    members = listing.stdout.splitlines()
    prefix = f"{release_id}/"
    if not members or any(not member.startswith(prefix) for member in members):
        raise ValueError("archive contains an invalid path")
    if any("/../" in member or member.startswith("/") for member in members):
        raise ValueError("archive path traversal detected")
    extract_root = temporary / "extract"
    extract_root.mkdir()
    run(["tar", "--zstd", "-xf", str(archive)], cwd=extract_root)
    root = extract_root / release_id
    sums = (root / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in sums:
        digest, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != f"sha256:{digest}":
            raise ValueError(f"{relative}: internal checksum mismatch")
    manifest = json.loads(
        (root / "release/archive_manifest.json").read_text()
    )
    if manifest["release_id"] != release_id:
        raise ValueError("archive root and release manifest disagree")
    if manifest["new_encrypted_executions"] != 0:
        raise ValueError("release claims new encrypted executions")
    return {
        "members": len(members),
        "release_id": release_id,
        "checksum_entries": len(sums),
        "internal_manifest_sha256": sha256(
            root / "release/archive_manifest.json"
        ),
    }


def verify(
    repo_root: Path,
    source_commit: str,
    archive: Path,
) -> dict[str, Any]:
    source_commit = run(
        ["git", "rev-parse", "--verify", f"{source_commit}^{{commit}}"],
        cwd=repo_root,
    ).stdout.strip()
    original_digest = sha256(archive)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="flipguard-clean-clone-") as temp:
        temporary = Path(temp)
        release_id = archive_release_id(archive, temporary)
        clone = temporary / "clone"
        run(
            ["git", "clone", "--no-local", "--quiet", str(repo_root), str(clone)],
            cwd=temporary,
        )
        run(["git", "checkout", "--detach", "--quiet", source_commit], cwd=clone)
        head = run(["git", "rev-parse", "HEAD"], cwd=clone).stdout.strip()
        status = run(["git", "status", "--porcelain"], cwd=clone).stdout
        if head != source_commit or status:
            raise ValueError("clean clone identity check failed")

        for command in STATIC_VERIFIERS:
            result = run(command, cwd=clone)
            checks.append(
                {
                    "command": " ".join(command),
                    "status": "PASS",
                    "stdout_tail": result.stdout.strip().splitlines()[-1:],
                }
            )

        frozen_pack_checks = [
            verify_frozen_pack(clone / relative)
            for relative in CHECKSUM_PACKS
        ]
        external = json.loads(
            (clone / "release/external_sources_v1.json").read_text()
        )
        for record in external["sources"]:
            for relative in record["derived_artifact_manifests"]:
                if not (clone / relative).is_file():
                    raise ValueError(f"{relative}: missing derived manifest")

        rebuilt = temporary / "rebuilt.tar.zst"
        result = run(
            [
                "python3",
                "scripts/build_flipguard_release_candidate.py",
                "--repo-root",
                str(clone),
                "--source-commit",
                source_commit,
                "--output",
                str(rebuilt),
                "--release-id",
                release_id,
            ],
            cwd=clone,
        )
        checks.append(
            {
                "command": "deterministic release archive rebuild",
                "status": "PASS",
                "stdout_tail": result.stdout.strip().splitlines()[-1:],
            }
        )
        if sha256(rebuilt) != original_digest:
            raise ValueError("clean-clone archive digest mismatch")
        archive_check = verify_archive(archive, temporary)

    return {
        "schema_version": "flipguard_clean_clone_release_verification_v1",
        "status": "PASS",
        "source_commit": source_commit,
        "archive": str(archive.resolve()),
        "archive_sha256": original_digest,
        "archive_bytes": archive.stat().st_size,
        "clean_clone": True,
        "deterministic_rebuild": True,
        "external_source_manifests_verified": True,
        "raw_external_sources_required": False,
        "new_encrypted_executions": 0,
        "policy_retuning": 0,
        "checks": checks,
        "frozen_pack_checks": frozen_pack_checks,
        "legacy_external_path_replay": {
            "status": "NOT_REQUIRED_FOR_CORE_CLEAN_CLONE",
            "reason": (
                "Historical freezer rebuild modes reference intentionally "
                "untracked results paths. Their frozen snapshots and checksum "
                "bindings are verified; the exact EVA materialization replay "
                "was separately verified in the source working checkout."
            ),
        },
        "archive_check": archive_check,
        "host": {
            "os_uname": " ".join(os.uname()),
            "python": run(["python3", "--version"], cwd=repo_root).stdout.strip(),
            "go": run(["go", "version"], cwd=repo_root).stdout.strip(),
            "git": run(["git", "--version"], cwd=repo_root).stdout.strip(),
            "tar": run(["tar", "--version"], cwd=repo_root).stdout.splitlines()[0],
            "zstd": run(["zstd", "--version"], cwd=repo_root).stdout.strip(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(
        args.repo_root.resolve(),
        args.source_commit,
        args.archive.resolve(),
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_json(result))
    print(
        "clean_clone_release=PASS "
        f"sha256={result['archive_sha256']} checks={len(result['checks'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
