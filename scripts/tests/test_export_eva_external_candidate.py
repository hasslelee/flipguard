import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/export_eva_external_candidate.py"
SPEC = importlib.util.spec_from_file_location(
    "export_eva_external_candidate",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVAExternalCandidateExporterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_json(
            REPO_ROOT / (
                "experiments/eva_external_adapter_v1/contract.json"
            )
        )

    def test_materialization_splits_final_key_prime(self) -> None:
        degree = 8192
        q = [1073153, 1097729, 1146881, 1179649, 1204225, 1220609, 1269761]
        p = 1294337
        values = q + [p]
        # Use actual bit lengths in this unit fixture; primality is tested by
        # SEAL in the pinned CI materializer.
        bits = [value.bit_length() for value in values]
        materialized = {
            "schema_version":
                "flipguard_eva_seal_prime_materialization_v1",
            "poly_modulus_degree": degree,
            "prime_bits": bits,
            "key_context_coeff_modulus": values,
            "first_context_coeff_modulus": q,
            "special_modulus": p,
            "using_keyswitching": True,
        }
        for index, value in enumerate(values):
            values[index] = (
                (value // (2 * degree)) * (2 * degree) + 1
            )
        materialized["key_context_coeff_modulus"] = values
        materialized["first_context_coeff_modulus"] = values[:-1]
        materialized["special_modulus"] = values[-1]
        materialized["prime_bits"] = [
            value.bit_length() for value in values
        ]
        actual_q, actual_p = MODULE.validate_materialization(
            degree,
            materialized["prime_bits"],
            materialized,
        )
        self.assertEqual(actual_q, values[:-1])
        self.assertEqual(actual_p, values[-1:])

    def test_graph_incompatible_candidate_is_fail_closed(self) -> None:
        q = [
            1125899906826241,
            1125899906629633,
            1125899906424833,
        ]
        p = [1125899906334721]
        request, gate = MODULE.derive_candidate(
            self.contract,
            8192,
            q,
            p,
        )
        self.assertEqual(
            gate["status"],
            "BLOCKED_GRAPH_COMPATIBILITY",
        )
        self.assertFalse(gate["encrypted_execution_allowed"])
        self.assertEqual(request["parameters"]["q"], q)
        self.assertEqual(request["parameters"]["p"], p)

    def test_security_failure_precedes_graph_gate(self) -> None:
        q = [(1 << 59) + 1] * 7
        p = [(1 << 59) + 3]
        _, gate = MODULE.derive_candidate(
            self.contract,
            8192,
            q,
            p,
        )
        self.assertEqual(gate["status"], "BLOCKED_SECURITY_V2")
        self.assertFalse(gate["encrypted_execution_allowed"])


if __name__ == "__main__":
    unittest.main()
