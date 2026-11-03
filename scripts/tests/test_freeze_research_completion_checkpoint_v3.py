import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v3",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    (
        REPO_ROOT
        / "docs/evidence/exact_security_estimator_v1/manifest.json"
    ).is_file(),
    "exact security estimator evidence is not frozen",
)
class ResearchCompletionCheckpointV3Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v3-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v3-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_security_and_replay_boundaries_remain_qualified(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES["security"],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["artifact_reproducibility"],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["portable_checkpoint_replay"],
            "SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["external_source_replay"],
            "NOT_EVALUATED",
        )

    def test_linked_pack_semantics(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_exact_estimator(
            manifests["exact_security_estimator"]
        )
        MODULE.validate_independent_replay(
            manifests["independent_machine_replay"]
        )


if __name__ == "__main__":
    unittest.main()
