#!/usr/bin/env python3

import importlib.util
import math
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "export_mnist_cnn_lite_holdout.py"
)
SPEC = importlib.util.spec_from_file_location(
    "export_mnist_cnn_lite_holdout",
    SCRIPT,
)
EXPORTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(EXPORTER)


class ExportMNISTCNNLiteHoldoutTest(unittest.TestCase):
    def test_pooling_constant_image(self):
        raw = [128] * (28 * 28)
        pooled = EXPORTER.pooled_pixels(raw)
        self.assertEqual(len(pooled), 16)
        for value in pooled:
            self.assertAlmostEqual(value, 128 / 255)

    def test_split_is_label_balanced_and_disjoint(self):
        rows = []
        for label in (0, 1):
            for source_index in range(400):
                rows.append(
                    (
                        source_index + label * 1000,
                        tuple([label / 2] * 16),
                        label,
                    )
                )
            for offset in range(200):
                rows.append(
                    (
                        EXPORTER.OFFICIAL_TRAIN_ROWS
                        + offset
                        + label * 1000,
                        tuple([label / 2] * 16),
                        label,
                    )
                )
        split = EXPORTER.split_rows(rows)
        self.assertEqual(
            len(split["model_development"]),
            2 * EXPORTER.MODEL_DEVELOPMENT_PER_CLASS,
        )
        self.assertEqual(
            len(split["configuration_validation"]),
            2 * EXPORTER.CONFIGURATION_VALIDATION_PER_CLASS,
        )
        self.assertEqual(
            len(split["locked_audit"]),
            2 * EXPORTER.LOCKED_AUDIT_PER_CLASS,
        )
        identities = []
        for role in split:
            role_ids = {row[0] for row in split[role]}
            self.assertEqual(len(role_ids), len(split[role]))
            identities.append(role_ids)
        for left in range(len(identities)):
            for right in range(left + 1, len(identities)):
                self.assertFalse(
                    identities[left] & identities[right]
                )

    def test_training_is_deterministic_and_finite(self):
        rows = []
        for index in range(64):
            label = index % 2
            base = 0.15 if label == 0 else 0.85
            features = tuple(
                max(
                    0.0,
                    min(
                        1.0,
                        base + ((column + index) % 5 - 2) * 0.01,
                    ),
                )
                for column in range(16)
            )
            rows.append((index, features, label))
        first, first_summary = EXPORTER.train_model(rows)
        second, second_summary = EXPORTER.train_model(rows)
        self.assertEqual(first, second)
        self.assertEqual(first_summary, second_summary)
        self.assertEqual(len(first), EXPORTER.parameter_count())
        self.assertTrue(all(math.isfinite(value) for value in first))
        self.assertAlmostEqual(
            first_summary["scaled_training_max_abs_score"],
            EXPORTER.MAX_ABS_TRAIN_SCORE,
            places=12,
        )

    def test_serialized_parameters_round_trip(self):
        parameters = EXPORTER.initial_parameters()
        model = {
            "learned_parameters": EXPORTER.structured_parameters(
                parameters
            )
        }
        self.assertEqual(
            EXPORTER.flatten_parameters(model),
            parameters,
        )

    def test_policy_declares_audit_noninterference(self):
        policy = EXPORTER.policy_spec()
        self.assertEqual(
            policy["roles"]["locked_audit"],
            "test_partition_no_retuning",
        )
        self.assertEqual(
            policy["training"]["score_scaling"]["source"],
            "training_rows_only",
        )
        self.assertEqual(
            policy["model"]["packing_scope"],
            "scalar_replicated_per_ciphertext_v1",
        )


if __name__ == "__main__":
    unittest.main()
