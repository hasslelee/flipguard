#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "freeze_independent_training_seed_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_independent_training_seed_evidence",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FreezeIndependentTrainingSeedEvidenceTest(unittest.TestCase):
    def test_completed_run_passes_deep_validation(self) -> None:
        run_root = (
            Path(__file__).resolve().parents[2]
            / MODULE.DEFAULT_RUN_ROOT
        )
        run_manifest, state, derived = MODULE.validate_run(run_root)
        self.assertEqual(
            MODULE.EXECUTION_COMMIT,
            run_manifest["source_commit"],
        )
        self.assertEqual("PASS", state["stage"])
        self.assertEqual(9, derived["summary"]["selection"]["selected"])
        self.assertEqual(
            9,
            derived["summary"]["locked_audit"]["pass"],
        )
        self.assertEqual(
            0,
            derived["summary"]["locked_audit"]["retuning"],
        )

    def test_duplicate_string_identity_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.string_ids([1, "1"])


if __name__ == "__main__":
    unittest.main()
