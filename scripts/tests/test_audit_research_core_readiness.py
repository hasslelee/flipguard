import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/audit_research_core_readiness.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_research_core_readiness", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    MODULE.CHECKPOINT.is_dir() and MODULE.MATCHED_PACK.is_dir(),
    "research checkpoint or matched-provider evidence is unavailable",
)
class ResearchCoreReadinessTest(unittest.TestCase):
    def test_claim_partition_is_disjoint(self) -> None:
        claim_groups = [
            set(MODULE.REQUIRED_CORE_CLAIMS),
            set(MODULE.EXCLUDED_CLAIMS),
            set(MODULE.SUPPORTED_CONTEXT_CLAIMS),
        ]
        self.assertFalse(claim_groups[0] & claim_groups[1])
        self.assertFalse(claim_groups[0] & claim_groups[2])
        self.assertFalse(claim_groups[1] & claim_groups[2])

    def test_ready_status_does_not_admit_paper(self) -> None:
        summary = MODULE.build_summary()
        self.assertEqual(
            summary["research_core_status"],
            "READY_WITH_SCOPED_LIMITATIONS",
        )
        self.assertTrue(summary["paper_work_prohibited"])
        self.assertFalse(summary["paper_claim_allowed"])
        self.assertTrue(summary["manual_scope_review_required"])
        self.assertGreater(len(summary["excluded_claims"]), 0)

    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-readiness-test-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            manifest = MODULE.verify(output)
            self.assertFalse(manifest["paper_claim_allowed"])

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-readiness-overwrite-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "analysis-source-commit")


if __name__ == "__main__":
    unittest.main()
