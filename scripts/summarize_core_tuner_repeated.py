#!/usr/bin/env python3

import argparse
import csv
import math
import statistics
from pathlib import Path
from typing import Dict, Iterable, List


WORKLOADS = [
    {
        "workload": "linear_regression",
        "label": "Linear Regression",
    },
    {
        "workload": "logreg_small_profile",
        "label": "LogReg/Profile",
    },
    {
        "workload": "polynomial_regression",
        "label": "Polynomial Regression",
    },
    {
        "workload": "sobel_edge",
        "label": "Sobel Edge Detection",
    },
]

POLICIES = [
    "reference",
    "fastest_safe",
    "latency_only",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize repeated FlipGuard core tuner runs."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("results/core_tuner_repeated/current"),
        help="Repeated core tuner result root.",
    )
    args = parser.parse_args()

    raw_root = args.root / "raw"
    if not raw_root.exists():
        raise FileNotFoundError(f"missing raw result root: {raw_root}")

    args.root.mkdir(parents=True, exist_ok=True)

    repeat_dirs = sorted(p for p in raw_root.glob("r*") if p.is_dir())
    if not repeat_dirs:
        raise FileNotFoundError(f"no repeat dirs under {raw_root}")

    policy_records = []
    workload_records = []

    for workload in WORKLOADS:
        records = load_workload_repeats(raw_root, repeat_dirs, workload)
        policy_records.extend(build_policy_summary(workload, records))
        workload_records.append(build_workload_summary(workload, records))

    write_csv(args.root / "policy_repeated_summary.csv", policy_records)
    write_csv(args.root / "workload_repeated_summary.csv", workload_records)

    write_policy_markdown(args.root / "policy_repeated_summary.md", policy_records)
    write_workload_markdown(args.root / "workload_repeated_summary.md", workload_records)
    write_readme(args.root / "README.md", workload_records, policy_records)

    print(f"wrote {args.root / 'policy_repeated_summary.csv'}")
    print(f"wrote {args.root / 'policy_repeated_summary.md'}")
    print(f"wrote {args.root / 'workload_repeated_summary.csv'}")
    print(f"wrote {args.root / 'workload_repeated_summary.md'}")
    print(f"wrote {args.root / 'README.md'}")


def load_workload_repeats(
    raw_root: Path,
    repeat_dirs: List[Path],
    workload: Dict[str, str],
) -> List[Dict[str, object]]:
    out = []

    for repeat_dir in repeat_dirs:
        repeat_id = repeat_dir.name
        result_dir = repeat_dir / workload["workload"]
        selection_path = result_dir / "tuner_selection.csv"
        candidates_path = result_dir / "tuner_candidates.csv"

        if not selection_path.exists():
            raise FileNotFoundError(f"missing selection CSV: {selection_path}")
        if not candidates_path.exists():
            raise FileNotFoundError(f"missing candidates CSV: {candidates_path}")

        selection_rows = read_csv(selection_path)
        candidate_rows = read_csv(candidates_path)

        selection_by_policy = {}
        for row in selection_rows:
            policy = row.get("policy", "")
            if policy:
                selection_by_policy[policy] = row

        for policy in POLICIES:
            if policy not in selection_by_policy:
                raise ValueError(f"missing policy={policy} in {selection_path}")

        out.append(
            {
                "repeat_id": repeat_id,
                "result_dir": str(result_dir),
                "selection": selection_by_policy,
                "candidate_rows": candidate_rows,
                "status_counts": count_candidate_statuses(candidate_rows),
            }
        )

    return out


def build_policy_summary(
    workload: Dict[str, str],
    records: List[Dict[str, object]],
) -> List[Dict[str, str]]:
    rows = []

    reference_mean = mean(
        [
            parse_float(record["selection"]["reference"]["mean_total_ms"])
            for record in records
        ]
    )

    for policy in POLICIES:
        selection_rows = [record["selection"][policy] for record in records]

        mean_total_values = [parse_float(row["mean_total_ms"]) for row in selection_rows]
        decision_flips = [parse_int(row["decision_flips"]) for row in selection_rows]
        error_violations = [parse_int(row["error_violations"]) for row in selection_rows]
        max_errors = [parse_float(row["max_output_error"]) for row in selection_rows]
        failed_runs = [parse_int(row["failed_runs"]) for row in selection_rows]
        success_runs = [parse_int(row["success_runs"]) for row in selection_rows]

        candidate_ids = unique_preserve(row["candidate_id"] for row in selection_rows)
        statuses = unique_preserve(row["status"] for row in selection_rows)
        paths = unique_preserve(row["path"] for row in selection_rows)
        chain_lengths = unique_preserve(row["chain_length"] for row in selection_rows)
        scale_bits = unique_preserve(row["scale_bits"] for row in selection_rows)

        policy_mean = mean(mean_total_values)
        speedup_vs_reference = percent_faster(reference_mean, policy_mean)

        rows.append(
            {
                "workload": workload["workload"],
                "label": workload["label"],
                "policy": policy,
                "repeat_count": str(len(records)),
                "candidate_id": join_unique(candidate_ids),
                "status": join_unique(statuses),
                "path": join_unique(paths),
                "chain_length": join_unique(chain_lengths),
                "scale_bits": join_unique(scale_bits),
                "mean_total_ms_mean": fmt_float(policy_mean),
                "mean_total_ms_std": fmt_float(stdev(mean_total_values)),
                "mean_total_ms_min": fmt_float(min(mean_total_values)),
                "mean_total_ms_max": fmt_float(max(mean_total_values)),
                "speedup_vs_reference_pct": fmt_float(speedup_vs_reference),
                "decision_flips_total": str(sum(decision_flips)),
                "decision_flips_max": str(max(decision_flips)),
                "error_violations_total": str(sum(error_violations)),
                "error_violations_max": str(max(error_violations)),
                "max_output_error_max": fmt_sci(max(max_errors)),
                "success_runs_total": str(sum(success_runs)),
                "failed_runs_total": str(sum(failed_runs)),
            }
        )

    return rows


def build_workload_summary(
    workload: Dict[str, str],
    records: List[Dict[str, object]],
) -> Dict[str, str]:
    reference_rows = [record["selection"]["reference"] for record in records]
    fastest_safe_rows = [record["selection"]["fastest_safe"] for record in records]
    latency_only_rows = [record["selection"]["latency_only"] for record in records]

    reference_values = [parse_float(row["mean_total_ms"]) for row in reference_rows]
    fastest_safe_values = [parse_float(row["mean_total_ms"]) for row in fastest_safe_rows]
    latency_only_values = [parse_float(row["mean_total_ms"]) for row in latency_only_rows]

    reference_mean = mean(reference_values)
    fastest_safe_mean = mean(fastest_safe_values)
    latency_only_mean = mean(latency_only_values)

    status_counts = summarize_status_counts(records)

    fastest_safe_flips = [parse_int(row["decision_flips"]) for row in fastest_safe_rows]
    fastest_safe_violations = [parse_int(row["error_violations"]) for row in fastest_safe_rows]
    latency_only_flips = [parse_int(row["decision_flips"]) for row in latency_only_rows]
    latency_only_violations = [parse_int(row["error_violations"]) for row in latency_only_rows]

    fastest_safe_candidates = unique_preserve(row["candidate_id"] for row in fastest_safe_rows)
    latency_only_candidates = unique_preserve(row["candidate_id"] for row in latency_only_rows)
    reference_candidates = unique_preserve(row["candidate_id"] for row in reference_rows)

    return {
        "workload": workload["workload"],
        "label": workload["label"],
        "repeat_count": str(len(records)),

        "candidate_count": fmt_float(mean([len(record["candidate_rows"]) for record in records])),
        "safe_count": fmt_float(status_counts["SAFE"]),
        "rejected_count": fmt_float(status_counts["REJECTED"]),
        "failed_count": fmt_float(status_counts["FAILED"]),

        "reference_candidate": join_unique(reference_candidates),
        "reference_mean_total_ms": fmt_float(reference_mean),
        "reference_std_total_ms": fmt_float(stdev(reference_values)),

        "fastest_safe_candidate": join_unique(fastest_safe_candidates),
        "fastest_safe_status": join_unique(row["status"] for row in fastest_safe_rows),
        "fastest_safe_mean_total_ms": fmt_float(fastest_safe_mean),
        "fastest_safe_std_total_ms": fmt_float(stdev(fastest_safe_values)),
        "fastest_safe_speedup_vs_reference_pct": fmt_float(
            percent_faster(reference_mean, fastest_safe_mean)
        ),
        "fastest_safe_decision_flips_total": str(sum(fastest_safe_flips)),
        "fastest_safe_decision_flips_max": str(max(fastest_safe_flips)),
        "fastest_safe_error_violations_total": str(sum(fastest_safe_violations)),
        "fastest_safe_error_violations_max": str(max(fastest_safe_violations)),

        "latency_only_candidate": join_unique(latency_only_candidates),
        "latency_only_status": join_unique(row["status"] for row in latency_only_rows),
        "latency_only_mean_total_ms": fmt_float(latency_only_mean),
        "latency_only_std_total_ms": fmt_float(stdev(latency_only_values)),
        "latency_only_speedup_vs_reference_pct": fmt_float(
            percent_faster(reference_mean, latency_only_mean)
        ),
        "latency_only_decision_flips_total": str(sum(latency_only_flips)),
        "latency_only_decision_flips_max": str(max(latency_only_flips)),
        "latency_only_error_violations_total": str(sum(latency_only_violations)),
        "latency_only_error_violations_max": str(max(latency_only_violations)),

        "fastest_safe_overhead_vs_latency_only_pct": fmt_float(
            percent_slower(latency_only_mean, fastest_safe_mean)
        ),
    }


def summarize_status_counts(records: List[Dict[str, object]]) -> Dict[str, float]:
    keys = ["SAFE", "REJECTED", "FAILED"]
    summary = {}
    for key in keys:
        values = [record["status_counts"][key] for record in records]
        summary[key] = mean(values)
    return summary


def count_candidate_statuses(rows: List[Dict[str, str]]) -> Dict[str, int]:
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


def write_policy_markdown(path: Path, rows: List[Dict[str, str]]) -> None:
    columns = [
        "label",
        "policy",
        "repeat_count",
        "candidate_id",
        "status",
        "mean_total_ms_mean",
        "mean_total_ms_std",
        "speedup_vs_reference_pct",
        "decision_flips_total",
        "error_violations_total",
    ]
    write_md_table(path, "Repeated policy-level core tuner summary", rows, columns)


def write_workload_markdown(path: Path, rows: List[Dict[str, str]]) -> None:
    columns = [
        "label",
        "repeat_count",
        "candidate_count",
        "safe_count",
        "rejected_count",
        "failed_count",
        "reference_candidate",
        "reference_mean_total_ms",
        "reference_std_total_ms",
        "fastest_safe_candidate",
        "fastest_safe_mean_total_ms",
        "fastest_safe_std_total_ms",
        "fastest_safe_speedup_vs_reference_pct",
        "latency_only_candidate",
        "latency_only_status",
        "latency_only_mean_total_ms",
        "latency_only_std_total_ms",
        "latency_only_decision_flips_total",
        "latency_only_error_violations_total",
    ]
    write_md_table(path, "Repeated workload-level core tuner summary", rows, columns)


def write_readme(
    path: Path,
    workload_rows: List[Dict[str, str]],
    policy_rows: List[Dict[str, str]],
) -> None:
    total_workloads = len(workload_rows)
    repeats = sorted({row["repeat_count"] for row in workload_rows})
    latency_only_rejected = sum(
        1 for row in workload_rows if "REJECTED" in row["latency_only_status"]
    )
    total_latency_only_flips = sum(
        int(row["latency_only_decision_flips_total"])
        for row in workload_rows
    )
    total_latency_only_violations = sum(
        int(row["latency_only_error_violations_total"])
        for row in workload_rows
    )
    total_fastest_safe_flips = sum(
        int(row["fastest_safe_decision_flips_total"])
        for row in workload_rows
    )
    total_fastest_safe_violations = sum(
        int(row["fastest_safe_error_violations_total"])
        for row in workload_rows
    )

    lines = []
    lines.append("# FlipGuard repeated core tuner benchmark\n\n")
    lines.append(
        "This directory summarizes independent repeated executions of the core FlipGuard tuner workloads.\n\n"
    )
    lines.append("## Summary\n\n")
    lines.append(f"- workloads: {total_workloads}\n")
    lines.append(f"- repeats per workload: {', '.join(repeats)}\n")
    lines.append(f"- latency-only rejected workloads: {latency_only_rejected}/{total_workloads}\n")
    lines.append(f"- fastest-safe total decision flips: {total_fastest_safe_flips}\n")
    lines.append(f"- fastest-safe total error violations: {total_fastest_safe_violations}\n")
    lines.append(f"- latency-only total decision flips: {total_latency_only_flips}\n")
    lines.append(f"- latency-only total error violations: {total_latency_only_violations}\n\n")
    lines.append("## Generated files\n\n")
    lines.append("- `workload_repeated_summary.csv`\n")
    lines.append("- `workload_repeated_summary.md`\n")
    lines.append("- `policy_repeated_summary.csv`\n")
    lines.append("- `policy_repeated_summary.md`\n")
    lines.append("- `raw/`\n\n")
    lines.append("## Interpretation\n\n")
    lines.append(
        "This repeated benchmark is used to reduce the risk that a one-shot latency measurement drives the evaluation. "
        "Each repeat reruns the full tuner experiment and then copies the resulting selection and candidate CSVs into `raw/`.\n"
    )

    path.write_text("".join(lines), encoding="utf-8")


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"no rows to write: {path}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md_table(
    path: Path,
    title: str,
    rows: List[Dict[str, str]],
    columns: List[str],
) -> None:
    lines = []
    lines.append(f"# {title}\n\n")
    lines.append("| " + " | ".join(columns) + " |\n")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |\n")
    for row in rows:
        lines.append("| " + " | ".join(md_cell(row.get(col, "")) for col in columns) + " |\n")
    path.write_text("".join(lines), encoding="utf-8")


def md_cell(value: str) -> str:
    return str(value).replace("|", "\\|")


def unique_preserve(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def join_unique(values: Iterable[str]) -> str:
    unique_values = unique_preserve(values)
    if len(unique_values) == 1:
        return unique_values[0]
    return "mixed:" + ";".join(unique_values)


def parse_float(value: str) -> float:
    value = str(value).strip()
    if value == "":
        return 0.0
    return float(value)


def parse_int(value: str) -> int:
    value = str(value).strip()
    if value == "":
        return 0
    return int(float(value))


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return math.nan
    return statistics.mean(values)


def stdev(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)


def percent_faster(reference_ms: float, candidate_ms: float) -> float:
    if reference_ms <= 0.0 or candidate_ms <= 0.0:
        return 0.0
    return (1.0 - candidate_ms / reference_ms) * 100.0


def percent_slower(reference_ms: float, candidate_ms: float) -> float:
    if reference_ms <= 0.0 or candidate_ms <= 0.0:
        return 0.0
    return (candidate_ms / reference_ms - 1.0) * 100.0


def fmt_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf"
    return f"{value:.10f}"


def fmt_sci(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf"
    return f"{value:.10e}"


if __name__ == "__main__":
    main()
