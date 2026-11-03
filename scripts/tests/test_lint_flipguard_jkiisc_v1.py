from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lint_flipguard_jkiisc_v1 import audit_manuscript  # noqa: E402


class JKIISCLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "docs/journal/01_manuscript_ko.md").read_text(encoding="utf-8")

    def test_authoritative_source_passes(self) -> None:
        report = audit_manuscript(ROOT, self.source, rendered=False)
        self.assertEqual(report["status"], "PASS", report["findings"])

    def test_affirmative_global_optimum_fails(self) -> None:
        mutated = self.source.replace(
            "주장 범위는 의도적으로 제한된다.",
            "FlipGuard achieves the global optimum.\n\n주장 범위는 의도적으로 제한된다.",
            1,
        )
        report = audit_manuscript(ROOT, mutated, rendered=False)
        self.assertTrue(any(row["code"] == "PROHIBITED_CLAIM" for row in report["findings"]))

    def test_missing_structural_negative_fails(self) -> None:
        mutated = self.source.replace("24 PASS", "25 PASS")
        report = audit_manuscript(ROOT, mutated, rendered=False)
        self.assertTrue(any(row["code"] == "NUMBER_REGISTRY" for row in report["findings"]))

    def test_author_metadata_fails(self) -> None:
        mutated = self.source.replace("# I. 서론", "저자: Example Author\n\n# I. 서론", 1)
        report = audit_manuscript(ROOT, mutated, rendered=False)
        self.assertTrue(any(row["code"] == "AUTHORLESS" for row in report["findings"]))

    def test_rendered_placeholders_fail(self) -> None:
        report = audit_manuscript(ROOT, self.source, rendered=True)
        self.assertTrue(any(row["code"] == "RENDERED_PLACEHOLDER" for row in report["findings"]))


if __name__ == "__main__":
    unittest.main()
