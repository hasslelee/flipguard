import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/verify_eva_native_scale_sensitivity.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_scale_sensitivity", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVANativeScaleSensitivityVerifierTest(unittest.TestCase):
    def test_predeclared_contract_is_bound(self) -> None:
        contract = MODULE.validate_contract()
        self.assertEqual(
            contract["candidate_matrix"]["arm_order"], [20, 30, 40]
        )
        self.assertEqual(
            contract["execution_protocol"][
                "validation_key_repeats_per_arm"
            ],
            3,
        )
        self.assertEqual(
            contract["security_reference"]["runtime_security_claim"],
            "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        )
        self.assertFalse(contract["paper_claim_allowed"])

    def test_security_reference_splits_q_and_special_prime(self) -> None:
        result = MODULE.security_reference(
            degree=16384,
            prime_bits=[60, 60, 60, 60],
            caps={"14": 430},
        )
        self.assertEqual(result["log_q"], 180)
        self.assertEqual(result["log_p"], 60)
        self.assertEqual(result["log_qp"], 240)
        self.assertEqual(result["headroom_bits"], 190)
        self.assertEqual(result["final_admission"], "PASS")

    def test_security_reference_rejects_qp_above_cap(self) -> None:
        result = MODULE.security_reference(
            degree=8192,
            prime_bits=[60, 60, 60, 60],
            caps={"13": 214},
        )
        self.assertEqual(result["ciphertext_q_admission"], "PASS")
        self.assertEqual(
            result["evaluation_key_qp_admission"], "FAIL"
        )
        self.assertEqual(result["final_admission"], "FAIL")

    def test_first_safe_skips_compilation_failure(self) -> None:
        failed = {
            "input_scale_bits": 20,
            "compilation_status": "FAILED",
            "security_reference": {"final_admission": "NOT_EVALUATED"},
            "validation": {"status": "FAILED_COMPILATION"},
        }
        safe = {
            "input_scale_bits": 30,
            "compilation_status": "OK",
            "security_reference": {"final_admission": "PASS"},
            "validation": {"status": "SAFE"},
        }
        later = {
            "input_scale_bits": 40,
            "compilation_status": "OK",
            "security_reference": {"final_admission": "PASS"},
            "validation": {"status": "REJECTED"},
        }
        selected = MODULE.choose_first_safe(
            [failed, safe, later], [20, 30, 40]
        )
        self.assertIs(selected, safe)


if __name__ == "__main__":
    unittest.main()
