import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
MODULE_PATH = ROOT / "scripts/build_journal_multiclass_extension_checkpoint_v1.py"
SPEC = importlib.util.spec_from_file_location("checkpoint_builder", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class JournalMulticlassCheckpointTest(unittest.TestCase):
    def test_build_and_verify_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "checkpoint"
            MODULE.build(ROOT, output)
            manifest = MODULE.verify(output, ROOT)
            self.assertEqual(manifest["source_commit"], MODULE.SOURCE_COMMIT)

    def test_builder_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "checkpoint"
            output.mkdir()
            with self.assertRaisesRegex(RuntimeError, "refusing to overwrite"):
                MODULE.build(ROOT, output)


if __name__ == "__main__":
    unittest.main()
