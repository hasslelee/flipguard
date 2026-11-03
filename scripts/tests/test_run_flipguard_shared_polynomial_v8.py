#!/usr/bin/env python3
"""Tests for the focused V8 FlipGuard runner's static plan gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/external_v8/run_flipguard_shared_polynomial_v8.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("flipguard_v8_runner", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogPlanSupportTests(unittest.TestCase):
    def test_rejects_security_admitted_but_structurally_short_profile(self):
        result = load_runner().catalog_plan_support(
            "short_chain_3",
            {"q": [17, 19, 23]},
            7,
        )
        self.assertEqual(result["status"], "PLAN_UNSUPPORTED")
        self.assertEqual(result["reason_code"], "INSUFFICIENT_Q_PRIMES_FOR_FROZEN_GRAPH")
        self.assertEqual(result["encrypted_candidate_executions"], 0)

    def test_accepts_profile_with_enough_concrete_q_primes(self):
        result = load_runner().catalog_plan_support(
            "deep_chain_8_scale45",
            {"q": list(range(8))},
            7,
        )
        self.assertEqual(result["status"], "PLAN_SUPPORTED")
        self.assertEqual(result["available_q_primes"], 8)

    def test_supports_legacy_logarithmic_literal_counting(self):
        result = load_runner().catalog_plan_support(
            "legacy",
            {"log_q": [40] * 7},
            7,
        )
        self.assertEqual(result["status"], "PLAN_SUPPORTED")


if __name__ == "__main__":
    unittest.main()
