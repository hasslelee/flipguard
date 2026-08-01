#!/usr/bin/env python3
"""Verify the immutable FlipGuard RC2 research-release binding overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = Path("docs/evidence/research_release_binding_rc2_v1")
RC1_TAG = "flipguard-thesis-v1.0.0-rc1"
RC2_TAG = "flipguard-thesis-v1.0.0-rc2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def verify(root: Path, repo: Path, archive: Path | None) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    binding = load(root / "release_binding_rc2.json")
    predecessor = load(root / "predecessor_binding.json")
    if manifest["schema_version"] != "flipguard_research_release_binding_rc2_v1":
        raise ValueError("RC2 overlay schema changed")
    if (
        manifest["new_encrypted_executions"] != 0
        or manifest["policy_retuning"] != 0
        or not manifest["thesis_release_baseline"]
    ):
        raise ValueError("RC2 overlay changes the frozen research contract")

    for key in ("v10", "paper_artifacts_v3", "claim_admission"):
        record = binding[key]
        if sha256(repo / record["manifest_path"]) != record["manifest_sha256"]:
            raise ValueError(f"{key}: bound manifest digest changed")

    rc1_commit = git(repo, "rev-parse", f"{RC1_TAG}^{{commit}}")
    rc2_commit = git(repo, "rev-parse", f"{RC2_TAG}^{{commit}}")
    if rc1_commit != predecessor["rc1"]["tag_commit"]:
        raise ValueError("RC1 tag identity changed")
    if rc2_commit != binding["source_commit"]:
        raise ValueError("RC2 tag/source identity changed")
    changed = git(
        repo,
        "diff",
        "--name-only",
        f"{RC1_TAG}^{{commit}}..{RC2_TAG}^{{commit}}",
    ).splitlines()
    if changed != predecessor["rc2_allowed_changed_paths"]:
        raise ValueError("RC1-to-RC2 changed-path closure changed")

    archive_record = binding["archive"]
    candidate = archive
    if candidate is None:
        default_archive = repo / archive_record["path"]
        candidate = default_archive if default_archive.is_file() else None
    archive_status = "BOUND_NOT_PRESENT"
    if candidate is not None:
        if (
            not candidate.is_file()
            or candidate.stat().st_size != archive_record["bytes"]
            or sha256(candidate) != archive_record["sha256"]
        ):
            raise ValueError("RC2 archive binding mismatch")
        archive_status = "VERIFIED"

    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(
                f"{sha256(path).removeprefix('sha256:')}  "
                f"{path.relative_to(root).as_posix()}\n"
            )
    if (root / "SHA256SUMS").read_text(encoding="ascii") != "".join(lines):
        raise ValueError("RC2 overlay SHA256SUMS mismatch")
    return {
        "status": "PASS",
        "source_commit": rc2_commit,
        "archive_status": archive_status,
        "new_encrypted_executions": 0,
        "policy_retuning": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    result = verify(
        args.binding_root.resolve(),
        args.repo_root.resolve(),
        args.archive.resolve() if args.archive else None,
    )
    print(
        "research_release_binding_rc2=VERIFIED "
        f"archive={result['archive_status']} "
        f"source_commit={result['source_commit']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
