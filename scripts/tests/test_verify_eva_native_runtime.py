import csv
import importlib.util
import json
import shutil
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
            shutil.copy2(
                REPO_ROOT
                / "docs/evidence/eva_external_adapter_replay_v1/run/"
                "compiled_program.dot",
                root / "compiled_program.dot",
            )
            self._write_ledger(
                root / "validation_ledger.csv", 14, 3, "0.405"
            )
            self._write_ledger(
                root / "locked_audit_ledger.csv", 16, 3, "0.405"
            )
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
                "compiler_output_sha256": self._contract_value(
                    "compiler_binding", "compiler_output_sha256"
                ),
                "compiled_program_sha256": self._contract_value(
                    "compiler_binding", "compiled_program_sha256"
                ),
                "compiled_program_identity": (
                    self._compiled_program_identity()
                ),
                "candidate": self._candidate(),
                "direct_policy_digest": MODULE.DIRECT_DIGEST,
                "security_policy_digest": MODULE.SECURITY_DIGEST,
                "runtime_security_claim": (
                    "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
                ),
                "policy_modifications": 0,
                "validation": {"status": "SAFE", "counts": counts},
                "locked_audit": {
                    "status": "SAFE",
                    "counts": MODULE.verify_ledger(
                        root / "locked_audit_ledger.csv",
                        threshold=0.5,
                        alpha=0.5,
                        margin_floor=0.001,
                    ),
                },
                "accounting": {
                    "candidate_trials": 1,
                    "validation_key_runs": 3,
                    "validation_encrypted_sample_evaluations": 42,
                    "locked_audit_key_runs": 3,
                    "locked_audit_encrypted_sample_evaluations": 48,
                    "synthesis_calls": 0,
                    "repair_calls": 0,
                    "retuning": 0,
                },
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
            shutil.copy2(
                REPO_ROOT
                / "docs/evidence/eva_external_adapter_replay_v1/run/"
                "compiled_program.dot",
                root / "compiled_program.dot",
            )
            self._write_ledger(
                root / "validation_ledger.csv", 14, 3, "0.6"
            )
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
                "compiler_output_sha256": self._contract_value(
                    "compiler_binding", "compiler_output_sha256"
                ),
                "compiled_program_sha256": self._contract_value(
                    "compiler_binding", "compiled_program_sha256"
                ),
                "compiled_program_identity": (
                    self._compiled_program_identity()
                ),
                "candidate": self._candidate(),
                "direct_policy_digest": MODULE.DIRECT_DIGEST,
                "security_policy_digest": MODULE.SECURITY_DIGEST,
                "runtime_security_claim": (
                    "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION"
                ),
                "policy_modifications": 0,
                "validation": {"status": "REJECTED", "counts": counts},
                "locked_audit": {"status": "NOT_EVALUATED"},
                "accounting": {
                    "candidate_trials": 1,
                    "validation_key_runs": 3,
                    "validation_encrypted_sample_evaluations": 42,
                    "locked_audit_key_runs": 0,
                    "locked_audit_encrypted_sample_evaluations": 0,
                    "synthesis_calls": 0,
                    "repair_calls": 0,
                    "retuning": 0,
                },
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

    def _write_ledger(
        self,
        path: Path,
        sample_count: int,
        key_count: int,
        native_score: str,
    ) -> None:
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
            for key_repeat in range(1, key_count + 1):
                for sample in range(sample_count):
                    writer.writerow(
                        {
                            "phase": "test",
                            "row_id": str(sample),
                            "key_repeat": str(key_repeat),
                            "execution_status": "OK",
                            "plaintext_score": plain,
                            "native_ckks_score": score,
                            "decision_margin": margin,
                            "error_budget": budget,
                            "absolute_error": error,
                            "normalized_budget_usage": error / budget,
                            "certifiable": "true",
                            "decision_flip": (
                                "true"
                                if (plain >= 0.5) != (score >= 0.5)
                                else "false"
                            ),
                            "error_violation": (
                                "true" if error >= budget else "false"
                            ),
                        }
                    )

    def _contract_value(self, section: str, key: str):
        contract = MODULE.load_json(MODULE.CONTRACT_DEFAULT)
        return contract[section][key]

    def _candidate(self):
        compiler = MODULE.load_json(MODULE.CONTRACT_DEFAULT)[
            "compiler_binding"
        ]
        return {
            "poly_modulus_degree": compiler["poly_modulus_degree"],
            "prime_bits": compiler["prime_bits"],
            "q": compiler["q"],
            "p": compiler["p"],
            "input_scale_bits": compiler["input_scale_bits"],
        }

    def _compiled_program_identity(self):
        compiler = MODULE.load_json(MODULE.CONTRACT_DEFAULT)[
            "compiler_binding"
        ]
        return {
            "expected_raw_sha256": compiler["compiled_program_sha256"],
            "observed_raw_sha256": compiler["compiled_program_sha256"],
            "semantic_sha256": compiler[
                "compiled_program_semantic_sha256"
            ],
            "identity_class": "BYTE_IDENTICAL",
        }

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
