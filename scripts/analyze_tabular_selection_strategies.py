#!/usr/bin/env python3

import csv
import math
import statistics
from pathlib import Path
from typing import Dict, List, Callable


INPUT = Path("results/ckks_tabular_profile_sweep_summary/current/profile_summary.csv")
OUTPUT_ROOT = Path("results/ckks_tabular_strategy_analysis/current")


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")

    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"no rows to write: {path}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: str) -> float:
    if value == "":
        return math.nan
    return float(value)


def to_int(value: str) -> int:
    if value == "":
        return 0
    return int(float(value))


def safe_candidate(row: Dict[str, str]) -> bool:
    return row["strict_safe"] == "true"


def completed_candidate(row: Dict[str, str]) -> bool:
    return row["ok_runs"] != "0" and row["mean_total_ms"] != ""


def output_error_safe(row: Dict[str, str]) -> bool:
    return completed_candidate(row) and to_int(row["max_score_error_violations"]) == 0


def decision_safe(row: Dict[str, str]) -> bool:
    return completed_candidate(row) and to_int(row["max_decision_flips"]) == 0


def rescale_path(row: Dict[str, str]) -> bool:
    return completed_candidate(row) and row["path"] == "rescale_aware"


def fastest(rows: List[Dict[str, str]]) -> Dict[str, str]:
    if not rows:
        return {}
    return min(rows, key=lambda row: to_float(row["mean_total_ms"]))


def by_workload(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}

    for row in rows:
        key = f"{row['dataset_id']}::{row['model_id']}"
        grouped.setdefault(key, []).append(row)

    return grouped


def select_for_strategy(
    rows: List[Dict[str, str]],
    strategy_id: str,
    description: str,
    selector: Callable[[List[Dict[str, str]]], Dict[str, str]],
    fixed_default_total: float,
) -> Dict[str, str]:
    selected = selector(rows)

    dataset_id = rows[0]["dataset_id"]
    model_id = rows[0]["model_id"]

    if not selected:
        return {
            "dataset_id": dataset_id,
            "model_id": model_id,
            "strategy_id": strategy_id,
            "strategy_description": description,
            "selected_profile": "",
            "selected_path": "",
            "selected_mean_total_ms": "",
            "selected_mean_eval_only_ms": "",
            "strict_safe": "false",
            "decision_flips": "",
            "score_error_violations": "",
            "speedup_vs_fixed_default": "",
            "selection_status": "no_candidate",
        }

    selected_total = to_float(selected["mean_total_ms"])
    speedup = fixed_default_total / selected_total if selected_total > 0 else math.nan

    is_strict_safe = selected["strict_safe"] == "true"
    decision_flips = to_int(selected["max_decision_flips"])
    score_violations = to_int(selected["max_score_error_violations"])

    if is_strict_safe:
        status = "safe"
    elif selected["failed_runs"] != "0":
        status = "failed_or_incomplete"
    else:
        status = "unsafe"

    return {
        "dataset_id": dataset_id,
        "model_id": model_id,
        "strategy_id": strategy_id,
        "strategy_description": description,
        "selected_profile": selected["profile"],
        "selected_path": selected["path"],
        "selected_mean_total_ms": selected["mean_total_ms"],
        "selected_mean_eval_only_ms": selected["mean_eval_only_ms"],
        "strict_safe": str(is_strict_safe).lower(),
        "decision_flips": selected["max_decision_flips"],
        "score_error_violations": selected["max_score_error_violations"],
        "speedup_vs_fixed_default": f"{speedup:.4f}",
        "selection_status": status,
    }


def fixed_default_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    for row in rows:
        if row["profile"] == "default" and row["path"] == "rescale_aware":
            return row
    return {}


def fastest_without_guard_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return fastest([row for row in rows if completed_candidate(row)])


def output_error_only_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return fastest([row for row in rows if output_error_safe(row)])


def decision_only_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return fastest([row for row in rows if decision_safe(row)])


def rescale_only_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return fastest([row for row in rows if rescale_path(row) and safe_candidate(row)])


def proposed_selector(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return fastest([row for row in rows if safe_candidate(row)])


def build_workload_strategy_rows(profile_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    workload_rows = []

    strategies = [
        (
            "fixed_default_safe_path",
            "fixed default profile with rescale-aware path",
            fixed_default_selector,
        ),
        (
            "fastest_without_guard",
            "fastest completed candidate without safety guard",
            fastest_without_guard_selector,
        ),
        (
            "output_error_guard_only",
            "fastest candidate with output error guard only",
            output_error_only_selector,
        ),
        (
            "decision_guard_only",
            "fastest candidate with decision stability guard only",
            decision_only_selector,
        ),
        (
            "rescale_path_only",
            "fastest safe candidate restricted to rescale-aware path",
            rescale_only_selector,
        ),
        (
            "proposed_dual_guard",
            "fastest candidate satisfying both output error and decision guards",
            proposed_selector,
        ),
    ]

    for _, rows in sorted(by_workload(profile_rows).items()):
        default_row = fixed_default_selector(rows)
        if not default_row:
            raise ValueError(f"missing fixed default row for {rows[0]['dataset_id']} {rows[0]['model_id']}")

        fixed_default_total = to_float(default_row["mean_total_ms"])

        for strategy_id, description, selector in strategies:
            workload_rows.append(
                select_for_strategy(
                    rows,
                    strategy_id,
                    description,
                    selector,
                    fixed_default_total,
                )
            )

    return workload_rows


def summarize_strategies(workload_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}

    for row in workload_rows:
        grouped.setdefault(row["strategy_id"], []).append(row)

    summary_rows = []

    for strategy_id, rows in sorted(grouped.items()):
        total = len(rows)
        safe_count = sum(1 for row in rows if row["strict_safe"] == "true")
        unsafe_count = sum(1 for row in rows if row["selection_status"] == "unsafe")
        missing_count = sum(1 for row in rows if row["selection_status"] == "no_candidate")
        failed_count = sum(1 for row in rows if row["selection_status"] == "failed_or_incomplete")

        total_flips = sum(to_int(row["decision_flips"]) for row in rows)
        total_violations = sum(to_int(row["score_error_violations"]) for row in rows)

        latencies = [
            to_float(row["selected_mean_total_ms"])
            for row in rows
            if row["selected_mean_total_ms"] != ""
        ]
        speedups = [
            to_float(row["speedup_vs_fixed_default"])
            for row in rows
            if row["speedup_vs_fixed_default"] != ""
        ]

        mean_latency = statistics.mean(latencies) if latencies else math.nan
        std_latency = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
        mean_speedup = statistics.mean(speedups) if speedups else math.nan

        summary_rows.append({
            "strategy_id": strategy_id,
            "workloads": str(total),
            "safe_selections": str(safe_count),
            "unsafe_selections": str(unsafe_count),
            "failed_or_incomplete_selections": str(failed_count),
            "missing_selections": str(missing_count),
            "total_decision_flips": str(total_flips),
            "total_score_error_violations": str(total_violations),
            "mean_total_ms": f"{mean_latency:.10f}" if not math.isnan(mean_latency) else "",
            "std_total_ms": f"{std_latency:.10f}" if not math.isnan(std_latency) else "",
            "mean_speedup_vs_fixed_default": f"{mean_speedup:.4f}" if not math.isnan(mean_speedup) else "",
        })

    return summary_rows


def write_latex(summary_rows: List[Dict[str, str]]) -> None:
    label_map = {
        "fixed_default_safe_path": "Fixed default",
        "fastest_without_guard": "Fastest only",
        "output_error_guard_only": "Output guard only",
        "decision_guard_only": "Decision guard only",
        "rescale_path_only": "Rescale path only",
        "proposed_dual_guard": "Proposed",
    }

    lines = []
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Strategy & Safe Sel. & Unsafe Sel. & Flips & Viol. & Speedup \\")
    lines.append(r"\midrule")

    for row in summary_rows:
        strategy = label_map.get(row["strategy_id"], row["strategy_id"]).replace("_", r"\_")
        lines.append(
            f"{strategy} & {row['safe_selections']} & {row['unsafe_selections']} & "
            f"{row['total_decision_flips']} & {row['total_score_error_violations']} & "
            f"{float(row['mean_speedup_vs_fixed_default']):.4f}$\\times$ \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    (OUTPUT_ROOT / "strategy_comparison_table.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_readme(summary_rows: List[Dict[str, str]]) -> None:
    proposed = next(row for row in summary_rows if row["strategy_id"] == "proposed_dual_guard")
    fastest = next(row for row in summary_rows if row["strategy_id"] == "fastest_without_guard")

    text = f"""FlipGuard strategy and ablation analysis

This analysis compares profile-selection strategies using the repeated tabular profile sweep result.

Main result:
- proposed safe selections: {proposed["safe_selections"]}/{proposed["workloads"]}
- proposed unsafe selections: {proposed["unsafe_selections"]}
- proposed total decision flips: {proposed["total_decision_flips"]}
- proposed total score error violations: {proposed["total_score_error_violations"]}
- proposed mean speedup versus fixed default safe path: {proposed["mean_speedup_vs_fixed_default"]}x

Fastest-only baseline:
- fastest-only safe selections: {fastest["safe_selections"]}/{fastest["workloads"]}
- fastest-only unsafe selections: {fastest["unsafe_selections"]}
- fastest-only total decision flips: {fastest["total_decision_flips"]}
- fastest-only total score error violations: {fastest["total_score_error_violations"]}

Interpretation:
The proposed strategy chooses the fastest candidate satisfying both output error and decision stability guards. The fastest-only baseline can reduce latency but may select unsafe candidates. The guard-only variants show whether each individual condition is sufficient or whether both conditions are needed.
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    profile_rows = read_rows(INPUT)
    workload_rows = build_workload_strategy_rows(profile_rows)
    summary_rows = summarize_strategies(workload_rows)

    write_rows(OUTPUT_ROOT / "workload_strategy_selections.csv", workload_rows)
    write_rows(OUTPUT_ROOT / "strategy_summary.csv", summary_rows)
    write_latex(summary_rows)
    write_readme(summary_rows)

    print(f"wrote {OUTPUT_ROOT / 'workload_strategy_selections.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'strategy_summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'strategy_comparison_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
