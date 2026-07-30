import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v7.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v7",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointV7Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v7-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v7-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_native_eva_claims_are_fail_closed(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES["native_eva_seal_runtime_execution"],
            "SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "native_eva_seal_decision_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["native_eva_seal_locked_audit"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )
        self.assertFalse(
            MODULE.CLAIM_STATES[
                "general_external_compiler_interoperability"
            ]
            == "SUPPORTED"
        )

    def test_native_eva_pack_is_bound(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_eva_native(
            manifests["eva_native_runtime_replay"]
        )


if __name__ == "__main__":
    unittest.main()
