#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "export_bsds500_sobel_holdout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_bsds500_sobel_holdout",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExportBSDS500SobelHoldoutTest(unittest.TestCase):
    def test_patch_centers_are_deterministic_unique_and_in_bounds(self) -> None:
        first = MODULE.patch_centers("100075", "val", 481, 321, 32)
        second = MODULE.patch_centers("100075", "val", 481, 321, 32)
        self.assertEqual(first, second)
        self.assertEqual(32, len(set(first)))
        for x, y in first:
            self.assertGreaterEqual(x, 1)
            self.assertLessEqual(x, 479)
            self.assertGreaterEqual(y, 1)
            self.assertLessEqual(y, 319)

    def test_sobel_score_matches_canonical_step(self) -> None:
        vertical_step = [
            0.0, 0.0, 1.0,
            0.0, 0.0, 1.0,
            0.0, 0.0, 1.0,
        ]
        self.assertEqual(16.0, MODULE.sobel_score(vertical_step))

    def test_luma_formula_endpoints(self) -> None:
        self.assertEqual(0.0, MODULE.normalized_luma((0, 0, 0)))
        self.assertEqual(1.0, MODULE.normalized_luma((255, 255, 255)))
        self.assertTrue(
            math.isclose(
                MODULE.normalized_luma((255, 0, 0)),
                0.299,
            )
        )

    def test_nearest_rank_uses_predeclared_ceil_rule(self) -> None:
        self.assertEqual(
            4.0,
            MODULE.nearest_rank([1.0, 2.0, 3.0, 4.0, 5.0], 0.8),
        )

    def test_policy_digest_is_stable(self) -> None:
        self.assertEqual(
            (
                "sha256:"
                "07c196374cea947c5bd9d8d478311e75ba4754f875c4f19ce0387241d55da699"
            ),
            MODULE.policy_digest(),
        )


if __name__ == "__main__":
    unittest.main()
