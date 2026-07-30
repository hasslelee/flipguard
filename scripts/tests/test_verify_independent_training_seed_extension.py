#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "verify_independent_training_seed_extension.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_independent_training_seed_extension",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyIndependentTrainingSeedExtensionTest(unittest.TestCase):
    def test_frozen_suite_passes_structural_validation(self) -> None:
        root = (
            Path(__file__).resolve().parents[2]
            / MODULE.EXPORTER.DEFAULT_OUTPUT
        )
        summary = MODULE.validate_tree(root)
        self.assertEqual(9, summary["instance_count"])
        self.assertEqual(
            {
                (seed, dataset)
                for seed in MODULE.EXPORTER.SEEDS
                for dataset in MODULE.EXPORTER.DATASET_IDS
            },
            {
                (
                    int(instance["training_seed"]),
                    instance["dataset_id"],
                )
                for instance in summary["instances"]
            },
        )

    def test_logical_path_escape_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.resolve_suite_path(
                Path("/tmp/suite"),
                "datasets/tabular_suite/model.json",
            )


if __name__ == "__main__":
    unittest.main()
