#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from build_journal_multiclass_analysis_plan_v1 import midpoint_boundaries  # noqa: E402
from freeze_journal_multiclass_results_v1 import add_observations, summarize_groups  # noqa: E402


class JournalMulticlassEvidenceToolsTest(unittest.TestCase):
    def test_quintile_boundaries_use_adjacent_midpoints(self) -> None:
        values = [float(value) for value in range(500)]
        self.assertEqual(midpoint_boundaries(values), [99.5, 199.5, 299.5, 399.5])

    def test_observation_replay_uses_all_challengers_for_minimum_cap(self) -> None:
        labels = {f"sample_{index:03d}": 0 for index in range(500)}
        observations = []
        for key_run in range(1, 4):
            for sample_id in labels:
                observations.append(
                    {
                        "sample_id": sample_id,
                        "key_run": key_run,
                        "plain_logits": [2.0, 1.0, 0.0],
                        "ckks_logits": [2.1, 0.8, 0.3],
                        "per_logit_absolute_error": [0.1, 0.2, 0.3],
                        "plaintext_top_1": 0,
                        "plaintext_top_2": 1,
                        "ckks_top_1": 0,
                        "top_two_gap": 1.0,
                        "pairwise_decision_budget": 0.5,
                        "minimum_cap_required": 0.3,
                        "certifiable": True,
                        "plaintext_tie": False,
                        "argmax_flip": False,
                        "reserve_policy_pass": True,
                        "reserve_policy_violation": False,
                    }
                )
        rows: list[dict] = []
        add_observations(
            rows,
            "fixture",
            "fixture_model",
            "configuration_validation",
            "fixture_candidate",
            {"aggregation": {"observations": observations}},
            labels,
            [0.5, 1.5, 2.5, 3.5],
        )
        self.assertEqual(len(rows), 1500)
        self.assertEqual(rows[0]["minimum_cap_required"], "0.29999999999999999")
        self.assertEqual(rows[0]["gap_bin"], 2)
        grouped = summarize_groups(rows, ["model_name", "role", "label"])
        self.assertEqual(grouped[0]["unique_samples"], 500)
        self.assertEqual(grouped[0]["fresh_key_observations"], 1500)


if __name__ == "__main__":
    unittest.main()
