#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_external_autotuner_comparison_v2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("external_baseline_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ExternalBaselineBuilderTest(unittest.TestCase):
    def test_registry_has_exactly_twenty_unique_systems(self):
        registry = json.loads(
            (ROOT / "docs/evidence/external_autotuner_comparison_v2/protocol/source_registry.json").read_text(encoding="utf-8")
        )
        names = [row["system"] for row in registry["systems"]]
        self.assertEqual(len(names), 20)
        self.assertEqual(len(set(names)), 20)
        self.assertGreaterEqual(len(registry["downloaded_primary_source_sha256"]), 8)
        for source_digest in registry["downloaded_primary_source_sha256"].values():
            self.assertRegex(source_digest, r"^[0-9a-f]{64}$")
        for row in registry["systems"]:
            if row["official_repository"] != "NR":
                self.assertRegex(row["artifact_revision"], r"^.+@[0-9a-f]{40}$")

    def test_csv_writer_keeps_declared_schema(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.csv"
            module.write_csv(path, [{"system": "EVA", "extra": "ignored"}], ["system"])
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"system": "EVA"}])

    def test_csv_reader_returns_declared_rows(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text("system,status\nEVA,PASS\n", encoding="utf-8")
            self.assertEqual(module.read_csv(path), [{"system": "EVA", "status": "PASS"}])

    def test_portability_policy_is_fail_closed(self):
        policy = json.loads(
            (ROOT / "docs/evidence/external_autotuner_comparison_v2/protocol/reproduction_policy.json").read_text(encoding="utf-8")
        )
        exact = set(policy["portable_exact_requires"])
        self.assertIn("packing", exact)
        self.assertIn("output_semantics", exact)
        self.assertFalse(policy["native_track"]["raw_cross_runtime_speed_ranking_allowed"])

    def test_applicability_schema_has_frozen_workload_columns(self):
        path = ROOT / "docs/evidence/external_autotuner_comparison_v2/protocol/tool_workload_applicability.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        self.assertTrue(
            {"Sobel", "Harris", "MLP-100", "LeNet-5-small", "deeper_bootstrapping_workload"} <= set(header)
        )

    def test_comparison_input_commit_can_be_frozen(self):
        module = load_module()
        expected = "1" * 40
        previous = os.environ.get("FLIPGUARD_COMPARISON_INPUT_COMMIT")
        os.environ["FLIPGUARD_COMPARISON_INPUT_COMMIT"] = expected
        try:
            self.assertEqual(module.comparison_input_commit(), expected)
        finally:
            if previous is None:
                os.environ.pop("FLIPGUARD_COMPARISON_INPUT_COMMIT", None)
            else:
                os.environ["FLIPGUARD_COMPARISON_INPUT_COMMIT"] = previous

    def test_builder_keeps_build_and_exact_reproduction_concepts_separate(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"native_end_to_end_systems"', source)
        self.assertIn('"external_exact_workload_mappings"', source)
        self.assertIn('"provider_gate_systems"', source)

    def test_build_attempt_ledger_is_complete_and_bounded(self):
        ledger = json.loads(
            (ROOT / "docs/evidence/external_autotuner_comparison_v2/protocol/build_attempts.json").read_text(encoding="utf-8")
        )
        systems = ledger["systems"]
        self.assertEqual(len(systems), 20)
        self.assertEqual(sum(row["status"] == "PASS" for row in systems), 8)
        self.assertEqual(sum(row["reproduced"] for row in systems), 8)
        for row in systems:
            self.assertLessEqual(row["attempts"], 3)
            self.assertFalse(row["algorithm_semantics_changed"])
            if row["attempts"]:
                for value in row["log_sha256"].split(";"):
                    self.assertRegex(value, r"^sha256:[0-9a-f]{64}$")

    def test_eva_native_metrics_are_derived_from_frozen_ledger(self):
        module = load_module()
        metrics = module.eva_native_metrics()
        self.assertGreater(metrics["rms_error"], 0)
        self.assertGreater(metrics["max_error"], metrics["rms_error"])
        self.assertGreater(metrics["keygen_mean_ms"], 0)
        self.assertGreater(metrics["evaluation_mean_ms"], 0)


if __name__ == "__main__":
    unittest.main()
