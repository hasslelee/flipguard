#!/usr/bin/env python3
"""Fail-closed verifier for the final manuscript audit overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REQUIRED_EVIDENCE = {
    "manifest.json",
    "dependency_manifest.json",
    "authoritative_number_registry.json",
    "clean_clone_audit.json",
    "final_audit_summary.json",
    "SHA256SUMS",
}
REQUIRED_REVIEW = {
    "EXECUTIVE_SUMMARY.md", "MANUSCRIPT_REVIEW_ISSUES.md", "PROPOSED_PATCHES.md",
    "claim_sentence_traceability.csv", "formal_definition_audit.md",
    "table_figure_source_binding.csv", "citation_audit.csv", "reviewer_attack_matrix.md",
    "THESIS_DEFENSE_QA.md", "ONE_PAGE_DEFENSE_CHEATSHEET.md", "ADVISOR_BRIEFING_2MIN.md",
    "DEMO_SCRIPT_5MIN.md", "PRESENTATION_OUTLINES.md", "KIISC_SUBMISSION_CHECKLIST.md",
    "THESIS_SUBMISSION_CHECKLIST.md",
}
REQUIRED_REPRO = {
    "QUICKSTART.md", "FULL_REPRODUCTION.md", "ARTIFACT_EVALUATION_GUIDE.md",
    "EXPECTED_OUTPUTS.md", "ENVIRONMENT_LOCK.json", "THIRD_PARTY_LICENSES.md",
    "RELEASE_CHECKLIST.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"final_manuscript_audit_v1=FAILED reason={message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--allow-clean-clone-pending", action="store_true")
    args = parser.parse_args()
    root = args.repo.resolve()
    evidence = root / "docs/evidence/final_manuscript_audit_v1"
    review = root / "docs/review/final_manuscript_audit_v1"
    repro = root / "docs/reproducibility/final_release_readiness_v1"

    for directory, required in ((evidence, REQUIRED_EVIDENCE), (review, REQUIRED_REVIEW), (repro, REQUIRED_REPRO)):
        missing = sorted(name for name in required if not (directory / name).is_file())
        if missing:
            fail(f"missing_files:{directory}:{','.join(missing)}")

    checksum_path = evidence / "SHA256SUMS"
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split("  ", 1)
        target = root / rel
        if not target.is_file():
            fail(f"checksum_target_missing:{rel}")
        if sha256(target) != expected:
            fail(f"checksum_mismatch:{rel}")

    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((evidence / "final_audit_summary.json").read_text(encoding="utf-8"))
    registry = json.loads((evidence / "authoritative_number_registry.json").read_text(encoding="utf-8"))
    clean_clone = json.loads((evidence / "clean_clone_audit.json").read_text(encoding="utf-8"))
    if manifest["source_commit"] != "98e5e4105c0b0597d6fb245b5718a00eb4828349":
        fail("source_commit")
    if manifest["manuscript_files_modified"] != 0 or manifest["new_experimental_runs"] != 0:
        fail("immutable_boundary")
    if summary["numeric_mismatches"] != 1 or "NUM-CONFLICT-001" not in summary["numeric_mismatch_ids"]:
        fail("numeric_conflict_not_preserved")
    if summary["reviewer_questions"] < 40 or summary["defense_questions"] < 60:
        fail("question_count")
    if registry["number_count"] != len(registry["numbers"]):
        fail("number_registry_count")
    if clean_clone.get("status") != "PASS" and not args.allow_clean_clone_pending:
        fail("clean_clone_not_pass")

    with (review / "claim_sentence_traceability.csv").open(encoding="utf-8", newline="") as handle:
        trace = list(csv.DictReader(handle))
    documents = {row["document"] for row in trace}
    if documents != {"journal_v10", "thesis_v10"}:
        fail(f"trace_documents:{sorted(documents)}")
    with (review / "table_figure_source_binding.csv").open(encoding="utf-8", newline="") as handle:
        bindings = list(csv.DictReader(handle))
    if len(bindings) != 54 or any(row["binding_status"] != "BOUND" for row in bindings):
        fail("table_figure_binding")
    with (review / "citation_audit.csv").open(encoding="utf-8", newline="") as handle:
        citations = list(csv.DictReader(handle))
    if len(citations) != 21:
        fail("citation_count")
    title_errors = {row["citation_key"] for row in citations if row["metadata_consistency"] == "TITLE_MISMATCH_IN_DOCX_P0"}
    if title_errors != {"orion2025", "lohen2025", "slothe2025"}:
        fail("citation_title_errors_not_preserved")

    print(
        "final_manuscript_audit_v1=VERIFIED "
        f"numbers={registry['number_count']} trace_rows={len(trace)} assets={len(bindings)} "
        f"citations={len(citations)} clean_clone={clean_clone.get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
