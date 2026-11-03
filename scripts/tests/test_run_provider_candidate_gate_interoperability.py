import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/run_provider_candidate_gate_interoperability.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_provider_candidate_gate_interoperability",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProviderCandidateGateRunnerTest(unittest.TestCase):
    def test_execution_source_closure_is_deterministic(self) -> None:
        first_files, first_digest = MODULE.execution_source_closure()
        second_files, second_digest = MODULE.execution_source_closure()
        self.assertEqual(first_files, second_files)
        self.assertEqual(first_digest, second_digest)
        self.assertRegex(first_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertIn(
            "cmd/flipguard-certify-candidate/main.go",
            first_files,
        )
        self.assertIn(
            "cmd/flipguard-audit-candidate/main.go",
            first_files,
        )
        self.assertIn(
            "internal/providergate/provider_candidate.go",
            first_files,
        )

    def test_initialize_refuses_existing_run_root(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-provider-runner-test-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            with self.assertRaises(FileExistsError):
                MODULE.initialize(
                    REPO_ROOT / MODULE.DEFAULT_CONTRACT,
                    root,
                    "a" * 40,
                    "a" * 40,
                )


if __name__ == "__main__":
    unittest.main()
