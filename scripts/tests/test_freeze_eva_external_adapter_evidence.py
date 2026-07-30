import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / (
    "scripts/freeze_eva_external_adapter_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_external_adapter_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FreezeEVAExternalAdapterEvidenceTest(unittest.TestCase):
    def test_frozen_pack_when_present(self) -> None:
        root = MODULE.REPO_ROOT / MODULE.DEFAULT_OUTPUT
        if not root.is_dir():
            self.skipTest("EVA evidence pack not frozen yet")
        manifest = MODULE.verify_frozen(root)
        self.assertEqual(
            manifest["status"],
            "BLOCKED_GRAPH_COMPATIBILITY",
        )
        self.assertFalse(manifest["paper_claim_allowed"])
        self.assertEqual(
            manifest["summary"]["encrypted_candidate_trials"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
