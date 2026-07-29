#!/usr/bin/env python3
"""Build and verify the mixed-commit confirmatory resume provenance gate."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
    "resume_provenance"
)
DEFAULT_EXECUTION_COMMIT = (
    "ebbdcb0112ea6dfeb6115239cba812e4d2707650"
)
IDENTITY_CHECKPOINT_COMMIT = (
    "7f7d30c3f544096c25a65e46189cc2ff77bca819"
)
RUN_MANIFEST = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
    "run_manifest/run_manifest.json"
)
CRITICAL_PREFIXES = (
    "cmd/flipguard/",
    "cmd/flipguard-autotune/",
    "cmd/flipguard-audit/",
    "cmd/flipguard-paired-latency/",
    "internal/",
)
COMPARISON_PATHS = (
    "cmd/flipguard-validation-identity/main.go",
    "internal/ckksplanner/validation_identity.go",
    "scripts/build_confirmatory_run_manifest.py",
    "scripts/build_resume_execution_provenance.py",
    "scripts/build_validation_identity_audit.py",
    "scripts/compare_direct_synthesis_to_catalog_oracle.py",
    "scripts/freeze_validation_identity_comparison_evidence.py",
    "scripts/run_thesis_final_confirmatory_suite.sh",
    "scripts/verify_validation_identity_audit.py",
    "scripts/verify_validation_identity_comparison_evidence.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--execution-source-commit",
        default=DEFAULT_EXECUTION_COMMIT,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def command(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def git_paths(commit: str) -> list[str]:
    output = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", commit],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [
        item.decode("utf-8")
        for item in output.split(b"\0")
        if item
    ]


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def excluded_from_default_build(path: str, data: bytes) -> bool:
    if path.endswith("_test.go"):
        return True
    if not path.endswith(".go"):
        return False
    header = b"\n".join(data.splitlines()[:8])
    return b"//go:build validationidentity" in header


def critical_bindings(commit: str) -> tuple[dict[str, str], list[str]]:
    bindings: dict[str, str] = {}
    excluded: list[str] = []
    for path in git_paths(commit):
        selected = (
            path in {"go.mod", "go.sum"}
            or any(path.startswith(prefix) for prefix in CRITICAL_PREFIXES)
        )
        if not selected or (
            path.endswith(".go") is False
            and path not in {"go.mod", "go.sum"}
        ):
            continue
        data = git_bytes(commit, path)
        if excluded_from_default_build(path, data):
            excluded.append(path)
            continue
        bindings[path] = sha256_bytes(data)
    return bindings, sorted(excluded)


def bindings_digest(bindings: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(bindings.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def comparison_bindings(commit: str) -> dict[str, str]:
    return {
        path: sha256_bytes(git_bytes(commit, path))
        for path in COMPARISON_PATHS
    }


def build_execution_flipguard(
    execution_commit: str,
    output_binary: Path,
) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", execution_commit],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(
        prefix="flipguard-execution-source-",
        dir="/tmp",
    ) as temporary:
        source_root = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as handle:
            handle.extractall(source_root, filter="data")
        output_binary.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["GOCACHE"] = (
            "/tmp/flipguard-resume-provenance-gocache"
        )
        subprocess.run(
            [
                "go",
                "build",
                "-buildvcs=false",
                "-trimpath",
                "-o",
                str(output_binary),
                "./cmd/flipguard",
            ],
            cwd=source_root,
            env=environment,
            check=True,
        )


def source_clean() -> bool:
    return not command(
        "git",
        "status",
        "--porcelain",
        "--",
        "cmd",
        "internal",
        "scripts",
        "go.mod",
        "go.sum",
    )


def generate(args: argparse.Namespace) -> None:
    output = (REPO_ROOT / args.output_root).resolve()
    if output.exists():
        if not args.force:
            raise ValueError(f"{output} exists; use --force")
        shutil.rmtree(output)
    if not source_clean():
        raise ValueError("resume provenance requires clean source")
    current_commit = command("git", "rev-parse", "HEAD")
    baseline, baseline_excluded = critical_bindings(
        args.execution_source_commit
    )
    current, current_excluded = critical_bindings(current_commit)
    baseline_digest = bindings_digest(baseline)
    current_digest = bindings_digest(current)
    if baseline != current or baseline_digest != current_digest:
        changed = sorted(set(baseline) ^ set(current) | {
            path
            for path in set(baseline) & set(current)
            if baseline[path] != current[path]
        })
        raise ValueError(
            f"execution-critical default-build closure changed: {changed}"
        )

    run_manifest_path = REPO_ROOT / RUN_MANIFEST
    run_manifest = load_json(run_manifest_path)
    if run_manifest["execution_source_commit"] != (
        args.execution_source_commit
    ):
        raise ValueError("run manifest execution commit mismatch")
    for record in run_manifest["binaries"].values():
        path = REPO_ROOT / record["path"]
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"{path}: frozen binary changed")

    flipguard_binary = output / "binaries/flipguard"
    build_execution_flipguard(
        args.execution_source_commit,
        flipguard_binary,
    )
    comparison = comparison_bindings(current_commit)
    manifest = {
        "schema_version": 1,
        "provenance_id": "flipguard_confirmatory_resume_provenance_v1",
        "execution_source_commit": args.execution_source_commit,
        "validation_identity_audit_commit":
            IDENTITY_CHECKPOINT_COMMIT,
        "current_suite_commit": current_commit,
        "execution_critical_source_digest": current_digest,
        "baseline_execution_critical_source_digest": baseline_digest,
        "comparison_source_digest": bindings_digest(comparison),
        "execution_critical_source_unchanged": True,
        "default_build_exclusions": current_excluded,
        "baseline_default_build_exclusions": baseline_excluded,
        "execution_critical_files": current,
        "comparison_files": comparison,
        "run_manifest": {
            "path": str(RUN_MANIFEST),
            "sha256": sha256_file(run_manifest_path),
        },
        "frozen_binaries": run_manifest["binaries"],
        "resume_flipguard_binary": {
            "path": str(flipguard_binary.relative_to(REPO_ROOT)),
            "sha256": sha256_file(flipguard_binary),
            "build": "go build -buildvcs=false -trimpath ./cmd/flipguard",
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "resume_provenance.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "SHA256SUMS").write_text(
        f"{sha256_file(flipguard_binary).removeprefix('sha256:')}  "
        "binaries/flipguard\n"
        f"{sha256_file(manifest_path).removeprefix('sha256:')}  "
        "resume_provenance.json\n",
        encoding="utf-8",
    )


def verify(args: argparse.Namespace) -> None:
    output = (REPO_ROOT / args.output_root).resolve()
    manifest_path = output / "resume_provenance.json"
    manifest = load_json(manifest_path)
    current_commit = command("git", "rev-parse", "HEAD")
    if manifest["current_suite_commit"] != current_commit:
        raise ValueError("resume suite commit changed")
    baseline, _ = critical_bindings(args.execution_source_commit)
    current, exclusions = critical_bindings(current_commit)
    if (
        baseline != current
        or bindings_digest(current)
        != manifest["execution_critical_source_digest"]
        or exclusions != manifest["default_build_exclusions"]
    ):
        raise ValueError("execution-critical source closure changed")
    comparison = comparison_bindings(current_commit)
    if bindings_digest(comparison) != manifest[
        "comparison_source_digest"
    ]:
        raise ValueError("comparison source closure changed")
    binary = REPO_ROOT / manifest["resume_flipguard_binary"]["path"]
    if sha256_file(binary) != manifest[
        "resume_flipguard_binary"
    ]["sha256"]:
        raise ValueError("resume flipguard binary changed")
    recorded = (output / "SHA256SUMS").read_text(
        encoding="utf-8"
    )
    expected = (
        f"{sha256_file(binary).removeprefix('sha256:')}  "
        "binaries/flipguard\n"
        f"{sha256_file(manifest_path).removeprefix('sha256:')}  "
        "resume_provenance.json\n"
    )
    if recorded != expected:
        raise ValueError("resume provenance SHA256SUMS changed")
    print(
        "resume_execution_provenance=VERIFIED "
        f"execution_commit={args.execution_source_commit} "
        f"suite_commit={current_commit} "
        f"source_digest={manifest['execution_critical_source_digest']}"
    )


def main() -> int:
    args = parse_args()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        verify(args)
        return 0
    generate(args)
    verify(args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
