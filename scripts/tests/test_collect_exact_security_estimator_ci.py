import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/collect_exact_security_estimator_ci.py"
)
SPEC = importlib.util.spec_from_file_location(
    "collect_exact_security_estimator_ci",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactSecurityEstimatorCollectorTest(unittest.TestCase):
    def test_refuses_incomplete_run(self) -> None:
        completed = mock.Mock()
        completed.stdout = (
            '{"workflowName":"Exact Security Estimator",'
            '"status":"in_progress"}'
        )
        with mock.patch.object(
            MODULE,
            "run_command",
            return_value=completed,
        ):
            with self.assertRaisesRegex(ValueError, "not completed"):
                MODULE.load_run(123)

    def test_refuses_wrong_workflow(self) -> None:
        completed = mock.Mock()
        completed.stdout = (
            '{"workflowName":"Different Workflow","status":"completed"}'
        )
        with mock.patch.object(
            MODULE,
            "run_command",
            return_value=completed,
        ):
            with self.assertRaisesRegex(ValueError, "workflow="):
                MODULE.load_run(123)

    def test_refuses_overwrite_before_network_access(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-exact-ci-overwrite-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            with mock.patch.object(MODULE, "load_run") as load_run:
                with self.assertRaises(FileExistsError):
                    MODULE.collect(123, output)
                load_run.assert_not_called()

    def test_incomplete_collection_classification_is_explicit(self) -> None:
        self.assertEqual(
            MODULE.collection_classification({"missing"}, "failure"),
            "PRE_ESTIMATOR_IMPLEMENTATION_RECOVERY",
        )
        self.assertEqual(
            MODULE.collection_classification(set(), "success"),
            "COMPLETE_ARTIFACT_COLLECTION",
        )
        self.assertEqual(
            MODULE.collection_classification(set(), "failure"),
            "POST_ESTIMATOR_ARTIFACT_FINALIZATION_RECOVERY",
        )


if __name__ == "__main__":
    unittest.main()
