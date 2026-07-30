#!/usr/bin/env python3
"""Verify a FlipGuard independent-machine replay artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "flipguard_independent_machine_replay_v1"
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXPECTED_CHECKS = (
    "source_identity",
    "initial_clean_tree",
    "go_test",
    "go_vet",
    "python_unittest",
    "python_py_compile",
    "bash_syntax",
    "git_diff_check",
    "checkpoint_v1",
    "checkpoint_v2",
    "final_clean_tree",
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    if not checksum_path.is_file():
        raise ValueError("missing SHA256SUMS")
    indexed: set[str] = set()
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64:
            raise ValueError(f"malformed checksum line: {line}")
        if relative in indexed:
            raise ValueError(f"duplicate checksum path: {relative}")
        indexed.add(relative)
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing indexed file: {relative}")
        if sha256_path(path) != digest:
            raise ValueError(f"checksum mismatch: {relative}")
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if indexed != actual:
        raise ValueError(
            f"checksum coverage mismatch: indexed={sorted(indexed)} "
            f"actual={sorted(actual)}"
        )


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def verify(root: Path, expected_source_commit: str | None = None) -> None:
    root = root.resolve()
    verify_checksums(root)
    record = load_json(root / "replay.json")
    require_equal(record["schema_version"], SCHEMA_VERSION, "schema")
    require_equal(record["status"], "PASS", "replay status")
    require_equal(
        record["classification"],
        "INDEPENDENT_MACHINE_DETERMINISTIC_REPLAY",
        "classification",
    )
    if expected_source_commit is not None:
        require_equal(
            record["source_commit"],
            expected_source_commit,
            "source commit",
        )
    require_equal(
        record["policies"],
        {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "policy binding",
    )
    require_equal(
        tuple(item["name"] for item in record["checks"]),
        EXPECTED_CHECKS,
        "check ordering",
    )
    for item in record["checks"]:
        require_equal(item["status"], "PASS", f"{item['name']} status")
        require_equal(item["exit_code"], 0, f"{item['name']} exit")
        for stream in ("stdout", "stderr"):
            metadata = item[stream]
            path = root / metadata["path"]
            require_equal(
                sha256_path(path),
                metadata["sha256"],
                f"{item['name']} {stream} digest",
            )
            require_equal(
                path.stat().st_size,
                metadata["bytes"],
                f"{item['name']} {stream} size",
            )
    require_equal(
        record["encrypted_execution"],
        {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "encrypted execution accounting",
    )
    require_equal(
        record["paper_claim_allowed"],
        False,
        "paper claim gate",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    verify(args.result_dir, args.source_commit)
    print(
        "independent_machine_replay=VERIFIED "
        f"result_dir={args.result_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
