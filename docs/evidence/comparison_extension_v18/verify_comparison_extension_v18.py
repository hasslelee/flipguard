#!/usr/bin/env python3
"""Verify V18 outputs and prove immutable V17 inputs remain unchanged."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/evidence/comparison_extension_v18"
RESULTS = ROOT / "results/comparison_extension_v18"
CHECKPOINT = ROOT / "docs/checkpoints/comparison_extension_v18"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def close(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    assert math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), (actual, expected)


def verify_input_inventory() -> int:
    inventory = rows(CHECKPOINT / "v17_input_inventory.csv")
    assert len(inventory) == 4201
    for item in inventory:
        path = ROOT / item["relative_path"]
        assert path.is_file(), f"missing immutable input: {item['relative_path']}"
        assert path.stat().st_size == int(item["size_bytes"]), f"size changed: {item['relative_path']}"
        assert sha256(path) == item["sha256"], f"digest changed: {item['relative_path']}"
    return len(inventory)


def verify_manifest() -> tuple[int, str]:
    manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "V18 COMPARISON EXTENSION COMPLETE — OFFLINE REPLAY SUFFICIENT"
    canonical = ""
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        assert path.stat().st_size == item["size_bytes"]
        assert sha256(path) == item["sha256"]
        canonical += f"{item['sha256']}  {item['path']}\n"
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    assert digest == manifest["package_payload_sha256"]
    sums = {}
    for line in (EVIDENCE / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest_value, path = line.split("  ", 1)
        sums[path] = digest_value
    for path, digest_value in sums.items():
        assert sha256(ROOT / path) == digest_value, path
    return len(manifest["files"]), digest


def main() -> None:
    subprocess.run([sys.executable, str(EVIDENCE / "verify_protocol_v18.py")], check=True, cwd=ROOT)
    input_count = verify_input_inventory()

    case_rows = rows(RESULTS / "case_level_ledger.csv")
    candidate_rows = rows(RESULTS / "candidate_level_ledger.csv")
    sequence = rows(RESULTS / "selection_sequence.csv")
    literals = rows(RESULTS / "literal_inventory.csv")
    formal = rows(RESULTS / "table_finite_reference_quality.csv")
    assert len(case_rows) == 131 and len({row["case_id"] for row in case_rows}) == 131
    assert sum(row["scope"] == "primary" for row in case_rows) == 68
    assert len(sequence) == 89
    assert sum(row["candidate_source"] == "direct" for row in candidate_rows) == 89
    assert sum(row["candidate_source"] == "finite_reference" for row in candidate_rows) == 537
    assert len(formal) == 68
    assert len(literals) == 16
    assert len({(row["case_id"], row["candidate_source"], row["candidate_order"], row["candidate_id"]) for row in candidate_rows}) == len(candidate_rows)

    metrics = json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["direct_candidate_evaluations"] == 89
    assert metrics["finite_reference_candidate_evaluations"] == 537
    close(metrics["candidate_evaluation_reduction"], 1 - 89 / 537)
    assert metrics["formal_latency_rows"] == 68
    assert metrics["decision_gate"]["selection_flip_cases"] == 20
    assert metrics["decision_gate"]["reserve_violation_cases"] == 21
    assert metrics["decision_gate"]["proposed_literal_changed"] == 21
    assert metrics["decision_gate"]["separate_input_evaluated"] == 47
    assert metrics["repair_ablation"]["repair_success"] == 21
    assert metrics["finite_reference"]["false_no_safe"] == 0
    close(metrics["finite_reference"]["formal_latency_regret"]["median"], -0.00015323624671320646)
    bootstrap = metrics["finite_reference"]["formal_finite_over_direct_total_ratio_cluster_bootstrap"]
    assert bootstrap["bootstrap_replicates"] == 10000
    assert bootstrap["bootstrap_seed"] == 20260824
    assert bootstrap["cluster_count"] == 16
    assert bootstrap["ci_low"] < 1 < bootstrap["ci_high"]
    assert metrics["new_encrypted_candidate_evaluations"] == 0
    assert metrics["external_comparator_counts"] == {
        "EXACT_COMPARABLE": 1,
        "NUMERICAL_ONLY": 2,
        "OUTPUT_COMPARABLE": 1,
        "RELATED_WORK_ONLY": 7,
    }
    assert Counter(row["c4_latency_only_status"] for row in case_rows if row["scope"] == "primary") == Counter(
        {"SAFE": 51, "REJECTED": 15, "NOT_EVALUATED_PACKING": 1, "NOT_EVALUATED_PLAN_UNSUPPORTED": 1}
    )

    plan = json.loads((EVIDENCE / "targeted_run_plan.json").read_text(encoding="utf-8"))
    assert plan["planned_atomic_workload_cases"] == 0
    assert plan["planned_encrypted_candidate_evaluations"] == 0
    assert plan["counterfactual_separate_input_gap"]["case_count"] == 21
    plan_sum, plan_name = (EVIDENCE / "targeted_run_plan.sha256").read_text(encoding="ascii").strip().split("  ")
    assert plan_name == "targeted_run_plan.json" and plan_sum == sha256(EVIDENCE / plan_name)

    package_files, package_digest = verify_manifest()
    print(
        "V18_COMPARISON_VERIFY_PASS "
        f"immutable_inputs={input_count} cases=131 primary=68 direct=89 finite=537 formal=68 "
        f"package_files={package_files} payload_sha256={package_digest}"
    )


if __name__ == "__main__":
    main()
