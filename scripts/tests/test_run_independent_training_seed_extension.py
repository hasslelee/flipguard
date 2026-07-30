#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
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

    def test_encrypted_evaluation_accounting_uses_contract(self) -> None:
        result = {
            "plan": {
                "contract": {
                    "decision": {"validation_samples": 7},
                },
            },
            "trials": [
                {"key_repeats_completed": 3},
                {"key_repeats_completed": 2},
            ],
        }
        self.assertEqual(
            35,
            MODULE.selection_encrypted_evaluations(result),
        )
        audit = {
            "audit_contract": {
                "decision": {"validation_samples": 11},
            },
            "audit_trial": {"key_repeats_completed": 3},
        }
        self.assertEqual(
            33,
            MODULE.audit_encrypted_evaluations(audit),
        )

    def test_manifest_compatibility_preserves_assignment(self) -> None:
        payload = {
            "configuration_validation": {
                "path": "validation.csv",
                "csv_digest": "sha256:validation",
                "row_ids": [1, 2],
            },
            "locked_audit_test": {
                "path": "audit.csv",
                "csv_digest": "sha256:audit",
                "row_ids": [3, 4],
            },
        }
        with tempfile.TemporaryDirectory(
            dir=MODULE.REPO_ROOT,
        ) as temporary:
            root = Path(temporary)
            source = root / "source.json"
            output = root / "output.json"
            source.write_text(
                json.dumps(payload),
                encoding="ascii",
            )
            recovery = MODULE.build_audit_compatibility_manifest(
                source,
                output,
            )
            converted = json.loads(output.read_text(encoding="ascii"))
        self.assertFalse(recovery["semantic_assignment_changed"])
        self.assertEqual(
            ["1", "2"],
            converted["configuration_validation"]["row_ids"],
        )
        self.assertEqual(
            "sha256:audit",
            converted["locked_audit_test"]["csv_digest"],
        )


if __name__ == "__main__":
    unittest.main()
