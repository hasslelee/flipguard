#!/usr/bin/env python3
"""Verify the JKIISC content pack by a deterministic in-memory rebuild."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_flipguard_jkiisc_v1 import SCHEMA, build_manifest, collect, digest


def fail(message: str) -> None:
    raise SystemExit("FAIL: " + message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="results/journal/flipguard_jkiisc_v1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != SCHEMA:
        fail("schema")
    if manifest["artifact_status"] != "TEMPLATE_READY_AUTHORLESS_CONTENT_PACK":
        fail("status")
    if manifest["core_artifacts_modified"] or manifest["policy_retuning"] != 0:
        fail("immutable inputs")
    for binding in manifest["inputs"]:
        if digest(root / binding["path"]) != binding["sha256"]:
            fail("input binding " + binding["path"])
    replay = collect(root, manifest["content_source_commit"])
    expected_manifest = build_manifest(root, manifest["content_source_commit"], replay)
    if expected_manifest != manifest:
        fail("manifest replay")
    if set(replay) != set(manifest["generated_files"]):
        fail("generated set")
    for name, content in replay.items():
        path = pack / name
        if not path.is_file() or path.read_bytes() != content:
            fail("content replay " + name)
        if "sha256:" + hashlib.sha256(content).hexdigest() != manifest["generated_files"][name]["sha256"]:
            fail("content digest " + name)
    for line in (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        if hashlib.sha256((pack / name).read_bytes()).hexdigest() != expected:
            fail("SHA256SUMS " + name)
    lint = json.loads((pack / "lint_report.json").read_text(encoding="utf-8"))
    if lint["status"] != "PASS" or lint["findings"]:
        fail("lint")
    report = json.loads((pack / "build_report.json").read_text(encoding="utf-8"))
    if report["figures"] != 6 or report["tables"] != 7 or report["citations"] != 12:
        fail("counts")
    print("flipguard_jkiisc_v1=VERIFIED status=TEMPLATE_READY_AUTHORLESS_CONTENT_PACK")
    print("manifest=" + digest(pack / "manifest.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
