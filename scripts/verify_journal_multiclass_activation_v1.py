#!/usr/bin/env python3
"""Fail-closed deterministic verifier for the multiclass activation overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freeze_journal_multiclass_activation_v1 import SCHEMA, collect


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="docs/evidence/journal_multiclass_activation_v1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == SCHEMA, "schema")
    require(manifest["frozen_core_modified"] is False, "frozen-core flag")
    require(manifest["policy_retuning"] == 0, "policy retuning")
    require(manifest["audit_based_change"] == 0, "audit-based change")
    for binding in manifest["inputs"]:
        require(digest(root / binding["path"]) == binding["sha256"], f"input {binding['path']}")
    for name, binding in manifest["generated_files"].items():
        require(digest(pack / name) == binding["sha256"], f"generated {name}")
    for line in (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        require(digest(pack / name) == "sha256:" + expected, f"SHA256SUMS {name}")
    try:
        replay = collect(root)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit("FAIL: replay: " + str(error)) from error
    for name in manifest["generated_files"]:
        require((pack / name).read_text(encoding="utf-8") == replay[name], f"replay {name}")
    summary = json.loads((pack / "activation_summary.json").read_text(encoding="utf-8"))
    require(summary["study_id"] == "natural_data_margin_literal_effect", "study ID")
    require(summary["activation_class"] in {
        "A_LITERAL_EFFECT_SUPPORTED", "B_ADMISSION_EFFECT_ONLY", "C_NO_OBSERVED_ACTIVATION"
    }, "activation class")
    require(summary["lenet_graph_only"]["encrypted_execution"] == 0, "LeNet graph-only execution")
    print("PASS: journal multiclass activation v1")
    print("manifest=" + digest(pack / "manifest.json"))


if __name__ == "__main__":
    main()
