import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/verify_exact_security_estimator.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_exact_security_estimator",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactSecurityEstimatorVerifierTest(unittest.TestCase):
    def make_result(self, input_path: Path) -> dict:
        identities = MODULE.expected_identities(input_path)
        objects = []
        for identifier, payload in sorted(identities.items()):
            q = MODULE.exact_product(payload["exact_q_primes"])
            p = MODULE.exact_product(payload["exact_p_primes"])
            for object_type, modulus in (
                ("CIPHERTEXT_Q", q),
                ("EVALUATION_KEY_QP", q * p),
            ):
                attacks = [
                    {
                        "attack": attack,
                        "status": "PASS",
                        "log2_rop": "129.25",
                    }
                    for attack in sorted(MODULE.EXPECTED_ATTACKS)
                ]
                objects.append(
                    {
                        "signature_id": identifier,
                        "object_type": object_type,
                        "log_n": payload["log_n"],
                        "n": 1 << payload["log_n"],
                        "exact_modulus": str(modulus),
                        "exact_modulus_bit_length": modulus.bit_length(),
                        "attacks": attacks,
                        "attack_success_count": 3,
                        "attack_failure_count": 0,
                        "status": "PASS_ESTIMATOR_MODEL",
                    }
                )
        return {
            "schema_version": "flipguard_exact_security_estimator_run_v1",
            "model_id": "test-model",
            "security_policy_id": (
                "security_guidelines_cic2025_table5_2_ternary_128_v2"
            ),
            "security_policy_effect": "NONE_SENSITIVITY_ONLY",
            "input": {"sha256": MODULE.sha256_path(input_path)},
            "estimator": {
                "cost_model": "RC.BDGL16",
                "attacks": sorted(MODULE.EXPECTED_ATTACKS),
                "sample_model": "m=oo",
            },
            "distribution_binding": {
                "xs_match": "EXACT_COEFFICIENT_DISTRIBUTION",
                "xe_match": "SIGMA_MATCH_BOUND_NOT_MODELED",
                "exact_distribution_claim_allowed": False,
            },
            "summary": {
                "paper_claim_allowed": False,
                "run_status": "COMPLETE_ESTIMATOR_EXECUTION",
                "status_counts": {"PASS_ESTIMATOR_MODEL": 18},
                "attack_failures": 0,
            },
            "objects": objects,
        }

    def test_accepts_exact_modulus_results(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-exact-estimator-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "result.json"
            result = self.make_result(MODULE.INPUT_DEFAULT)
            output.write_bytes(MODULE.canonical_json(result))
            summary = MODULE.verify(output)
            self.assertEqual(summary["attack_failures"], 0)
            self.assertEqual(
                summary["status_counts"],
                {"PASS_ESTIMATOR_MODEL": 18},
            )

    def test_rejects_changed_modulus(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-exact-estimator-modulus-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "result.json"
            result = self.make_result(MODULE.INPUT_DEFAULT)
            result["objects"][0]["exact_modulus"] = "17"
            output.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact modulus"):
                MODULE.verify(output)

    def test_rejects_paper_claim_promotion(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-exact-estimator-paper-gate-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "result.json"
            result = self.make_result(MODULE.INPUT_DEFAULT)
            result["summary"]["paper_claim_allowed"] = True
            output.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "paper claim gate"):
                MODULE.verify(output)

    def test_complete_attack_gate_rejects_partial_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "coverage is incomplete"):
            MODULE.require_complete_attack_coverage(
                {"attack_failures": 1}
            )
        MODULE.require_complete_attack_coverage({"attack_failures": 0})


if __name__ == "__main__":
    unittest.main()
