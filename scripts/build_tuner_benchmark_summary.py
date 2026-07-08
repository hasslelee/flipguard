#!/usr/bin/env python3

import csv
from pathlib import Path


WORKLOADS = [
    {
        "workload": "linear_regression",
        "label": "Linear Regression",
        "result_dir": Path("results/ckks_linear_regression_tuner"),
    },
    {
        "workload": "logreg_small_profile",
        "label": "LogReg/Profile",
        "result_dir": Path("results/ckks_auto_tuner_eval"),
    },
    {
        "workload": "polynomial_regression",
        "label": "Polynomial Regression",
        "result_dir": Path("results/ckks_polynomial_regression_tuner"),
    },
    {
        "workload": "sobel_edge",
        "label": "Sobel Edge Detection",
        "result_dir": Path("results/ckks_sobel_edge_tuner"),
    },
]

OUTPUT_DIR = Path("results/tuner_benchmark_summary")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for workload in WORKLOADS:
        rows.append(build_workload_summary(workload))

    summary_csv = OUTPUT_DIR / "summary.csv"
    table_md = OUTPUT_DIR / "table.md"

    write_summary_csv(summary_csv, rows)
    write_table_md(table_md, rows)

    print(f"Wrote {summary_csv}")
    print(f"Wrote {table_md}")


def build_workload_summary(workload: dict) -> dict:
    result_dir = workload["result_dir"]

    selection_path = result_dir / "tuner_selection.csv"
    candidates_path = result_dir / "tuner_candidates.csv"

    if not selection_path.exists():
        raise FileNotFoundError(f"missing selection CSV: {selection_path}")
    if not candidates_path.exists():
        raise FileNotFoundError(f"missing candidates CSV: {candidates_path}")

    selection_rows = read_csv(selection_path)
    candidate_rows = read_csv(candidates_path)

    reference = require_policy(selection_rows, "reference")
    fastest_safe = require_policy(selection_rows, "fastest_safe")
    latency_only = require_policy(selection_rows, "latency_only")

    status_counts = count_candidate_statuses(candidate_rows)

    reference_ms = parse_float(reference["mean_total_ms"])
    fastest_safe_ms = parse_float(fastest_safe["mean_total_ms"])
    latency_only_ms = parse_float(latency_only["mean_total_ms"])

    fastest_safe_speedup = percent_faster(reference_ms, fastest_safe_ms)
    latency_only_speedup = percent_faster(reference_ms, latency_only_ms)
    fastest_safe_overhead = percent_slower(latency_only_ms, fastest_safe_ms)

    return {
        "workload": workload["workload"],
        "label": workload["label"],

        "candidate_count": len(candidate_rows),
        "safe_count": status_counts["SAFE"],
        "rejected_count": status_counts["REJECTED"],
        "failed_count": status_counts["FAILED"],

        "reference_candidate": reference["candidate_id"],
        "reference_status": reference["status"],
        "reference_ms": reference_ms,

        "fastest_safe_candidate": fastest_safe["candidate_id"],
        "fastest_safe_status": fastest_safe["status"],
        "fastest_safe_ms": fastest_safe_ms,
        "fastest_safe_flips": parse_int(fastest_safe["decision_flips"]),
        "fastest_safe_violations": parse_int(fastest_safe["error_violations"]),
        "fastest_safe_error": parse_float(fastest_safe["max_output_error"]),
        "fastest_safe_speedup_vs_reference_pct": fastest_safe_speedup,

        "latency_only_candidate": latency_only["candidate_id"],
        "latency_only_status": latency_only["status"],
        "latency_only_ms": latency_only_ms,
        "latency_only_flips": parse_int(latency_only["decision_flips"]),
        "latency_only_violations": parse_int(latency_only["error_violations"]),
        "latency_only_error": parse_float(latency_only["max_output_error"]),
        "latency_only_speedup_vs_reference_pct": latency_only_speedup,

        "fastest_safe_overhead_vs_latency_only_pct": fastest_safe_overhead,
    }


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def require_policy(rows: list[dict], policy: str) -> dict:
    for row in rows:
        if row.get("policy") == policy:
            return row

    raise ValueError(f"policy {policy!r} not found")


def count_candidate_statuses(rows: list[dict]) -> dict:
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
        "candidate_count",
        "safe_count",
        "rejected_count",
        "failed_count",
        "reference_candidate",
        "reference_status",
        "reference_ms",
        "fastest_safe_candidate",
        "fastest_safe_status",
        "fastest_safe_ms",
        "fastest_safe_flips",
        "fastest_safe_violations",
        "fastest_safe_error",
        "fastest_safe_speedup_vs_reference_pct",
        "latency_only_candidate",
        "latency_only_status",
        "latency_only_ms",
        "latency_only_flips",
        "latency_only_violations",
        "latency_only_error",
        "latency_only_speedup_vs_reference_pct",
        "fastest_safe_overhead_vs_latency_only_pct",
    ]

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(format_csv_row(row, fieldnames))


def write_table_md(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        f.write("# FlipGuard Tuner Benchmark Summary\n\n")

        f.write("## Workload-Level Selection Table\n\n")
        f.write(
            "| Workload | Candidates | SAFE | REJECTED | FAILED | Reference | Fastest-safe | Latency-only | Fastest-safe speedup | Latency-only status |\n"
        )
        f.write(
            "|---|---:|---:|---:|---:|---|---|---|---:|---|\n"
        )

        for row in rows:
            f.write(
                "| {label} | {candidate_count} | {safe_count} | {rejected_count} | {failed_count} | "
                "`{reference_candidate}` ({reference_ms:.3f} ms) | "
                "`{fastest_safe_candidate}` ({fastest_safe_ms:.3f} ms) | "
                "`{latency_only_candidate}` ({latency_only_ms:.3f} ms) | "
                "{fastest_safe_speedup_vs_reference_pct:.2f}% | "
                "{latency_only_status} |\n".format(**row)
            )

        f.write("\n## Safety Contrast\n\n")
        f.write(
            "| Workload | Latency-only flips | Latency-only violations | Latency-only max error | Fastest-safe flips | Fastest-safe violations | Fastest-safe max error |\n"
        )
        f.write(
            "|---|---:|---:|---:|---:|---:|---:|\n"
        )

        for row in rows:
            f.write(
                "| {label} | {latency_only_flips} | {latency_only_violations} | {latency_only_error:.10g} | "
                "{fastest_safe_flips} | {fastest_safe_violations} | {fastest_safe_error:.10g} |\n".format(**row)
            )

        f.write("\n## Interpretation\n\n")
        f.write(
            "Across the evaluated workloads, the fastest-safe policy selects the lowest-latency candidate among configurations with zero failures, zero decision flips, and zero output-error violations. "
        )
        f.write(
            "The latency-only policy can select faster candidates, but those candidates may violate decision stability. "
        )
        f.write(
            "This table is intended as a paper-facing summary of the core FlipGuard claim: safety-constrained configuration selection provides a measurable speedup over conservative references while avoiding unsafe latency-only choices.\n"
        )


def format_csv_row(row: dict, fieldnames: list[str]) -> dict:
    formatted = {}
    for key in fieldnames:
        value = row[key]
        if isinstance(value, float):
            formatted[key] = f"{value:.10f}"
        else:
            formatted[key] = value
    return formatted


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


if __name__ == "__main__":
    main()