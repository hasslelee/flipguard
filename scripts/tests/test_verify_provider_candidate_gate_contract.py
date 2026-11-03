import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/verify_provider_candidate_gate_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_provider_candidate_gate_contract",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProviderCandidateGateContractTest(unittest.TestCase):
    def test_frozen_contract_passes(self) -> None:
        summary = MODULE.validate_contract()
        self.assertEqual(summary["arm_count"], 4)
        self.assertEqual(summary["validation_rows"], 14)
        self.assertEqual(summary["audit_rows"], 16)
        self.assertFalse(summary["paper_claim_allowed"])

    def test_policy_digest_mutation_fails(self) -> None:
        original = MODULE.load_json(MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT)
        split = MODULE.load_json(
            MODULE.REPO_ROOT /
            "results/thesis_grade_protocol/tabular_splits_v1/"
            "split_seed_0/iris_binary/linear_poly3/"
            "split_manifest.json"
        )
        mutated = copy.deepcopy(original)
        mutated["policy"]["direct_policy_digest"] = "sha256:" + "0" * 64
        with mock.patch.object(MODULE, "load_json") as load_json:
            load_json.side_effect = [mutated, split]
            with self.assertRaisesRegex(ValueError, "policy changed"):
                MODULE.validate_contract()


if __name__ == "__main__":
    unittest.main()
