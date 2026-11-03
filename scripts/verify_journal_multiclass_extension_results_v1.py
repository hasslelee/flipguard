#!/usr/bin/env python3
"""Fail-closed replay verifier for journal multiclass result summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freeze_journal_multiclass_results_v1 import collect


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
        default="docs/evidence/journal_multiclass_extension_results_v1",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = load(pack / "manifest.json")
    require(manifest["schema_version"] == "flipguard_journal_multiclass_extension_results_v1", "schema")
    require(manifest["policy_retuning"] == 0, "policy retuning")
    require(manifest["frozen_core_modified"] is False, "frozen core flag")
    for bindings in manifest["raw_inputs"].values():
        for binding in bindings:
            require(digest(root / binding["path"]) == binding["sha256"], f"raw input {binding['path']}")
    require(digest(root / manifest["analysis_plan"]["path"]) == manifest["analysis_plan"]["sha256"], "analysis plan")
    for name, binding in manifest["generated_files"].items():
        require(digest(pack / name) == binding["sha256"], f"generated digest {name}")
    for line in (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        require(digest(pack / name) == "sha256:" + expected, f"SHA256SUMS {name}")
    try:
        replay = collect(root, manifest["execution_source_commit"])
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        raise SystemExit("FAIL: replay: " + str(error)) from error
    for name in manifest["generated_files"]:
        require((pack / name).read_text(encoding="utf-8") == replay[name], f"deterministic replay {name}")
    summary = load(pack / "summary.json")
    require(summary["combined"]["models"] == 2, "model count")
    require(summary["combined"]["security_v2_bounded_catalog_denominator"] == 14, "catalog denominator")
    require(summary["combined"]["direct_trials"] == 2, "direct trials")
    require(summary["audit_retuning"] == 0, "audit retuning")
    print("PASS: journal multiclass extension results v1")
    print("manifest=" + digest(pack / "manifest.json"))


if __name__ == "__main__":
    main()
