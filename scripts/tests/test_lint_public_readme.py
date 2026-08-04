from __future__ import annotations

import unittest
from pathlib import Path

from scripts.lint_public_readme import ROOT, lint_repository, scan_claim_language


FIXTURES = ROOT / "scripts/tests/fixtures/public_readme"


class PublicReadmeLintTest(unittest.TestCase):
    def test_repository_is_positive_fixture(self) -> None:
        self.assertEqual([], lint_repository(ROOT))

    def test_scoped_negative_wording_is_allowed(self) -> None:
        text = (FIXTURES / "positive_claims.md").read_text(encoding="utf-8")
        self.assertEqual([], scan_claim_language(text, "en", "positive_claims.md", ROOT))

    def test_global_optimum_overclaim_is_rejected(self) -> None:
        text = (FIXTURES / "negative_global_optimum.md").read_text(encoding="utf-8")
        codes = {issue.code for issue in scan_claim_language(text, "en", "negative_global_optimum.md", ROOT)}
        self.assertIn("PROHIBITED_CLAIM", codes)

    def test_s29_speed_overclaim_is_rejected(self) -> None:
        text = (FIXTURES / "negative_s29_speed.md").read_text(encoding="utf-8")
        codes = {issue.code for issue in scan_claim_language(text, "en", "negative_s29_speed.md", ROOT)}
        self.assertIn("S29_SPEED_OVERCLAIM", codes)

    def test_lenet_no_safe_overclaim_is_rejected(self) -> None:
        text = (FIXTURES / "negative_lenet_no_safe.md").read_text(encoding="utf-8")
        codes = {issue.code for issue in scan_claim_language(text, "en", "negative_lenet_no_safe.md", ROOT)}
        self.assertIn("LENET_STATUS", codes)


if __name__ == "__main__":
    unittest.main()
