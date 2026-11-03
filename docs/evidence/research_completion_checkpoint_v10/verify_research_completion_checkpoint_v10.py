#!/usr/bin/env python3
"""Verify the immutable FlipGuard research completion checkpoint V10."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def find_repo_root(script: Path) -> Path:
    for candidate in (script.parent, *script.parents):
        if (
            (candidate / "go.mod").is_file()
            and (candidate / "docs/evidence").is_dir()
            and (candidate / "scripts").is_dir()
        ):
            return candidate
    raise ValueError(f"cannot locate FlipGuard repository from {script}")


ROOT = find_repo_root(Path(__file__).resolve())
DEFAULT_ROOT = Path("docs/evidence/research_completion_checkpoint_v10")
ALLOWED_STATES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "BLOCKED",
    "NOT_EVALUATED",
    "SUPERSEDED",
    "PILOT_ONLY",
}


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
    return json.loads(path.read_text(encoding="utf-8"))


def verify(root: Path, repo_root: Path, archive: Path | None = None) -> dict[str, Any]:
    manifest = load(root / "manifest.json")
    completion = load(root / "completion_state.json")
    release = load(root / "release_binding.json")
    auxiliary = load(root / "auxiliary_work.json")
    if manifest["schema_version"] != "flipguard_research_completion_checkpoint_v10":
        raise ValueError("V10 schema changed")
    if any(state != "PASS" for state in manifest["core_gates"].values()):
        raise ValueError("a mandatory V10 core gate is not PASS")
    policies = manifest["policies"]
    if (
        policies["direct_policy_digest"]
        != "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
        or policies["security_policy_digest"]
        != "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
        or sha256(repo_root / policies["direct_policy_artifact"]["path"])
        != policies["direct_policy_artifact"]["sha256"]
    ):
        raise ValueError("V10 frozen policy binding changed")
    if (
        not completion["core_development_complete"]
        or not completion["paper_artifacts_final_admissible"]
        or not completion["paper_writing_allowed"]
        or completion["remaining_core_blockers"]
    ):
        raise ValueError("V10 core completion flags are inconsistent")
    if completion["admitted_claim_count"] <= 0:
        raise ValueError("V10 admits no paper claims")
    if len(auxiliary) != completion["future_work_count"]:
        raise ValueError("V10 auxiliary count mismatch")
    if any(item["state"] not in ALLOWED_STATES for item in auxiliary):
        raise ValueError("V10 auxiliary state vocabulary changed")
    if any(item["blocking"] for item in auxiliary):
        raise ValueError("V10 auxiliary work incorrectly blocks core closure")
    for record in manifest["packs"].values():
        evidence_root = repo_root / record["path"]
        if (
            sha256(evidence_root / "manifest.json")
            != record["manifest_sha256"]
            or tree_sha256(evidence_root) != record["tree_sha256"]
        ):
            raise ValueError(f"{record['path']}: V10 evidence binding changed")
    for key in ("completion_state", "release_binding"):
        record = manifest[key]
        if sha256(root / record["path"]) != record["sha256"]:
            raise ValueError(f"V10 {key} changed")
    if (
        release["archive"]["archive_sha256"]
        != manifest["release_archive_sha256"]
        or release["clean_clone_verification"]["status"] != "PASS"
        or not release["clean_clone_verification"]["deterministic_rebuild"]
    ):
        raise ValueError("V10 release binding is not admissible")
    if archive is not None and sha256(archive) != manifest["release_archive_sha256"]:
        raise ValueError("V10 release archive digest mismatch")

    expected = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{sha256(path).removeprefix('sha256:')}  "
                f"{path.relative_to(root).as_posix()}\n"
            )
    if (root / "SHA256SUMS").read_text() != "".join(expected):
        raise ValueError("V10 SHA256SUMS mismatch")
    return completion


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    completion = verify(
        args.checkpoint_root.resolve(),
        args.repo_root.resolve(),
        args.archive.resolve() if args.archive else None,
    )
    print(
        "research_completion_checkpoint_v10=VERIFIED "
        f"paper_writing_allowed={str(completion['paper_writing_allowed']).lower()} "
        f"admitted_claims={completion['admitted_claim_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
