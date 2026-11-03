#!/usr/bin/env python3
"""Reconstruct and replay V18 comparators from immutable V17/V8 artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z"
FINAL = ROOT / "results/model_family_expansion_v17/final_vm1x6"
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
RESULTS = ROOT / "results/comparison_extension_v18"
REPORTS = ROOT / "docs/reports/comparison_extension_v18"

P4 = "mnist_mlp_square_784_100_10_v1"
P5 = "mnist_lenet5_small_square_v1"
P6 = "packed_cnn_lite_binary01_v17"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def yes(value: Any) -> bool:
    return str(value).lower() in {"true", "1", "yes", "pass", "safe", "selected"}


def quantile(values: Iterable[float], q: float) -> float | None:
    data = sorted(values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return data[lo]
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def summary(values: Iterable[float]) -> dict[str, float | int | None]:
    data = sorted(values)
    return {
        "n": len(data),
        "median": statistics.median(data) if data else None,
        "q1": quantile(data, 0.25),
        "q3": quantile(data, 0.75),
        "iqr": (quantile(data, 0.75) - quantile(data, 0.25)) if data else None,
        "p90": quantile(data, 0.90),
        "maximum": max(data) if data else None,
    }


def geometric_mean(values: Iterable[float]) -> float:
    data = list(values)
    if not data or any(value <= 0 for value in data):
        raise ValueError("geometric mean requires positive values")
    return math.exp(sum(math.log(value) for value in data) / len(data))


def cluster_bootstrap_geomean(
    rows: list[dict[str, str]],
    value_key: str,
    replicates: int = 10000,
    seed: int = 20260824,
) -> dict[str, Any]:
    clusters: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        clusters[(row["dataset"], row["model_id"])].append(float(row[value_key]))
    cluster_values = [geometric_mean(values) for _, values in sorted(clusters.items())]
    rng = random.Random(seed)
    bootstrap = []
    for _ in range(replicates):
        sample = [cluster_values[rng.randrange(len(cluster_values))] for _ in cluster_values]
        bootstrap.append(geometric_mean(sample))
    return {
        "cluster_count": len(cluster_values),
        "case_count": len(rows),
        "estimate": geometric_mean(cluster_values),
        "ci_low": quantile(bootstrap, 0.025),
        "ci_high": quantile(bootstrap, 0.975),
        "bootstrap_replicates": replicates,
        "bootstrap_seed": seed,
        "cluster_definition": "dataset_model",
    }


def bit_sum(value: str) -> int:
    return sum(int(part) for part in value.split(";") if part)


def case_id(row: dict[str, str]) -> str:
    return f"{row['phase']}|{row['dataset']}|{row['model_id']}|{row['split_id']}"


def training_seed(split_id: str) -> str:
    match = re.search(r"training_seed[_/](\d+)", split_id)
    if not match:
        match = re.search(r"training_seed_(\d+)", split_id)
    return match.group(1) if match else "0"


def primary_sources(row: dict[str, str]) -> tuple[Path, Path, Path | None]:
    model = row["model_id"]
    if model in {P4, P5}:
        direct = ROOT / "results/journal_multiclass_extension_v1/encrypted" / model / "selection_result.json"
        finite = RUN / "exhaustive" / model / "exhaustive.json"
        return direct, finite, None
    if model == P6:
        base = RUN / "primary" / P6
    else:
        base = (ROOT / row["case_path"]).parent
    return base / "selection.json", base / "exhaustive.json", (base / "legacy_finite.json")


def direct_result(path: Path) -> dict[str, Any]:
    data = read_json(path)
    return data.get("result", data)


def trial_observation_errors(trial: dict[str, Any]) -> list[float]:
    if isinstance(trial.get("sample_ledger"), list):
        return [float(row["absolute_error"]) for row in trial["sample_ledger"] if row.get("absolute_error") is not None]
    agg = trial.get("aggregation") or {}
    errors: list[float] = []
    for row in agg.get("observations", []):
        if isinstance(row.get("per_logit_absolute_error"), list):
            errors.extend(float(value) for value in row["per_logit_absolute_error"])
        elif row.get("absolute_error") is not None:
            errors.append(float(row["absolute_error"]))
    return errors


def trial_metrics(trial: dict[str, Any]) -> dict[str, Any]:
    agg = trial.get("aggregation") or {}
    errors = trial_observation_errors(trial)
    flips = trial.get("decision_flips")
    if flips is None:
        flips = agg.get("argmax_flips", agg.get("decision_flips", 0))
    violations = trial.get("error_violations")
    if violations is None:
        violations = agg.get("reserve_policy_violations", 0)
    max_error = trial.get("max_observed_error")
    if max_error is None:
        max_error = agg.get("max_logit_absolute_error")
    if max_error is None and errors:
        max_error = max(errors)
    rms = math.sqrt(sum(value * value for value in errors) / len(errors)) if errors else None
    success_runs = trial.get("success_runs", agg.get("success_runs", trial.get("key_repeats_completed", 0)))
    return {
        "status": trial.get("status", agg.get("status", "NOT_REPORTED")),
        "execution_status": "PASS" if as_int(success_runs, 0) and as_int(success_runs, 0) > 0 else "FAILED",
        "flips": as_int(flips, 0) or 0,
        "violations": as_int(violations, 0) or 0,
        "max_absolute_error": as_float(max_error),
        "rms_error": rms,
        "mean_total_ms": as_float(trial.get("mean_total_ms", agg.get("mean_total_ms"))),
        "median_total_ms": as_float(trial.get("median_total_ms", agg.get("median_total_ms"))),
        "key_repeats": as_int(trial.get("key_repeats_completed", agg.get("success_runs")), 0) or 0,
    }


def candidate_values(candidate: dict[str, Any]) -> dict[str, Any]:
    params = candidate.get("parameters") or {}
    security = candidate.get("security") or {}
    return {
        "candidate_id": candidate.get("id", "NOT_REPORTED"),
        "log_n": params.get("log_n", "NOT_REPORTED"),
        "ordered_q": ";".join(str(value) for value in params.get("log_q", [])),
        "ordered_p": ";".join(str(value) for value in params.get("log_p", [])),
        "initial_scale": params.get("log_default_scale", "NOT_REPORTED"),
        "path": candidate.get("path", "NOT_REPORTED"),
        "security_status": security.get("final_admission", security.get("admission_status", "NOT_REPORTED")),
        "literal_key": json.dumps(
            [
                params.get("log_n"),
                params.get("log_q", []),
                params.get("log_p", []),
                params.get("log_default_scale"),
                candidate.get("path"),
            ],
            separators=(",", ":"),
        ),
    }


def finite_fastest(entries: list[dict[str, Any]], acceptable_only: bool) -> dict[str, Any] | None:
    candidates = []
    for entry in entries:
        metrics = trial_metrics(entry)
        valid = metrics["execution_status"] == "PASS" and candidate_values(entry.get("candidate") or {})["security_status"] == "PASS"
        if not valid:
            continue
        if acceptable_only and not (metrics["status"] == "SAFE" and metrics["flips"] == 0 and metrics["violations"] == 0):
            continue
        if metrics["mean_total_ms"] is not None:
            candidates.append((metrics["mean_total_ms"], as_int(entry.get("trial_index"), 0), entry))
    return min(candidates, default=(None, None, None), key=lambda item: (item[0], item[1]))[2]


def minimum_error(entries: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = []
    for entry in entries:
        metrics = trial_metrics(entry)
        value = metrics[key]
        if metrics["execution_status"] != "PASS" or candidate_values(entry.get("candidate") or {})["security_status"] != "PASS" or value is None:
            continue
        candidates.append((value, as_int(entry.get("trial_index"), 0), entry))
    return min(candidates, default=(None, None, None), key=lambda item: (item[0], item[1]))[2]


def pareto(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = []
    for entry in entries:
        metrics = trial_metrics(entry)
        if (
            metrics["execution_status"] == "PASS"
            and candidate_values(entry.get("candidate") or {})["security_status"] == "PASS"
            and metrics["mean_total_ms"] is not None
            and metrics["max_absolute_error"] is not None
        ):
            eligible.append((metrics["mean_total_ms"], metrics["max_absolute_error"], entry))
    frontier = []
    for latency, error, entry in eligible:
        dominated = any(
            other_latency <= latency
            and other_error <= error
            and (other_latency < latency or other_error < error)
            for other_latency, other_error, _ in eligible
        )
        if not dominated:
            frontier.append(entry)
    return sorted(frontier, key=lambda item: (trial_metrics(item)["mean_total_ms"], candidate_values(item["candidate"])["candidate_id"]))


def collect_formal_latency(rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str], dict[str, float]], dict[str, dict[str, str]]]:
    values: dict[tuple[str, str], dict[str, float]] = {}
    row_by_case: dict[str, dict[str, str]] = {}
    direct_rows = read_csv(FINAL / "table_04_direct_vs_exhaustive.csv")
    primary = [row for row in direct_rows if row["phase"] == "primary"]
    for formal in rows:
        path = ROOT / formal["path"]
        data = read_json(path)
        grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"total": [], "eval": []})
        records = list(data.get("records", []))
        for keyset in data.get("keysets", []):
            measurement = keyset.get("measurement", keyset)
            records.extend(measurement.get("records", []))
        for record in records:
            arm = record.get("arm_id", record.get("arm"))
            if arm not in {"direct", "finite_fastest_safe"}:
                continue
            if record.get("total_ms") is not None:
                grouped[arm]["total"].append(float(record["total_ms"]))
            eval_value = record.get(
                "eval_only_ms",
                record.get("evaluation_only_ms", record.get("evaluate_ms")),
            )
            if eval_value is not None:
                grouped[arm]["eval"].append(float(eval_value))
        for arm in ("direct", "finite_fastest_safe"):
            if not grouped[arm]["total"] or not grouped[arm]["eval"]:
                raise AssertionError(f"missing formal latency arm {arm}: {formal['path']}")
        values[(formal["direct_candidate_id"], "direct")] = {
            "median_total_ms": statistics.median(grouped["direct"]["total"]),
            "median_eval_ms": statistics.median(grouped["direct"]["eval"]),
        }
        values[(formal["finite_candidate_id"], "finite_reference")] = {
            "median_total_ms": statistics.median(grouped["finite_fastest_safe"]["total"]),
            "median_eval_ms": statistics.median(grouped["finite_fastest_safe"]["eval"]),
        }
        match = next(
            row
            for row in primary
            if row["model_id"] == formal["model_id"]
            and row["candidate_id"] == formal["direct_candidate_id"]
        )
        row_by_case[case_id(match)] = formal
    return values, row_by_case


def make_candidate_row(
    case: dict[str, str],
    source: str,
    order: int,
    trial: dict[str, Any],
    source_path: Path,
    formal: dict[tuple[str, str], dict[str, float]],
    direct_selected: str,
    finite_selected: str,
    previous_failure: str = "NONE",
) -> dict[str, Any]:
    candidate = trial.get("candidate") or {}
    cv = candidate_values(candidate)
    metrics = trial_metrics(trial)
    formal_role = "direct" if source == "direct" else "finite_reference"
    formal_values = formal.get((cv["candidate_id"], formal_role), {})
    separate_status = "NOT_EVALUATED"
    separate_flips: Any = "NOT_EVALUATED"
    separate_violations: Any = "NOT_EVALUATED"
    if source == "direct" and cv["candidate_id"] == direct_selected:
        separate_status = case["direct_independent_status"]
        separate_flips = case["direct_independent_flips"]
        separate_violations = case["direct_independent_violations"]
    if source == "finite_reference" and cv["candidate_id"] == finite_selected:
        separate_status = case["fastest_independent_status"]
        separate_flips = case["fastest_independent_flips"]
        separate_violations = case["fastest_independent_violations"]
    return {
        "phase": case["phase"],
        "dataset": case["dataset"],
        "model_id": case["model_id"],
        "split_id": case["split_id"],
        "training_seed": training_seed(case["split_id"]),
        "case_id": case_id(case),
        "candidate_id": cv["candidate_id"],
        "candidate_order": order,
        "candidate_source": source,
        "repair_step": max(0, order - 1) if source == "direct" else 0,
        "repair_reason": previous_failure,
        "log_n": cv["log_n"],
        "ordered_q": cv["ordered_q"],
        "ordered_p": cv["ordered_p"],
        "initial_scale": cv["initial_scale"],
        "path": cv["path"],
        "packing": case["packing_strategy"],
        "rotations": case["rotations"],
        "materialization_status": "PASS",
        "security_status": cv["security_status"],
        "execution_status": metrics["execution_status"],
        "selection_status": metrics["status"],
        "selection_input_flips": metrics["flips"],
        "selection_input_reserve_violations": metrics["violations"],
        "boundary_input_flips": "NOT_AVAILABLE",
        "separate_input_status": separate_status,
        "separate_input_flips": separate_flips,
        "separate_input_reserve_violations": separate_violations,
        "maximum_absolute_error": metrics["max_absolute_error"],
        "rms_error": metrics["rms_error"],
        "selection_stage_mean_total_ms": metrics["mean_total_ms"],
        "formal_paired_median_total_ms": formal_values.get("median_total_ms", "NOT_MEASURED"),
        "formal_paired_median_eval_ms": formal_values.get("median_eval_ms", "NOT_MEASURED"),
        "total_selection_wall_clock_ms": case["selection_wall_clock_ms"] if source == "direct" else case["exhaustive_wall_clock_ms"],
        "key_repeat_count": metrics["key_repeats"],
        "literal_key": cv["literal_key"],
        "source_path": source_path.relative_to(ROOT).as_posix(),
        "source_hash": sha256(source_path),
        "result_hash": object_hash(trial),
    }


def external_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = V8 / "audit_records.csv"
    for index, item in enumerate(read_csv(source), start=1):
        rows.append(
            {
                "phase": "external_v8",
                "dataset": "shared_polynomial_threshold_v8",
                "model_id": "shared_polynomial_linear_poly3_v8",
                "split_id": "locked_audit",
                "training_seed": "NOT_APPLICABLE",
                "case_id": f"external_v8|{item['provider']}|{item['candidate_id']}",
                "candidate_id": item["candidate_id"],
                "candidate_order": index,
                "candidate_source": "external_locked_audit",
                "repair_step": 0,
                "repair_reason": "NONE",
                "log_n": "SEE_V8_PROVIDER_MANIFEST",
                "ordered_q": "SEE_V8_PROVIDER_MANIFEST",
                "ordered_p": "SEE_V8_PROVIDER_MANIFEST",
                "initial_scale": "SEE_V8_PROVIDER_MANIFEST",
                "path": item["arm"],
                "packing": "SEE_V8_WORKLOAD_CONTRACT",
                "rotations": "SEE_V8_WORKLOAD_CONTRACT",
                "materialization_status": "PASS",
                "security_status": "SEE_V8_SECURITY_SUMMARY",
                "execution_status": "PASS",
                "selection_status": item["status"],
                "selection_input_flips": "NOT_REPORTED_IN_AUDIT_ROW",
                "selection_input_reserve_violations": "NOT_REPORTED_IN_AUDIT_ROW",
                "boundary_input_flips": "NOT_AVAILABLE",
                "separate_input_status": item["status"],
                "separate_input_flips": item["decision_flips"],
                "separate_input_reserve_violations": item["reserve_policy_violations"],
                "maximum_absolute_error": "SEE_V8_NUMERICAL_SUMMARY",
                "rms_error": "SEE_V8_NUMERICAL_SUMMARY",
                "selection_stage_mean_total_ms": "NATIVE_OR_DIAGNOSTIC_ONLY",
                "formal_paired_median_total_ms": "NOT_ADMITTED",
                "formal_paired_median_eval_ms": "NOT_ADMITTED",
                "total_selection_wall_clock_ms": "NOT_APPLICABLE",
                "key_repeat_count": item["fresh_key_runs"],
                "literal_key": item["candidate_id"],
                "source_path": source.relative_to(ROOT).as_posix(),
                "source_hash": sha256(source),
                "result_hash": object_hash(item),
            }
        )
    return rows


def aggregate_gate(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    c2 = [row for row in rows if row["scope"] == "primary" and (label == "ALL_PRIMARY" or row["model_id"] == label)]
    latency_gaps = [float(row["candidate_stage_latency_gap_ms"]) for row in c2 if row["candidate_stage_latency_gap_ms"] != "NOT_AVAILABLE"]
    changed = [row for row in c2 if row["c1_candidate_id"] != row["c2_candidate_id"]]
    changed_latency_gaps = [float(row["candidate_stage_latency_gap_ms"]) for row in changed if row["candidate_stage_latency_gap_ms"] != "NOT_AVAILABLE"]

    def changed_median(field: str) -> float | str:
        values = [float(row[field]) for row in changed if row[field] != "NOT_AVAILABLE"]
        return statistics.median(values) if values else "NOT_APPLICABLE"

    return {
        "group": label,
        "cases": len(c2),
        "gate_off_selected": sum(row["c2_state"] == "SELECTED" for row in c2),
        "selection_flip_cases": sum(int(row["c2_selection_flips"]) > 0 for row in c2),
        "selection_flip_events": sum(int(row["c2_selection_flips"]) for row in c2),
        "reserve_violation_cases": sum(int(row["c2_selection_violations"]) > 0 for row in c2),
        "reserve_violation_events": sum(int(row["c2_selection_violations"]) for row in c2),
        "separate_input_evaluated": sum(row["c2_separate_status"] != "NOT_EVALUATED" for row in c2),
        "separate_input_failures": sum(row["c2_separate_status"] in {"REJECTED", "FAILED"} for row in c2),
        "proposed_literal_changed": sum(row["c1_candidate_id"] != row["c2_candidate_id"] for row in c2),
        "additional_candidate_evaluations": sum(int(row["c1_candidate_evaluations"]) - int(row["c2_candidate_evaluations"]) for row in c2),
        "median_candidate_stage_latency_gap_ms": statistics.median(latency_gaps) if latency_gaps else "NOT_AVAILABLE",
        "changed_literal_median_candidate_stage_latency_gap_ms": statistics.median(changed_latency_gaps) if changed_latency_gaps else "NOT_APPLICABLE",
        "formal_inference_latency_gap": "NOT_MEASURED_FOR_GATE_OFF_ARM",
        "changed_literal_median_log_n_delta": changed_median("gate_cost_log_n_delta"),
        "changed_literal_median_q_bits_delta": changed_median("gate_cost_q_bits_delta"),
        "changed_literal_median_p_bits_delta": changed_median("gate_cost_p_bits_delta"),
        "changed_literal_median_scale_bits_delta": changed_median("gate_cost_scale_bits_delta"),
        "changed_literal_log_n_increase_cases": sum(float(row["gate_cost_log_n_delta"]) > 0 for row in changed),
        "changed_literal_q_bits_increase_cases": sum(float(row["gate_cost_q_bits_delta"]) > 0 for row in changed),
        "changed_literal_p_bits_increase_cases": sum(float(row["gate_cost_p_bits_delta"]) > 0 for row in changed),
        "changed_literal_scale_increase_cases": sum(float(row["gate_cost_scale_bits_delta"]) > 0 for row in changed),
        "proposed_abstentions": sum(row["c1_state"] != "SELECTED" for row in c2),
        "gate_off_abstentions": sum(row["c2_state"] != "SELECTED" for row in c2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--reports", type=Path, default=REPORTS)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)
    args.reports.mkdir(parents=True, exist_ok=True)

    cases = read_csv(FINAL / "table_04_direct_vs_exhaustive.csv")
    formal_rows = read_csv(FINAL / "table_05_formal_paired_latency.csv")
    regret_rows = read_csv(FINAL / "table_06_latency_regret.csv")
    assert len(cases) == 131
    primary = [row for row in cases if row["phase"] == "primary"]
    assert len(primary) == 68
    assert sum(int(row["direct_trials"]) for row in primary) == 89
    assert sum(int(row["exhaustive_denominator"]) for row in primary) == 537
    assert len(formal_rows) == 68
    assert len({(row["log_n"], row["q_bits"], row["p_bits"], row["scale_bits"], row["path"]) for row in cases}) == 16
    assert len({(row["log_n"], row["q_bits"], row["p_bits"], row["scale_bits"], row["path"]) for row in primary}) == 7

    formal, formal_by_case = collect_formal_latency(formal_rows)
    candidate_rows: list[dict[str, Any]] = []
    sequence_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    numerical_rows: list[dict[str, Any]] = []
    finite_rows: list[dict[str, Any]] = []
    overlay_rows: list[dict[str, Any]] = []

    for case in cases:
        base_case = {
            "phase": case["phase"],
            "dataset": case["dataset"],
            "model_id": case["model_id"],
            "split_id": case["split_id"],
            "case_id": case_id(case),
            "scope": "primary" if case["phase"] == "primary" else "secondary_context",
            "c1_state": case["direct_outcome"],
            "c1_candidate_id": case["candidate_id"],
            "c1_candidate_evaluations": case["direct_trials"],
            "c1_repairs": case["direct_repairs"],
            "c1_separate_status": case["direct_independent_status"],
            "c1_separate_flips": case["direct_independent_flips"],
            "c1_separate_violations": case["direct_independent_violations"],
            "c2_state": "NOT_REPLAYED_SECONDARY",
            "c2_candidate_id": "NOT_REPLAYED_SECONDARY",
            "c2_candidate_evaluations": "NOT_REPLAYED_SECONDARY",
            "c2_selection_flips": "NOT_REPLAYED_SECONDARY",
            "c2_selection_violations": "NOT_REPLAYED_SECONDARY",
            "c2_separate_status": "NOT_REPLAYED_SECONDARY",
            "c3_state": "NOT_REPLAYED_SECONDARY",
            "c3_candidate_id": "NOT_REPLAYED_SECONDARY",
            "c4_fixed_default_status": case["fixed_default_status"],
            "c4_latency_only_candidate_id": case["latency_only_candidate_id"] or "NOT_AVAILABLE",
            "c4_latency_only_status": case["latency_only_gate_status"],
            "c5_fastest_executable_candidate": "NOT_REPLAYED_SECONDARY",
            "c5_minimum_error_candidate": "NOT_REPLAYED_SECONDARY",
            "c5_minimum_rms_candidate": "NOT_REPLAYED_SECONDARY",
            "c5_pareto_candidate_count": "NOT_REPLAYED_SECONDARY",
            "c5_unstable_pareto_candidate_count": "NOT_REPLAYED_SECONDARY",
            "c6_fastest_acceptable_candidate": "NOT_REPLAYED_SECONDARY",
            "c6_finite_evaluations": case["exhaustive_denominator"],
            "false_no_safe": case["false_no_safe"],
            "selected_safe_rank": case["selected_safe_rank"],
            "candidate_stage_latency_gap_ms": "NOT_AVAILABLE",
            "gate_cost_log_n_delta": "NOT_AVAILABLE",
            "gate_cost_q_bits_delta": "NOT_AVAILABLE",
            "gate_cost_p_bits_delta": "NOT_AVAILABLE",
            "gate_cost_scale_bits_delta": "NOT_AVAILABLE",
            "formal_latency_regret": "NOT_AVAILABLE",
        }
        if case["phase"] != "primary":
            case_rows.append(base_case)
            continue

        direct_path, finite_path, legacy_path = primary_sources(case)
        direct = direct_result(direct_path)
        direct_trials = direct.get("trials", [])
        finite_data = read_json(finite_path)
        entries = finite_data.get("entries", [])
        assert len(direct_trials) == int(case["direct_trials"]), (case_id(case), len(direct_trials), case["direct_trials"])
        assert len(entries) == int(case["exhaustive_denominator"]), (case_id(case), len(entries), case["exhaustive_denominator"])
        finite_best = finite_fastest(entries, acceptable_only=True)
        finite_best_id = candidate_values(finite_best["candidate"])["candidate_id"] if finite_best else "NO_SAFE"

        previous_failure = "NONE"
        for order, trial in enumerate(direct_trials, start=1):
            row = make_candidate_row(case, "direct", order, trial, direct_path, formal, case["candidate_id"], finite_best_id, previous_failure)
            candidate_rows.append(row)
            sequence_rows.append({key: row[key] for key in ["case_id", "phase", "dataset", "model_id", "split_id", "candidate_order", "candidate_id", "repair_step", "repair_reason", "selection_status", "selection_input_flips", "selection_input_reserve_violations", "selection_stage_mean_total_ms", "result_hash"]})
            previous_failure = trial.get("failure_signal", trial.get("status", "UNKNOWN"))
        for order, entry in enumerate(entries, start=1):
            row = make_candidate_row(case, "finite_reference", order, entry, finite_path, formal, case["candidate_id"], finite_best_id)
            candidate_rows.append(row)
            unstable = int(row["selection_input_flips"]) > 0 or int(row["selection_input_reserve_violations"]) > 0
            overlay_rows.append(
                {
                    "case_id": row["case_id"],
                    "dataset": row["dataset"],
                    "model_id": row["model_id"],
                    "candidate_id": row["candidate_id"],
                    "selection_stage_mean_total_ms": row["selection_stage_mean_total_ms"],
                    "maximum_absolute_error": row["maximum_absolute_error"],
                    "rms_error": row["rms_error"],
                    "decision_state": "UNSTABLE" if unstable else "STABLE",
                    "decision_flips": row["selection_input_flips"],
                    "reserve_violations": row["selection_input_reserve_violations"],
                    "is_proposed": row["candidate_id"] == case["candidate_id"],
                    "is_finite_fastest_acceptable": row["candidate_id"] == finite_best_id,
                }
            )

        if legacy_path and legacy_path.exists():
            legacy = read_json(legacy_path)
            fixed = legacy.get("fixed_default") or {}
            fixed_candidate = fixed.get("candidate")
            if fixed_candidate:
                static_trial = {
                    "trial_index": 0,
                    "candidate": fixed_candidate,
                    "status": fixed.get("static_status", "NOT_EVALUATED"),
                    "key_repeats_completed": 0,
                }
                fixed_row = make_candidate_row(case, "preexisting_fixed_default", 0, static_trial, legacy_path, formal, case["candidate_id"], finite_best_id)
                fixed_row["materialization_status"] = "NOT_EXECUTED"
                fixed_row["execution_status"] = "NOT_EXECUTED"
                candidate_rows.append(fixed_row)
            for order, legacy_entry in enumerate(legacy.get("entries", []), start=1):
                static = legacy_entry.get("static") or {}
                trial = legacy_entry.get("trial")
                if trial is None:
                    trial = {
                        "trial_index": order,
                        "candidate": static.get("candidate") or {},
                        "status": static.get("static_status", "PLAN_UNSUPPORTED"),
                        "key_repeats_completed": 0,
                    }
                legacy_row = make_candidate_row(case, "preexisting_legacy", order, trial, legacy_path, formal, case["candidate_id"], finite_best_id)
                if static.get("static_status") != "PLAN_OK":
                    legacy_row["materialization_status"] = static.get("static_status", "NOT_EXECUTED")
                    legacy_row["execution_status"] = "NOT_EXECUTED"
                candidate_rows.append(legacy_row)

        c1_trial = next(trial for trial in direct_trials if candidate_values(trial["candidate"])["candidate_id"] == case["candidate_id"])
        c2_trial = next(
            (
                trial
                for trial in direct_trials
                if candidate_values(trial["candidate"])["security_status"] == "PASS"
                and trial_metrics(trial)["execution_status"] == "PASS"
            ),
            None,
        )
        first = direct_trials[0]
        c3_ok = trial_metrics(first)["status"] == "SAFE" and trial_metrics(first)["flips"] == 0 and trial_metrics(first)["violations"] == 0
        fastest_exec = finite_fastest(entries, acceptable_only=False)
        min_error = minimum_error(entries, "max_absolute_error")
        min_rms = minimum_error(entries, "rms_error")
        frontier = pareto(entries)
        c2_id = candidate_values(c2_trial["candidate"])["candidate_id"] if c2_trial else "NO_SELECTION"
        c2_metrics = trial_metrics(c2_trial) if c2_trial else {"flips": 0, "violations": 0, "mean_total_ms": None}
        c1_metrics = trial_metrics(c1_trial)
        c1_values = candidate_values(c1_trial["candidate"])
        c2_values = candidate_values(c2_trial["candidate"]) if c2_trial else None
        c2_separate = "NOT_EVALUATED"
        if c2_id == case["candidate_id"]:
            c2_separate = case["direct_independent_status"]
        elif c2_id == finite_best_id:
            c2_separate = case["fastest_independent_status"]
        formal_case = formal_by_case[case_id(case)]
        regret = next(
            float(row["latency_regret"])
            for row in regret_rows
            if row["direct_candidate_id"] == formal_case["direct_candidate_id"] and row["finite_candidate_id"] == formal_case["finite_candidate_id"]
        )
        gap = "NOT_AVAILABLE"
        if c1_metrics["mean_total_ms"] is not None and c2_metrics["mean_total_ms"] is not None:
            gap = c1_metrics["mean_total_ms"] - c2_metrics["mean_total_ms"]

        base_case.update(
            {
                "c2_state": "SELECTED" if c2_trial else "NO_SELECTION",
                "c2_candidate_id": c2_id,
                "c2_candidate_evaluations": direct_trials.index(c2_trial) + 1 if c2_trial else len(direct_trials),
                "c2_selection_flips": c2_metrics["flips"],
                "c2_selection_violations": c2_metrics["violations"],
                "c2_separate_status": c2_separate,
                "c3_state": "SELECTED" if c3_ok else "STOPPED_INITIAL_REJECT",
                "c3_candidate_id": candidate_values(first["candidate"])["candidate_id"] if c3_ok else "NO_SELECTION",
                "c5_fastest_executable_candidate": candidate_values(fastest_exec["candidate"])["candidate_id"] if fastest_exec else "NONE",
                "c5_minimum_error_candidate": candidate_values(min_error["candidate"])["candidate_id"] if min_error else "NONE",
                "c5_minimum_rms_candidate": candidate_values(min_rms["candidate"])["candidate_id"] if min_rms else "NOT_AVAILABLE",
                "c5_pareto_candidate_count": len(frontier),
                "c5_unstable_pareto_candidate_count": sum(trial_metrics(item)["flips"] > 0 or trial_metrics(item)["violations"] > 0 for item in frontier),
                "c6_fastest_acceptable_candidate": finite_best_id,
                "candidate_stage_latency_gap_ms": gap,
                "gate_cost_log_n_delta": c1_values["log_n"] - c2_values["log_n"] if c2_values else "NOT_AVAILABLE",
                "gate_cost_q_bits_delta": bit_sum(c1_values["ordered_q"]) - bit_sum(c2_values["ordered_q"]) if c2_values else "NOT_AVAILABLE",
                "gate_cost_p_bits_delta": bit_sum(c1_values["ordered_p"]) - bit_sum(c2_values["ordered_p"]) if c2_values else "NOT_AVAILABLE",
                "gate_cost_scale_bits_delta": c1_values["initial_scale"] - c2_values["initial_scale"] if c2_values else "NOT_AVAILABLE",
                "formal_latency_regret": regret,
            }
        )
        case_rows.append(base_case)

        fastest_metrics = trial_metrics(fastest_exec) if fastest_exec else {}
        error_metrics = trial_metrics(min_error) if min_error else {}
        numerical_rows.append(
            {
                "case_id": case_id(case),
                "dataset": case["dataset"],
                "model_id": case["model_id"],
                "fastest_executable_candidate": candidate_values(fastest_exec["candidate"])["candidate_id"] if fastest_exec else "NONE",
                "fastest_executable_flips": fastest_metrics.get("flips", "NOT_AVAILABLE"),
                "fastest_executable_violations": fastest_metrics.get("violations", "NOT_AVAILABLE"),
                "minimum_error_candidate": candidate_values(min_error["candidate"])["candidate_id"] if min_error else "NONE",
                "minimum_error_flips": error_metrics.get("flips", "NOT_AVAILABLE"),
                "minimum_error_violations": error_metrics.get("violations", "NOT_AVAILABLE"),
                "pareto_candidates": len(frontier),
                "unstable_pareto_candidates": sum(trial_metrics(item)["flips"] > 0 or trial_metrics(item)["violations"] > 0 for item in frontier),
                "proposed_candidate": case["candidate_id"],
                "finite_fastest_acceptable_candidate": finite_best_id,
            }
        )
        finite_rows.append(
            {
                "case_id": case_id(case),
                "dataset": case["dataset"],
                "model_id": case["model_id"],
                "proposed_candidate_evaluations": case["direct_trials"],
                "finite_reference_evaluations": case["exhaustive_denominator"],
                "candidate_evaluation_reduction": case["candidate_evaluation_reduction"],
                "false_no_safe": case["false_no_safe"],
                "selected_safe_rank": case["selected_safe_rank"],
                "proposed_candidate": case["candidate_id"],
                "finite_fastest_acceptable_candidate": finite_best_id,
                "formal_latency_regret": regret,
                "finite_over_direct_geomean_total": formal_case["finite_over_direct_geomean_total"],
                "formal_status": formal_case["status"],
            }
        )

    candidate_rows.extend(external_rows())
    candidate_keys = [(row["case_id"], row["candidate_source"], row["candidate_order"], row["candidate_id"]) for row in candidate_rows]
    assert len(candidate_keys) == len(set(candidate_keys)), "duplicate candidate binding"
    assert len(case_rows) == 131 and len({row["case_id"] for row in case_rows}) == 131
    assert len(sequence_rows) == 89

    candidate_fields = list(candidate_rows[0])
    write_csv(args.results / "candidate_level_ledger.csv", candidate_rows, candidate_fields)
    write_csv(args.results / "case_level_ledger.csv", case_rows)
    write_csv(args.results / "selection_sequence.csv", sequence_rows)
    literal_counts: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for case in cases:
        key = (case["log_n"], case["q_bits"], case["p_bits"], case["scale_bits"], case["path"])
        row = literal_counts.setdefault(
            key,
            {
                "log_n": key[0],
                "ordered_q": key[1],
                "ordered_p": key[2],
                "scale": key[3],
                "path": key[4],
                "all_scope_case_count": 0,
                "primary_case_count": 0,
                "models": set(),
            },
        )
        row["all_scope_case_count"] += 1
        row["primary_case_count"] += case["phase"] == "primary"
        row["models"].add(case["model_id"])
    literal_rows = []
    for index, row in enumerate(sorted(literal_counts.values(), key=lambda value: (int(value["log_n"]), value["ordered_q"], value["path"])), start=1):
        row = dict(row)
        row["literal_id"] = f"L{index:02d}"
        row["models"] = ";".join(sorted(row["models"]))
        literal_rows.append(row)
    write_csv(args.results / "literal_inventory.csv", literal_rows, ["literal_id", "log_n", "ordered_q", "ordered_p", "scale", "path", "all_scope_case_count", "primary_case_count", "models"])

    legacy_by_candidate = {
        (row["case_id"], row["candidate_id"]): row
        for row in candidate_rows
        if row["candidate_source"] == "preexisting_legacy"
    }
    preexisting_rows = []
    for row in [item for item in case_rows if item["scope"] == "primary"]:
        legacy = legacy_by_candidate.get((row["case_id"], row["c4_latency_only_candidate_id"]))
        preexisting_rows.append(
            {
                "case_id": row["case_id"],
                "dataset": row["dataset"],
                "model_id": row["model_id"],
                "fixed_default_status": row["c4_fixed_default_status"],
                "latency_only_candidate_id": row["c4_latency_only_candidate_id"],
                "latency_only_gate_status": row["c4_latency_only_status"],
                "latency_only_selection_flips": legacy["selection_input_flips"] if legacy else "NOT_AVAILABLE",
                "latency_only_reserve_violations": legacy["selection_input_reserve_violations"] if legacy else "NOT_AVAILABLE",
                "latency_only_separate_input_status": legacy["separate_input_status"] if legacy else "NOT_EVALUATED",
                "provenance": "PREEXISTING_V17_LEGACY_ARTIFACT",
            }
        )
    write_csv(args.results / "table_preexisting_baselines.csv", preexisting_rows)

    gate_rows = [aggregate_gate(case_rows, "ALL_PRIMARY")]
    gate_rows.extend(aggregate_gate(case_rows, model) for model in sorted({row["model_id"] for row in primary}))
    write_csv(args.results / "table_decision_gate_effect.csv", gate_rows)

    primary_case_rows = [row for row in case_rows if row["scope"] == "primary"]
    repair_rows = []
    for label in ["ALL_PRIMARY", *sorted({row["model_id"] for row in primary})]:
        group = [row for row in primary_case_rows if label == "ALL_PRIMARY" or row["model_id"] == label]
        repair_rows.append(
            {
                "group": label,
                "cases": len(group),
                "initial_candidate_acceptable": sum(row["c3_state"] == "SELECTED" for row in group),
                "repair_needed": sum(row["c3_state"] != "SELECTED" for row in group),
                "repair_success": sum(row["c3_state"] != "SELECTED" and row["c1_state"] == "SELECTED" for row in group),
                "repair_failure": sum(row["c3_state"] != "SELECTED" and row["c1_state"] != "SELECTED" for row in group),
                "additional_candidate_evaluations": sum(int(row["c1_candidate_evaluations"]) - 1 for row in group),
                "full_method_separate_input_pass": sum(row["c1_separate_status"] == "SAFE" for row in group),
                "full_method_separate_input_reject_or_fail": sum(row["c1_separate_status"] in {"REJECTED", "FAILED"} for row in group),
            }
        )
    write_csv(args.results / "table_repair_ablation.csv", repair_rows)
    write_csv(args.results / "table_numerical_objective_diagnostics.csv", numerical_rows)
    write_csv(args.results / "table_finite_reference_quality.csv", finite_rows)
    write_csv(args.results / "figure_error_latency_decision_overlay.csv", overlay_rows)
    component_rows = []
    for row in primary_case_rows:
        for comparator in ["C1_PROPOSED_FULL", "C2_DECISION_GATE_OFF", "C3_INITIAL_ONLY", "C6_FINITE_REFERENCE"]:
            prefix = {"C1_PROPOSED_FULL": "c1", "C2_DECISION_GATE_OFF": "c2", "C3_INITIAL_ONLY": "c3", "C6_FINITE_REFERENCE": "c6"}[comparator]
            state = row.get(f"{prefix}_state", "REFERENCE")
            candidate = row.get(f"{prefix}_candidate_id", row.get("c6_fastest_acceptable_candidate", "NOT_AVAILABLE"))
            component_rows.append({"case_id": row["case_id"], "dataset": row["dataset"], "model_id": row["model_id"], "comparator": comparator, "state": state, "candidate_id": candidate})
    write_csv(args.results / "figure_component_ablation.csv", component_rows)
    write_csv(args.results / "table_cost_of_decision_stability.csv", gate_rows)
    write_csv(args.results / "figure_additional_cost_vs_avoided_instability.csv", gate_rows)
    write_csv(args.results / "figure_proposed_vs_finite_latency_gap.csv", finite_rows)

    eligibility = read_csv(ROOT / "docs/evidence/comparison_extension_v18/comparator_eligibility_matrix.csv")
    external_table = []
    for item in eligibility:
        evidence_state = "RELATED_WORK_ONLY"
        if item["system"] == "HEIR":
            evidence_state = "V8_LOCKED_AUDIT_SAFE; PORTABLE_EXACT; COMMON_EXECUTOR_LATENCY_BLOCKED_UNSAFE_COMPARISON_ARM"
        elif item["system"] == "EVA":
            evidence_state = "V8_500_VALIDATION_PLUS_500_AUDIT; ZERO_SELECTED_ARM_AUDIT_FLIPS; NATIVE_LATENCY_SEPARATE"
        elif item["system"] == "ELASM":
            evidence_state = "V8_70_OF_72_PLANS_COMPLETE; NUMERICAL_ONLY"
        elif item["system"] == "HECATE":
            evidence_state = "NO_EXACT_V17_DECISION_OUTPUT"
        external_table.append({**item, "existing_evidence_state": evidence_state, "new_encrypted_evaluations": 0})
    write_csv(args.results / "table_exact_external_comparator_subset.csv", external_table)
    write_csv(args.results / "figure_external_comparator_eligibility.csv", external_table)

    direct_evals = sum(int(row["direct_trials"]) for row in primary)
    finite_evals = sum(int(row["exhaustive_denominator"]) for row in primary)
    numeric_wall_rows = [row for row in primary if as_float(row["selection_wall_clock_ms"]) is not None and as_float(row["exhaustive_wall_clock_ms"]) is not None]
    wall_ratio = sum(float(row["exhaustive_wall_clock_ms"]) for row in numeric_wall_rows) / sum(float(row["selection_wall_clock_ms"]) for row in numeric_wall_rows)
    wall_case_ratios = [float(row["exhaustive_wall_clock_ms"]) / float(row["selection_wall_clock_ms"]) for row in numeric_wall_rows]
    regrets = [float(row["latency_regret"]) for row in regret_rows]
    formal_ratio_bootstrap = cluster_bootstrap_geomean(formal_rows, "finite_over_direct_geomean_total")
    fastest_unstable = sum(int(row["fastest_executable_flips"]) > 0 or int(row["fastest_executable_violations"]) > 0 for row in numerical_rows)
    min_error_unstable = sum(int(row["minimum_error_flips"]) > 0 or int(row["minimum_error_violations"]) > 0 for row in numerical_rows)
    unstable_pareto = sum(int(row["unstable_pareto_candidates"]) for row in numerical_rows)
    gate = gate_rows[0]
    repair = repair_rows[0]
    class_counts = Counter(row["classification"] for row in eligibility)
    metrics = {
        "schema_version": "flipguard_comparison_extension_v18_metrics_v1",
        "protocol_sha256": sha256(ROOT / "docs/evidence/comparison_extension_v18/protocol_v18.json"),
        "v17_cases_all_scope": 131,
        "v17_cases_primary": 68,
        "formal_latency_rows": 68,
        "candidate_ledger_rows": len(candidate_rows),
        "direct_candidate_evaluations": direct_evals,
        "finite_reference_candidate_evaluations": finite_evals,
        "candidate_evaluation_reduction": 1 - direct_evals / finite_evals,
        "selection_wall_clock_ratio_finite_over_direct_aggregate": wall_ratio,
        "selection_wall_clock_ratio_finite_over_direct_case_distribution": summary(wall_case_ratios),
        "selection_wall_clock_ratio_definition": "sum(finite_reference_wall_clock_ms)/sum(direct_selection_wall_clock_ms)",
        "selection_wall_clock_matched_cases": len(numeric_wall_rows),
        "decision_gate": gate,
        "repair_ablation": repair,
        "traditional_objectives": {
            "cases": len(numerical_rows),
            "fastest_executable_unstable_cases": fastest_unstable,
            "minimum_max_error_unstable_cases": min_error_unstable,
            "unstable_pareto_candidates": unstable_pareto,
            "rms_available_for_all_finite_candidates": all(row["rms_error"] not in {None, ""} for row in overlay_rows),
        },
        "finite_reference": {
            "false_no_safe": sum(yes(row["false_no_safe"]) for row in primary),
            "formal_latency_regret": summary(regrets),
            "formal_finite_over_direct_total_ratio_cluster_bootstrap": formal_ratio_bootstrap,
            "selected_rank": summary(float(row["selected_safe_rank"]) for row in primary),
        },
        "preexisting_baselines": {
            "fixed_default_status_counts": dict(sorted(Counter(row["fixed_default_status"] for row in preexisting_rows).items())),
            "latency_only_gate_status_counts": dict(sorted(Counter(row["latency_only_gate_status"] for row in preexisting_rows).items())),
        },
        "all_scope_negative_context": {
            "cases": 131,
            "separate_input_rejected": sum(row["direct_independent_status"] == "REJECTED" for row in cases),
            "separate_input_failed": sum(row["direct_independent_status"] == "FAILED" for row in cases),
            "false_no_safe": sum(yes(row["false_no_safe"]) for row in cases),
        },
        "selected_literal_counts": {"all_scope": 16, "primary": 7},
        "external_comparator_counts": dict(sorted(class_counts.items())),
        "new_encrypted_candidate_evaluations": 0,
        "targeted_execution_state": "OFFLINE_COMPARISON_COMPLETE_NO_NEW_ENCRYPTED_RUN_REQUIRED",
    }
    (args.results / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = f"""# Offline Replay Results

## Frozen populations

The replay reconciled `131/131` selected case identities, including `68/68`
primary cases. The primary candidate ledger contains `{direct_evals}` direct
candidate evaluations and `{finite_evals}` finite-reference evaluations. It
reuses the `68/68` formal latency rows; no encrypted execution was started.

## Decision-stability gate effect

Removing only the decision gate selected `{gate['gate_off_selected']}/{gate['cases']}`
primary cases. The selected first candidates contained
`{gate['selection_flip_cases']}` case(s) with observed selection-input flips and
`{gate['reserve_violation_cases']}` case(s) with reserve-policy violations.
FlipGuard changed the literal in `{gate['proposed_literal_changed']}` cases and
spent `{gate['additional_candidate_evaluations']}` additional encrypted candidate
evaluations. Separate-input outcomes are available for
`{gate['separate_input_evaluated']}/{gate['cases']}` gate-off selections; missing
candidate-specific held-out evaluations are reported as `NOT_EVALUATED`, not
imputed. A formal gate-off inference-latency arm was not measured.
Among changed literals, median LogN, Q-chain, P-chain, and scale deltas were
`{gate['changed_literal_median_log_n_delta']}`,
`{gate['changed_literal_median_q_bits_delta']}` bits,
`{gate['changed_literal_median_p_bits_delta']}` bits, and
`{gate['changed_literal_median_scale_bits_delta']}` bits, respectively.
The changed-literal candidate-stage median total-latency delta was
`{gate['changed_literal_median_candidate_stage_latency_gap_ms']:.6f}` ms; it is
diagnostic and is not substituted for the unmeasured formal gate-off arm.

## Bounded adjustment

The initial candidate passed in `{repair['initial_candidate_acceptable']}` cases.
The remaining `{repair['repair_needed']}` required a recorded bounded adjustment;
`{repair['repair_success']}` were selected by the full method and
`{repair['repair_failure']}` remained unresolved. This cost exactly
`{repair['additional_candidate_evaluations']}` additional candidate evaluations.

## Numerical objectives

Across `{len(numerical_rows)}` primary cases, the fastest execution-valid finite
candidate violated the decision gate in `{fastest_unstable}` cases. The candidate
with minimum maximum-absolute error violated it in `{min_error_unstable}` cases.
There were `{unstable_pareto}` unstable candidates on case-wise numerical
error/latency Pareto frontiers. These rows are diagnostics, not stand-ins for a
named external system.

## Finite reference

The direct method avoided `{metrics['candidate_evaluation_reduction']:.6%}` of
the encrypted candidate evaluations required by the declared finite reference.
Over the `{len(numeric_wall_rows)}` cases with both timing boundaries, the ratio
of aggregate finite-reference selection wall-clock to aggregate direct selection
wall-clock was `{wall_ratio:.6f}`. This is an offline reference burden and not a
speedup over an existing tuner. The separate case-level ratio had median
`{metrics['selection_wall_clock_ratio_finite_over_direct_case_distribution']['median']:.6f}`
and IQR
`{metrics['selection_wall_clock_ratio_finite_over_direct_case_distribution']['iqr']:.6f}`;
the aggregate and case-level summaries are intentionally not conflated. False
`NO_SAFE` was `0`.

Formal latency regret is `(direct - fastest acceptable) / fastest acceptable`.
Its median was `{metrics['finite_reference']['formal_latency_regret']['median']:.9f}`,
IQR `{metrics['finite_reference']['formal_latency_regret']['iqr']:.9f}`, p90
`{metrics['finite_reference']['formal_latency_regret']['p90']:.9f}`, and maximum
`{metrics['finite_reference']['formal_latency_regret']['maximum']:.9f}` over 68
case-level paired rows.

The dataset-model-cluster geometric mean of finite/direct total latency was
`{formal_ratio_bootstrap['estimate']:.9f}` with deterministic cluster-bootstrap
95% CI `[{formal_ratio_bootstrap['ci_low']:.9f},
{formal_ratio_bootstrap['ci_high']:.9f}]` across
`{formal_ratio_bootstrap['cluster_count']}` clusters. The interval includes 1;
the result supports near-reference selection quality, not latency superiority.

## Preexisting baselines

The frozen fixed default was not a runnable common comparator: 65 cases were
security-inadmissible, two multiclass cases were not reevaluated, and one packed
case was plan-unsupported. The preexisting latency-only candidate was SAFE in
51 cases, REJECTED in 15, and not evaluated in two. These are preserved as
preexisting V17 rows rather than synthesized after observing V18 outcomes.

## External boundary

One frozen HEIR shared-polynomial workload is portable-exact, one EVA workload
is output-comparable, and HECATE/ELASM contribute two numerical-only system
classes. Seven remaining systems or library guides are related-work-only. No
external runtime is folded into the V17 primary latency aggregate.
"""
    (args.reports / "OFFLINE_REPLAY_RESULTS.md").write_text(report, encoding="utf-8")
    print(
        "V18_OFFLINE_REPLAY "
        f"cases={len(case_rows)} primary={len(primary_case_rows)} direct={direct_evals} finite={finite_evals} "
        f"ledger={len(candidate_rows)} new_encrypted=0"
    )


if __name__ == "__main__":
    main()
