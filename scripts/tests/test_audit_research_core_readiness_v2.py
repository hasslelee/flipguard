import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/audit_research_core_readiness_v2.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_research_core_readiness_v2", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCoreReadinessV2Test(unittest.TestCase):
    def test_claim_partition_is_disjoint(self) -> None:
        claim_groups = [
            set(MODULE.REQUIRED_CORE_CLAIMS),
            set(MODULE.EXCLUDED_CLAIMS),
            set(MODULE.SUPPORTED_CONTEXT_CLAIMS),
        ]
        self.assertFalse(claim_groups[0] & claim_groups[1])
        self.assertFalse(claim_groups[0] & claim_groups[2])
        self.assertFalse(claim_groups[1] & claim_groups[2])

    def test_ready_status_preserves_native_negative_result(self) -> None:
        summary = MODULE.build_summary()
        self.assertEqual(
            summary["research_core_status"],
            "READY_WITH_SCOPED_LIMITATIONS",
        )
        native = summary["native_external_runtime_result"]
        self.assertEqual(native["runtime_execution"], "SUPPORTED")
        self.assertEqual(native["validation_status"], "REJECTED")
        self.assertEqual(native["locked_audit"], "NOT_EVALUATED")
        self.assertTrue(summary["paper_work_prohibited"])
        self.assertFalse(summary["paper_claim_allowed"])

    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-readiness-v2-test-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            manifest = MODULE.verify(output)
            self.assertFalse(manifest["paper_claim_allowed"])

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-readiness-v2-overwrite-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "analysis-source-commit")


if __name__ == "__main__":
    unittest.main()
