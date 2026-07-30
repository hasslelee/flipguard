import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = REPO_ROOT / "scripts/verify_external_source_replay.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_external_source_replay",
    VERIFY_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
RUNNER_PATH = REPO_ROOT / "scripts/run_external_source_replay.py"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_external_source_replay",
    RUNNER_PATH,
)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


class ExternalSourceReplayVerifierTest(unittest.TestCase):
    def test_static_contract_command_excludes_encrypted_smoke(self) -> None:
        commands = RUNNER.command_specs(Path("/tmp/fetch.json"))
        static = dict(commands)["static_graph_contracts"]
        rendered = " ".join(static)
        self.assertIn(
            "TestBuildCNNLiteWorkloadContractAndSynthesize",
            rendered,
        )
        self.assertNotIn("TestCNNLiteInitialCandidateOneRowSmoke", rendered)

    def test_runner_rejects_fetch_commit_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-replay-source-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            fetch = root / "fetch.json"
            fetch.write_text(
                json.dumps(
                    {
                        "source_commit": "other",
                        "status": "PASS",
                    }
                ),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "does not match"):
                RUNNER.run_replay(
                    root / "replay",
                    "expected",
                    fetch,
                )

    def test_rejects_non_pass_status(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-replay-status-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            record = {
                "schema_version": VERIFY.SCHEMA_VERSION,
                "status": "FAIL",
            }
            (root / "replay.json").write_text(
                json.dumps(record),
                encoding="ascii",
            )
            digest = VERIFY.sha256_path(root / "replay.json")
            (root / "SHA256SUMS").write_text(
                f"{digest}  replay.json\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "replay status"):
                VERIFY.verify(root)

    def test_checksum_verifier_rejects_unindexed_file(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-replay-checksum-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            (root / "indexed.txt").write_text("indexed", encoding="ascii")
            (root / "extra.txt").write_text("extra", encoding="ascii")
            digest = VERIFY.sha256_path(root / "indexed.txt")
            (root / "SHA256SUMS").write_text(
                f"{digest}  indexed.txt\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "checksum coverage"):
                VERIFY.verify_checksums(root)


if __name__ == "__main__":
    unittest.main()
