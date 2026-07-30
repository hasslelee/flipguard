#!/usr/bin/env python3
"""Build a non-retroactive, build-aware FlipGuard source closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "flipguard_source_closure_v2"
DEFAULT_ENTRYPOINTS = (
    "./cmd/flipguard",
    "./cmd/flipguard-autotune",
    "./cmd/flipguard-audit",
    "./cmd/flipguard-paired-latency",
)
REPOSITORY_ASSURANCE_ROOTS = (
    ".github/workflows",
    "cmd",
    "internal",
    "research",
    "scripts",
)
REPOSITORY_ASSURANCE_FILES = (
    "AGENTS.md",
    "go.mod",
    "go.sum",
)
PACKAGE_SOURCE_FIELDS = (
    "GoFiles",
    "CgoFiles",
    "CFiles",
    "CXXFiles",
    "MFiles",
    "HFiles",
    "FFiles",
    "SFiles",
    "SwigFiles",
    "SwigCXXFiles",
    "SysoFiles",
    "EmbedFiles",
)


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


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def run(
    arguments: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=text,
    )


def git_text(*arguments: str) -> str:
    return run(["git", *arguments]).stdout.strip()


def tracked_paths(
    roots: Iterable[str],
    files: Iterable[str] = (),
) -> list[Path]:
    arguments = ["git", "ls-files", "-z", "--", *roots, *files]
    output = run(arguments, text=False).stdout
    return sorted(
        Path(value.decode("utf-8"))
        for value in output.split(b"\0")
        if value
    )


def bindings(paths: Iterable[Path]) -> dict[str, str]:
    records: dict[str, str] = {}
    for relative in sorted(set(paths)):
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe source path: {relative}")
        source = REPO_ROOT / relative
        if not source.is_file():
            raise ValueError(f"source path is not a file: {relative}")
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative.as_posix()],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise ValueError(f"source path is not tracked: {relative}")
        records[relative.as_posix()] = sha256_path(source)
    return records


def decode_json_stream(value: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    offset = 0
    records = []
    while True:
        while offset < len(value) and value[offset].isspace():
            offset += 1
        if offset == len(value):
            return records
        record, offset = decoder.raw_decode(value, offset)
        if not isinstance(record, dict):
            raise ValueError("go list stream contains a non-object")
        records.append(record)


def go_packages(entrypoints: Iterable[str]) -> list[dict[str, Any]]:
    selected = tuple(entrypoints)
    if not selected:
        raise ValueError("at least one Go entrypoint is required")
    output = run(
        ["go", "list", "-deps", "-json", *selected]
    ).stdout
    return decode_json_stream(output)


def relative_repo_path(path: Path) -> Path:
    candidate = path if path.is_absolute() else REPO_ROOT / path
    resolved = candidate.resolve()
    try:
        return resolved.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError(f"path is outside repository: {path}") from error


def go_build_closure(
    entrypoints: Iterable[str],
) -> tuple[dict[str, str], list[str]]:
    package_paths: set[Path] = {Path("go.mod"), Path("go.sum")}
    package_names = []
    for package in go_packages(entrypoints):
        directory_text = package.get("Dir")
        if not directory_text:
            continue
        directory = Path(directory_text).resolve()
        try:
            relative_directory = directory.relative_to(REPO_ROOT)
        except ValueError:
            continue
        package_names.append(package["ImportPath"])
        for field in PACKAGE_SOURCE_FIELDS:
            for name in package.get(field, []):
                package_paths.add(relative_directory / name)
    return bindings(package_paths), sorted(package_names)


def explicit_bindings(paths: Iterable[Path]) -> dict[str, str]:
    return bindings(relative_repo_path(path) for path in paths)


def repository_assurance_bindings() -> dict[str, str]:
    return bindings(
        tracked_paths(
            REPOSITORY_ASSURANCE_ROOTS,
            REPOSITORY_ASSURANCE_FILES,
        )
    )


def go_environment() -> dict[str, str]:
    keys = ("GOOS", "GOARCH", "GOVERSION", "CGO_ENABLED")
    values = run(["go", "env", *keys]).stdout.splitlines()
    if len(values) != len(keys):
        raise ValueError("unexpected go env output")
    return dict(zip(keys, values, strict=True))


def require_clean_tree() -> None:
    status = git_text("status", "--short")
    if status:
        raise ValueError(
            "source closure requires a clean working tree:\n" + status
        )


def build_manifest(
    *,
    entrypoints: Iterable[str],
    orchestrators: Iterable[Path],
    policy_inputs: Iterable[Path],
    comparison_sources: Iterable[Path],
    require_clean: bool,
) -> dict[str, Any]:
    if require_clean:
        require_clean_tree()
    entrypoint_list = tuple(entrypoints)
    build_files, packages = go_build_closure(entrypoint_list)
    orchestration_files = explicit_bindings(orchestrators)
    policy_files = explicit_bindings(policy_inputs)
    comparison_files = explicit_bindings(comparison_sources)
    repository_files = repository_assurance_bindings()
    execution_layers = {
        "go_default_build_files": build_files,
        "orchestration_files": orchestration_files,
        "policy_input_files": policy_files,
    }
    test_files = sorted(
        path for path in repository_files if path.endswith("_test.go")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "semantics": {
            "non_retroactive": True,
            "historical_evidence_reinterpreted": False,
            "execution_closure": (
                "Go default-build dependency files plus explicitly bound "
                "orchestrators and policy inputs"
            ),
            "comparison_closure": "explicitly bound comparison/report files",
            "repository_assurance": (
                "tracked implementation, test, workflow, and research "
                "support files"
            ),
        },
        "source_commit": git_text("rev-parse", "HEAD"),
        "entrypoints": list(entrypoint_list),
        "go_environment": go_environment(),
        "execution_critical": {
            "digest": canonical_digest(execution_layers),
            "go_packages": packages,
            "go_default_build_files": build_files,
            "orchestration_files": orchestration_files,
            "policy_input_files": policy_files,
        },
        "comparison_report": {
            "digest": canonical_digest(comparison_files),
            "files": comparison_files,
        },
        "repository_assurance": {
            "digest": canonical_digest(repository_files),
            "files": repository_files,
            "tracked_test_files": test_files,
        },
        "accounting": {
            "execution_go_packages": len(packages),
            "execution_go_files": len(build_files),
            "execution_orchestrator_files": len(orchestration_files),
            "execution_policy_input_files": len(policy_files),
            "comparison_report_files": len(comparison_files),
            "repository_assurance_files": len(repository_files),
            "repository_test_files": len(test_files),
        },
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite source closure: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(manifest))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--entrypoint",
        action="append",
        dest="entrypoints",
    )
    parser.add_argument(
        "--orchestrator",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--policy-input",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--comparison-source",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument("--verify", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if bool(args.output) == bool(args.verify):
        raise ValueError("choose exactly one of --output or --verify")
    manifest = build_manifest(
        entrypoints=args.entrypoints or DEFAULT_ENTRYPOINTS,
        orchestrators=args.orchestrator,
        policy_inputs=args.policy_input,
        comparison_sources=args.comparison_source,
        require_clean=True,
    )
    if args.verify:
        expected = json.loads(args.verify.read_text(encoding="ascii"))
        if manifest != expected:
            raise ValueError("source closure does not match current source")
        print(
            "source_closure_v2=VERIFIED "
            f"execution_digest={manifest['execution_critical']['digest']}"
        )
        return
    write_manifest(args.output, manifest)
    print(
        "source_closure_v2=GENERATED "
        f"execution_digest={manifest['execution_critical']['digest']}"
    )


if __name__ == "__main__":
    main()
