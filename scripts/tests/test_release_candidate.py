import gzip
import hashlib
import io
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/build_flipguard_release_candidate.py"
SPEC = importlib.util.spec_from_file_location("release_builder", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VERIFY_PATH = ROOT / "scripts/verify_flipguard_release_candidate.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "release_verifier", VERIFY_PATH
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)
FETCH_PATH = ROOT / "scripts/fetch_release_external_sources.py"
FETCH_SPEC = importlib.util.spec_from_file_location(
    "release_fetcher", FETCH_PATH
)
assert FETCH_SPEC is not None and FETCH_SPEC.loader is not None
FETCH = importlib.util.module_from_spec(FETCH_SPEC)
FETCH_SPEC.loader.exec_module(FETCH)


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, encoding: str) -> None:
        super().__init__(payload)
        self.headers = {"Content-Encoding": encoding}


class ReleaseCandidateTest(unittest.TestCase):
    def test_external_registry_binds_derived_artifacts(self) -> None:
        registry = json.loads(
            (ROOT / "release/external_sources_v1.json").read_text()
        )
        self.assertFalse(registry["raw_sources_bundled"])
        self.assertEqual(len(registry["sources"]), 2)
        for source in registry["sources"]:
            self.assertEqual(len(source["expected_sha256"]), 64)
            for relative in source["derived_artifact_manifests"]:
                self.assertTrue((ROOT / relative).is_file())

    def test_gzip_transport_is_preserved_and_semantically_verified(self) -> None:
        content = b"@RELATION test\n@DATA\n1\n"
        payload = gzip.compress(content, mtime=0)
        observed_headers: dict[str, str] = {}

        def opener(request: object) -> FakeResponse:
            observed_headers.update(dict(request.header_items()))
            return FakeResponse(payload, "gzip")

        record = {
            "source_url": "https://example.invalid/data.arff",
            "required_content_encoding": "gzip",
            "expected_sha256": hashlib.sha256(payload).hexdigest(),
            "uncompressed_sha256": hashlib.sha256(content).hexdigest(),
        }
        with tempfile.TemporaryDirectory(
            prefix="flipguard-fetch-test-"
        ) as temporary:
            destination = Path(temporary) / "data.arff.gz"
            FETCH.download_source(record, destination, opener=opener)
            FETCH.verify_download(record, destination)
            self.assertEqual(destination.read_bytes(), payload)
        self.assertEqual(observed_headers["Accept-encoding"], "gzip")

    def test_archive_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="flipguard-release-test-") as temp:
            first = Path(temp) / "first.tar.zst"
            second = Path(temp) / "second.tar.zst"
            one = MODULE.build(ROOT, "HEAD", first)
            two = MODULE.build(ROOT, "HEAD", second)
            self.assertEqual(one["archive_sha256"], two["archive_sha256"])
            self.assertFalse(one["raw_external_sources_bundled"])

    def test_manifest_only_frozen_pack(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-pack-test-"
        ) as temporary:
            root = Path(temporary)
            payload = root / "payload.txt"
            payload.write_text("frozen\n", encoding="ascii")
            digest = VERIFY.sha256(payload)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "files": {
                            "payload.txt": {
                                "bytes": payload.stat().st_size,
                                "sha256": digest,
                            }
                        }
                    }
                ),
                encoding="ascii",
            )
            record = VERIFY.verify_frozen_pack(root)
            self.assertEqual(record["status"], "PASS")
            self.assertEqual(record["mode"], "MANIFEST_FILES")


if __name__ == "__main__":
    unittest.main()
