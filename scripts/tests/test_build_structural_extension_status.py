import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "build_structural_extension_status",
    ROOT / "scripts/build_structural_extension_status.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StructuralExtensionStatusTest(unittest.TestCase):
    def test_preserved_checkpoint_is_partial_scientific_result(self):
        document = MODULE.expected_document()
        self.assertEqual(document["stage_status"], "PARTIAL_SCIENTIFIC_RESULT")
        self.assertEqual(document["counts"]["locked_audit_pass"], 24)
        self.assertEqual(document["counts"]["locked_audit_rejected"], 1)
        self.assertEqual(document["counts"]["policy_modification_after_audit"], 0)


if __name__ == "__main__":
    unittest.main()
