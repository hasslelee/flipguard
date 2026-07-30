import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/run_eva_schedule_bound_adapter.py"
SPEC = importlib.util.spec_from_file_location(
    "run_eva_schedule_bound_adapter",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def selection(status: str = "SAFE") -> dict:
    return {
        "outcome": "SELECTED" if status == "SAFE" else "NO_SAFE",
        "trials_used": 1,
        "encrypted_key_runs": 3,
        "trial": {
            "status": status,
            "v_cert": 14,
            "encrypted_sample_evaluations": 42,
            "decision_flips": 0,
            "error_violations": 0 if status == "SAFE" else 1,
            "max_observed_error": 0.01,
            "max_error_budget_usage": 0.4,
        },
    }


class RunEVAScheduleBoundAdapterTest(unittest.TestCase):
    def test_summary_counts_smoke_separately(self) -> None:
        smoke = selection()
        smoke["encrypted_key_runs"] = 1
        smoke["trial"]["v_cert"] = 1
        audit = {
            "outcome": "LOCKED_AUDIT_PASS",
            "retuning_performed": False,
            "audit_trial": {
                "status": "SAFE",
                "key_repeats_completed": 3,
                "encrypted_sample_evaluations": 48,
                "decision_flips": 0,
                "error_violations": 0,
            },
        }
        summary = MODULE.build_summary(smoke, selection(), audit)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(
            summary["accounting"]["formal_candidate_trials"],
            1,
        )
        self.assertEqual(
            summary["accounting"]["diagnostic_candidate_trials"],
            1,
        )
        self.assertEqual(
            summary["accounting"]["formal_key_runs"],
            3,
        )
        self.assertEqual(
            summary["accounting"]["diagnostic_key_runs"],
            1,
        )
        self.assertFalse(summary["paper_claim_allowed"])

    def test_rejection_is_preserved(self) -> None:
        smoke = selection()
        smoke["encrypted_key_runs"] = 1
        smoke["trial"]["v_cert"] = 1
        summary = MODULE.build_summary(
            smoke,
            selection("REJECTED"),
            None,
        )
        self.assertEqual(summary["status"], "PARTIAL_SCIENTIFIC_RESULT")
        self.assertEqual(
            summary["claim_states"][
                "encrypted_external_candidate_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            summary["claim_states"][
                "locked_audit_external_schedule_replay"
            ],
            "NOT_EVALUATED",
        )


if __name__ == "__main__":
    unittest.main()
