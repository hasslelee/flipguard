import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "manage_autonomous_suite_state",
    ROOT / "scripts/manage_autonomous_suite_state.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AutonomousSuiteStateTest(unittest.TestCase):
    def test_dependency_graph_keeps_paired_independent_of_structural(self):
        self.assertNotIn(
            "structural_holdout",
            MODULE.DEPENDENCY_GRAPH["paired_latency"],
        )

    def test_append_jsonl_preserves_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            MODULE.append_jsonl(path, {"value": 1})
            MODULE.append_jsonl(path, {"value": 2})
            self.assertEqual(
                path.read_text(encoding="utf-8").splitlines(),
                ['{"value": 1}', '{"value": 2}'],
            )


if __name__ == "__main__":
    unittest.main()
