import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "paper_inputs", ROOT / "scripts/build_journal_extension_paper_inputs_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


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


if __name__ == "__main__":
    unittest.main()
