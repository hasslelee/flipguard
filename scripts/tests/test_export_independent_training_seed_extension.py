#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "export_independent_training_seed_extension.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_independent_training_seed_extension",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExportIndependentTrainingSeedExtensionTest(unittest.TestCase):
    def fixture(self) -> object:
        return MODULE.SourceDataset(
            dataset_id="fixture",
            dataset_name="fixture",
            upstream_name="fixture.csv",
            upstream_path=Path("fixture.csv"),
            upstream_sha256="sha256:" + "0" * 64,
            feature_names=("x",),
            row_ids=tuple(range(20)),
            labels=tuple([0] * 10 + [1] * 10),
            features=tuple((float(index),) for index in range(20)),
        )

    def test_role_assignment_is_complete_and_disjoint(self) -> None:
        roles = MODULE.assign_roles(self.fixture(), 1729)
        self.assertEqual(4, len(roles["configuration_validation"]))
        self.assertEqual(4, len(roles["locked_audit"]))
        self.assertEqual(12, len(roles["model_training"]))
        sets = [set(values) for values in roles.values()]
        self.assertFalse(sets[0] & sets[1])
        self.assertFalse(sets[0] & sets[2])
        self.assertFalse(sets[1] & sets[2])
        self.assertEqual(set(range(20)), set.union(*sets))

    def test_seed_changes_role_assignment(self) -> None:
        first = MODULE.assign_roles(self.fixture(), 1729)
        second = MODULE.assign_roles(self.fixture(), 2718)
        self.assertNotEqual(
            first["configuration_validation"],
            second["configuration_validation"],
        )

    def test_policy_digest_is_stable(self) -> None:
        self.assertEqual(
            "sha256:"
            "e9353654e5ec899fc91ce70e8dd501905b95973bcb8493cc1d27f3ffc77af1cb",
            MODULE.canonical_digest(MODULE.POLICY),
        )


if __name__ == "__main__":
    unittest.main()
