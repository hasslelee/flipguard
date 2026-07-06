#!/usr/bin/env python3

import csv
from pathlib import Path


PLANNER_MATCHES = Path("results/tuner_planner_demo/profile_matches.csv")
OUTPUT_DIR = Path("results/planner_guided_validation")

WORKLOADS = [
    {
        "planner_workload": "linear_regression",
        "label": "Linear Regression",
        "result_dir": Path("results/ckks_linear_regression_tuner"),
        "candidate_profile_parser": "linreg_profile",
    },
    {
        "planner_workload": "logreg_small",
        "label": "LogReg/Profile",
        "result_dir": Path("results/ckks_auto_tuner_eval"),
        "candidate_profile_parser": "logreg_profile_mode",
    },
    {
        "planner_workload": "polynomial_regression",
        "label": "Polynomial Regression",
        "result_dir": Path("results/ckks_polynomial_regression_tuner"),
        "candidate_profile_parser": "polyreg_profile",
    },
]

ALLOWED_PLANNER_FAMILIES = {
    "reference",
    "planner_min_feasible",
    "planner_scale_guard",
    "planner_chain_guard",
    "planner_aggressive",
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not PLANNER_MATCHES.exists():
        raise FileNotFoundError(f"missing planner matches: {PLANNER_MATCHES}")

    planner_matches = read_csv(PLANNER_MATCHES)

    summary_rows = []
    selection_rows = []

    for workload in WORKLOADS:
        summary, selections = summarize_workload(workload, planner_matches)
        summary_rows.append(summary)
        selection_rows.extend(selections)

    summary_csv = OUTPUT_DIR / "summary.csv"
    selection_csv = OUTPUT_DIR / "selection.csv"
    table_md = OUTPUT_DIR / "table.md"

    write_summary_csv(summary_csv, summary_rows)
    write_selection_csv(selection_csv, selection_rows)
    write_table_md(table_md, summary_rows, selection_rows)

    print(f"Wrote {summary_csv}")
    print(f"Wrote {selection_csv}")
    print(f"Wrote {table_md}")


def summarize_workload(workload: dict, planner_matches: list[dict]) -> tuple[dict, list[dict]]:
    result_dir = workload["result_dir"]

    candidates_path = result_dir / "tuner_candidates.csv"
    selection_path = result_dir / "tuner_selection.csv"

    if not candidates_path.exists():
        raise FileNotFoundError(f"missing candidates CSV: {candidates_path}")
    if not selection_path.exists():
        raise FileNotFoundError(f"missing full selection CSV: {selection_path}")

    full_candidates = read_csv(candidates_path)
    full_selection = read_csv(selection_path)

    resolved_profiles = resolved_profiles_for_workload(
        planner_matches,
        workload["planner_workload"],
    )

    planner_candidates = [
        row
        for row in full_candidates
        if candidate_profile_name(row["candidate_id"], workload["candidate_profile_parser"])
        in resolved_profiles
    ]

    if not planner_candidates:
        raise ValueError(
            f"no measured candidates matched planner-resolved profiles for {workload['planner_workload']}"
        )

    reference = choose_reference(planner_candidates, full_selection)
    fastest_safe = select_fastest_safe(planner_candidates)
    latency_only = select_latency_only(planner_candidates)

    full_fastest_safe = require_policy(full_selection, "fastest_safe")
    full_latency_only = require_policy(full_selection, "latency_only")
    full_reference = require_policy(full_selection, "reference")

    full_candidate_count = len(full_candidates)
    planner_candidate_count = len(planner_candidates)
    reduction_pct = percent_reduction(full_candidate_count, planner_candidate_count)

    reference_ms = parse_float(reference["mean_total_ms"])
    fastest_safe_ms = parse_float(fastest_safe["mean_total_ms"])
    latency_only_ms = parse_float(latency_only["mean_total_ms"])

    full_fastest_safe_ms = parse_float(full_fastest_safe["mean_total_ms"])
    full_latency_only_ms = parse_float(full_latency_only["mean_total_ms"])

    summary = {
        "workload": workload["planner_workload"],
        "label": workload["label"],
        "resolved_profile_count": len(resolved_profiles),
        "resolved_profiles": ";".join(sorted(resolved_profiles)),
        "full_candidate_count": full_candidate_count,
        "planner_candidate_count": planner_candidate_count,
        "candidate_reduction_pct": reduction_pct,
        "full_reference_candidate": full_reference["candidate_id"],
        "full_fastest_safe_candidate": full_fastest_safe["candidate_id"],
        "full_fastest_safe_ms": full_fastest_safe_ms,
        "full_latency_only_candidate": full_latency_only["candidate_id"],
        "full_latency_only_status": full_latency_only["status"],
        "full_latency_only_ms": full_latency_only_ms,
        "planner_reference_candidate": reference["candidate_id"],
        "planner_reference_ms": reference_ms,
        "planner_fastest_safe_candidate": fastest_safe["candidate_id"],
        "planner_fastest_safe_status": fastest_safe["status"],
        "planner_fastest_safe_ms": fastest_safe_ms,
        "planner_fastest_safe_flips": parse_int(fastest_safe["decision_flips"]),
        "planner_fastest_safe_violations": parse_int(fastest_safe["error_violations"]),
        "planner_fastest_safe_error": parse_float(fastest_safe["max_output_error"]),
        "planner_latency_only_candidate": latency_only["candidate_id"],
        "planner_latency_only_status": latency_only["status"],
        "planner_latency_only_ms": latency_only_ms,
        "planner_latency_only_flips": parse_int(latency_only["decision_flips"]),
        "planner_latency_only_violations": parse_int(latency_only["error_violations"]),
        "planner_latency_only_error": parse_float(latency_only["max_output_error"]),
        "planner_fastest_safe_speedup_vs_reference_pct": percent_faster(
            reference_ms,
            fastest_safe_ms,
        ),
        "planner_latency_only_speedup_vs_reference_pct": percent_faster(
            reference_ms,
            latency_only_ms,
        ),
        "planner_fastest_safe_overhead_vs_latency_only_pct": percent_slower(
            latency_only_ms,
            fastest_safe_ms,
        ),
        "planner_fastest_safe_overhead_vs_full_fastest_safe_pct": percent_slower(
            full_fastest_safe_ms,
            fastest_safe_ms,
        ),
    }

    selections = [
        selection_record(workload, "reference", reference),
        selection_record(workload, "fastest_safe", fastest_safe),
        selection_record(workload, "latency_only", latency_only),
    ]

    return summary, selections


def resolved_profiles_for_workload(
    planner_matches: list[dict],
    workload_name: str,
) -> set[str]:
    profiles = set()

    for row in planner_matches:
        if row.get("workload") != workload_name:
            continue

        family = row.get("planned_family", "")
        if family not in ALLOWED_PLANNER_FAMILIES:
            continue

        profile_name = row.get("profile_name", "").strip()
        if profile_name:
            profiles.add(profile_name)

    return profiles


def candidate_profile_name(candidate_id: str, parser: str) -> str:
    candidate_id = candidate_id.strip()

    if parser == "logreg_profile_mode":
        for suffix in ("_naive", "_rescale"):
            if candidate_id.endswith(suffix):
                return candidate_id[: -len(suffix)]
        return candidate_id

    if parser == "polyreg_profile":
        suffix = "_polyreg"
        if candidate_id.endswith(suffix):
            return candidate_id[: -len(suffix)]
        return candidate_id

    if parser == "linreg_profile":
        suffix = "_linreg"
        if candidate_id.endswith(suffix):
            return candidate_id[: -len(suffix)]
        return candidate_id

    raise ValueError(f"unknown candidate profile parser: {parser}")


def choose_reference(planner_candidates: list[dict], full_selection: list[dict]) -> dict:
    full_reference = require_policy(full_selection, "reference")
    full_reference_id = full_reference["candidate_id"]

    for row in planner_candidates:
        if row["candidate_id"] == full_reference_id:
            return row

    for row in planner_candidates:
        if truthy(row.get("is_reference", "")):
            return row

    safe = [row for row in planner_candidates if status(row) == "SAFE"]
    if safe:
        return min(safe, key=lambda row: parse_float(row["mean_total_ms"]))

    return min(planner_candidates, key=lambda row: parse_float(row["mean_total_ms"]))


def select_fastest_safe(rows: list[dict]) -> dict:
    safe = [row for row in rows if status(row) == "SAFE"]
    if not safe:
        raise ValueError("no SAFE planner-guided candidate")

    return min(safe, key=lambda row: parse_float(row["mean_total_ms"]))


def select_latency_only(rows: list[dict]) -> dict:
    successful = [row for row in rows if status(row) != "FAILED"]
    if not successful:
        raise ValueError("no successful planner-guided candidate")

    return min(successful, key=lambda row: parse_float(row["mean_total_ms"]))


def selection_record(workload: dict, policy: str, row: dict) -> dict:
    return {
        "workload": workload["planner_workload"],
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


def write_summary_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "workload",
        "label",
        "resolved_profile_count",
        "resolved_profiles",
        "full_candidate_count",
        "planner_candidate_count",
        "candidate_reduction_pct",
        "full_reference_candidate",
        "full_fastest_safe_candidate",
        "full_fastest_safe_ms",
        "full_latency_only_candidate",
        "full_latency_only_status",
        "full_latency_only_ms",
        "planner_reference_candidate",
        "planner_reference_ms",
        "planner_fastest_safe_candidate",
        "planner_fastest_safe_status",
        "planner_fastest_safe_ms",
        "planner_fastest_safe_flips",
        "planner_fastest_safe_violations",
        "planner_fastest_safe_error",
        "planner_latency_only_candidate",
        "planner_latency_only_status",
        "planner_latency_only_ms",
        "planner_latency_only_flips",
        "planner_latency_only_violations",
        "planner_latency_only_error",
        "planner_fastest_safe_speedup_vs_reference_pct",
        "planner_latency_only_speedup_vs_reference_pct",
        "planner_fastest_safe_overhead_vs_latency_only_pct",
        "planner_fastest_safe_overhead_vs_full_fastest_safe_pct",
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
        f.write("# Planner-Guided Validation Summary\n\n")

        f.write("## Candidate Reduction\n\n")
        f.write(
            "| Workload | Resolved Profiles | Full Candidates | Planner-Guided Candidates | Reduction | Planner Fastest-safe | Planner Latency-only |\n"
        )
        f.write("|---|---:|---:|---:|---:|---|---|\n")

        for row in summary_rows:
            f.write(
                "| {label} | {resolved_profile_count} | {full_candidate_count} | {planner_candidate_count} | "
                "{candidate_reduction_pct:.2f}% | "
                "`{planner_fastest_safe_candidate}` ({planner_fastest_safe_ms:.3f} ms, {planner_fastest_safe_status}) | "
                "`{planner_latency_only_candidate}` ({planner_latency_only_ms:.3f} ms, {planner_latency_only_status}) |\n".format(
                    **row
                )
            )

        f.write("\n## Safety Contrast Within Planner-Guided Set\n\n")
        f.write(
            "| Workload | Fastest-safe flips | Fastest-safe violations | Fastest-safe max error | Latency-only flips | Latency-only violations | Latency-only max error |\n"
        )
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")

        for row in summary_rows:
            f.write(
                "| {label} | {planner_fastest_safe_flips} | {planner_fastest_safe_violations} | {planner_fastest_safe_error:.10g} | "
                "{planner_latency_only_flips} | {planner_latency_only_violations} | {planner_latency_only_error:.10g} |\n".format(
                    **row
                )
            )

        f.write("\n## Comparison to Full Search\n\n")
        f.write(
            "| Workload | Full fastest-safe | Planner fastest-safe | Planner overhead vs full fastest-safe |\n"
        )
        f.write("|---|---|---|---:|\n")

        for row in summary_rows:
            f.write(
                "| {label} | `{full_fastest_safe_candidate}` ({full_fastest_safe_ms:.3f} ms) | "
                "`{planner_fastest_safe_candidate}` ({planner_fastest_safe_ms:.3f} ms) | "
                "{planner_fastest_safe_overhead_vs_full_fastest_safe_pct:.2f}% |\n".format(
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
            "This report performs a retrospective planner-guided validation using already measured tuner outputs. "
        )
        f.write(
            "It filters the full measured candidate table to only the profiles selected by the analysis-driven planner and executable-profile resolver. "
        )
        f.write(
            "The goal is to estimate how much validation work can be avoided before adding a dedicated execution path that runs only the resolved profile subset.\n"
        )


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def require_policy(rows: list[dict], policy: str) -> dict:
    for row in rows:
        if row.get("policy") == policy:
            return row

    raise ValueError(f"policy {policy!r} not found")


def status(row: dict) -> str:
    return row.get("status", "").strip().upper()


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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