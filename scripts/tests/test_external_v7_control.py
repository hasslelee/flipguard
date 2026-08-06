import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalV7ControlTest(unittest.TestCase):
    def test_queue_is_ordered_and_unique(self):
        payload = json.loads(
            (ROOT / "docs/evidence/external_end_to_end_code_v7/execution_queue.json").read_text()
        )
        providers = payload["providers"]
        self.assertEqual([row["priority"] for row in providers], list(range(1, 18)))
        self.assertEqual(len({row["id"] for row in providers}), 17)
        for row in providers:
            runner = row["id"].replace("-", "_")
            self.assertTrue(
                (ROOT / f"scripts/external_v7/providers/run_{runner}_v7.sh").is_file(),
                row["id"],
            )

    def test_service_owns_long_running_process(self):
        unit = (ROOT / "scripts/external_v7/flipguard-external-v7.service").read_text()
        self.assertIn("run_master_queue_v7.sh", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("KillMode=control-group", unit)

    def test_missing_value_vocabulary_has_no_numeric_zero(self):
        module = load_module(
            "normalize_provider_output_v7",
            ROOT / "scripts/external_v7/normalize_provider_output_v7.py",
        )
        self.assertNotIn(0, module.MISSING)
        self.assertIn("NOT_EVALUATED", module.MISSING)


if __name__ == "__main__":
    unittest.main()
