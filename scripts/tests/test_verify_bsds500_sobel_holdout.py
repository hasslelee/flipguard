#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "verify_bsds500_sobel_holdout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_bsds500_sobel_holdout",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerifyBSDS500SobelHoldoutTest(unittest.TestCase):
    def test_tracked_artifact_passes_without_source_archive(self) -> None:
        root = (
            Path(__file__).resolve().parents[2]
            / "datasets/vision_suite/bsds500/sobel_edge_score"
        )
        MODULE.verify(
            root,
            source_replay=False,
            archive=MODULE.EXPORTER.DEFAULT_ARCHIVE,
            image_root=MODULE.EXPORTER.DEFAULT_IMAGE_ROOT,
        )


if __name__ == "__main__":
    unittest.main()
