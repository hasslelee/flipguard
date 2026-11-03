from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "scripts" / "compare_direct_synthesis_to_catalog_oracle.py"
)
SPEC = importlib.util.spec_from_file_location(
    "compare_direct_synthesis_to_catalog_oracle",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
COMPARATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARATOR)


class DirectCatalogIdentityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        digest = "sha256:" + "a" * 64
        self.identity = {
            "identity_class":
                "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER",
            "source_replay_verified": "true",
            "source_raw_match": "true",
            "ordered_row_ids_match": "true",
            "feature_semantics_match": "true",
            "decision_semantics_match": "true",
            "policy_match": "true",
            "direct_ordered_row_id_digest": digest,
            "catalog_ordered_row_id_digest": digest,
            "direct_feature_semantic_digest": digest,
            "catalog_feature_semantic_digest": digest,
            "direct_decision_semantic_digest": digest,
            "catalog_decision_semantic_digest": digest,
            "direct_V_cert": "10",
            "catalog_V_cert": "10",
            "direct_V_amb": "0",
            "catalog_V_amb": "0",
            "threshold": "0.5",
            "alpha": "0.5",
            "margin_floor": "0.001",
        }
        self.materialization = {"source_replay_verified": True}
        self.decision = {
            "threshold": 0.5,
            "safety_factor": 0.5,
            "margin_floor": 0.001,
            "certifiable_samples": 10,
            "ambiguous_samples": 0,
        }
        self.coverage = {
            "threshold": "0.5",
            "margin_floor": "0.001",
            "v_cert": "10",
            "v_amb": "0",
        }

    def validate(
        self,
        identity: dict[str, str] | None = None,
        materialization: dict[str, object] | None = None,
        decision: dict[str, object] | None = None,
        coverage: dict[str, str] | None = None,
    ) -> None:
        COMPARATOR.validate_identity_gate(
            (0, "toy", "linear_poly3"),
            identity or self.identity,
            materialization or self.materialization,
            decision or self.decision,
            coverage or self.coverage,
        )

    def test_accepts_class_a_strict_bridge(self) -> None:
        self.validate()

    def test_rejects_materialization_replay_false(self) -> None:
        materialization = {"source_replay_verified": False}
        with self.assertRaisesRegex(ValueError, "source replay"):
            self.validate(materialization=materialization)

    def test_rejects_row_feature_and_decision_mismatch(self) -> None:
        for field in (
            "ordered_row_ids_match",
            "feature_semantics_match",
            "decision_semantics_match",
        ):
            with self.subTest(field=field):
                identity = copy.deepcopy(self.identity)
                identity[field] = "false"
                with self.assertRaisesRegex(
                    ValueError,
                    "failed predicate",
                ):
                    self.validate(identity=identity)

    def test_rejects_coverage_mismatch(self) -> None:
        coverage = dict(self.coverage)
        coverage["v_cert"] = "9"
        with self.assertRaisesRegex(ValueError, "coverage partition"):
            self.validate(coverage=coverage)

    def test_rejects_threshold_alpha_and_margin_mismatch(self) -> None:
        for field, value in (
            ("threshold", "0.4"),
            ("alpha", "0.25"),
            ("margin_floor", "0.0005"),
        ):
            with self.subTest(field=field):
                identity = copy.deepcopy(self.identity)
                identity[field] = value
                with self.assertRaisesRegex(
                    ValueError,
                    "threshold, alpha, or margin",
                ):
                    self.validate(identity=identity)


if __name__ == "__main__":
    unittest.main()
