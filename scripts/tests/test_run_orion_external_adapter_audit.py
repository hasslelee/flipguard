import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/run_orion_external_adapter_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "run_orion_external_adapter_audit",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RunOrionExternalAdapterAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )

    def test_pinned_source_urls(self) -> None:
        sources = {
            source["source_id"]: source
            for source in self.contract["sources"]
        }
        mlp = MODULE.source_url(
            self.contract,
            sources["orion_mlp_config"],
        )
        self.assertIn(self.contract["upstream"]["commit"], mlp)
        self.assertTrue(mlp.endswith("/configs/mlp.yml"))
        fork = MODULE.source_url(
            self.contract,
            sources["orion_lattigo_ckks_params"],
        )
        self.assertIn(self.contract["upstream"]["backend_commit"], fork)
        target = MODULE.source_url(
            self.contract,
            sources["flipguard_lattigo_ckks_params"],
        )
        self.assertIn(
            self.contract["upstream"]["comparison_backend_commit"],
            target,
        )

    def test_report_validation_preserves_blocked_claims(self) -> None:
        reports = {}
        for config in self.contract["configurations"]:
            reports[config["config_id"]] = {
                "status": config["predicted_status"],
                "block_reasons": config["predicted_reasons"],
                "encrypted_execution": False,
                "candidate_request_emitted": False,
                "policy_modification_count": 0,
                "parsed_parameters": {"log_n": 13},
                "security_assessment": {
                    "log_qp": 217,
                    "final_admission": "FAIL",
                },
            }
        summary = MODULE.validate_reports(self.contract, reports)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["counts"]["encrypted_executions"], 0)
        self.assertEqual(
            summary["claim_states"]["lossless_orion_candidate_import"],
            "BLOCKED",
        )
        self.assertEqual(
            summary["claim_states"]["third_party_autotuner_integration"],
            "NOT_EVALUATED",
        )

    def test_report_validation_rejects_reason_removal(self) -> None:
        reports = {}
        for config in self.contract["configurations"]:
            reasons = list(config["predicted_reasons"])
            if config["config_id"] == "orion_mlp_public_config":
                reasons.pop()
            reports[config["config_id"]] = {
                "status": config["predicted_status"],
                "block_reasons": reasons,
                "encrypted_execution": False,
                "candidate_request_emitted": False,
                "policy_modification_count": 0,
                "parsed_parameters": {"log_n": 13},
                "security_assessment": None,
            }
        with self.assertRaisesRegex(ValueError, "block reasons changed"):
            MODULE.validate_reports(self.contract, reports)


if __name__ == "__main__":
    unittest.main()
