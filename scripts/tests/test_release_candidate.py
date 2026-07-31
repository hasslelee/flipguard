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

    def test_archive_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="flipguard-release-test-") as temp:
            first = Path(temp) / "first.tar.zst"
            second = Path(temp) / "second.tar.zst"
            one = MODULE.build(ROOT, "HEAD", first)
            two = MODULE.build(ROOT, "HEAD", second)
            self.assertEqual(one["archive_sha256"], two["archive_sha256"])
            self.assertFalse(one["raw_external_sources_bundled"])


if __name__ == "__main__":
    unittest.main()
