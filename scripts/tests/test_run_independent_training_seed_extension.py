#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "run_independent_training_seed_extension.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_independent_training_seed_extension",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RunIndependentTrainingSeedExtensionTest(unittest.TestCase):
    def candidate(self, admission: str = "PASS") -> dict:
        return {
            "id": "candidate",
            "security": {
                "envelope_id":
                    "security_guidelines_cic2025_table5_2_ternary_128_v2",
                "admission_status": admission,
                "ciphertext_q_admission": admission,
                "evaluation_key_qp_admission": admission,
                "final_admission": admission,
                "headroom_bits": 10,
            },
        }

    def test_security_gate_accepts_fully_admitted_candidate(self) -> None:
        MODULE.validate_candidate_security(self.candidate())

    def test_security_gate_rejects_inadmissible_candidate(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.validate_candidate_security(self.candidate("FAIL"))

    def test_selection_rejects_trial_budget_overrun(self) -> None:
        result = {
            "plan": {
                "direct_policy_digest": MODULE.DIRECT_POLICY_DIGEST,
                "security_policy_digest": MODULE.SECURITY_POLICY_DIGEST,
            },
            "outcome": "NO_SAFE",
            "trials_used": 5,
            "trials": [],
        }
        with self.assertRaises(ValueError):
            MODULE.validate_selection_result(result)


if __name__ == "__main__":
    unittest.main()
