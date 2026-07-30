import copy
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/run_hit_external_adapter_replay.py"
SPEC = importlib.util.spec_from_file_location(
    "run_hit_external_adapter_replay",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RunHITExternalAdapterReplayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = MODULE.load_json(
            MODULE.REPO_ROOT / MODULE.DEFAULT_CONTRACT
        )
        self.materialization = {
            "input": self.contract["candidate_input"],
            "derived": {
                "log_n": 14,
                "log_q": [60, 20, 20, 20, 20, 20, 20],
                "log_p": [61],
            },
            "lattigo_v2_2_0": {
                "module": "github.com/ldsec/lattigo/v2",
                "version": "v2.2.0",
                "q": [
                    1152921504606748673,
                    1146881,
                    1179649,
                    786433,
                    1376257,
                    557057,
                    1769473,
                ],
                "p": [2305843009211662337],
            },
            "lattigo_v6_2_0_concrete_import": {
                "module": "github.com/tuneinsight/lattigo/v6",
                "version": "v6.2.0",
                "log_n": 14,
                "q": [
                    1152921504606748673,
                    1146881,
                    1179649,
                    786433,
                    1376257,
                    557057,
                    1769473,
                ],
                "p": [2305843009211662337],
                "log_default_scale": 20,
                "ring_type": "standard",
                "xs": "uniform_ternary_[1/3,1/3,1/3]",
                "xe": "discrete_gaussian_sigma_3.2_bound_19.2",
            },
            "lattigo_v6_2_0_native_log_literal_error": "diagnostic",
            "concrete_import_q_identical": True,
            "concrete_import_p_identical": True,
            "scale_identical": True,
            "ring_identical": True,
            "xs_identical": True,
            "xe_identical": True,
            "exact_concrete_translation": True,
        }

    def test_pinned_source_urls(self) -> None:
        sources = {
            source["source_id"]: source
            for source in self.contract["sources"]
        }
        hit = MODULE.source_url(
            self.contract,
            sources["hit_parameter_formula"],
        )
        self.assertIn(self.contract["upstream"]["hit_commit"], hit)
        self.assertTrue(hit.endswith("/src/hit/api/params.cpp"))
        v2 = MODULE.source_url(
            self.contract,
            sources["lattigo_v2_keygen"],
        )
        self.assertIn(self.contract["upstream"]["lattigo_v2_commit"], v2)

    def test_materialization_and_candidate_are_exact(self) -> None:
        MODULE.validate_materialization(
            self.contract,
            self.materialization,
        )
        request = MODULE.candidate_request(self.materialization)
        self.assertEqual(request["schema_version"], 2)
        self.assertEqual(
            request["parameters"]["q"],
            self.materialization[
                "lattigo_v6_2_0_concrete_import"
            ]["q"],
        )

    def test_translation_mismatch_fails_closed(self) -> None:
        mutated = copy.deepcopy(self.materialization)
        mutated["lattigo_v6_2_0_concrete_import"]["q"][1] += 1
        with self.assertRaisesRegex(
            ValueError,
            "concrete runtime semantics changed",
        ):
            MODULE.validate_materialization(self.contract, mutated)

    def test_summary_preserves_scientific_negative(self) -> None:
        selection = {
            "outcome": "NO_SAFE",
            "trials_used": 1,
            "encrypted_key_runs": 3,
            "trial": {
                "status": "REJECTED",
                "decision_flips": 0,
                "error_violations": 1,
            },
            "bound_candidate": {
                "candidate": {
                    "id": "provider_external_autotuner_fixture",
                    "security": {"final_admission": "PASS"},
                }
            },
        }
        summary = MODULE.build_summary(
            Path("/tmp/unused"),
            selection,
            None,
        )
        self.assertEqual(summary["selection"]["outcome"], "NO_SAFE")
        self.assertEqual(
            summary["claim_states"][
                "encrypted_external_candidate_certification"
            ],
            "BLOCKED",
        )
        self.assertFalse(summary["paper_claim_allowed"])


if __name__ == "__main__":
    unittest.main()
