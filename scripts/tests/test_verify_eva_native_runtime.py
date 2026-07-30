import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/verify_eva_native_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_native_runtime", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVANativeRuntimeVerifierTest(unittest.TestCase):
    def test_predeclared_contract_is_bound(self) -> None:
        contract = MODULE.validate_contract()
        self.assertEqual(
            contract["execution_protocol"]["validation_key_repeats"], 3
        )
        self.assertEqual(
            contract["execution_protocol"]["locked_audit_key_repeats"], 3
        )
        self.assertEqual(
            contract["security_interpretation"][
                "formal_security_v2_runtime_claim"
            ],
            "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        )
        self.assertFalse(contract["paper_claim_allowed"])

    def test_safe_validation_requires_safe_locked_audit(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-eva-native-verifier-", dir="/tmp"
        ) as temporary:
            root = Path(temporary)
            self._write_ledger(root / "validation_ledger.csv", "0.405")
            self._write_ledger(root / "locked_audit_ledger.csv", "0.405")
            contract_sha = MODULE.sha256_path(MODULE.CONTRACT_DEFAULT)
            counts = MODULE.verify_ledger(
                root / "validation_ledger.csv",
                threshold=0.5,
                alpha=0.5,
                margin_floor=0.001,
            )
            manifest = {
                "schema_version": (
                    "flipguard_eva_native_runtime_result_v1"
                ),
                "status": "PASS",
                "contract_sha256": contract_sha,
                "direct_policy_digest": MODULE.DIRECT_DIGEST,
                "security_policy_digest": MODULE.SECURITY_DIGEST,
                "policy_modifications": 0,
                "validation": {"status": "SAFE", "counts": counts},
                "locked_audit": {"status": "SAFE", "counts": counts},
                "paper_claim_allowed": False,
            }
            (root / "manifest.json").write_bytes(
                MODULE.canonical_json(manifest)
            )
            self._write_checksums(root)
            result = MODULE.verify_result(root)
            self.assertEqual(result["locked_audit_status"], "SAFE")

    def test_non_safe_validation_forbids_audit(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-eva-native-reject-", dir="/tmp"
        ) as temporary:
            root = Path(temporary)
            self._write_ledger(root / "validation_ledger.csv", "0.6")
            contract_sha = MODULE.sha256_path(MODULE.CONTRACT_DEFAULT)
            counts = MODULE.verify_ledger(
                root / "validation_ledger.csv",
                threshold=0.5,
                alpha=0.5,
                margin_floor=0.001,
            )
            manifest = {
                "schema_version": (
                    "flipguard_eva_native_runtime_result_v1"
                ),
                "status": "PARTIAL_SCIENTIFIC_RESULT",
                "contract_sha256": contract_sha,
                "direct_policy_digest": MODULE.DIRECT_DIGEST,
                "security_policy_digest": MODULE.SECURITY_DIGEST,
                "policy_modifications": 0,
                "validation": {"status": "REJECTED", "counts": counts},
                "locked_audit": {"status": "NOT_EVALUATED"},
                "paper_claim_allowed": False,
            }
            (root / "manifest.json").write_bytes(
                MODULE.canonical_json(manifest)
            )
            self._write_checksums(root)
            result = MODULE.verify_result(root)
            self.assertEqual(
                result["locked_audit_status"], "NOT_EVALUATED"
            )

    def _write_ledger(self, path: Path, native_score: str) -> None:
        plain = 0.405941150447
        score = float(native_score)
        margin = abs(plain - 0.5)
        budget = 0.5 * margin
        error = abs(score - plain)
        fields = [
            "phase",
            "row_id",
            "key_repeat",
            "execution_status",
            "plaintext_score",
            "native_ckks_score",
            "decision_margin",
            "error_budget",
            "absolute_error",
            "normalized_budget_usage",
            "certifiable",
            "decision_flip",
            "error_violation",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "phase": "test",
                    "row_id": "1",
                    "key_repeat": "1",
                    "execution_status": "OK",
                    "plaintext_score": plain,
                    "native_ckks_score": score,
                    "decision_margin": margin,
                    "error_budget": budget,
                    "absolute_error": error,
                    "normalized_budget_usage": error / budget,
                    "certifiable": "true",
                    "decision_flip": (
                        "true" if (plain >= 0.5) != (score >= 0.5)
                        else "false"
                    ),
                    "error_violation": (
                        "true" if error >= budget else "false"
                    ),
                }
            )

    def _write_checksums(self, root: Path) -> None:
        lines = []
        for path in sorted(root.iterdir()):
            if path.is_file() and path.name != "SHA256SUMS":
                digest = MODULE.hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f"{digest}  {path.name}")
        (root / "SHA256SUMS").write_text(
            "\n".join(lines) + "\n", encoding="ascii"
        )


if __name__ == "__main__":
    unittest.main()
