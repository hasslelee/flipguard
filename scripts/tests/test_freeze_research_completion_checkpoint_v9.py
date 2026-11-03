import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v9.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v9", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointV9Test(unittest.TestCase):
    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v9-", dir="/tmp"
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_cross_runtime_pack_is_bound_fail_closed(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_cross_runtime_readiness(
            manifests["eva_cross_runtime_replay_readiness"]
        )
        gate = MODULE.cross_runtime_gate_summary()
        self.assertFalse(gate["encrypted_execution_allowed"])
        self.assertEqual(
            gate["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )
        self.assertFalse(gate["selected_native_exact_qp_captured"])
        self.assertFalse(gate["matched_population_available"])

    def test_claim_registry_does_not_promote_cross_runtime(self) -> None:
        self.assertEqual(
            MODULE.CLAIM_STATES["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES["native_eva_seal_decision_certification"],
            "PARTIALLY_SUPPORTED",
        )


if __name__ == "__main__":
    unittest.main()
