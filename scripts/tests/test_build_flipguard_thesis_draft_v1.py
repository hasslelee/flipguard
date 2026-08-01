#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_flipguard_thesis_draft_v1.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("build_flipguard_thesis_draft_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ThesisDraftBuilderTest(unittest.TestCase):
    def test_claim_traceability_covers_all_admitted_claims(self) -> None:
        rows = MODULE.claim_traceability_rows(MODULE.canonical_commit("HEAD"))
        claim_ids = {row["claim_id"] for row in rows}
        self.assertEqual(claim_ids, set(MODULE.CLAIM_ASSET))
        self.assertTrue(all(row["paper_admitted"] == "true" for row in rows))

    def test_figure_table_map_is_complete_and_resolved(self) -> None:
        rows = MODULE.updated_figure_map()
        self.assertEqual(len(rows), 23)
        self.assertTrue(all(row["first_reference_line"].isdigit() for row in rows))

    def test_source_closure_is_bound_to_head(self) -> None:
        commit = MODULE.canonical_commit("HEAD")
        digest = MODULE.source_closure_digest(commit)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertGreater(len(MODULE.source_closure_paths()), 20)

    def test_build_is_deterministic(self) -> None:
        commit = MODULE.canonical_commit("HEAD")
        with tempfile.TemporaryDirectory(prefix="flipguard-thesis-test-") as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            MODULE.build(first, commit, refresh_sources=False)
            MODULE.build(second, commit, refresh_sources=False)
            self.assertEqual(MODULE.tree_digest_map(first), MODULE.tree_digest_map(second))
            unresolved = {
                path.name: marker
                for path in first.glob("*.md")
                for marker in ("{{N:", "{{V3_")
                if marker in path.read_text(encoding="utf-8")
            }
            self.assertEqual(unresolved, {})
            self.assertTrue((first / "advisor_defense_qa.md").is_file())
            self.assertTrue((first / "qa_report_v1.md").is_file())
            self.assertTrue((first / "reviewer_attack_checklist.md").is_file())
            report = json.loads((first / "build_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["qa_passes"], 8)
            self.assertEqual(report["advisor_questions"], 30)
            self.assertEqual(report["reviewer_attacks"], 18)
            manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("qa_report", manifest["outputs"])
            self.assertEqual(
                manifest["source_closure"]["sha256"],
                f"sha256:{MODULE.source_closure_digest(commit)}",
            )


if __name__ == "__main__":
    unittest.main()
