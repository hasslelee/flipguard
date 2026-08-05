import unittest

from scripts.lint_comprehensive_ckks_comparison_v3 import PROHIBITED_AFFIRMATIVE, text_findings


class ComparisonFairnessLintTest(unittest.TestCase):
    def test_positive_scoped_sentence(self):
        text = "Representative systems are separated by evidence tier; native latency is diagnostic only."
        self.assertEqual(text_findings(text), [])

    def test_negative_global_fastest_sentence(self):
        self.assertIn("globally fastest", text_findings("FlipGuard is the globally fastest system."))

    def test_negative_build_smoke_sentence(self):
        self.assertIn("build smoke equals reproduction", text_findings("Build smoke equals reproduction."))

    def test_vocabulary_has_no_empty_phrase(self):
        self.assertTrue(all(PROHIBITED_AFFIRMATIVE))


if __name__ == "__main__":
    unittest.main()
