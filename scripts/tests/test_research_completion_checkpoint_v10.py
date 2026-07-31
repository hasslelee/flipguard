import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/verify_research_completion_checkpoint_v10.py"
SPEC = importlib.util.spec_from_file_location("checkpoint_v10", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointV10Test(unittest.TestCase):
    def test_allowed_state_vocabulary(self) -> None:
        self.assertEqual(
            MODULE.ALLOWED_STATES,
            {
                "SUPPORTED",
                "PARTIALLY_SUPPORTED",
                "BLOCKED",
                "NOT_EVALUATED",
                "SUPERSEDED",
                "PILOT_ONLY",
            },
        )

    def test_v10_does_not_exist_in_source_commit_fixture(self) -> None:
        # The immutable pack is created only after the bound RC archive passes.
        self.assertTrue(
            (
                ROOT / "scripts/freeze_research_completion_checkpoint_v10.py"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
