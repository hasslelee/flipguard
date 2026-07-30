import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/collect_external_source_replay_ci.py"
SPEC = importlib.util.spec_from_file_location(
    "collect_external_source_replay_ci",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalSourceReplayCollectorTest(unittest.TestCase):
    def test_complete_classification_requires_both_passes(self) -> None:
        self.assertEqual(
            MODULE.classification("success", "PASS"),
            "COMPLETE_EXTERNAL_SOURCE_REPLAY",
        )
        for workflow, replay in (
            ("failure", "PASS"),
            ("success", "FAIL"),
            ("failure", "FAIL"),
        ):
            with self.subTest(workflow=workflow, replay=replay):
                self.assertEqual(
                    MODULE.classification(workflow, replay),
                    "RECOVERABLE_SOURCE_REPLAY_IMPLEMENTATION_FAILURE",
                )


if __name__ == "__main__":
    unittest.main()
