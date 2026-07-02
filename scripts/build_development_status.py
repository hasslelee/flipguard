#!/usr/bin/env python3

import csv
import re
from collections import Counter
from pathlib import Path


OUT_DIR = Path("results/development_status/current")
OUT_CSV = OUT_DIR / "development_status.csv"

PRESENTATION = Path("results/presentation_ready/current")
PROFILE_SUMMARY_README = Path("results/ckks_tabular_profile_sweep_summary/current/README.txt")
CANDIDATE_CATALOG = PRESENTATION / "candidate_catalog.csv"
EXECUTION_CATALOG = PRESENTATION / "execution_configuration_catalog.csv"
SELECTED_CONFIGS = PRESENTATION / "selected_configurations.csv"
STRATEGY_SUMMARY = PRESENTATION / "strategy_summary.csv"
MNIST_SUMMARY = PRESENTATION / "mnist_summary.csv"
PARAMETER_SAFETY = Path("results/ckks_profile_parameter_analysis/current/profile_parameter_safety.csv")


def read_rows(path):
    if not path.exists():
        return []
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def parse_readme_number(path, labels):
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:=]\s*([0-9,]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).replace(",", "")
    return ""


def add(rows, section, item, metric, value, unit="", source="", note=""):
    rows.append({
        "section": section,
        "item": item,
        "metric": metric,
        "value": str(value),
        "unit": unit,
        "source": source,
        "note": note,
    })


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["section", "item", "metric", "value", "unit", "source", "note"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = []

    candidate_rows = read_rows(CANDIDATE_CATALOG)
    execution_rows = read_rows(EXECUTION_CATALOG)
    selected_rows = read_rows(SELECTED_CONFIGS)
    strategy_rows = read_rows(STRATEGY_SUMMARY)
    mnist_rows = read_rows(MNIST_SUMMARY)
    parameter_rows = read_rows(PARAMETER_SAFETY)

    workloads = len(selected_rows)
    parameter_candidates = len(candidate_rows)
    execution_configurations = len(execution_rows)
    configs_per_workload = int(execution_configurations / parameter_candidates * parameter_candidates) if parameter_candidates else ""
    strict_safe_total = sum(int(float(r.get("strict_safe_candidate_count", 0))) for r in selected_rows)

    requested_runs = parse_readme_number(PROFILE_SUMMARY_README, ["total requested runs", "requested runs"])
    successful_runs = parse_readme_number(PROFILE_SUMMARY_README, ["successful runs"])
    failed_runs = parse_readme_number(PROFILE_SUMMARY_README, ["failed runs"])

    if not requested_runs and workloads and execution_configurations:
        requested_runs = workloads * execution_configurations * 3

    add(rows, "project", "FlipGuard", "research_goal",
        "Select the fastest safe CKKS execution configuration",
        source="docs/terminology_policy.md",
        note="Safety means no failure, no decision flip, and no output error violation.")

    add(rows, "terminology", "execution_path", "path_1", "rescale")
    add(rows, "terminology", "execution_path", "path_2", "non-rescale")
    add(rows, "terminology", "baseline", "default_meaning",
        "chain7_scale45_N14_default",
        note="Default is the project baseline, not a universal CKKS standard.")

    add(rows, "experiment_scale", "workloads", "count", workloads, "count",
        str(SELECTED_CONFIGS))
    add(rows, "experiment_scale", "parameter_candidates", "count", parameter_candidates, "count",
        str(CANDIDATE_CATALOG))
    add(rows, "experiment_scale", "execution_configurations_per_workload", "count",
        execution_configurations, "count", str(EXECUTION_CATALOG),
        "11 parameter candidates x 2 execution paths.")
    add(rows, "experiment_scale", "repeated_runs", "requested", requested_runs, "runs",
        str(PROFILE_SUMMARY_README))
    add(rows, "experiment_scale", "repeated_runs", "successful", successful_runs, "runs",
        str(PROFILE_SUMMARY_README))
    add(rows, "experiment_scale", "repeated_runs", "failed", failed_runs, "runs",
        str(PROFILE_SUMMARY_README))
    add(rows, "experiment_scale", "strict_safe_candidates", "count", strict_safe_total, "candidates",
        str(SELECTED_CONFIGS))

    for r in candidate_rows:
        item = r["display_name"]
        add(rows, "candidate_catalog", item, "internal_name", r["internal_name"], source=str(CANDIDATE_CATALOG))
        add(rows, "candidate_catalog", item, "family", r["candidate_family"], source=str(CANDIDATE_CATALOG))
        add(rows, "candidate_catalog", item, "chain_length", r["chain_length"], source=str(CANDIDATE_CATALOG))
        add(rows, "candidate_catalog", item, "scale_bits", r["scale_bits"], "bits", source=str(CANDIDATE_CATALOG))
        add(rows, "candidate_catalog", item, "log_n", r["log_n"], source=str(CANDIDATE_CATALOG))
        add(rows, "candidate_catalog", item, "slots", r["slots"], source=str(CANDIDATE_CATALOG))

    selected_counter = Counter(r["selected_candidate"] for r in selected_rows)
    selected_path_counter = Counter(r["selected_path"] for r in selected_rows)

    for candidate, count in selected_counter.most_common():
        add(rows, "selection_distribution", candidate, "selected_count", count, "workloads",
            str(SELECTED_CONFIGS))

    for path, count in selected_path_counter.most_common():
        add(rows, "selection_distribution", path, "selected_path_count", count, "workloads",
            str(SELECTED_CONFIGS))

    for r in selected_rows:
        item = f"{r['dataset_id']}__{r['model_id']}"
        add(rows, "selected_workload", item, "selected_candidate", r["selected_candidate"], source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "selected_path", r["selected_path"], source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "strict_safe_candidate_count", r["strict_safe_candidate_count"], "candidates", source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "selected_mean_total_ms", r["selected_mean_total_ms"], "ms", source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "selected_speedup_vs_default", r["selected_total_speedup_vs_default"], "x", source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "fastest_rejected_candidate", r["fastest_rejected_candidate"], source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "fastest_rejected_path", r["fastest_rejected_path"], source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "fastest_rejected_decision_flips", r["fastest_rejected_decision_flips"], "count", source=str(SELECTED_CONFIGS))
        add(rows, "selected_workload", item, "fastest_rejected_error_violations", r["fastest_rejected_score_error_violations"], "count", source=str(SELECTED_CONFIGS))

    for r in strategy_rows:
        item = r["strategy_id"]
        add(rows, "strategy_comparison", item, "safe_selections", r["safe_selections"], "workloads", source=str(STRATEGY_SUMMARY))
        add(rows, "strategy_comparison", item, "unsafe_selections", r["unsafe_selections"], "workloads", source=str(STRATEGY_SUMMARY))
        add(rows, "strategy_comparison", item, "decision_flips", r["decision_flips"], "count", source=str(STRATEGY_SUMMARY))
        add(rows, "strategy_comparison", item, "error_violations", r["score_error_violations"], "count", source=str(STRATEGY_SUMMARY))
        add(rows, "strategy_comparison", item, "mean_total_ms", r["mean_total_ms"], "ms", source=str(STRATEGY_SUMMARY))
        add(rows, "strategy_comparison", item, "mean_speedup_vs_fixed_default", r["mean_speedup_vs_fixed_default"], "x", source=str(STRATEGY_SUMMARY))

    for r in mnist_rows:
        item = f"mnist_pool16__{r['model_id']}"
        add(rows, "mnist_summary", item, "train_samples", r["train_samples"], "samples", source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "test_samples", r["test_samples"], "samples", source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "raw_accuracy", r["raw_accuracy"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "raw_auc", r["raw_auc"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "raw_f1", r["raw_f1"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "selected_candidate", r["selected_candidate"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "selected_path", r["selected_path"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "selected_mean_total_ms", r["selected_mean_total_ms"], "ms", source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "selected_speedup_vs_default", r["selected_total_speedup_vs_default"], "x", source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "fastest_rejected_candidate", r["fastest_rejected_candidate"], source=str(MNIST_SUMMARY))
        add(rows, "mnist_summary", item, "fastest_rejected_decision_flips", r["fastest_rejected_decision_flips"], "count", source=str(MNIST_SUMMARY))

    for r in parameter_rows:
        item = r["profile"]
        add(rows, "parameter_safety", item, "profile_class", r["profile_class"], source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "log_n", r["log_n"], source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "slots", r["slots"], source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "q_prime_count", r["q_prime_count"], source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "scale_bits", r["log_default_scale"], "bits", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "strict_safe_candidate_count", r["strict_safe_candidate_count"], "candidates", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "rejected_candidate_count", r["rejected_candidate_count"], "candidates", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "failed_candidate_count", r["failed_candidate_count"], "candidates", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "total_decision_flips", r["total_decision_flips"], "count", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "total_error_violations", r["total_score_error_violations"], "count", source=str(PARAMETER_SAFETY))
        add(rows, "parameter_safety", item, "mean_total_ms_completed_candidates", r["mean_total_ms_completed_candidates"], "ms", source=str(PARAMETER_SAFETY))

    write_rows(OUT_CSV, rows)
    print(f"wrote {OUT_CSV}")
    print(f"rows: {len(rows)}")


if __name__ == "__main__":
    main()
