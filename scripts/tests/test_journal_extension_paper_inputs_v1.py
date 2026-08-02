import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "paper_inputs", ROOT / "scripts/build_journal_extension_paper_inputs_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_paper_inputs", ROOT / "scripts/verify_journal_extension_paper_inputs_v1.py"
)
VERIFY_MODULE = importlib.util.module_from_spec(VERIFY_SPEC)
assert VERIFY_SPEC.loader is not None
VERIFY_SPEC.loader.exec_module(VERIFY_MODULE)


class JournalExtensionPaperInputsTest(unittest.TestCase):
    def test_markdown_table_escapes_pipes(self):
        value = MODULE.markdown_table(["A"], [["x|y"]])
        self.assertIn("x\\|y", value)

    def test_extract_table_is_bounded(self):
        text = "# X\n\n| Work | Count |\n|---|---|\n| A | 1 |\n\nafter\n"
        self.assertEqual(
            MODULE.extract_first_table(text, "Work"),
            "| Work | Count |\n|---|---|\n| A | 1 |\n",
        )

    def test_svg_escapes_text(self):
        self.assertIn("a &lt; b", MODULE.svg_text(1, 2, "a < b"))

    def test_overclaim_scan_rejects_affirmative_claims(self):
        findings = VERIFY_MODULE.prohibited_overclaims(
            {"table.md": "FlipGuard reaches the global optimum and production speedup."}
        )
        self.assertEqual(
            findings,
            [("table.md", "global_optimum"), ("table.md", "production_speedup")],
        )

    def test_overclaim_scan_allows_scoped_limitations(self):
        findings = VERIFY_MODULE.prohibited_overclaims(
            {
                "figure.svg": (
                    "No global-oracle claim is made. This is not arbitrary packed-CNN "
                    "generalization, and extension timing is descriptive and unpaired."
                )
            }
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
