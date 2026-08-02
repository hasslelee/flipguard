import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "run_journal_mlp_paired_latency_v1.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("run_journal_mlp_paired_latency_v1", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FocusedMLPPairedRunnerTest(unittest.TestCase):
    def test_next_attempt_preserves_existing_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "attempt_01").mkdir()
            (root / "attempt_03").mkdir()
            self.assertEqual(MODULE.next_attempt(root), 4)

    def test_next_attempt_counts_preserved_log_without_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "keyset_01"
            (parent / "keyset_01_attempt_01.log").write_text("failed before output\n", encoding="utf-8")
            self.assertEqual(MODULE.next_attempt(root), 2)

    def test_complete_attempt_rejects_truncated_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ["run_manifest.json", "result.json"]:
                (root / name).write_text("{}\n", encoding="utf-8")
            (root / "records.jsonl").write_text(json.dumps({"record": 1}) + "\n", encoding="utf-8")
            completion = {
                "records": 2,
                "ledger_sha256": MODULE.sha(root / "records.jsonl"),
                "result_sha256": MODULE.sha(root / "result.json"),
            }
            (root / "completed.json").write_text(json.dumps(completion), encoding="utf-8")
            self.assertFalse(MODULE.complete_attempt(root, 2))


if __name__ == "__main__":
    unittest.main()
