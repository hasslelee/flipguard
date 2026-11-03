import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/freeze_exact_security_estimator_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_exact_security_estimator_evidence",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactSecurityEstimatorFreezerTest(unittest.TestCase):
    def test_static_admission_covers_all_exported_identities(self) -> None:
        admissions = MODULE.static_admission_map()
        self.assertEqual(len(admissions), 9)
        self.assertEqual(
            {record["final_admission"] for record in admissions.values()},
            {"PASS", "FAIL"},
        )

    def test_overall_status_fails_on_admitted_counterexample(self) -> None:
        summaries = [
            {
                "static_admitted_estimator_failures": 1,
                "static_admitted_estimator_incomplete": 0,
            }
        ]
        self.assertEqual(
            MODULE.overall_status(summaries),
            "FALSIFIED_FOR_STATIC_ADMITTED_OBJECT",
        )

    def test_overall_status_preserves_incomplete_coverage(self) -> None:
        summaries = [
            {
                "static_admitted_estimator_failures": 0,
                "static_admitted_estimator_incomplete": 1,
            }
        ]
        self.assertEqual(
            MODULE.overall_status(summaries),
            "PARTIALLY_SUPPORTED",
        )

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-exact-security-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                MODULE.freeze(
                    MODULE.RAW_ROOT_DEFAULT,
                    output,
                    "freezer-commit",
                )


if __name__ == "__main__":
    unittest.main()
