import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/audit_research_core_readiness_v3.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_research_core_readiness_v3", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ResearchCoreReadinessV3Test(unittest.TestCase):
    def test_claim_partition_is_disjoint(self) -> None:
        groups = [
            set(MODULE.REQUIRED_CORE_CLAIMS),
            set(MODULE.EXCLUDED_CLAIMS),
            set(MODULE.SUPPORTED_CONTEXT_CLAIMS),
        ]
        self.assertFalse(groups[0] & groups[1])
        self.assertFalse(groups[0] & groups[2])
        self.assertFalse(groups[1] & groups[2])

    def test_safe_native_result_remains_scoped(self) -> None:
        self.assertEqual(
            MODULE.SUPPORTED_CONTEXT_CLAIMS[
                "native_eva_seal_decision_certification"
            ],
            "PARTIALLY_SUPPORTED",
        )
        self.assertEqual(
            MODULE.EXCLUDED_CLAIMS[
                "original_scale20_candidate_decision_certification"
            ],
            "BLOCKED",
        )
        self.assertEqual(
            MODULE.EXCLUDED_CLAIMS[
                "general_external_autotuner_integration"
            ],
            "NOT_EVALUATED",
        )


if __name__ == "__main__":
    unittest.main()
