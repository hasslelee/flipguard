import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "analyze_structural_audit_failure",
    ROOT / "scripts/analyze_structural_audit_failure.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StructuralAuditFailureAnalysisTest(unittest.TestCase):
    def test_quantile_interpolates(self):
        self.assertEqual(MODULE.quantile([0.0, 10.0], 0.25), 2.5)

    def test_sha256_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value"
            path.write_bytes(b"flipguard")
            self.assertEqual(
                MODULE.sha256(path),
                "sha256:3e1624323279becccc15d64c4a3c5fa4d146dbf833d3ab"
                "0ad9048815493a4ec5",
            )


if __name__ == "__main__":
    unittest.main()
