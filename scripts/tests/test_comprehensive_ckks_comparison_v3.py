import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ComprehensiveComparisonV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load("comparison_builder", ROOT / "scripts/build_comprehensive_ckks_comparison_v3.py")
        cls.verifier = load("comparison_verifier", ROOT / "scripts/verify_comprehensive_ckks_comparison_v3.py")

    def test_landscape_has_exactly_21_unique_rows(self):
        rows = self.builder.load_systems()
        self.assertEqual(len(rows), 21)
        self.assertEqual(len({row["system"] for row in rows}), 21)

    def test_missing_states_are_not_numeric_zeroes(self):
        self.assertIn("NOT_EVALUATED", self.builder.MISSING)
        self.assertNotIn(0, self.builder.MISSING)

    def test_reported_results_use_source_locators(self):
        rows = self.builder.read_json(self.builder.PROTOCOL / "paper_reported_source_records.json")["records"]
        self.assertGreaterEqual(len({row["system"] for row in rows if row["system"] != "FlipGuard"}), 12)
        self.assertTrue(all(row["source_locator"] for row in rows))

    def test_frozen_pack_verifies(self):
        result = self.verifier.verify()
        self.assertEqual(result["completion"], "EXHAUSTED_FEASIBLE_SET")
        self.assertEqual(result["external_common_executor"], 0)


if __name__ == "__main__":
    unittest.main()
