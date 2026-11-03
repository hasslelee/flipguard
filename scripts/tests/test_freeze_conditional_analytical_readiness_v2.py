import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_conditional_analytical_readiness_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_conditional_analytical_readiness_v2",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConditionalAnalyticalFreezeTest(unittest.TestCase):
    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-analytical-freeze-test-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            raw = root / "raw"
            output = root / "evidence"
            MODULE.BUILDER.build(raw, "derivation-source-commit")
            MODULE.freeze(raw, output, "freezer-source-commit")
            MODULE.verify(output)

            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="ascii")
            )
            self.assertEqual(
                manifest["accounting"]["primary_candidates"],
                50,
            )
            self.assertEqual(
                manifest["accounting"]["proof_eligible_candidates"],
                0,
            )
            self.assertEqual(
                manifest["claims"][
                    "conditional_propagation_lemma"
                ],
                "SUPPORTED",
            )
            self.assertEqual(
                manifest["claims"][
                    "instantiated_ckks_analytical_certificate"
                ],
                "BLOCKED",
            )

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-analytical-freeze-overwrite-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            raw = root / "raw"
            output = root / "evidence"
            MODULE.BUILDER.build(raw, "derivation-source-commit")
            MODULE.freeze(raw, output, "freezer-source-commit")
            with self.assertRaises(FileExistsError):
                MODULE.freeze(raw, output, "freezer-source-commit")


if __name__ == "__main__":
    unittest.main()
