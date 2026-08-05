import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ExternalV5TimingTest(unittest.TestCase):
    def test_records_success_and_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "run"
            completed = subprocess.run([
                "python3", str(ROOT / "scripts/run_external_v5_timed.py"),
                "--provider", "fixture", "--workload", "fixture",
                "--stage", "fixture", "--mode", "pipeline",
                "--output-dir", str(output), "--", "printf", "hello\\n",
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((output / "run_manifest.json").read_text())
            self.assertEqual(record["exit_status"], 0)
            self.assertEqual(record["cpu_affinity"], "0,1")
            self.assertTrue(record["stdout_sha256"].startswith("sha256:"))
            self.assertEqual((output / "stdout.log").read_text(), "hello\n")
            state = json.loads((output / "run_state.json").read_text())
            heartbeat = json.loads((output / "heartbeat.json").read_text())
            self.assertEqual(state["status"], "PASS")
            self.assertEqual(heartbeat["status"], "PASS")

    def test_relative_output_survives_changed_command_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command_cwd = root / "provider"
            command_cwd.mkdir()
            completed = subprocess.run([
                "python3", str(ROOT / "scripts/run_external_v5_timed.py"),
                "--provider", "fixture", "--workload", "fixture",
                "--stage", "fixture", "--mode", "pipeline",
                "--output-dir", "run", "--cwd", str(command_cwd),
                "--", "printf", "hello\\n",
            ], cwd=root, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads((root / "run/run_manifest.json").read_text())
            self.assertEqual(record["exit_status"], 0)

    def test_detached_launcher_outlives_launcher_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger"
            marker = root / "completed.txt"
            completed = subprocess.run([
                sys.executable, str(ROOT / "scripts/launch_external_v5_detached.py"),
                "--label", "fixture", "--ledger-dir", str(ledger),
                "--cwd", str(root), "--", sys.executable, "-c",
                "import pathlib,time; time.sleep(0.5); pathlib.Path('completed.txt').write_text('done')",
            ], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for _ in range(30):
                if marker.exists():
                    break
                time.sleep(0.1)
            self.assertEqual(marker.read_text(), "done")
            record = json.loads((ledger / "fixture.json").read_text())
            self.assertTrue(record["alive_after_launch"])


if __name__ == "__main__":
    unittest.main()
