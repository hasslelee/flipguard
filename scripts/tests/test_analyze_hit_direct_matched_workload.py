import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/analyze_hit_direct_matched_workload.py"
SPEC = importlib.util.spec_from_file_location(
    "analyze_hit_direct_matched_workload",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    MODULE.DIRECT_SELECTION.is_file() and MODULE.HIT_SELECTION.is_file(),
    "matched direct/HIT frozen evidence is unavailable",
)
class HitDirectMatchedWorkloadTest(unittest.TestCase):
    def test_identity_and_claim_boundary(self) -> None:
        summary, arms = MODULE.build_analysis()
        self.assertTrue(
            summary["identity"]["raw_validation_source_byte_identical"]
        )
        self.assertTrue(summary["identity"]["model_byte_identical"])
        self.assertTrue(summary["identity"]["graph_semantics_identical"])
        self.assertLessEqual(
            summary["identity"]["decision_numeric_max_abs_delta"], 1e-12
        )
        self.assertEqual(arms[0]["selection_status"], "SAFE")
        self.assertEqual(arms[1]["selection_status"], "REJECTED")
        self.assertFalse(
            summary["interpretation"]["paired_latency_claim_allowed"]
        )

    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-hit-direct-test-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            manifest = MODULE.verify(output)
            self.assertFalse(manifest["paper_claim_allowed"])
            self.assertEqual(manifest["encrypted_executions_added"], 0)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-hit-direct-overwrite-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "analysis-source-commit")


if __name__ == "__main__":
    unittest.main()
