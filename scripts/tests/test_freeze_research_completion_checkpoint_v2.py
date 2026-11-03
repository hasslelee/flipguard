import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_research_completion_checkpoint_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_research_completion_checkpoint_v2",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCompletionCheckpointV2Test(unittest.TestCase):
    def test_freeze_and_verify_current_authoritative_packs(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v2-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            MODULE.verify(output)

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-research-checkpoint-v2-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            MODULE.freeze(output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(output, "freezer-source-commit")

    def test_claim_vocabulary_and_boundary_are_closed(self) -> None:
        self.assertTrue(
            set(MODULE.CLAIM_STATES.values())
            <= MODULE.V1.ALLOWED_STATES
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "decision_contract_candidate_synthesis_effect"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.CLAIM_STATES[
                "finite_domain_decision_contract_activation"
            ],
            "SUPPORTED",
        )

    def test_activation_pack_semantics(self) -> None:
        manifests = MODULE.load_manifests()
        MODULE.validate_activation(
            manifests["decision_contract_activation"]
        )

    def test_rejects_generated_python_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-evidence-hygiene-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            generated = root / "__pycache__"
            generated.mkdir()
            (generated / "module.pyc").write_bytes(b"generated")
            with self.assertRaisesRegex(
                ValueError,
                "generated Python artifacts",
            ):
                MODULE.validate_evidence_tree_hygiene(root)


if __name__ == "__main__":
    unittest.main()
