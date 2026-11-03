#!/usr/bin/env python3

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "freeze_mnist_cnn_lite_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_mnist_cnn_lite_evidence",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FreezeMNISTCNNLiteEvidenceTest(unittest.TestCase):
    def raw_run_root(self) -> Path:
        run_root = (
            Path(__file__).resolve().parents[2]
            / MODULE.DEFAULT_RUN_ROOT
        )
        if not (run_root / "run_manifest.json").is_file():
            self.skipTest("requires ignored CNN-lite raw results")
        return run_root

    def test_raw_run_passes_deep_validation(self) -> None:
        run_root = self.raw_run_root()
        run_manifest, selection, audit, summary = MODULE.validate_run(
            run_root
        )
        self.assertEqual(
            MODULE.EXECUTION_COMMIT,
            run_manifest["execution_commit"],
        )
        self.assertEqual("SELECTED", selection["outcome"])
        self.assertEqual("LOCKED_AUDIT_PASS", audit["outcome"])
        self.assertEqual(
            750,
            summary["selection"]["encrypted_sample_evaluations"],
        )
        self.assertEqual(
            750,
            summary["locked_audit"]["encrypted_sample_evaluations"],
        )

    def test_sample_mutation_fails_closed(self) -> None:
        run_root = self.raw_run_root()
        _, selection, _, _ = MODULE.validate_run(run_root)
        trial = copy.deepcopy(selection["trials"][0])
        trial["sample_ledger"][0]["ckks_score"] += 0.25
        inputs = MODULE.read_input_rows(
            Path(__file__).resolve().parents[2]
            / MODULE.INPUT_ROOT
            / "configuration_validation.csv"
        )
        with self.assertRaises(ValueError):
            MODULE.validate_trial(
                trial,
                selection["plan"]["contract"],
                inputs,
                "train",
            )


if __name__ == "__main__":
    unittest.main()
