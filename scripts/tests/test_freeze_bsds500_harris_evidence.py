#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "freeze_bsds500_harris_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_bsds500_harris_evidence",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FreezeBSDS500HarrisEvidenceTest(unittest.TestCase):
    def test_raw_run_passes_deep_validation(self) -> None:
        run_root = (
            Path(__file__).resolve().parents[2]
            / MODULE.DEFAULT_RUN_ROOT
        )
        if not (run_root / "run_manifest.json").is_file():
            self.skipTest("requires ignored Harris raw results")
        run_manifest, selection, audit, derived = MODULE.validate_run(
            run_root
        )
        self.assertEqual(MODULE.EXECUTION_COMMIT, run_manifest["source_commit"])
        self.assertEqual("SELECTED", selection["outcome"])
        self.assertEqual("LOCKED_AUDIT_PASS", audit["outcome"])
        self.assertEqual(
            600,
            derived["selection_ledger"]["observations"],
        )
        self.assertEqual(
            600,
            derived["audit_ledger"]["observations"],
        )


if __name__ == "__main__":
    unittest.main()
