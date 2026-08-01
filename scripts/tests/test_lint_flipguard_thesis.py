#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
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


if __name__ == "__main__":
    unittest.main()
