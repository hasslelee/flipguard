import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / (
    "scripts/verify_eva_external_adapter_output.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_external_adapter_output",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVAExternalAdapterOutputTest(unittest.TestCase):
    def test_deterministic_u64_primality(self) -> None:
        for value in MODULE.EXPECTED_Q + MODULE.EXPECTED_P:
            self.assertTrue(MODULE.is_prime_u64(value))
        self.assertFalse(MODULE.is_prime_u64(MODULE.EXPECTED_Q[0] * 3))

    def test_frozen_output_when_present(self) -> None:
        root = MODULE.REPO_ROOT / MODULE.DEFAULT_ROOT
        if not root.is_dir():
            self.skipTest("EVA evidence pack not frozen yet")
        summary = MODULE.verify(root)
        self.assertEqual(
            summary["status"],
            "BLOCKED_GRAPH_COMPATIBILITY",
        )
        self.assertEqual(summary["encrypted_candidate_trials"], 0)
        self.assertFalse(summary["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
