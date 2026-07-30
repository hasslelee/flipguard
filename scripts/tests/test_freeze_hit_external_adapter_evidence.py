import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_hit_external_adapter_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_hit_external_adapter_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FreezeHITExternalAdapterEvidenceTest(unittest.TestCase):
    def test_selected_run_paths_exclude_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bin").mkdir()
            (root / "bin/certify").write_text("binary", encoding="ascii")
            (root / "logs").mkdir()
            (root / "logs/selection.log").write_text(
                "log",
                encoding="ascii",
            )
            (root / "summary.json").write_text("{}", encoding="ascii")
            selected = {
                path.relative_to(root).as_posix()
                for path in MODULE.selected_run_paths(root)
            }
            self.assertIn("summary.json", selected)
            self.assertIn("logs/selection.log", selected)
            self.assertNotIn("bin/certify", selected)

    def test_default_output_is_non_overwriting_pack(self) -> None:
        self.assertEqual(
            MODULE.DEFAULT_OUTPUT,
            Path("docs/evidence/hit_external_adapter_replay_v1"),
        )


if __name__ == "__main__":
    unittest.main()
