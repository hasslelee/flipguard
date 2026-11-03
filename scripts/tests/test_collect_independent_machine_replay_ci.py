from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/collect_independent_machine_replay_ci.py"
)
SPEC = importlib.util.spec_from_file_location(
    "collect_independent_machine_replay_ci",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IndependentMachineReplayCollectorTest(unittest.TestCase):
    def test_classification_distinguishes_success_and_recovery(self) -> None:
        self.assertEqual(
            MODULE.collection_classification(False, "success"),
            "COMPLETE_INDEPENDENT_REPLAY",
        )
        self.assertEqual(
            MODULE.collection_classification(False, "failure"),
            "INDEPENDENT_REPLAY_RECOVERY",
        )
        self.assertEqual(
            MODULE.collection_classification(True, "failure"),
            "INDEPENDENT_REPLAY_RECOVERY",
        )

    def test_refuses_overwrite_before_network_access(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-replay-collector-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with mock.patch.object(MODULE, "load_run") as load_run:
                with self.assertRaises(FileExistsError):
                    MODULE.collect(1, output)
                load_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
