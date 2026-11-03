import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/audit_eva_cross_runtime_replay_readiness_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_eva_cross_runtime_replay_readiness_v1", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVACrossRuntimeReplayReadinessV1Test(unittest.TestCase):
    def test_current_state_fails_closed_with_exact_blockers(self) -> None:
        state = MODULE.inspect_current_state()
        self.assertEqual(
            set(state["blockers"]),
            {
                "SELECTED_NATIVE_EXACT_QP_NOT_CAPTURED",
                "LATTIGO_ADAPTER_BINDS_SCALE20_NOT_SELECTED_SCALE30",
                "PROVIDER_GATE_BINDS_SCALE20_SOURCE_DIGEST",
                "LATTIGO_NATIVE_PAIRED_POPULATION_MISSING",
                "RUNTIME_SPECIFIC_SECURITY_DISTRIBUTIONS_DIFFER",
            },
        )
        self.assertFalse(
            state["selected_native_candidate"][
                "exact_qp_captured_in_selected_run"
            ]
        )
        self.assertFalse(
            state["lattigo_adapter"]["supports_selected_scale30"]
        )

    def test_same_materializer_inputs_do_not_promote_identity(self) -> None:
        state = MODULE.inspect_current_state()
        bridge = state["deterministic_materialization_bridge"]
        self.assertTrue(
            bridge["same_degree_and_ordered_prime_bits_as_scale20"]
        )
        self.assertFalse(bridge["formal_identity_usable"])
        self.assertEqual(len(bridge["derived_q"]), 3)
        self.assertEqual(len(bridge["derived_p"]), 1)

    def test_summary_prohibits_encrypted_execution(self) -> None:
        summary = MODULE.build_summary(MODULE.inspect_current_state())
        self.assertEqual(
            summary["status"], "NOT_READY_INTEGRITY_PRESERVING_REPLAY"
        )
        self.assertFalse(summary["encrypted_execution_allowed"])
        self.assertFalse(summary["paper_claim_allowed"])
        self.assertEqual(summary["policy_modifications"], 0)
        self.assertEqual(summary["encrypted_executions_added"], 0)


if __name__ == "__main__":
    unittest.main()
