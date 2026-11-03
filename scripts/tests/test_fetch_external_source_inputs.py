import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/fetch_external_source_inputs.py"
SPEC = importlib.util.spec_from_file_location(
    "fetch_external_source_inputs",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalSourceFetchTest(unittest.TestCase):
    def test_validate_source_accepts_exact_file(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-source-",
            dir="/tmp",
        ) as temporary:
            path = Path(temporary) / "source.bin"
            path.write_bytes(b"source")
            spec = {
                "bytes": 6,
                "sha256": MODULE.sha256_path(path),
            }
            MODULE.validate_source(path, spec)

    def test_validate_source_rejects_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-source-mismatch-",
            dir="/tmp",
        ) as temporary:
            path = Path(temporary) / "source.bin"
            path.write_bytes(b"source")
            spec = {"bytes": 6, "sha256": "0" * 64}
            with self.assertRaisesRegex(ValueError, "sha256"):
                MODULE.validate_source(path, spec)

    def test_verify_local_sources_and_manifest(self) -> None:
        manifest = {
            "schema_version": MODULE.SCHEMA_VERSION,
            "status": "PASS",
            "classification": "EXTERNAL_SOURCE_FETCH_ONLY",
            "source_commit": "source-commit",
            "started_at": "start",
            "ended_at": "end",
            "sources": [
                {
                    **spec,
                    "disposition": "EXISTING_VERIFIED",
                }
                for spec in MODULE.SOURCE_SPECS
            ],
            "derived_extractions": [
                MODULE.ensure_bsds500_extraction(REPO_ROOT)
            ],
            "encrypted_execution": {
                "candidate_trials": 0,
                "key_runs": 0,
                "sample_evaluations": 0,
            },
            "policy_modifications": 0,
            "paper_claim_allowed": False,
        }
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-source-manifest-",
            dir="/tmp",
        ) as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_bytes(MODULE.canonical_json(manifest))
            verified = MODULE.verify(REPO_ROOT, path)
            self.assertEqual(verified["status"], "PASS")

    def test_refuses_manifest_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-external-source-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "manifest.json"
            output.write_text(json.dumps({}), encoding="ascii")
            with self.assertRaises(FileExistsError):
                MODULE.fetch(
                    REPO_ROOT,
                    output,
                    attempts=1,
                    timeout_seconds=1,
                )


if __name__ == "__main__":
    unittest.main()
