from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/freeze_external_source_replay_evidence.py"
SPEC = importlib.util.spec_from_file_location(
    "freeze_external_source_replay_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalSourceReplayEvidenceTest(unittest.TestCase):
    def test_failed_checks_preserves_order(self) -> None:
        replay = {
            "checks": [
                {"name": "first", "status": "PASS"},
                {"name": "second", "status": "FAIL"},
                {"name": "third", "status": "FAIL"},
            ]
        }
        self.assertEqual(
            MODULE.failed_checks(replay),
            ["second", "third"],
        )

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-evidence-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                MODULE.freeze(
                    MODULE.RAW_ROOT_DEFAULT,
                    output,
                    "freezer-commit",
                )


if __name__ == "__main__":
    unittest.main()
