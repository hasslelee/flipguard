import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v8.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v8", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointV8Test(unittest.TestCase):
    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v8-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_claims_preserve_development_scope(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "native_eva_seal_decision_certification"
            ],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["native_eva_seal_locked_audit"],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "original_scale20_candidate_decision_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )

    def test_scale_pack_is_bound(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_scale_sensitivity(
            manifests["eva_native_scale_sensitivity"]
        )


if __name__ == "__main__":
    unittest.main()
