#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "run_direct_synthesis_ablation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_direct_synthesis_ablation",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RunDirectSynthesisAblationTest(unittest.TestCase):
    def test_contract_and_frozen_views_pass(self) -> None:
        contract = MODULE.load_contract()
        workloads = MODULE.load_direct_workloads()
        MODULE.verify_catalog_pack()
        catalog, certificates = MODULE.load_catalog_views()
        self.assertEqual(4, len(contract["arms"]))
        self.assertEqual(10, len(workloads))
        self.assertEqual(10, len(catalog))
        self.assertEqual({14}, {len(rows) for rows in certificates.values()})

    def test_security_v2_rejects_failed_admission(self) -> None:
        candidate = {
            "id": "inadmissible",
            "security": {
                "envelope_id":
                    "security_guidelines_cic2025_table5_2_ternary_128_v2",
                "admission_status": "FAIL",
                "ciphertext_q_admission": "PASS",
                "evaluation_key_qp_admission": "FAIL",
                "final_admission": "FAIL",
            },
        }
        with self.assertRaises(ValueError):
            MODULE.validate_security(candidate)


if __name__ == "__main__":
    unittest.main()
