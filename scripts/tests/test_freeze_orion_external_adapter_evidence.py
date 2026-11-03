import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_orion_external_adapter_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_orion_external_adapter_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FreezeOrionExternalAdapterEvidenceTest(unittest.TestCase):
    def test_checksum_verifier_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-orion-freezer-test-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            artifact = root / "artifact.json"
            artifact.write_text("{}\n", encoding="ascii")
            MODULE.write_checksums(root)
            MODULE.verify_checksums(root)
            artifact.write_text('{"changed":true}\n', encoding="ascii")
            with self.assertRaisesRegex(
                ValueError,
                "artifact changed",
            ):
                MODULE.verify_checksums(root)

    def test_default_output_is_non_overwriting_pack(self) -> None:
        self.assertEqual(
            MODULE.DEFAULT_OUTPUT.as_posix(),
            "docs/evidence/orion_external_adapter_audit_v1",
        )

    def test_frozen_actual_orion_pack_verifies(self) -> None:
        summary = MODULE.verify()
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(
            summary["counts"]["actual_public_configurations"],
            3,
        )
        self.assertEqual(
            summary["counts"]["blocked_semantic_mismatch"],
            3,
        )
        self.assertEqual(summary["counts"]["encrypted_executions"], 0)
        self.assertFalse(summary["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
