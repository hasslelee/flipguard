#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "export_bsds500_harris_holdout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_bsds500_harris_holdout",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExportBSDS500HarrisHoldoutTest(unittest.TestCase):
    def test_patch_centers_are_deterministic_unique_and_in_bounds(self) -> None:
        first = MODULE.patch_centers("100075", "val", 481, 321, 32)
        second = MODULE.patch_centers("100075", "val", 481, 321, 32)
        self.assertEqual(first, second)
        self.assertEqual(32, len(set(first)))
        for x, y in first:
            self.assertGreaterEqual(x, 2)
            self.assertLessEqual(x, 478)
            self.assertGreaterEqual(y, 2)
            self.assertLessEqual(y, 318)

    def test_harris_corner_and_edge_signatures(self) -> None:
        flat = [0.0] * 25
        self.assertEqual(0.0, MODULE.harris_components(flat)["plaintext_score"])

        corner = [
            0.0 if row < 2 or column < 2 else 1.0
            for row in range(5)
            for column in range(5)
        ]
        edge = [
            0.0 if column < 2 else 1.0
            for _row in range(5)
            for column in range(5)
        ]
        self.assertGreater(
            MODULE.harris_components(corner)["plaintext_score"],
            0.0,
        )
        self.assertLess(
            MODULE.harris_components(edge)["plaintext_score"],
            0.0,
        )

    def test_luma_formula_endpoints(self) -> None:
        self.assertEqual(0.0, MODULE.normalized_luma((0, 0, 0)))
        self.assertEqual(1.0, MODULE.normalized_luma((255, 255, 255)))
        self.assertTrue(
            math.isclose(
                MODULE.normalized_luma((255, 0, 0)),
                0.299,
            )
        )

    def test_policy_digest_is_stable(self) -> None:
        self.assertEqual(
            (
                "sha256:"
                "90befad9bdf9c58b817a54664348b421233e5834995a2648793024892b5cb291"
            ),
            MODULE.policy_digest(),
        )


if __name__ == "__main__":
    unittest.main()
