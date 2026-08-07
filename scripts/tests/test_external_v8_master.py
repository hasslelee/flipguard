#!/usr/bin/env python3
"""Regression tests for the V8 deadline-bound master."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "scripts/external_v8/master_v8.py"
SPEC = importlib.util.spec_from_file_location("external_v8_master", MASTER_PATH)
assert SPEC and SPEC.loader
MASTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MASTER)

FINALIZER_PATH = ROOT / "scripts/external_v8/finalize_v8.py"
FINALIZER_SPEC = importlib.util.spec_from_file_location("external_v8_finalizer", FINALIZER_PATH)
assert FINALIZER_SPEC and FINALIZER_SPEC.loader
FINALIZER = importlib.util.module_from_spec(FINALIZER_SPEC)
FINALIZER_SPEC.loader.exec_module(FINALIZER)

EVA_PATH = ROOT / "scripts/external_v8/run_eva_shared_polynomial_v8.py"
EVA_SPEC = importlib.util.spec_from_file_location("external_v8_eva", EVA_PATH)
assert EVA_SPEC and EVA_SPEC.loader
EVA = importlib.util.module_from_spec(EVA_SPEC)
EVA_SPEC.loader.exec_module(EVA)


class ExternalV8MasterTest(unittest.TestCase):
    def test_resource_state_is_complete_and_usable(self) -> None:
        state = MASTER.resource_state()
        self.assertEqual(state["gate"], "PASS")
        self.assertGreater(state["disk_free_bytes"], 0)
        self.assertGreater(state["disk_free_gib"], 0)
        self.assertGreater(state["inode_free_pct"], 0)
        self.assertGreater(state["memory_available_kib"], 0)
        self.assertGreaterEqual(state["swap_used_kib"], 0)
        self.assertIn("timestamp", state)

    def test_eva_candidate_is_predeclared_before_v8_validation(self) -> None:
        self.assertEqual(EVA.PREDECLARED_SELECTED_SCALE, 30)
        source = EVA_PATH.read_text(encoding="utf-8")
        self.assertIn("V7_PREDECLARED_SCALE30_BEFORE_V8_VALIDATION", source)
        self.assertNotIn('next((arm for arm in arms if arm["validation"]', source)

    def test_missing_provider_accounting_is_not_a_false_zero(self) -> None:
        self.assertEqual(
            FINALIZER.observed_or_not_evaluated(False, 0),
            "NOT_EVALUATED",
        )
        self.assertEqual(FINALIZER.observed_or_not_evaluated(True, 17), 17)


if __name__ == "__main__":
    unittest.main()
