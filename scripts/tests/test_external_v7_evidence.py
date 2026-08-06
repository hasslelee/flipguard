import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ExternalV7EvidenceTest(unittest.TestCase):
    def test_builder_is_fail_closed_on_actual_v7_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            subprocess.run(
                [
                    "python3",
                    "scripts/external_v7/build_external_v7_evidence.py",
                    "--destination",
                    str(destination),
                    "--source-commit",
                    "TEST_COMMIT",
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            with (destination / "artifact_execution_levels.csv").open(newline="") as handle:
                levels = {row["system"]: row for row in csv.DictReader(handle)}
            self.assertEqual(len(levels), 18)
            self.assertEqual(levels["EVA"]["evidence_level"], "6")
            self.assertEqual(levels["ELASM"]["encrypted_e2e_runs"], "70")
            capture = ROOT / "external/v7/outputs/heir/dot-product-8f-output-capture-v1/decrypted_outputs.csv"
            self.assertEqual(levels["HEIR"]["evidence_level"], "3" if capture.is_file() else "2")
            self.assertEqual(levels["HECO"]["evidence_level"], "2")
            self.assertEqual(levels["ANT-ACE"]["evidence_level"], "0")

            with (destination / "failure_summary.csv").open(newline="") as handle:
                failures = list(csv.DictReader(handle))
            plan_failures = {
                row["run_id"] for row in failures if row["stage"] == "ENCRYPTED_PLAN_EXECUTION"
            }
            self.assertEqual(plan_failures, {"elasm_36", "elasm_41"})

            claims = json.loads((destination / "claim_admission.json").read_text())
            self.assertEqual(claims["encrypted_e2e_system_count"], 3 if capture.is_file() else 2)
            self.assertEqual(claims["decision_bearing_provider_count"], 1)
            self.assertEqual(claims["final_classification"], "PARTIAL_EXTERNAL_EVIDENCE")
            self.assertFalse(claims["paper_claim_allowed"])

            with (destination / "execution_accounting.csv").open(newline="") as handle:
                accounting = {row["system"]: row for row in csv.DictReader(handle)}
            self.assertEqual(accounting["EVA"]["unique_inputs"], "31")
            self.assertEqual(accounting["EVA"]["encrypted_candidate_runs"], "18")
            self.assertEqual(accounting["EVA"]["contexts_keysets"], "18")
            self.assertEqual(accounting["ELASM"]["unique_inputs"], "1")
            self.assertEqual(accounting["ELASM"]["contexts_keysets"], "72")
            self.assertEqual(accounting["ELASM"]["source_commit"], "3c37c11b29ca480525bb6681e0254bdf90029425")
            self.assertIn("compile_wall_clock_seconds", accounting["ELASM"])
            self.assertIn("inference_wall_clock_seconds", accounting["ELASM"])

            per_sample = json.loads(
                (destination / "per_sample_outputs/manifest.json").read_text()
            )
            self.assertEqual(per_sample["row_counts"]["eva_official"], 24576)
            self.assertEqual(per_sample["row_counts"]["eva_shared"], 174)
            self.assertEqual(per_sample["row_counts"]["corelab"], 72)
            self.assertEqual(per_sample["row_counts"]["heir"], 2 if capture.is_file() else 0)
            for directory in (
                "workload_contracts", "input_manifests", "provider_candidate_manifests",
                "operation_manifests", "per_sample_outputs",
            ):
                self.assertTrue((destination / directory / "manifest.json").is_file())
