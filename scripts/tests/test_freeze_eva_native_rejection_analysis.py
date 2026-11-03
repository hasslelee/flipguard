import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_eva_native_rejection_analysis.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_native_rejection_analysis", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVANativeRejectionAnalysisTest(unittest.TestCase):
    def test_key_and_sample_scope_is_preserved(self) -> None:
        analysis, key_rows, sample_rows = MODULE.build_records()
        self.assertEqual(
            [row["error_violations"] for row in key_rows],
            [14, 13, 9],
        )
        self.assertEqual(
            analysis["sample_key_scope"]["keys_with_any_violation"], 3
        )
        self.assertEqual(
            analysis["sample_key_scope"]["samples_with_any_key_violation"],
            14,
        )
        self.assertEqual(
            analysis["sample_key_scope"]["samples_with_all_keys_violation"],
            8,
        )
        self.assertEqual(len(sample_rows), 14)

    def test_causal_and_claim_boundaries_are_fail_closed(self) -> None:
        analysis, _, _ = MODULE.build_records()
        causal = analysis["causal_assessment"]
        self.assertEqual(
            causal["low_scale_relative_to_schedule_hypothesis"],
            "CONSISTENT_WITH_EVIDENCE_NOT_CAUSALLY_ESTABLISHED",
        )
        self.assertEqual(
            analysis["claim_effect"][
                "native_eva_seal_decision_certification"
            ],
            "BLOCKED",
        )
        self.assertFalse(
            analysis["direct_matched_diagnostic"][
                "cross_runtime_numerical_equivalence_claim_allowed"
            ]
        )
        self.assertEqual(analysis["encrypted_executions_added"], 0)

    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-eva-rejection-test-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            manifest = MODULE.verify(output)
            self.assertFalse(manifest["paper_claim_allowed"])

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-eva-rejection-overwrite-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "evidence"
            MODULE.freeze(output, "analysis-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "analysis-source-commit")


if __name__ == "__main__":
    unittest.main()
