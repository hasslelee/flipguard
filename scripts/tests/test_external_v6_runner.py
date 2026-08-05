from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "external_v6_run_stage", ROOT / "scripts/external_v6/run_stage.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalV6RunnerTest(unittest.TestCase):
    def test_atomic_text_and_digest_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "nested/value.txt"
            MODULE.atomic_text(path, "value\n")
            first = MODULE.digest_path(root)
            second = MODULE.digest_path(root)
            self.assertEqual(first, second)
            self.assertTrue(first.startswith("sha256:"))

    def test_missing_path_is_not_false_zero(self) -> None:
        self.assertEqual(MODULE.digest_path(None), "NOT_AVAILABLE")

    def test_source_digest_excludes_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.atomic_text(root / "source.txt", "source\n")
            MODULE.atomic_text(root / ".git/HEAD", "ref: refs/heads/main\n")
            before = MODULE.digest_path(root, exclude_vcs=True)
            MODULE.atomic_text(root / ".git/HEAD", "ref: refs/heads/other\n")
            self.assertEqual(before, MODULE.digest_path(root, exclude_vcs=True))


if __name__ == "__main__":
    unittest.main()
