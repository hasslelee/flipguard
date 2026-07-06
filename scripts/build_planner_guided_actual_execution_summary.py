#!/usr/bin/env python3

import csv
from pathlib import Path


BASE_DIR = Path("results/planner_guided_actual_execution")

WORKLOADS = [
    {
        "workload": "linear_regression",
        "label": "Linear Regression",
        "subset_dir": BASE_DIR / "linear_regression",
        "full_dir": BASE_DIR / "full_cache" / "ckks_linear_regression_tuner",
    },
    {
        "workload": "logreg_small",
        "label": "LogReg/Profile",
        "subset_dir": BASE_DIR / "logreg_small",
        "full_dir": BASE_DIR / "full_cache" / "ckks_auto_tuner_eval",
    },
    {
        "workload": "polynomial_regression",
        "label": "Polynomial Regression",
        "subset_dir": BASE_DIR / "polynomial_regression",
        "full_dir": BASE_DIR / "full_cache" / "ckks_polynomial_regression_tuner",
    },
]


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    selection_rows = []

    for workload in WORKLOADS:
        summary, selections = summarize_workload(workload)
        summary_rows.append(summary)
        selection_rows.extend(selections)

    summary_csv = BASE_DIR / "summary.csv"
    selection_csv = BASE_DIR / "selection.csv"
    table_md = BASE_DIR / "table.md"

    write_summary_csv(summary_csv, summary_rows)
    write_selection_csv(selection_csv, selection_rows)
    write_table_md(table_md, summary_rows, selection_rows)

    print(f"Wrote {summary_csv}")
    print(f"Wrote {selection_csv}")
    print(f"Wrote {table_md}")


def summarize_workload(workload: dict) -> tuple[dict, list[dict]]:
    subset_candidates_path = workload["subset_dir"] / "tuner_candidates.csv"
    subset_selection_path = workload["subset_dir"] / "tuner_selection.csv"

    full_candidates_path = workload["full_dir"] / "tuner_candidates.csv"
    full_selection_path = workload["full_dir"] / "tuner_selection.csv"

    for path in (
        subset_candidates_path,
        subset_selection_path,
        full_candidates_path,
        full_selection_path,
    ):
        if not path.exists():
            raise FileNotFoundError(f"missing required CSV: {path}")

    subset_candidates = read_csv(subset_candidates_path)
    subset_selection = read_csv(subset_selection_path)

    full_candidates = read_csv(full_candidates_path)
    full_selection = read_csv(full_selection_path)

    subset_reference = require_policy(subset_selection, "reference")
    subset_fastest_safe = require_policy(subset_selection, "fastest_safe")
    subset_latency_only = require_policy(subset_selection, "latency_only")

    full_reference = require_policy(full_selection, "reference")
    full_fastest_safe = require_policy(full_selection, "fastest_safe")
    full_latency_only = require_policy(full_selection, "latency_only")

    subset_candidate_count = len(subset_candidates)
    full_candidate_count = len(full_candidates)

    subset_status_counts = count_statuses(subset_candidates)
    full_status_counts = count_statuses(full_candidates)

    subset_reference_ms = parse_float(subset_reference["mean_total_ms"])
    subset_fastest_safe_ms = parse_float(subset_fastest_safe["mean_total_ms"])
    subset_latency_only_ms = parse_float(subset_latency_only["mean_total_ms"])

    full_fastest_safe_ms = parse_float(full_fastest_safe["mean_total_ms"])

    summary = {
        "workload": workload["workload"],
        "label": workload["label"],
        "full_candidate_count": full_candidate_count,
        "full_safe_count": full_status_counts["SAFE"],
        "full_rejected_count": full_status_counts["REJECTED"],
        "full_failed_count": full_status_counts["FAILED"],
        "subset_candidate_count": subset_candidate_count,
        "subset_safe_count": subset_status_counts["SAFE"],
        "subset_rejected_count": subset_status_counts["REJECTED"],
        "subset_failed_count": subset_status_counts["FAILED"],
        "candidate_reduction_pct": percent_reduction(
            full_candidate_count,
            subset_candidate_count,
        ),
        "full_reference_candidate": full_reference["candidate_id"],
        "full_fastest_safe_candidate": full_fastest_safe["candidate_id"],
        "full_fastest_safe_status": full_fastest_safe["status"],
        "full_fastest_safe_ms": full_fastest_safe_ms,
        "full_latency_only_candidate": full_latency_only["candidate_id"],
        "full_latency_only_status": full_latency_only["status"],
        "full_latency_only_ms": parse_float(full_latency_only["mean_total_ms"]),
        "subset_reference_candidate": subset_reference["candidate_id"],
        "subset_reference_ms": subset_reference_ms,
        "subset_fastest_safe_candidate": subset_fastest_safe["candidate_id"],
        "subset_fastest_safe_status": subset_fastest_safe["status"],
        "subset_fastest_safe_ms": subset_fastest_safe_ms,
        "subset_fastest_safe_flips": parse_int(subset_fastest_safe["decision_flips"]),
        "subset_fastest_safe_violations": parse_int(
            subset_fastest_safe["error_violations"]
        ),
        "subset_fastest_safe_error": parse_float(
            subset_fastest_safe["max_output_error"]
        ),
        "subset_latency_only_candidate": subset_latency_only["candidate_id"],
        "subset_latency_only_status": subset_latency_only["status"],
        "subset_latency_only_ms": subset_latency_only_ms,
        "subset_latency_only_flips": parse_int(subset_latency_only["decision_flips"]),
        "subset_latency_only_violations": parse_int(
            subset_latency_only["error_violations"]
        ),
        "subset_latency_only_error": parse_float(
            subset_latency_only["max_output_error"]
        ),
        "subset_fastest_safe_speedup_vs_reference_pct": percent_faster(
            subset_reference_ms,
            subset_fastest_safe_ms,
        ),
        "subset_latency_only_speedup_vs_reference_pct": percent_faster(
            subset_reference_ms,
            subset_latency_only_ms,
        ),
        "subset_fastest_safe_overhead_vs_latency_only_pct": percent_slower(
            subset_latency_only_ms,
            subset_fastest_safe_ms,
        ),
        "subset_fastest_safe_overhead_vs_full_fastest_safe_pct": percent_slower(
            full_fastest_safe_ms,
            subset_fastest_safe_ms,
        ),
    }

    selections = [
        selection_record(workload, "reference", subset_reference),
        selection_record(workload, "fastest_safe", subset_fastest_safe),
        selection_record(workload, "latency_only", subset_latency_only),
    ]

    return summary, selections


def selection_record(workload: dict, policy: str, row: dict) -> dict:
    return {
        "workload": workload["workload"],
        "label": workload["label"],
        "policy": policy,
        "candidate_id": row["candidate_id"],
        "path": row["path"],
        "status": row["status"],
        "chain_length": row["chain_length"],
        "scale_bits": row["scale_bits"],
        "logN": row["logN"],
        "mean_total_ms": row["mean_total_ms"],
        "decision_flips": row["decision_flips"],
        "error_violations": row["error_violations"],
        "max_output_error": row["max_output_error"],
    }


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def require_policy(rows: list[dict], policy: str) -> dict:
    for row in rows:
        if row.get("policy") == policy:
            return row

    raise ValueError(f"policy {policy!r} not found")


def count_statuses(rows: list[dict]) -> dict:
    counts = {
        "SAFE": 0,
        "REJECTED": 0,
        "FAILED": 0,
    }

    for row in rows:
        status = row.get("status", "").strip().upper()
        if status in counts:
            counts[status] += 1

    return counts


def write_summary_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "workload",
        "label",
        "full_candidate_count",
        "full_safe_count",
        "full_rejected_count",
        "full_failed_count",
        "subset_candidate_count",
        "subset_safe_count",
        "subset_rejected_count",
        "subset_failed_count",
        "candidate_reduction_pct",
        "full_reference_candidate",
        "full_fastest_safe_candidate",
        "full_fastest_safe_status",
        "full_fastest_safe_ms",
        "full_latency_only_candidate",
        "full_latency_only_status",
        "full_latency_only_ms",
        "subset_reference_candidate",
        "subset_reference_ms",
        "subset_fastest_safe_candidate",
        "subset_fastest_safe_status",
        "subset_fastest_safe_ms",
        "subset_fastest_safe_flips",
        "subset_fastest_safe_violations",
        "subset_fastest_safe_error",
        "subset_latency_only_candidate",
        "subset_latency_only_status",
        "subset_latency_only_ms",
        "subset_latency_only_flips",
        "subset_latency_only_violations",
        "subset_latency_only_error",
        "subset_fastest_safe_speedup_vs_reference_pct",
        "subset_latency_only_speedup_vs_reference_pct",
        "subset_fastest_safe_overhead_vs_latency_only_pct",
        "subset_fastest_safe_overhead_vs_full_fastest_safe_pct",
    ]

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(format_csv_row(row, fieldnames))


def write_selection_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "workload",
        "label",
        "policy",
        "candidate_id",
        "path",
        "status",
        "chain_length",
        "scale_bits",
        "logN",
        "mean_total_ms",
        "decision_flips",
        "error_violations",
        "max_output_error",
    ]

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(format_csv_row(row, fieldnames))


def write_table_md(
    path: Path,
    summary_rows: list[dict],
    selection_rows: list[dict],
) -> None:
    with path.open("w") as f:
        f.write("# Planner-Guided Actual Execution Summary\n\n")

        f.write("## Candidate Reduction\n\n")
        f.write(
            "| Workload | Full Candidates | Actually Executed Planner-Guided Candidates | Reduction | Subset Fastest-safe | Subset Latency-only |\n"
        )
        f.write("|---|---:|---:|---:|---|---|\n")

        for row in summary_rows:
            f.write(
                "| {label} | {full_candidate_count} | {subset_candidate_count} | "
                "{candidate_reduction_pct:.2f}% | "
                "`{subset_fastest_safe_candidate}` ({subset_fastest_safe_ms:.3f} ms, {subset_fastest_safe_status}) | "
                "`{subset_latency_only_candidate}` ({subset_latency_only_ms:.3f} ms, {subset_latency_only_status}) |\n".format(
                    **row
                )
            )

        f.write("\n## Safety Contrast Within Actual Planner-Guided Execution\n\n")
        f.write(
            "| Workload | Fastest-safe flips | Fastest-safe violations | Fastest-safe max error | Latency-only flips | Latency-only violations | Latency-only max error |\n"
        )
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")

        for row in summary_rows:
            f.write(
                "| {label} | {subset_fastest_safe_flips} | {subset_fastest_safe_violations} | {subset_fastest_safe_error:.10g} | "
                "{subset_latency_only_flips} | {subset_latency_only_violations} | {subset_latency_only_error:.10g} |\n".format(
                    **row
                )
            )

        f.write("\n## Comparison to Full Search\n\n")
        f.write(
            "| Workload | Full fastest-safe | Planner-guided fastest-safe | Overhead vs full fastest-safe |\n"
        )
        f.write("|---|---|---|---:|\n")

        for row in summary_rows:
            f.write(
                "| {label} | `{full_fastest_safe_candidate}` ({full_fastest_safe_ms:.3f} ms) | "
                "`{subset_fastest_safe_candidate}` ({subset_fastest_safe_ms:.3f} ms) | "
                "{subset_fastest_safe_overhead_vs_full_fastest_safe_pct:.2f}% |\n".format(
                    **row
                )
            )

        f.write("\n## Selected Candidates\n\n")
        f.write(
            "| Workload | Policy | Candidate | Path | Status | Chain | Scale | LogN | Mean ms | Flips | Violations |\n"
        )
        f.write("|---|---|---|---|---|---:|---:|---:|---:|---:|---:|\n")

        for row in selection_rows:
            f.write(
                "| {label} | {policy} | `{candidate_id}` | `{path}` | {status} | "
                "{chain_length} | {scale_bits} | {logN} | {mean_total_ms} | {decision_flips} | {error_violations} |\n".format(
                    **row
                )
            )

        f.write("\n## Interpretation\n\n")
        f.write(
            "This report runs the planner-resolved profile subset and compares the resulting fastest-safe selection against the cached full-search result. "
        )
        f.write(
            "Unlike the retrospective summary, this artifact is based on actually executing only the profiles selected by the planner and resolver, while preserving the full-search outputs as a comparison baseline.\n"
        )


def parse_float(value: str) -> float:
    value = str(value).strip()
    if value == "":
        return 0.0
    return float(value)


def parse_int(value: str) -> int:
    value = str(value).strip()
    if value == "":
        return 0
    return int(value)


def percent_faster(reference_ms: float, candidate_ms: float) -> float:
    if reference_ms <= 0 or candidate_ms <= 0:
        return 0.0
    return (1.0 - candidate_ms / reference_ms) * 100.0


def percent_slower(reference_ms: float, candidate_ms: float) -> float:
    if reference_ms <= 0 or candidate_ms <= 0:
        return 0.0
    return (candidate_ms / reference_ms - 1.0) * 100.0


def percent_reduction(full_count: int, reduced_count: int) -> float:
    if full_count <= 0:
        return 0.0
    return (1.0 - float(reduced_count) / float(full_count)) * 100.0


def format_csv_row(row: dict, fieldnames: list[str]) -> dict:
    formatted = {}

    for key in fieldnames:
        value = row[key]
        if isinstance(value, float):
            formatted[key] = f"{value:.10f}"
        else:
            formatted[key] = value

    return formatted


if __name__ == "__main__":
    main()