#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/lint_flipguard_thesis.py"
SPEC = importlib.util.spec_from_file_location("lint_flipguard_thesis", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ThesisLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        claims = json.loads(
            (ROOT / "docs/evidence/paper_claim_admission_v1/claims.json").read_text(encoding="utf-8")
        )["claims"]
        cls.claims = claims

    def fixture(self, name: str) -> str:
        return (ROOT / "scripts/tests/fixtures" / name).read_text(encoding="utf-8")

    def test_positive_fixture_allows_scoped_negation(self) -> None:
        findings = MODULE.prohibited_occurrences(
            self.fixture("thesis_lint_positive.md"), self.claims
        )
        self.assertEqual(findings, [])

    def test_negative_fixture_rejects_overclaim(self) -> None:
        findings = MODULE.prohibited_occurrences(
            self.fixture("thesis_lint_negative.md"), self.claims
        )
        self.assertTrue(any(item["claim_id"] == "scoped_direct_synthesis" for item in findings))

    def test_authoritative_source_passes(self) -> None:
        result = MODULE.lint_source(ROOT, Path("docs/thesis"))
        self.assertEqual(result["status"], "PASS", result["errors"])

    def test_number_registry_is_fully_reconstructed_from_evidence(self) -> None:
        registry = json.loads(
            (ROOT / "docs/thesis/number_registry.json").read_text(encoding="utf-8")
        )
        reconstructed = MODULE.extract_authoritative_numbers(ROOT)
        self.assertGreaterEqual(len(reconstructed), 50)
        for key, value in reconstructed.items():
            self.assertIn(key, registry)
            self.assertEqual(registry[key], value, key)

    def test_number_registry_mutation_fails_closed(self) -> None:
        registry = json.loads(
            (ROOT / "docs/thesis/number_registry.json").read_text(encoding="utf-8")
        )
        registry["formal_catalog_all"] = 1100
        errors: list[str] = []
        MODULE.validate_registry(ROOT, registry, errors)
        self.assertTrue(any("formal_catalog_all" in error for error in errors))

    def lint_mutated_source(self, mutate) -> dict:
        with tempfile.TemporaryDirectory(prefix="thesis-lint-fixture-", dir=ROOT) as directory:
            source = Path(directory) / "thesis"
            shutil.copytree(ROOT / "docs/thesis", source)
            mutate(source)
            return MODULE.lint_source(ROOT, source.relative_to(ROOT))

    def test_unverified_citation_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "citation_audit.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(",true,02_background", ",false,02_background", 1), encoding="utf-8")

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("primary-source verification" in error for error in result["errors"]))

    def test_stale_figure_reference_line_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "figure_table_map.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(",05_flipguard_design,7,", ",05_flipguard_design,999,"), encoding="utf-8")

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("stale first-reference line" in error for error in result["errors"]))

    def test_number_marker_rendering_and_unknown_key(self) -> None:
        registry = {"count": 7, "ratio": 0.9}
        rendered = MODULE.render_number_markers(
            "{{N:count}} candidates, {{N:ratio|.0%}} reduction", registry
        )
        self.assertEqual(rendered, "7 candidates, 90% reduction")
        with self.assertRaisesRegex(ValueError, "unknown thesis number key"):
            MODULE.render_number_markers("{{N:not_registered}}", registry)


if __name__ == "__main__":
    unittest.main()
