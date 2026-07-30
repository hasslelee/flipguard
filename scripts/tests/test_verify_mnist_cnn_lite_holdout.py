#!/usr/bin/env python3

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/verify_mnist_cnn_lite_holdout.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_mnist_cnn_lite_holdout",
    SCRIPT,
)
VERIFIER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VERIFIER)


class VerifyMNISTCNNLiteHoldoutTest(unittest.TestCase):
    def test_frozen_artifact_passes(self):
        VERIFIER.verify(
            REPO_ROOT / VERIFIER.DEFAULT_ROOT,
            False,
            VERIFIER.EXPORTER.DEFAULT_SOURCE,
        )

    def test_checksum_mutation_fails_closed(self):
        source = REPO_ROOT / VERIFIER.DEFAULT_ROOT
        with tempfile.TemporaryDirectory(
            prefix="flipguard_mnist_cnn_verify_test_"
        ) as temporary:
            root = Path(temporary) / "artifact"
            shutil.copytree(source, root)
            path = root / "configuration_validation.csv"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(
                ValueError,
                "checksum mismatch",
            ):
                VERIFIER.verify(
                    root,
                    False,
                    VERIFIER.EXPORTER.DEFAULT_SOURCE,
                )


if __name__ == "__main__":
    unittest.main()
