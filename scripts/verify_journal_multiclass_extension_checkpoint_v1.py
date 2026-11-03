#!/usr/bin/env python3
"""Verify the immutable pre-reconciliation journal multiclass checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_extension_checkpoint_v1"
SOURCE_COMMIT = "affc38b54f5abed8b491442fbed4b74949c2a05b"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_sha256sums(pack: Path) -> None:
    expected = []
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{digest(path).removeprefix('sha256:')}  {path.relative_to(pack)}\n"
            )
    require(
        (pack / "SHA256SUMS").read_text(encoding="utf-8") == "".join(expected),
        "checkpoint SHA256SUMS mismatch",
    )


def verify(pack: Path, repo: Path) -> dict:
    manifest = load(pack / "manifest.json")
    checkpoint = load(pack / "checkpoint.json")
    require(manifest["schema_version"] == SCHEMA, "checkpoint manifest schema")
    require(checkpoint["schema_version"] == SCHEMA, "checkpoint schema")
    require(manifest["source_commit"] == SOURCE_COMMIT, "checkpoint source commit")
    require(checkpoint["source_commit"] == SOURCE_COMMIT, "checkpoint source binding")
    require(manifest["new_encrypted_execution"] == 0, "checkpoint encrypted execution")
    require(manifest["policy_retuning"] == 0, "checkpoint policy retuning")
    require(manifest["pre_security_reconciliation"] is True, "checkpoint role")
    require(digest(pack / "checkpoint.json") == manifest["checkpoint_sha256"], "checkpoint digest")

    for binding in manifest["input_bindings"]:
        path = repo / binding["path"]
        require(path.is_file(), f"missing checkpoint input: {binding['path']}")
        require(digest(path) == binding["sha256"], f"changed checkpoint input: {binding['path']}")

    models = checkpoint["models"]
    mlp = models["mlp_100"]
    lenet = models["lenet5_small"]
    require(mlp["validation"] == "SAFE" and mlp["locked_audit"] == "SAFE", "MLP status")
    require(lenet["validation"] == "SAFE" and lenet["locked_audit"] == "SAFE", "LeNet status")
    require(mlp["argmax_flips"] == 0 and lenet["argmax_flips"] == 0, "checkpoint flips")
    require(mlp["direct_literal"]["log_default_scale"] == 29, "MLP direct S29")
    require(mlp["graph_only_literal"]["log_default_scale"] == 32, "MLP graph-only S32")
    require(
        lenet["catalog_status"] == "PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG",
        "LeNet catalog status",
    )
    security = checkpoint["security_state"]
    require(
        security["global_exact_estimator_run_status"] == "FALSIFIED_UNDER_ESTIMATOR_MODEL",
        "original estimator status not preserved",
    )
    require(
        security["journal_candidate_attribution"] == "NOT_ESTABLISHED_AT_CHECKPOINT",
        "pre-reconciliation estimator attribution",
    )
    require(checkpoint["extension_paired_latency"] == "BLOCKED_NOT_EVALUATED", "latency status")

    subprocess.run(
        ["git", "cat-file", "-e", f"{SOURCE_COMMIT}^{{commit}}"],
        cwd=repo,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    verify_sha256sums(pack)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack",
        type=Path,
        default=Path("docs/evidence/journal_multiclass_extension_checkpoint_v1"),
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = verify(args.pack.resolve(), args.repo.resolve())
    print(
        "journal_multiclass_extension_checkpoint_v1=VERIFIED "
        f"source_commit={manifest['source_commit']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
