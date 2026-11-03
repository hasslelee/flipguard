import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/run_decision_contract_activation_control.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_decision_contract_activation_control",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DecisionContractActivationRunnerTest(unittest.TestCase):
    def test_generated_input_passes_runner_gate(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-decision-activation-runner-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary) / "input"
            source_commit = "a" * 40
            subprocess.run(
                [
                    "go",
                    "run",
                    "./research/decisionactivation/cmd",
                    "--output",
                    str(root),
                    "--source-commit",
                    source_commit,
                ],
                cwd=REPO_ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            static = MODULE.validate_input_root(root)
            self.assertEqual(static["source_commit"], source_commit)
            self.assertEqual(static["static_claim_state"], "SUPPORTED")
            self.assertEqual(
                [row["aggregate_sensitivity"] for row in static["regimes"]],
                [120.803, 120.803],
            )
            for name in ("narrow_margin", "wide_margin"):
                for suffix in ("validation", "locked_audit"):
                    rows = (
                        root / f"{name}_{suffix}.csv"
                    ).read_text(encoding="ascii").splitlines()[1:]
                    self.assertTrue(rows)
                    self.assertTrue(
                        all(row.split(",", 1)[0].isdigit() for row in rows)
                    )

    def test_execution_closure_digest_is_deterministic(self) -> None:
        head = MODULE.git("rev-parse", "HEAD")
        first = MODULE.commit_source_digest(head)
        self.assertEqual(first, MODULE.commit_source_digest(head))
        self.assertRegex(
            first,
            r"^sha256:[0-9a-f]{64}$",
        )


if __name__ == "__main__":
    unittest.main()
