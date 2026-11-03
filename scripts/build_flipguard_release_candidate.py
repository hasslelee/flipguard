#!/usr/bin/env python3
"""Build a deterministic FlipGuard thesis release-candidate archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "flipguard-thesis-artifact-v1.0.0-rc1"
DEFAULT_OUTPUT = Path(f"dist/{ARCHIVE_NAME}.tar.zst")
EXTERNAL_REGISTRY = Path("release/external_sources_v1.json")
ENVIRONMENT_REQUIREMENTS = Path("release/environment_requirements_v1.json")
REPRODUCTION_GUIDE = Path("docs/research/reproducibility_release_v1.md")


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
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


def canonical_commit(repo_root: Path, revision: str) -> str:
    value = run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=repo_root,
        capture=True,
    ).stdout.strip()
    if len(value) != 40:
        raise ValueError(f"{revision}: not a canonical commit")
    return value


def tracked_paths(repo_root: Path, commit: str) -> list[str]:
    output = run(
        ["git", "ls-tree", "-r", "--name-only", commit],
        cwd=repo_root,
        capture=True,
    ).stdout
    paths = [line for line in output.splitlines() if line]
    if not paths or any(path.startswith("/") or ".." in Path(path).parts for path in paths):
        raise ValueError("invalid tracked path set")
    return sorted(paths)


def write_checksums(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            relative = path.relative_to(root).as_posix()
            lines.append(f"{sha256(path).removeprefix('sha256:')}  {relative}\n")
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_internal_checksums(root: Path) -> None:
    expected = (root / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in expected:
        digest, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != f"sha256:{digest}":
            raise ValueError(f"{relative}: archive checksum mismatch")


def build(
    repo_root: Path,
    source_commit: str,
    output: Path,
    release_id: str = ARCHIVE_NAME,
) -> dict[str, Any]:
    if (
        not release_id
        or "/" in release_id
        or release_id in {".", ".."}
    ):
        raise ValueError(f"invalid release ID: {release_id!r}")
    commit = canonical_commit(repo_root, source_commit)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    tracked = tracked_paths(repo_root, commit)
    commit_timestamp = int(
        run(
            ["git", "show", "-s", "--format=%ct", commit],
            cwd=repo_root,
            capture=True,
        ).stdout.strip()
    )
    with tempfile.TemporaryDirectory(prefix="flipguard-release-build-") as temp:
        temporary = Path(temp)
        source_tar = temporary / "source.tar"
        staging_parent = temporary / "staging"
        staging_parent.mkdir()
        prefix = f"{release_id}/"
        with source_tar.open("wb") as handle:
            subprocess.run(
                ["git", "archive", f"--prefix={prefix}", commit],
                cwd=repo_root,
                check=True,
                stdout=handle,
            )
        with tarfile.open(source_tar) as archive:
            archive.extractall(staging_parent, filter="data")
        staging = staging_parent / release_id
        release_root = staging / "release"
        shutil.copy2(
            staging / REPRODUCTION_GUIDE,
            staging / "REPRODUCING.md",
        )
        environment = {
            "schema_version": "flipguard_release_environment_manifest_v1",
            "source_commit": commit,
            "source_commit_timestamp": commit_timestamp,
            "requirements": json.loads(
                (staging / ENVIRONMENT_REQUIREMENTS).read_text()
            ),
            "determinism": {
                "archive_mtime": commit_timestamp,
                "owner": 0,
                "group": 0,
                "file_order": "lexicographic",
                "zstd_threads": 1,
            },
        }
        (release_root / "environment_manifest.json").write_bytes(
            canonical_json(environment)
        )
        manifest = {
            "schema_version": "flipguard_thesis_release_candidate_v1",
            "release_id": release_id,
            "source_commit": commit,
            "tracked_source_files": len(tracked),
            "paper_artifacts_v3": {
                "path": (
                    "results/thesis_grade_protocol/"
                    "paper_artifacts_v3/final/manifest.json"
                ),
                "sha256": sha256(
                    staging
                    / "results/thesis_grade_protocol/"
                    "paper_artifacts_v3/final/manifest.json"
                ),
            },
            "external_source_registry": {
                "path": str(EXTERNAL_REGISTRY),
                "sha256": sha256(staging / EXTERNAL_REGISTRY),
            },
            "included": "all files tracked by source_commit plus generated release metadata",
            "excluded": [
                ".git/",
                "dist/",
                "results/source_datasets/",
                "ignored results working ledgers and duplicate raw executions",
                "caches, temporary files, and local virtual environments",
            ],
            "new_encrypted_executions": 0,
            "policy_retuning": 0,
        }
        (release_root / "archive_manifest.json").write_bytes(
            canonical_json(manifest)
        )
        write_checksums(staging)

        tar_path = temporary / f"{release_id}.tar"
        run(
            [
                "tar",
                "--sort=name",
                f"--mtime=@{commit_timestamp}",
                "--owner=0",
                "--group=0",
                "--numeric-owner",
                "-cf",
                str(tar_path),
                release_id,
            ],
            cwd=staging_parent,
        )
        temporary_output = output.with_suffix(output.suffix + ".tmp")
        temporary_output.unlink(missing_ok=True)
        run(
            [
                "zstd",
                "-19",
                "-T1",
                "--no-progress",
                "-f",
                str(tar_path),
                "-o",
                str(temporary_output),
            ]
        )
        os.replace(temporary_output, output)

        verify_internal_checksums(staging)
        record = {
            "schema_version": "flipguard_release_archive_record_v1",
            "archive": str(output),
            "archive_bytes": output.stat().st_size,
            "archive_sha256": sha256(output),
            "source_commit": commit,
            "tracked_source_files": len(tracked),
            "internal_checksum_entries": len(
                (staging / "SHA256SUMS").read_text().splitlines()
            ),
            "paper_artifacts_v3_manifest_sha256": manifest[
                "paper_artifacts_v3"
            ]["sha256"],
            "raw_external_sources_bundled": False,
            "new_encrypted_executions": 0,
            "policy_retuning": 0,
        }
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--release-id", default=ARCHIVE_NAME)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    record = build(
        args.repo_root.resolve(),
        args.source_commit,
        args.output,
        args.release_id,
    )
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_bytes(canonical_json(record))
    print(
        "release_candidate=BUILT "
        f"sha256={record['archive_sha256']} bytes={record['archive_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
