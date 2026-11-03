#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "freeze_bsds500_sobel_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_bsds500_sobel_evidence",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FreezeBSDS500SobelEvidenceTest(unittest.TestCase):
    def test_validate_ledger_recomputes_sample_budget(self) -> None:
        contract = {
            "decision": {
                "threshold": 0.2,
                "margin_floor": 0.001,
                "safety_factor": 0.5,
                "validation_samples": 1,
            },
        }
        trial = {
            "encrypted_sample_evaluations": 1,
            "key_repeats_completed": 1,
            "v_cert": 1,
            "v_amb": 0,
            "decision_flips": 0,
            "error_violations": 0,
            "max_observed_error": 0.01,
            "max_error_budget_usage": 0.1,
            "sample_ledger": [
                {
                    "key_run": 1,
                    "row_id": 100000,
                    "image_id": "100075",
                    "source_partition": "val",
                    "plain_score": 0.4,
                    "ckks_score": 0.39,
                    "threshold": 0.2,
                    "margin": 0.2,
                    "abs_error": 0.01,
                    "certifiable": True,
                    "error_budget": 0.1,
                    "error_budget_usage": 0.1,
                    "error_violation": False,
                    "plain_decision": True,
                    "ckks_decision": True,
                    "decision_flip": False,
                    "encode_encrypt_ms": 1,
                    "eval_only_ms": 1,
                    "decrypt_decode_ms": 1,
                    "total_eval_ms": 3,
                },
            ],
        }
        summary = MODULE.validate_ledger(
            trial,
            contract,
            "val",
        )
        self.assertEqual(1, summary["observations"])
        trial["sample_ledger"][0]["ckks_score"] = 0.1
        with self.assertRaises(ValueError):
            MODULE.validate_ledger(trial, contract, "val")


if __name__ == "__main__":
    unittest.main()
