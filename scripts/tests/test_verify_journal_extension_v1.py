import importlib.util
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "final_verifier", ROOT / "scripts/verify_journal_extension_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class JournalExtensionFinalVerifierTest(unittest.TestCase):
    def test_immutable_paths_cover_all_declared_core_artifacts(self):
        self.assertIn("docs/thesis", MODULE.IMMUTABLE_PATHS)
        self.assertIn("results/thesis_grade_protocol/paper_artifacts_v3/final", MODULE.IMMUTABLE_PATHS)
        self.assertIn("docs/evidence/research_completion_checkpoint_v10", MODULE.IMMUTABLE_PATHS)

    def test_rc2_tag_is_still_bound(self):
        commit = subprocess.check_output(
            ["git", "rev-parse", "flipguard-thesis-v1.0.0-rc2^{}"], cwd=ROOT, text=True
        ).strip()
        self.assertEqual(commit, MODULE.RC2_COMMIT)


if __name__ == "__main__":
    unittest.main()
