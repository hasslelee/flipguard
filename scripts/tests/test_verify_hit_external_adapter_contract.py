import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/verify_hit_external_adapter_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_hit_external_adapter_contract",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HITExternalAdapterContractTest(unittest.TestCase):
    def test_frozen_contract_passes(self) -> None:
        summary = MODULE.validate_contract()
        self.assertEqual(summary["source_count"], 8)
        self.assertEqual(summary["candidate_trials"], 1)
        self.assertFalse(summary["paper_claim_allowed"])

    def test_concrete_security_measurement_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["expected_literal"]["concrete_product_log_qp"] = 241
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "concrete-product LogQP changed",
            ):
                MODULE.validate_contract()

    def test_retuning_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["policy"]["retuning"] = 1
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "retuning was enabled",
            ):
                MODULE.validate_contract()


if __name__ == "__main__":
    unittest.main()
