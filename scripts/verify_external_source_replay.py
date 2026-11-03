#!/usr/bin/env python3
"""Fail-closed verifier for clean-runner external source replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "flipguard_external_source_replay_v1"
EXPECTED_CHECKS = (
    "source_identity",
    "source_fetch",
    "mnist_export",
    "bsds500_sobel_export",
    "bsds500_harris_export",
    "static_graph_contracts",
    "git_diff_check",
    "final_clean_tree",
)
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    indexed = set()
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64:
            raise ValueError(f"malformed checksum line: {line}")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing checksum target: {relative}")
        require_equal(
            sha256_path(path),
            digest,
            f"checksum {relative}",
        )
        indexed.add(relative)
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(indexed, actual, "checksum coverage")


def verify(
    root: Path,
    expected_source_commit: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    verify_checksums(root)
    record = json.loads((root / "replay.json").read_text(encoding="ascii"))
    require_equal(record["schema_version"], SCHEMA_VERSION, "schema")
    require_equal(record["status"], "PASS", "replay status")
    require_equal(
        record["classification"],
        "INDEPENDENT_EXTERNAL_SOURCE_REPLAY",
        "classification",
    )
    if expected_source_commit is not None:
        require_equal(
            record["source_commit"],
            expected_source_commit,
            "source commit",
        )
    require_equal(
        tuple(check["name"] for check in record["checks"]),
        EXPECTED_CHECKS,
        "check ordering",
    )
    for check in record["checks"]:
        require_equal(check["status"], "PASS", f"{check['name']} status")
        require_equal(check["exit_code"], 0, f"{check['name']} exit")
        for stream in ("stdout", "stderr"):
            metadata = check[stream]
            path = root / metadata["path"]
            require_equal(
                sha256_path(path),
                metadata["sha256"],
                f"{check['name']} {stream} digest",
            )
            require_equal(
                path.stat().st_size,
                metadata["bytes"],
                f"{check['name']} {stream} bytes",
            )
    fetch_path = root / record["source_fetch"]["path"]
    require_equal(
        sha256_path(fetch_path),
        record["source_fetch"]["sha256"],
        "source-fetch manifest digest",
    )
    require_equal(
        record["scope"],
        {
            "source_datasets": ["MNIST", "BSDS500"],
            "deterministic_exporters": [
                "mnist_cnn_lite",
                "bsds500_sobel",
                "bsds500_harris",
            ],
            "static_graph_contracts": 3,
            "encrypted_smoke_test_executed": False,
            "ignored_execution_ledger_replay": "NOT_EVALUATED",
        },
        "source replay scope",
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
        record["encrypted_execution"],
        {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "encrypted execution accounting",
    )
    require_equal(record["paper_claim_allowed"], False, "paper gate")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    record = verify(args.result_dir, args.source_commit)
    print(
        "external_source_replay=VERIFIED "
        f"checks={len(record['checks'])}"
    )


if __name__ == "__main__":
    main()
