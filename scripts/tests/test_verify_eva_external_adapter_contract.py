import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/verify_eva_external_adapter_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_external_adapter_contract",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVAExternalAdapterContractTest(unittest.TestCase):
    def test_predeclared_contract_passes(self) -> None:
        summary = MODULE.validate_contract()
        self.assertEqual(summary["source_count"], 13)
        self.assertEqual(summary["required_q_primes"], 7)
        self.assertEqual(summary["candidate_trials"], 1)
        self.assertFalse(summary["paper_claim_allowed"])

    def test_prime_padding_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["translation_contract"]["prime_padding_allowed"] = True
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "prime_padding_allowed was enabled",
            ):
                MODULE.validate_contract()

    def test_compiler_config_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["compiler_input"]["compiler_config"]["rescaler"] = "always"
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "compiler configuration changed",
            ):
                MODULE.validate_contract()

    def test_security_policy_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["policy"]["security_v2_caps"]["13"] = 218
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "Security V2 caps changed",
            ):
                MODULE.validate_contract()


if __name__ == "__main__":
    unittest.main()
