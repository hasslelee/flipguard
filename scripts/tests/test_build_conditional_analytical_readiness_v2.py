import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/build_conditional_analytical_readiness_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_conditional_analytical_readiness_v2",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConditionalAnalyticalReadinessTest(unittest.TestCase):
    def test_build_and_verify(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-analytical-readiness-test-",
            dir="/tmp",
        ) as temporary:
            output = Path(temporary) / "artifact"
            MODULE.build(output, "test-source-commit")
            MODULE.verify_existing(output)

            summary = json.loads(
                (output / "summary.json").read_text(encoding="ascii")
            )
            self.assertEqual(summary["primary_candidates"], 50)
            self.assertEqual(
                summary["development_seed0_candidates"],
                10,
            )
            self.assertEqual(
                summary["confirmatory_seeds1_4_candidates"],
                40,
            )
            self.assertEqual(summary["linear_poly3_candidates"], 25)
            self.assertEqual(
                summary["mlp_square_linear_score_candidates"],
                25,
            )
            self.assertEqual(
                summary["proof_eligible_candidates"],
                0,
            )
            self.assertEqual(
                summary["conditional_propagation_lemma"],
                "SUPPORTED",
            )
            self.assertEqual(
                summary["instantiated_ckks_analytical_certificate"],
                "BLOCKED",
            )
            self.assertFalse(summary["paper_claim_allowed"])

    def test_security_admission_is_pass_for_all_primary_rows(self) -> None:
        rows = MODULE.selection_rows()
        self.assertEqual(len(rows), 50)
        self.assertEqual(
            {row["security_admission"] for row in rows},
            {"PASS"},
        )
        self.assertEqual(
            sum(row["graph_contract_supported"] for row in rows),
            25,
        )
        self.assertTrue(
            all(not row["proof_eligible"] for row in rows)
        )


if __name__ == "__main__":
    unittest.main()
