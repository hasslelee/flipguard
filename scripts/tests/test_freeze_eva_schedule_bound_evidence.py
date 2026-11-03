import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_eva_schedule_bound_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_schedule_bound_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(commit: str, error: float, usage: float, flip: int) -> dict:
    trial = {
        "trial_index": 1,
        "status": "REJECTED",
        "key_repeats_completed": 1,
        "encrypted_sample_evaluations": 1,
        "decision_flips": flip,
        "error_violations": 1,
        "max_observed_error": error,
        "max_error_budget_usage": usage,
    }
    return {
        "manifest": {
            "source_commit": commit,
            "execution_critical_source_digest": "sha256:source",
            "binaries": {
                "certify_candidate": {"sha256": "sha256:binary"}
            },
        },
        "selection": {
            "trial": trial,
            "bound_candidate": {
                "execution_schedule": {"schedule_id": "eva-schedule"},
                "candidate": {
                    "security": {"final_admission": "PASS"}
                },
            },
        },
        "sample": {
            "plaintext_score": 0.4,
            "ckks_score": 0.4 + error,
        },
    }


class FreezeEVAScheduleBoundEvidenceTest(unittest.TestCase):
    def test_summary_preserves_negative_and_zero_formal_trials(self) -> None:
        summary = MODULE.build_summary(
            fixture("recovery", 0.2, 4.0, 1),
            fixture("corrected", 0.4, 8.0, 0),
        )
        self.assertEqual(summary["status"], "PARTIAL_SCIENTIFIC_RESULT")
        self.assertEqual(
            summary["corrected_smoke"]["status"],
            "REJECTED",
        )
        self.assertEqual(
            summary["formal_validation"]["candidate_trials"],
            0,
        )
        self.assertEqual(
            summary["locked_audit"]["status"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            summary["claim_states"][
                "encrypted_external_candidate_certification"
            ],
            "BLOCKED",
        )
        self.assertFalse(summary["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
