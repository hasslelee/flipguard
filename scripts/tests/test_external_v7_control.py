import importlib.util
import csv
import json
from pathlib import Path
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalV7ControlTest(unittest.TestCase):
    def test_atomic_text_is_safe_across_master_threads(self):
        master = load_module(
            "master_queue_v7_atomic_test",
            ROOT / "scripts/external_v7/master_queue_v7.py",
        )
        errors = []
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "master_state.json"

            def write_many(worker: int):
                try:
                    for sequence in range(50):
                        master.atomic_text(target, f"{worker}:{sequence}\n")
                except Exception as error:  # pragma: no cover - asserted below
                    errors.append(error)

            threads = [threading.Thread(target=write_many, args=(worker,)) for worker in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertRegex(target.read_text(), r"^\d+:\d+\n$")
            self.assertEqual(list(target.parent.glob(".master_state.json.tmp-*")), [])

    def test_queue_is_ordered_and_unique(self):
        payload = json.loads(
            (ROOT / "docs/evidence/external_end_to_end_code_v7/execution_queue.json").read_text()
        )
        providers = payload["providers"]
        self.assertEqual([row["priority"] for row in providers], list(range(1, 18)))
        self.assertEqual(len({row["id"] for row in providers}), 17)
        for row in providers:
            runner = row["id"].replace("-", "_")
            self.assertTrue(
                (ROOT / f"scripts/external_v7/providers/run_{runner}_v7.sh").is_file(),
                row["id"],
            )

    def test_service_owns_long_running_process(self):
        unit = (ROOT / "scripts/external_v7/flipguard-external-v7.service").read_text()
        self.assertIn("run_master_queue_v7.sh", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("KillMode=control-group", unit)

    def test_missing_value_vocabulary_has_no_numeric_zero(self):
        module = load_module(
            "normalize_provider_output_v7",
            ROOT / "scripts/external_v7/normalize_provider_output_v7.py",
        )
        self.assertNotIn(0, module.MISSING)
        self.assertIn("NOT_EVALUATED", module.MISSING)

    def test_recoveries_reuse_completed_stages(self):
        dispatcher = (ROOT / "scripts/external_v7/run_provider_job_v7.sh").read_text()
        heir_recovery = (
            ROOT / "scripts/external_v7/providers/run_heir_recovery_v7.sh"
        ).read_text()
        self.assertIn("run_corelab_recovery_v7.sh", dispatcher)
        self.assertIn("run_heir_recovery_v7.sh", dispatcher)
        self.assertIn("run_heco_recovery_v7.sh", dispatcher)
        self.assertIn("run_orion_recovery_v7.sh", dispatcher)
        self.assertIn("0002-openfhe-lattigo-e2e/current_stage.txt", dispatcher)
        self.assertNotIn("bazelisk", heir_recovery)
        self.assertIn("encrypted_execution_reused", heir_recovery)

        heco_recovery = (
            ROOT / "scripts/external_v7/providers/run_heco_recovery_v7.sh"
        ).read_text()
        self.assertNotIn("../build/bin/benchmark", heco_recovery)
        self.assertIn("0004-official-encrypted-benchmark", heco_recovery)
        self.assertIn("encrypted_execution_reused", heco_recovery)

        orion_recovery = (
            ROOT / "scripts/external_v7/providers/run_orion_recovery_v7.sh"
        ).read_text()
        self.assertIn("poetry-core==1.9.1", orion_recovery)
        self.assertIn("0002b-environment-recovery1", orion_recovery)
        self.assertIn("be8a827350a147d610fe3bb998b5bea8de814ff8", orion_recovery)

    def test_output_root_repair_requires_idle_queue_and_lock(self):
        repair = (ROOT / "scripts/external_v7/prepare_writable_output_root_v7.sh").read_text()
        self.assertIn("QUEUE_EXHAUSTED_QA", repair)
        self.assertIn('"${master[2]}" != NONE', repair)
        self.assertIn("flock -n", repair)
        self.assertIn("outputs-root-owned-attempt1", repair)
        self.assertIn('"encrypted_execution": 0', repair)

    def test_elasm_grid_resume_is_canonical_and_cleans_ephemeral_keys(self):
        grid_path = ROOT / "scripts/external_v7/run_elasm_grid_v7.py"
        grid_source = grid_path.read_text()
        wrapper = (ROOT / "scripts/external_v7/run_elasm_grid_v7.sh").read_text()
        recovery = (
            ROOT / "scripts/external_v7/providers/run_corelab_recovery_v7.sh"
        ).read_text()
        self.assertIn("def plan_sequence()", grid_source)
        self.assertIn("noncanonical resume prefix", grid_source)
        self.assertIn("shutil.rmtree(context_root)", grid_source)
        self.assertIn('"ephemeral_key_context_retained": False', grid_source)
        self.assertIn("--resume", wrapper)
        self.assertIn("resume_args=(--resume)", recovery)

        grid = load_module("run_elasm_grid_v7", grid_path)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            run_dir = output / "eva_15"
            run_dir.mkdir(parents=True)
            for name in (
                "compile.stdout",
                "compile.stderr",
                "optimized.mlir",
                "plan.hevm",
                "constants.cst",
                "execute.stdout",
                "execute.stderr",
                "result.json",
                "decrypted_outputs.npz",
            ):
                (run_dir / name).touch()
            row = {field: "" for field in grid.FIELDS}
            row.update(
                {
                    "mode": "eva",
                    "waterline": "15",
                    "compile_status": "PASS",
                    "encrypted_end_to_end": "true",
                }
            )
            with (output / "records.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=grid.FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerow(row)
            self.assertEqual(len(grid.load_resume_records(output, True)), 1)

            row["waterline"] = "16"
            with (output / "records.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=grid.FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "noncanonical resume prefix"):
                grid.load_resume_records(output, True)

    def test_heir_supplementary_capture_is_output_only_and_bounded(self):
        runner = (
            ROOT / "scripts/external_v7/providers/run_heir_output_capture_v7.sh"
        ).read_text()
        patch = (
            ROOT / "scripts/external_v7/patches/heir-dot-product-output-capture-v1.patch"
        ).read_text()
        amendment = json.loads(
            (
                ROOT
                / "docs/evidence/external_end_to_end_code_v7/orchestration_amendment_008.json"
            ).read_text()
        )
        self.assertIn("0005-output-capture-e2e-v1", runner)
        self.assertIn("--nocache_test_results", runner)
        self.assertIn("heir-output-capture-v1", runner)
        self.assertIn("FLIPGUARD_V7_OPENFHE_ACTUAL", patch)
        self.assertIn("FLIPGUARD_V7_LATTIGO_ACTUAL", patch)
        self.assertFalse(amendment["patch_semantic_change"])
        self.assertEqual(amendment["maximum_provider_attempt"], 3)

    def test_finalizer_separates_preparation_from_hard_pause_freeze(self):
        master = (ROOT / "scripts/external_v7/master_queue_v7.py").read_text()
        finalizer = (ROOT / "scripts/external_v7/finalize_external_v7.py").read_text()
        self.assertIn("--prepare-finalization", master)
        self.assertIn('"--freeze"', master)
        self.assertIn("if now() < pause:", finalizer)
        self.assertIn("refusing to overwrite nonidentical evidence", finalizer)
        self.assertIn("write_json_once_or_verify", finalizer)
        self.assertIn("prepared V7 raw result index drift", finalizer)
        self.assertIn('"raw_file_count": len(raw_files)', finalizer)
        self.assertIn('"declared_hard_pause_timestamp"', finalizer)
        self.assertIn('"docker_system_df"', finalizer)
        self.assertIn('"policy_bindings"', finalizer)
        self.assertIn("--preflight-only", finalizer)

    def test_queue_exhausted_wait_is_interruptible(self):
        master = (ROOT / "scripts/external_v7/master_queue_v7.py").read_text()
        self.assertNotIn("time.sleep(min(300", master)
        self.assertIn("self.stop_requested.wait(", master)

    def test_hard_pause_runs_fail_closed_qa_and_commit(self):
        master = (ROOT / "scripts/external_v7/master_queue_v7.py").read_text()
        final_qa = (ROOT / "scripts/external_v7/final_qa_commit_v7.sh").read_text()
        self.assertIn("final_qa_commit_v7.sh", master)
        self.assertIn("FINAL_QA_COMMIT_FAILED", master)
        self.assertIn("unexpected working-tree changes", final_qa)
        self.assertIn("sha256sum -c SHA256SUMS", final_qa)
        self.assertNotIn("run_provider_job_v7.sh", final_qa)


if __name__ == "__main__":
    unittest.main()
