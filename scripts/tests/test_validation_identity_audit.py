from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "build_validation_identity_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "build_validation_identity_audit",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ValidationIdentityClassificationTests(unittest.TestCase):
    def classify(self, **overrides: bool) -> tuple[str, bool, str]:
        values = {
            "source_raw_match": True,
            "prepared_raw_match": False,
            "ordered_row_ids_match": True,
            "feature_semantics_match": True,
            "decision_semantics_match": True,
            "policy_match": True,
            "split_match": True,
        }
        values.update(overrides)
        return AUDIT.classify(**values)

    def test_class_a_representation_layer_mismatch(self) -> None:
        identity_class, rerun, _ = self.classify()
        self.assertEqual(
            identity_class,
            "SOURCE_AND_SEMANTICS_MATCH_PREPARED_BYTES_DIFFER",
        )
        self.assertFalse(rerun)

    def test_class_b_source_bytes_differ(self) -> None:
        identity_class, rerun, _ = self.classify(
            source_raw_match=False
        )
        self.assertEqual(
            identity_class,
            "SOURCE_DIFFERS_SEMANTICS_MATCH",
        )
        self.assertFalse(rerun)

    def test_row_order_rejects(self) -> None:
        identity_class, rerun, _ = self.classify(
            ordered_row_ids_match=False
        )
        self.assertEqual(identity_class, "ROW_ORDER_ONLY_MISMATCH")
        self.assertTrue(rerun)

    def test_feature_and_decision_mutations_reject(self) -> None:
        for field in (
            "feature_semantics_match",
            "decision_semantics_match",
            "policy_match",
        ):
            with self.subTest(field=field):
                identity_class, rerun, _ = self.classify(
                    **{field: False}
                )
                self.assertEqual(identity_class, "SEMANTIC_MISMATCH")
                self.assertTrue(rerun)

    def test_wrong_split_rejects(self) -> None:
        identity_class, rerun, _ = self.classify(split_match=False)
        self.assertEqual(identity_class, "WRONG_SPLIT_OR_MANIFEST")
        self.assertTrue(rerun)


if __name__ == "__main__":
    unittest.main()
