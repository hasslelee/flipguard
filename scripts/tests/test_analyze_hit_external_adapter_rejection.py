import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/analyze_hit_external_adapter_rejection.py"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_hit_external_adapter_rejection",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AnalyzeHITExternalAdapterRejectionTest(unittest.TestCase):
    def test_frozen_source_analysis_is_fail_closed(self) -> None:
        rows, summary = MODULE.build_analysis(MODULE.SOURCE_PACK)
        self.assertEqual(len(rows), 14)
        self.assertEqual(summary["workload"]["observation_count"], 42)
        self.assertEqual(
            summary["observed_aggregate"]["error_violations"],
            6,
        )
        self.assertTrue(
            summary["observed_aggregate"][
                "all_observations_below_guaranteed_flip_boundary"
            ]
        )
        self.assertEqual(
            summary["localization_limit"][
                "sample_level_encrypted_scores"
            ],
            "NOT_AVAILABLE_TABULAR_TRIAL_RESULT_V1",
        )
        self.assertFalse(summary["paper_claim_allowed"])

    def test_rendered_rows_do_not_invent_encrypted_scores(self) -> None:
        rows, _ = MODULE.build_analysis(MODULE.SOURCE_PACK)
        self.assertTrue(
            all(
                row["encrypted_score_available"] == "false"
                and row["violation_membership"] ==
                "NOT_RECOVERABLE_FROM_FROZEN_AGGREGATE"
                for row in rows
            )
        )


if __name__ == "__main__":
    unittest.main()
