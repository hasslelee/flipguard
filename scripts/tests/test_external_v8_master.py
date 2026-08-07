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


if __name__ == "__main__":
    unittest.main()
