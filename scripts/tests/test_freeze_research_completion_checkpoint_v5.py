import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v5.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v5",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(
    (
        REPO_ROOT
        / "docs/evidence/hit_external_adapter_rejection_analysis_v1"
        / "manifest.json"
    ).is_file(),
    "actual provider evidence is not frozen",
)
class ResearchCompletionCheckpointV5Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v5-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v5-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_external_provider_claims_remain_qualified(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES["provider_class_interoperability"],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "encrypted_external_candidate_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["general_external_autotuner_integration"],
            "NOT_EVALUATED",
        )

    def test_actual_provider_evidence_is_fail_closed(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_orion(manifests["orion_external_adapter"])
        MODULE.validate_hit(manifests["hit_external_adapter"])
        MODULE.validate_hit_rejection(manifests["hit_rejection_analysis"])


if __name__ == "__main__":
    unittest.main()
