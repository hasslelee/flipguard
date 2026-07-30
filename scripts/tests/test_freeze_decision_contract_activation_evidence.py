import copy
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_decision_contract_activation_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_decision_contract_activation_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_summary():
    rows = []
    specifications = (
        ("narrow_margin", "decision_contract", 21, 33, 4, 12, 384),
        (
            "narrow_margin",
            "graph_fixed_tolerance",
            20,
            32,
            4,
            12,
            384,
        ),
        ("wide_margin", "decision_contract", 20, 28, 3, 9, 288),
        (
            "wide_margin",
            "graph_fixed_tolerance",
            20,
            28,
            3,
            9,
            288,
        ),
    )
    for regime, arm, initial, selected, trials, keys, evaluations in (
        specifications
    ):
        rows.append(
            {
                "regime": regime,
                "arm": arm,
                "selection_outcome": "SELECTED",
                "initial_scale": initial,
                "selected_scale": selected,
                "trials": trials,
                "repairs": trials - 1,
                "key_runs": keys,
                "encrypted_sample_evaluations": evaluations,
                "audit_outcome": "LOCKED_AUDIT_PASS",
                "audit_status": "SAFE",
                "audit_flips": 0,
                "audit_violations": 0,
                "audit_retuning": 0,
                "audit_key_runs": 3,
                "audit_encrypted_sample_evaluations": 96,
            }
        )
    return {
        "execution_source_commit": MODULE.EXECUTION_SOURCE_COMMIT,
        "direct_policy_digest": MODULE.DIRECT_POLICY_DIGEST,
        "security_policy_digest": MODULE.SECURITY_POLICY_DIGEST,
        "static_claim_state": "SUPPORTED",
        "natural_data_decision_contract_synthesis_effect": "BLOCKED",
        "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
        "finite_domain_encrypted_control": "SUPPORTED",
        "encrypted_rows": 4,
        "failed_before_encryption": 0,
        "stage_status": "PASS",
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "rows": rows,
    }


class DecisionActivationEvidenceFreezeTest(unittest.TestCase):
    def test_success_summary_accounting(self) -> None:
        accounting = MODULE.validate_success_summary(valid_summary())
        self.assertEqual(accounting["selection_trials"], 14)
        self.assertEqual(accounting["selection_key_runs"], 42)
        self.assertEqual(accounting["locked_audit_pass"], 4)

    def test_rejects_audit_retuning(self) -> None:
        summary = copy.deepcopy(valid_summary())
        summary["rows"][0]["audit_retuning"] = 1
        with self.assertRaises(ValueError):
            MODULE.validate_success_summary(summary)

    def test_rejects_natural_claim_promotion(self) -> None:
        summary = copy.deepcopy(valid_summary())
        summary[
            "natural_data_decision_contract_synthesis_effect"
        ] = "SUPPORTED"
        with self.assertRaises(ValueError):
            MODULE.validate_success_summary(summary)


if __name__ == "__main__":
    unittest.main()
