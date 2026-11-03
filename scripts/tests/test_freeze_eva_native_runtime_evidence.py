import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_eva_native_runtime_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_native_runtime_evidence", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVANativeRuntimeEvidenceTest(unittest.TestCase):
    def test_log_normalization_preserves_content_and_line_boundaries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "actions.log"
            source.write_bytes(b"first \t \r\nsecond\t\r\nthird")
            self.assertEqual(
                MODULE.normalized_log_bytes(source),
                b"first\nsecond\nthird\n",
            )

    def test_summary_preserves_safe_native_boundary(self) -> None:
        contract = MODULE.VERIFIER.load_json(MODULE.CONTRACT)
        result = {
            "status": "PASS",
            "classification": (
                "SOURCE_REPLAYED_PUBLIC_COMPILER_NATIVE_RUNTIME_CONTROL"
            ),
            "validation": {"status": "SAFE", "counts": {}},
            "locked_audit": {"status": "SAFE", "counts": {}},
            "accounting": {},
            "candidate": {},
            "runtime": {},
            "runtime_security_claim": (
                "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
            ),
            "claim_states": {
                "native_eva_seal_decision_certification": "SUPPORTED"
            },
        }
        summary = MODULE.build_summary(result, contract)
        self.assertEqual(
            summary["claim_states"]["native_eva_seal_locked_audit"],
            "SUPPORTED",
        )
        self.assertEqual(
            summary["claim_states"]["cross_runtime_numerical_equivalence"],
            "NOT_EVALUATED",
        )
        self.assertFalse(summary["paper_claim_allowed"])

    def test_summary_preserves_rejected_native_boundary(self) -> None:
        contract = MODULE.VERIFIER.load_json(MODULE.CONTRACT)
        result = {
            "status": "PARTIAL_SCIENTIFIC_RESULT",
            "classification": (
                "SOURCE_REPLAYED_PUBLIC_COMPILER_NATIVE_RUNTIME_CONTROL"
            ),
            "validation": {"status": "REJECTED", "counts": {}},
            "locked_audit": {"status": "NOT_EVALUATED"},
            "accounting": {},
            "candidate": {},
            "runtime": {},
            "runtime_security_claim": (
                "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
            ),
            "claim_states": {
                "native_eva_seal_decision_certification": "BLOCKED"
            },
        }
        summary = MODULE.build_summary(result, contract)
        self.assertEqual(
            summary["claim_states"]["native_eva_seal_locked_audit"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            summary["claim_states"][
                "native_eva_seal_decision_certification"
            ],
            "BLOCKED",
        )

    @unittest.skipUnless(
        MODULE.OUTPUT_DEFAULT.is_dir(),
        "native EVA evidence is not frozen yet",
    )
    def test_frozen_pack_verifies(self) -> None:
        result = MODULE.verify()
        self.assertFalse(result["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
