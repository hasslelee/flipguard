import json
import subprocess
import tempfile
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


if __name__ == "__main__":
    unittest.main()
