import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_eva_native_scale_sensitivity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_eva_native_scale_sensitivity", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EVANativeScaleSensitivityFreezerTest(unittest.TestCase):
    def test_original_native_pack_is_still_valid(self) -> None:
        result = MODULE.BASE.verify(MODULE.ORIGINAL_PACK)
        self.assertEqual(result["validation_status"], "REJECTED")
        self.assertEqual(result["locked_audit_status"], "NOT_EVALUATED")
        self.assertFalse(result["paper_claim_allowed"])

    def test_log_normalization_is_stable(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-eva-scale-log-", dir="/tmp"
        ) as temporary:
            path = Path(temporary) / "execution.log"
            path.write_text("one  \n two\t\n", encoding="utf-8")
            self.assertEqual(
                MODULE.BASE.normalized_log_bytes(path),
                b"one\n two\n",
            )


if __name__ == "__main__":
    unittest.main()
