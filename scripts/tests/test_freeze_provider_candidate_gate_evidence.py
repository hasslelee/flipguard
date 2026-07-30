import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_provider_candidate_gate_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_provider_candidate_gate_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FreezeProviderCandidateGateEvidenceTest(unittest.TestCase):
    def test_successful_run_passes_deep_validation(self) -> None:
        validated = MODULE.validate_successful_run()
        self.assertEqual(validated["summary"]["counts"]["selected"], 4)
        self.assertEqual(
            validated["summary"]["counts"]["locked_audit_pass"],
            4,
        )

    def test_failed_run_preserves_fail_closed_incident(self) -> None:
        validated = MODULE.validate_failed_run()
        self.assertEqual(
            validated["incident"]["reason_code"],
            "SELECTION_SPLIT_ID_MANIFEST_MISMATCH",
        )
        self.assertEqual(
            validated["incident"]["locked_audit_results"][
                "encrypted_executions_started"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
