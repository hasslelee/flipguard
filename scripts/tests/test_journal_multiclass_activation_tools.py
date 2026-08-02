import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "activation", ROOT / "scripts/freeze_journal_multiclass_activation_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class JournalMulticlassActivationToolsTest(unittest.TestCase):
    def test_frozen_comparator_identity_is_full_length(self):
        self.assertEqual(len(MODULE.COMPARATOR_SOURCE_COMMIT), 40)
        self.assertEqual(len(MODULE.COMPARATOR_BINARY_DIGEST), 71)

    def test_parameter_signature_is_literal_not_candidate_id(self):
        candidate = {
            "id": "ignored",
            "path": "rescale",
            "parameters": {"log_n": 13, "log_q": [42, 29], "log_p": [42], "log_default_scale": 29},
        }
        self.assertEqual(
            MODULE.parameter_signature(candidate),
            {"path": "rescale", "log_n": 13, "log_q": [42, 29], "log_p": [42], "log_default_scale": 29},
        )

    def test_gap_boundaries_use_frozen_left_closed_rule(self):
        rows = []
        for index, gap in enumerate([0.1, 0.2, 0.3, 0.4, 0.5], start=1):
            rows.append(
                {
                    "sample_id": f"s{index}", "top_two_gap": gap, "argmax_flip": False,
                    "reserve_policy_violation": False, "minimum_cap_required": 0.01,
                }
            )
        summary = MODULE.summarize_gap_bins(rows, [0.15, 0.25, 0.35, 0.45])
        self.assertEqual([row["unique_samples"] for row in summary], [1, 1, 1, 1, 1])

    def test_boundary_value_stays_in_lower_bin(self):
        rows = [
            {
                "sample_id": f"s{index}", "top_two_gap": gap, "argmax_flip": False,
                "reserve_policy_violation": False, "minimum_cap_required": 0.01,
            }
            for index, gap in enumerate([0.1, 0.2, 0.25, 0.35, 0.425, 0.5])
        ]
        summary = MODULE.summarize_gap_bins(rows, [0.2, 0.3, 0.4, 0.45])
        self.assertEqual([row["unique_samples"] for row in summary], [2, 1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
