import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/bind_eva_selected_exact_materialization_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bind_eva_selected_exact_materialization_v1",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVASelectedExactMaterializationV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = MODULE.build_binding()

    def test_binds_expected_exact_literal(self) -> None:
        literal = self.binding["exact_literal"]["parameters"]
        self.assertEqual(literal["log_n"], 14)
        self.assertEqual(literal["log_default_scale"], 30)
        self.assertEqual(
            literal["q"],
            [
                1152921504605962241,
                1152921504606584833,
                1152921504606683137,
            ],
        )
        self.assertEqual(literal["p"], [1152921504606748673])
        self.assertEqual(
            self.binding["security_reference"][
                "final_reference_admission"
            ],
            "PASS",
        )

    def test_preserves_original_capture_boundary(self) -> None:
        bridge = self.binding["materializer_bridge"]
        self.assertFalse(
            bridge["exact_qp_captured_in_original_selected_run"]
        )
        self.assertTrue(
            bridge["exact_qp_bound_by_posthoc_static_replay"]
        )
        self.assertTrue(
            bridge["deterministic_materializer_inputs_identical"]
        )
        self.assertEqual(
            self.binding["status"],
            "EXACT_MATERIALIZATION_BOUND_POSTHOC",
        )

    def test_does_not_open_cross_runtime_or_paper_claims(self) -> None:
        boundary = self.binding["claim_boundary"]
        self.assertEqual(
            boundary["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            boundary["runtime_specific_native_security"],
            "NOT_EVALUATED",
        )
        self.assertEqual(self.binding["encrypted_executions_added"], 0)
        self.assertEqual(self.binding["policy_modifications"], 0)
        self.assertFalse(self.binding["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
