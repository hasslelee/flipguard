#!/usr/bin/env python3
"""Verify a frozen validation-identity audit without encrypted execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            "results/thesis_grade_protocol/validation_identity_audit_v2"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sums_path = args.root / "SHA256SUMS"
    expected_sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if name in expected_sums:
            raise ValueError(f"duplicate SHA256SUMS entry {name}")
        expected_sums[name] = digest
    required = {
        "validation_identity_matrix.csv",
        "mismatch_details.json",
        "summary.json",
        "verify_validation_identity_audit.py",
    }
    if set(expected_sums) != required:
        raise ValueError(
            f"SHA256SUMS entries {sorted(expected_sums)} != {sorted(required)}"
        )
    for name, expected in expected_sums.items():
        path = args.root / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{path}: digest mismatch")

    summary = load_json(args.root / "summary.json")
    if summary.get("schema_version") != 2:
        raise ValueError("unsupported validation identity audit schema")
    if summary.get("reason_code") != (
        "VALIDATION_IDENTITY_UNRESOLVED_FAIL_CLOSED"
    ):
        raise ValueError("original fail-closed reason was not preserved")
    with (args.root / "validation_identity_matrix.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != summary.get("workload_partition_instances"):
        raise ValueError("identity matrix row count mismatch")
    keys = {
        (
            int(row["split_seed"]),
            row["dataset_id"],
            row["model_id"],
        )
        for row in rows
    }
    if len(keys) != len(rows):
        raise ValueError("identity matrix contains duplicate workloads")
    classes = Counter(row["identity_class"] for row in rows)
    if dict(sorted(classes.items())) != summary.get(
        "identity_class_counts"
    ):
        raise ValueError("identity class counts do not match matrix")
    reruns = sum(
        row["encrypted_rerun_required"] == "true" for row in rows
    )
    if reruns != summary.get("encrypted_rerun_required_workloads"):
        raise ValueError("encrypted rerun count mismatch")
    original = next(
        (
            row
            for row in rows
            if row["split_seed"] == "0"
            and row["dataset_id"] == "banknote"
            and row["model_id"] == "linear_poly3"
        ),
        None,
    )
    if original is None:
        raise ValueError("original failing workload is absent")
    regression = summary.get("original_failing_workload_regression", {})
    if (
        original["identity_class"] != regression.get("identity_class")
        or original["validation_semantic_digest"]
        != regression.get("validation_semantic_digest")
    ):
        raise ValueError("original failing workload regression changed")
    print(
        "validation_identity_audit=VERIFIED "
        f"workloads={len(rows)} classes={dict(sorted(classes.items()))} "
        f"encrypted_rerun_required={reruns}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
