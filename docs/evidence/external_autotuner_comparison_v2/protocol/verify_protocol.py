#!/usr/bin/env python3
"""Fail-closed verifier for the pre-result external baseline protocol."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
PACK = Path(__file__).resolve().parent
ALLOWED_STATES = {
    "EXACT_NATIVE",
    "EXACT_PORTABLE",
    "SEMANTICALLY_MAPPABLE",
    "DIFFERENT_MODEL",
    "NO_BOOTSTRAP_NOT_APPLICABLE",
    "PLAN_UNSUPPORTED",
    "ARTIFACT_UNAVAILABLE",
    "BUILD_BLOCKED",
}


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bound_file(path_text: str, digest_text: str) -> None:
    path = REPO_ROOT / path_text
    if not path.is_file():
        raise SystemExit(f"missing bound workload file: {path_text}")
    actual = file_digest(path)
    if actual != digest_text:
        raise SystemExit(
            f"bound workload digest mismatch: {path_text}: {actual} != {digest_text}"
        )


def main() -> int:
    manifest = read_json(PACK / "manifest.json")
    policy = read_json(PACK / manifest["reproduction_policy"])
    if manifest["landscape_system_count"] != 20:
        raise SystemExit("landscape count is not frozen at 20")
    if len(policy["required_reproduction"]) != 8:
        raise SystemExit("required reproduction set is not frozen at eight")
    if policy["maximum_build_recovery_attempts"] != 3:
        raise SystemExit("build recovery budget changed")
    if policy["direct_policy"]["retuning_allowed"]:
        raise SystemExit("frozen direct policy retuning was enabled")

    with (PACK / manifest["applicability_matrix"]).open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != manifest["matrix_tool_count_including_flipguard"]:
        raise SystemExit("applicability matrix tool count mismatch")
    workload_columns = [
        "Sobel",
        "Harris",
        "MLP-100",
        "LeNet-5-small",
        "deeper_bootstrapping_workload",
    ]
    for row in rows:
        for column in workload_columns:
            if row[column] not in ALLOWED_STATES:
                raise SystemExit(
                    f"invalid applicability state {row[column]} for {row['tool']} {column}"
                )

    for relative in manifest["workload_contracts"]:
        contract = read_json(PACK / relative)
        model = contract["model"]
        verify_bound_file(model["path"], model["sha256"])
        inputs = contract["inputs"]
        verify_bound_file(
            inputs["configuration_validation"],
            inputs["configuration_validation_sha256"],
        )
        verify_bound_file(inputs["locked_audit"], inputs["locked_audit_sha256"])
        if inputs.get("overlap", 0) != 0 or inputs.get("overlap_allowed", False):
            raise SystemExit(f"validation/audit overlap admitted by {relative}")

    print(
        "external_autotuner_protocol_v2=PASS "
        f"systems={manifest['landscape_system_count']} "
        f"required={len(policy['required_reproduction'])} "
        f"contracts={len(manifest['workload_contracts'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
