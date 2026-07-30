#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "freeze_direct_synthesis_ablation_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "freeze_direct_synthesis_ablation_evidence",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FreezeDirectSynthesisAblationEvidenceTest(unittest.TestCase):
    def raw_run_root(self) -> Path:
        run_root = (
            Path(__file__).resolve().parents[2]
            / MODULE.DEFAULT_RUN_ROOT
        )
        if not (run_root / "run_manifest.json").is_file():
            self.skipTest("requires ignored ablation raw results")
        return run_root

    def test_completed_run_passes_deep_validation(self) -> None:
        run_root = self.raw_run_root()
        manifest, summary, derived = MODULE.validate_run(run_root)
        self.assertEqual(
            MODULE.EXECUTION_COMMIT,
            manifest["source_commit"],
        )
        self.assertEqual("PASS", summary["status"])
        self.assertEqual(10, len(derived["workloads"]))
        self.assertEqual(
            30,
            derived["recovery"]["pre_ckks_failed_attempts"],
        )

    def test_latency_only_unevaluated_audit_is_null(self) -> None:
        run_root = self.raw_run_root()
        summary = MODULE.json.loads(
            (run_root / "summary.json").read_text(encoding="ascii")
        )
        latency = summary["arms"]["latency_only_no_certification"]
        self.assertIsNone(latency["audit_flips"])
        self.assertEqual(10, latency["audit_not_evaluated"])


if __name__ == "__main__":
    unittest.main()
