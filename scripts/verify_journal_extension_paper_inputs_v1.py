#!/usr/bin/env python3
"""Verify journal-extension publication inputs by deterministic rebuild."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from build_journal_extension_paper_inputs_v1 import SCHEMA, collect


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


PROHIBITED_AFFIRMATIVE_PATTERNS = {
    "global_optimum": r"\bglobal optimum\b",
    "universal_safety": r"\buniversally safe\b",
    "production_speedup": r"\bproduction speedup\b",
    "arbitrary_cnn_support": r"\barbitrary (?:packed )?cnn support\b",
    "all_audits_passed": r"\ball (?:standard-model )?locked audits passed\b",
    "independent_workload_inflation": r"\b50 independent workloads\b",
    "firstness": (
        r"\bfirst (?:ckks autotuner|direct ckks configuration synthesizer|"
        r"application-aware ckks configuration|repair-based selector)\b"
    ),
    "external_autotuner_generalization": r"\bgeneral external-autotuner support\b",
    "analytical_overclaim": r"\bcomplete analytical certificate\b",
    "extension_paired_speedup": r"\bpaired (?:journal )?extension speedup\b",
}


def prohibited_overclaims(files: dict[str, str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for name, text in sorted(files.items()):
        lowered = text.lower()
        for claim_id, pattern in PROHIBITED_AFFIRMATIVE_PATTERNS.items():
            if re.search(pattern, lowered):
                findings.append((name, claim_id))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="results/thesis_grade_protocol/journal_extension_paper_inputs_v1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == SCHEMA, "schema")
    require(manifest["frozen_core_modified"] is False, "frozen core")
    require(manifest["policy_retuning"] == 0, "policy retuning")
    for binding in manifest["inputs"]:
        require(digest(root / binding["path"]) == binding["sha256"], f"input {binding['path']}")
    try:
        replay = collect(root, manifest["source_commit"])["files"]
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise SystemExit("FAIL: replay: " + str(error)) from error
    require(set(replay) == set(manifest["generated_files"]), "generated file set")
    for name, content in replay.items():
        require((pack / name).read_text(encoding="utf-8") == content, f"replay {name}")
        require(digest(pack / name) == manifest["generated_files"][name]["sha256"], f"digest {name}")
    for line in (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        require(digest(pack / name) == "sha256:" + expected, f"SHA256SUMS {name}")
    publication_files = {
        str(path.relative_to(pack)): path.read_text(encoding="utf-8")
        for directory in ["tables", "figures", "publication_inputs"]
        for path in sorted((pack / directory).rglob("*"))
        if path.is_file()
    }
    require(not prohibited_overclaims(publication_files), "prohibited affirmative overclaim")
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    require(summary["tables"] == 8 and summary["figures"] == 8, "publication input count")
    require(summary["new_paired_latency_execution"] == 0, "new paired latency")
    require(summary["core_rc2_v3_v10_modified"] is False, "core modification")
    require(summary["formal_catalog_denominator"] == 14, "catalog denominator")
    print("PASS: journal extension paper inputs v1")
    print("manifest=" + digest(pack / "manifest.json"))


if __name__ == "__main__":
    main()
