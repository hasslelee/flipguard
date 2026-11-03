#!/usr/bin/env python3
"""Fail-closed verifier for the validation-only multiclass analysis plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_journal_multiclass_analysis_plan_v1 import midpoint_boundaries, validation_gaps


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack",
        default="docs/evidence/journal_multiclass_analysis_plan_v1",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = load(pack / "manifest.json")
    plan = load(pack / "analysis_plan.json")
    require(
        plan["schema_version"] == "flipguard_journal_multiclass_analysis_plan_v1",
        "schema",
    )
    require(plan["audit_artifact_used_to_choose_rules"] is False, "audit leakage flag")
    require(plan["gap_bin_policy"]["bin_count"] == 5, "bin count")
    require(
        manifest["analysis_plan"]["sha256"] == digest(pack / "analysis_plan.json"),
        "manifest digest",
    )
    for line in (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        require(digest(pack / name) == "sha256:" + expected, f"SHA256SUMS {name}")
    for short_name, bindings in plan["inputs"].items():
        for label, binding in bindings.items():
            require(digest(root / binding["path"]) == binding["sha256"], f"{short_name} {label}")
        key_run = load(root / bindings["validation_key_run_01"]["path"])
        recomputed = midpoint_boundaries(validation_gaps(key_run))
        require(
            recomputed == plan["models"][short_name]["boundary_values"],
            f"{short_name} boundaries",
        )
        require(plan["models"][short_name]["validation_sample_count"] == 500, f"{short_name} size")
    print("PASS: journal multiclass analysis plan v1")
    print("analysis_plan=" + digest(pack / "analysis_plan.json"))


if __name__ == "__main__":
    main()
