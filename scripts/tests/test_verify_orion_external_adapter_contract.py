import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/verify_orion_external_adapter_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_orion_external_adapter_contract",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OrionExternalAdapterContractTest(unittest.TestCase):
    def test_frozen_contract_passes(self) -> None:
        summary = MODULE.validate_contract()
        self.assertEqual(summary["source_count"], 9)
        self.assertEqual(summary["configuration_count"], 3)
        self.assertFalse(summary["encrypted_execution_allowed"])
        self.assertFalse(summary["paper_claim_allowed"])

    def test_encrypted_execution_mutation_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["execution"]["encrypted_execution_allowed"] = True
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "encrypted execution was enabled",
            ):
                MODULE.validate_contract()

    def test_distribution_reason_removal_fails(self) -> None:
        original = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        mutated = copy.deepcopy(original)
        mutated["configurations"][0]["predicted_reasons"].remove(
            "SECRET_DISTRIBUTION_MISMATCH"
        )
        with mock.patch.object(MODULE, "load_json", return_value=mutated):
            with self.assertRaisesRegex(
                ValueError,
                "predicted reasons changed",
            ):
                MODULE.validate_contract()


if __name__ == "__main__":
    unittest.main()
