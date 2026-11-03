import importlib.util
import math
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/exact_estimator_numeric.py"
SPEC = importlib.util.spec_from_file_location(
    "exact_estimator_numeric",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FloatOnlyValue:
    def __init__(self, value: float) -> None:
        self.value = value

    def __float__(self) -> float:
        return self.value


class ExactEstimatorNumericTest(unittest.TestCase):
    def test_formats_existing_53_bit_value_without_promotion(self) -> None:
        self.assertEqual(
            MODULE.format_53bit_real(
                FloatOnlyValue(295.299952585424)
            ),
            "295.299952585424",
        )

    def test_rejects_non_finite_cost(self) -> None:
        for value in (math.inf, -math.inf, math.nan):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "must be finite"):
                    MODULE.format_53bit_real(value)


if __name__ == "__main__":
    unittest.main()
