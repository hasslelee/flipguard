import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v6.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v6",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    (
        REPO_ROOT
        / "docs/evidence/eva_schedule_bound_adapter_replay_v1"
        / "manifest.json"
    ).is_file(),
    "EVA schedule-bound evidence is not frozen",
)
class ResearchCompletionCheckpointV6Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v6-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v6-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_eva_claims_remain_qualified(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "schedule_bound_external_candidate_import"
            ],
            "SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "general_external_compiler_interoperability"
            ],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "encrypted_external_candidate_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["native_eva_seal_runtime_execution"],
            "NOT_EVALUATED",
        )

    def test_eva_evidence_is_fail_closed(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_eva_parameter(
            manifests["eva_compiler_parameter_replay"]
        )
        MODULE.validate_eva_schedule(
            manifests["eva_schedule_bound_replay"]
        )


if __name__ == "__main__":
    unittest.main()
