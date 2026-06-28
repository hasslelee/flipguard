#!/usr/bin/env python3

import csv
import math
import statistics
from pathlib import Path
from typing import Dict, List, Tuple


STATUS_PATH = Path("results/ckks_tabular_profile_sweep_repeated/run_status.csv")
INFERENCE_ROOT = Path("results/ckks_tabular_inference")
OUTPUT_ROOT = Path("results/ckks_tabular_profile_sweep_summary/current")


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")

    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def read_single_summary(tag: str) -> Dict[str, str]:
    path = INFERENCE_ROOT / tag / "summary.csv"

    with path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 1:
        raise ValueError(f"expected one summary row in {path}, got {len(rows)}")

    return rows[0]


def to_float(value: str) -> float:
    return float(value)


def to_int(value: str) -> int:
    return int(float(value))


def mean(values: List[float]) -> float:
    if not values:
        return math.nan
    return statistics.mean(values)


def std(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)


def format_float(value: float, digits: int = 10) -> str:
    if math.isnan(value):
        return ""
    return f"{value:.{digits}f}"


def is_safe_summary(row: Dict[str, str]) -> bool:
    plain_accuracy = to_float(row["plain_accuracy"])
    ckks_accuracy = to_float(row["ckks_accuracy"])
    decision_flips = to_int(row["decision_flips"])
    score_violations = to_int(row["score_error_violations"])

    return (
        decision_flips == 0
        and score_violations == 0
        and abs(plain_accuracy - ckks_accuracy) <= 1e-12
    )


def build_run_rows(status_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    run_rows = []

    for status in status_rows:
        row = dict(status)
        tag = status["tag"]

        if status["status"] == "ok":
            summary = read_single_summary(tag)
            row.update({
                "plain_accuracy": summary["plain_accuracy"],
                "ckks_accuracy": summary["ckks_accuracy"],
                "decision_flips": summary["decision_flips"],
                "score_error_violations": summary["score_error_violations"],
                "max_y_error": summary["max_y_error"],
                "mean_eval_only_ms": summary["mean_eval_only_ms"],
                "mean_total_eval_ms": summary["mean_total_eval_ms"],
                "accepted": str(is_safe_summary(summary)).lower(),
            })
        else:
            row.update({
                "plain_accuracy": "",
                "ckks_accuracy": "",
                "decision_flips": "",
                "score_error_violations": "",
                "max_y_error": "",
                "mean_eval_only_ms": "",
                "mean_total_eval_ms": "",
                "accepted": "false",
            })

        run_rows.append(row)

    return run_rows


def group_key(row: Dict[str, str]) -> Tuple[str, str, str, str]:
    return (
        row["dataset"],
        row["model"],
        row["profile"],
        row["path"],
    )


def summarize_groups(run_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = {}

    for row in run_rows:
        groups.setdefault(group_key(row), []).append(row)

    summary_rows = []

    for key, rows in sorted(groups.items()):
        dataset, model, profile, path = key

        ok_rows = [row for row in rows if row["status"] == "ok"]
        accepted_rows = [row for row in ok_rows if row["accepted"] == "true"]

        eval_times = [to_float(row["mean_eval_only_ms"]) for row in ok_rows]
        total_times = [to_float(row["mean_total_eval_ms"]) for row in ok_rows]
        flips = [to_int(row["decision_flips"]) for row in ok_rows]
        violations = [to_int(row["score_error_violations"]) for row in ok_rows]
        max_errors = [to_float(row["max_y_error"]) for row in ok_rows]

        requested_runs = len(rows)
        ok_runs = len(ok_rows)
        accepted_runs = len(accepted_rows)
        strict_safe = ok_runs == requested_runs and accepted_runs == requested_runs

        summary_rows.append({
            "dataset_id": dataset,
            "model_id": model,
            "profile": profile,
            "path": path,
            "requested_runs": str(requested_runs),
            "ok_runs": str(ok_runs),
            "failed_runs": str(requested_runs - ok_runs),
            "accepted_runs": str(accepted_runs),
            "strict_safe": str(strict_safe).lower(),
            "mean_eval_only_ms": format_float(mean(eval_times)),
            "std_eval_only_ms": format_float(std(eval_times)),
            "mean_total_ms": format_float(mean(total_times)),
            "std_total_ms": format_float(std(total_times)),
            "max_decision_flips": str(max(flips) if flips else ""),
            "sum_decision_flips": str(sum(flips) if flips else ""),
            "max_score_error_violations": str(max(violations) if violations else ""),
            "sum_score_error_violations": str(sum(violations) if violations else ""),
            "max_y_error": format_float(max(max_errors) if max_errors else math.nan),
        })

    return summary_rows


def row_key(row: Dict[str, str]) -> Tuple[str, str, str, str]:
    return (
        row["dataset_id"],
        row["model_id"],
        row["profile"],
        row["path"],
    )


def select_profiles(profile_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_workload: Dict[Tuple[str, str], List[Dict[str, str]]] = {}

    for row in profile_rows:
        by_workload.setdefault((row["dataset_id"], row["model_id"]), []).append(row)

    selected_rows = []

    for workload, rows in sorted(by_workload.items()):
        dataset, model = workload

        default_safe = None
        for row in rows:
            if row["profile"] == "default" and row["path"] == "rescale_aware" and row["ok_runs"] != "0":
                default_safe = row
                break

        strict_safe_rows = [
            row for row in rows
            if row["strict_safe"] == "true" and row["mean_total_ms"] != ""
        ]

        rejected_rows = [
            row for row in rows
            if row["strict_safe"] != "true" and row["mean_total_ms"] != ""
        ]

        if not strict_safe_rows:
            selected = None
        else:
            selected = min(strict_safe_rows, key=lambda row: to_float(row["mean_total_ms"]))

        fastest_rejected = None
        if rejected_rows:
            fastest_rejected = min(rejected_rows, key=lambda row: to_float(row["mean_total_ms"]))

        base_total = to_float(default_safe["mean_total_ms"]) if default_safe else math.nan
        base_eval = to_float(default_safe["mean_eval_only_ms"]) if default_safe else math.nan

        if selected:
            selected_total = to_float(selected["mean_total_ms"])
            selected_eval = to_float(selected["mean_eval_only_ms"])
            selected_total_speedup = base_total / selected_total if selected_total > 0 else math.nan
            selected_eval_speedup = base_eval / selected_eval if selected_eval > 0 else math.nan
        else:
            selected_total_speedup = math.nan
            selected_eval_speedup = math.nan

        if fastest_rejected:
            rejected_total = to_float(fastest_rejected["mean_total_ms"])
            rejected_eval = to_float(fastest_rejected["mean_eval_only_ms"])
            rejected_total_speedup = base_total / rejected_total if rejected_total > 0 else math.nan
            rejected_eval_speedup = base_eval / rejected_eval if rejected_eval > 0 else math.nan
        else:
            rejected_total_speedup = math.nan
            rejected_eval_speedup = math.nan

        selected_rows.append({
            "dataset_id": dataset,
            "model_id": model,
            "candidate_count": str(len(rows)),
            "strict_safe_candidate_count": str(len(strict_safe_rows)),
            "selected_profile": selected["profile"] if selected else "",
            "selected_path": selected["path"] if selected else "",
            "selected_mean_eval_only_ms": selected["mean_eval_only_ms"] if selected else "",
            "selected_std_eval_only_ms": selected["std_eval_only_ms"] if selected else "",
            "selected_mean_total_ms": selected["mean_total_ms"] if selected else "",
            "selected_std_total_ms": selected["std_total_ms"] if selected else "",
            "selected_total_speedup_vs_default_safe": format_float(selected_total_speedup, 4),
            "selected_eval_only_speedup_vs_default_safe": format_float(selected_eval_speedup, 4),
            "fastest_rejected_profile": fastest_rejected["profile"] if fastest_rejected else "",
            "fastest_rejected_path": fastest_rejected["path"] if fastest_rejected else "",
            "fastest_rejected_mean_total_ms": fastest_rejected["mean_total_ms"] if fastest_rejected else "",
            "fastest_rejected_total_speedup_vs_default_safe": format_float(rejected_total_speedup, 4),
            "fastest_rejected_eval_only_speedup_vs_default_safe": format_float(rejected_eval_speedup, 4),
            "fastest_rejected_max_decision_flips": fastest_rejected["max_decision_flips"] if fastest_rejected else "",
            "fastest_rejected_max_score_error_violations": fastest_rejected["max_score_error_violations"] if fastest_rejected else "",
        })

    return selected_rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"no rows to write: {path}")

    fieldnames = list(rows[0].keys())

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_readme(run_rows, profile_rows, selected_rows) -> None:
    total_runs = len(run_rows)
    ok_runs = sum(1 for row in run_rows if row["status"] == "ok")
    failed_runs = total_runs - ok_runs

    total_profile_candidates = len(profile_rows)
    strict_safe_candidates = sum(1 for row in profile_rows if row["strict_safe"] == "true")
    selected_workloads = sum(1 for row in selected_rows if row["selected_profile"] != "")

    rejected_with_flips = sum(
        1 for row in profile_rows
        if row["strict_safe"] != "true"
        and row["max_decision_flips"] not in ("", "0")
    )

    text = f"""FlipGuard repeated tabular profile sweep summary

Experiment scale:
- total requested runs: {total_runs}
- successful runs: {ok_runs}
- failed runs: {failed_runs}
- profile candidates: {total_profile_candidates}
- strict safe candidates: {strict_safe_candidates}
- workloads with selected fastest safe profile: {selected_workloads}/{len(selected_rows)}

Interpretation:
This experiment evaluates multiple CKKS profiles and two evaluation paths across all tabular dataset-model combinations. A candidate is treated as strictly safe only when every repeated run completes successfully and preserves plaintext accuracy with zero decision flips and zero score error violations. The selected profile for each workload is the fastest strict safe candidate by mean total latency.
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def write_latex(selected_rows: List[Dict[str, str]]) -> None:
    lines = []
    lines.append(r"\begin{tabular}{llllrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"Dataset & Model & Selected profile & Path & Total (ms) & "
        r"Speedup & Rejected flips \\"
    )
    lines.append(r"\midrule")

    for row in selected_rows:
        dataset = row["dataset_id"].replace("_", r"\_")
        model = row["model_id"].replace("_", r"\_")
        selected_profile = row["selected_profile"].replace("_", r"\_")
        selected_path = row["selected_path"].replace("_", r"\_")
        total_ms = row["selected_mean_total_ms"]
        speedup = row["selected_total_speedup_vs_default_safe"]
        rejected_flips = row["fastest_rejected_max_decision_flips"]

        lines.append(
            f"{dataset} & {model} & {selected_profile} & {selected_path} & "
            f"{float(total_ms):.4f} & {float(speedup):.4f}$\\times$ & {rejected_flips} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    (OUTPUT_ROOT / "selected_profiles_table.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    status_rows = read_csv_rows(STATUS_PATH)
    run_rows = build_run_rows(status_rows)
    profile_rows = summarize_groups(run_rows)
    selected_rows = select_profiles(profile_rows)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    write_csv(OUTPUT_ROOT / "run_summary.csv", run_rows)
    write_csv(OUTPUT_ROOT / "profile_summary.csv", profile_rows)
    write_csv(OUTPUT_ROOT / "selected_profiles.csv", selected_rows)
    write_latex(selected_rows)
    write_readme(run_rows, profile_rows, selected_rows)

    print(f"wrote {OUTPUT_ROOT / 'run_summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'profile_summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'selected_profiles.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'selected_profiles_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
