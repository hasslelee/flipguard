#!/usr/bin/env python3
"""Verify the frozen validation-identity/comparator-v2 evidence pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(
            "docs/evidence/validation_identity_comparison_v2"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected: dict[str, str] = {}
    for line in (args.root / "SHA256SUMS").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = "sha256:" + digest
    actual_files = {
        str(path.relative_to(args.root))
        for path in args.root.rglob("*")
        if path.is_file() and path != args.root / "SHA256SUMS"
    }
    if set(expected) != actual_files:
        raise ValueError("SHA256SUMS file inventory mismatch")
    for name, digest in expected.items():
        if sha256_file(args.root / name) != digest:
            raise ValueError(f"{name}: digest mismatch")

    manifest = load_json(args.root / "manifest.json")
    identity = load_json(args.root / "identity/summary.json")
    comparison = load_json(args.root / "comparison/summary.json")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "SUPPORTED_CLASS_A_NO_RERUN"
        or manifest.get("paper_claim_allowed") is not False
    ):
        raise ValueError("evidence manifest status is invalid")
    if identity.get("encrypted_rerun_required_workloads") != 0:
        raise ValueError("identity audit requires encrypted rerun")
    if identity.get("identity_class_counts") != {
        "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER": 50
    }:
        raise ValueError("identity class count changed")
    if (
        comparison.get("schema_version") != 2
        or comparison.get(
            "direct_vs_security_v2_catalog_comparison_schema"
        )
        != 2
        or comparison.get("complete_oracle_workloads_compared") != 50
        or comparison.get("security_admitted_catalog_candidates") != 700
        or comparison.get("security_excluded_catalog_candidates") != 400
        or comparison.get("raw_catalog_executions") != 1100
    ):
        raise ValueError("strict comparison accounting is invalid")
    if (
        manifest["encrypted_execution_commit"]
        != identity["execution_source_commit"]
        or manifest["comparator_commit"]
        != comparison["comparison_builder_commit"]
        or manifest["comparator_commit"]
        != identity["comparison_builder_commit"]
    ):
        raise ValueError("execution/comparator provenance mismatch")
    print(
        "validation_identity_comparison_evidence=VERIFIED "
        "workloads=50 class_a=50 reruns=0 catalog_candidates=700"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
