import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v4",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    (
        REPO_ROOT / "docs/evidence/external_source_replay_v1/manifest.json"
    ).is_file(),
    "external source replay evidence is not frozen",
)
class ResearchCompletionCheckpointV4Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v4-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v4-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_replay_boundary_remains_qualified(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES["external_source_replay"],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["artifact_reproducibility"],
            "PARTIALLY_SUPPORTED",
        )
        manifests = MODULE.load_manifests()
        MODULE.validate_external_source_replay(
            manifests["external_source_replay"]
        )


if __name__ == "__main__":
    unittest.main()
