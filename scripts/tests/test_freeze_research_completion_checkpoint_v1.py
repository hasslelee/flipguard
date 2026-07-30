import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v1",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointTest(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_claim_vocabulary_is_closed(self) -> None:
        self.assertTrue(MODULE.CLAIM_STATES)
        self.assertTrue(
            set(MODULE.CLAIM_STATES.values())
            <= MODULE.ALLOWED_STATES
        )

    def test_verifies_frozen_checkpoint_through_historical_binding(
        self,
    ) -> None:
        MODULE.verify(MODULE.OUTPUT_DEFAULT)


if __name__ == "__main__":
    unittest.main()
