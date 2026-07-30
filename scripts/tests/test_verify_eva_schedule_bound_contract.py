import copy
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/verify_eva_schedule_bound_contract.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_schedule_bound_contract",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VerifyEVAScheduleBoundContractTest(unittest.TestCase):
    def test_repository_contract_passes(self) -> None:
        summary = MODULE.verify(MODULE.DEFAULT_CONTRACT)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["required_q_primes"], 3)
        self.assertEqual(summary["rescale_levels"], 2)
        self.assertEqual(summary["security_v2_headroom_bits"], 190)
        self.assertFalse(summary["paper_claim_allowed"])

    def test_policy_mutation_is_rejected(self) -> None:
        contract = MODULE.load_json(
            MODULE.absolute(MODULE.DEFAULT_CONTRACT)
        )
        mutated = copy.deepcopy(contract)
        mutated["policy"]["candidate_trials"] = 2
        self.assertNotEqual(
            mutated["policy"]["candidate_trials"],
            contract["policy"]["candidate_trials"],
        )
        with self.assertRaisesRegex(ValueError, "execution policy changed"):
            policy = mutated["policy"]
            MODULE.require(
                policy["margin_floor"] == 0.001
                and policy["safety_factor"] == 0.5
                and policy["validation_key_repeats"] == 3
                and policy["audit_key_repeats"] == 3
                and policy["candidate_trials"] == 1
                and policy["synthesis_calls"] == 0
                and policy["repair_calls"] == 0
                and policy["retuning"] == 0,
                "execution policy changed",
            )


if __name__ == "__main__":
    unittest.main()
