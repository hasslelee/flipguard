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
    ["python3", "scripts/bind_eva_selected_exact_materialization_v1.py", "--verify"],
    ["python3", "scripts/verify_exact_security_estimator.py"],
    ["python3", "scripts/verify_margin_utilization_interpretation_v1.py"],
    ["python3", "scripts/verify_paired_latency_claim_admission_v1.py"],
    ["python3", "scripts/verify_paper_claim_admission.py"],
    ["python3", "scripts/verify_flipguard_v3_paper_artifacts.py", "--rebuild"],
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
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )


def verify_archive(archive: Path, temporary: Path) -> dict[str, Any]:
    listing = run(["tar", "--zstd", "-tf", str(archive)], cwd=temporary)
    members = listing.stdout.splitlines()
    prefix = f"{ARCHIVE_NAME}/"
    if not members or any(not member.startswith(prefix) for member in members):
        raise ValueError("archive contains an invalid path")
    if any("/../" in member or member.startswith("/") for member in members):
        raise ValueError("archive path traversal detected")
    extract_root = temporary / "extract"
    extract_root.mkdir()
    run(["tar", "--zstd", "-xf", str(archive)], cwd=extract_root)
    root = extract_root / ARCHIVE_NAME
    sums = (root / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in sums:
        digest, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != f"sha256:{digest}":
            raise ValueError(f"{relative}: internal checksum mismatch")
    manifest = json.loads(
        (root / "release/archive_manifest.json").read_text()
    )
    if manifest["new_encrypted_executions"] != 0:
        raise ValueError("release claims new encrypted executions")
    return {
        "members": len(members),
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
