#!/usr/bin/env python3

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Tuple


MODE_LABELS = {
    "naive": "baseline_non_rescale",
    "baseline_non_rescale": "baseline_non_rescale",
    "rescale": "rescale_aware",
    "rescale_aware": "rescale_aware",
}

DEFAULT_INPUT_TAGS = [
    "profile_mode_speed_r1",
    "profile_mode_speed_r2",
    "profile_mode_speed_r3",
    "profile_mode_speed_r4",
    "profile_mode_speed_r5",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize repeated CKKS profile-mode speed benchmark results."
    )
    parser.add_argument(
        "--input-tags",
        default=",".join(DEFAULT_INPUT_TAGS),
        help="Comma-separated profile-mode comparison result tags.",
    )
    parser.add_argument(
        "--output-tag",
        default="speed_repetition_summary",
        help="Output tag under results/ckks_speed_summary/.",
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Repository-local results directory.",
    )
    return parser.parse_args()


def read_rows(results_root: Path, tag: str) -> List[Dict[str, str]]:
    path = results_root / "ckks_profile_mode_comparison" / tag / "summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing input summary: {path}")

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"input summary has no rows: {path}")

    for row in rows:
        row["input_tag"] = tag

    return rows


def mode_label(raw_mode: str) -> str:
    value = raw_mode.strip()
    if value not in MODE_LABELS:
        raise ValueError(f"unknown evaluation mode: {value}")
    return MODE_LABELS[value]


def parse_float(row: Dict[str, str], key: str) -> float:
    value = row.get(key, "").strip()
    if value == "":
        return 0.0
    return float(value)


def parse_int(row: Dict[str, str], key: str) -> int:
    value = row.get(key, "").strip()
    if value == "":
        return 0
    return int(value)


def parse_bool(row: Dict[str, str], key: str) -> bool:
    value = row.get(key, "").strip().lower()
    return value == "true"


def mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def sample_std(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0

    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def pct_reduction(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return (before - after) / before * 100.0


def group_rows(rows: List[Dict[str, str]]) -> Dict[Tuple[str, str], List[Dict[str, str]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, str]]] = {}

    for row in rows:
        key = (row["profile"], mode_label(row["evaluation_mode"]))
        grouped.setdefault(key, []).append(row)

    return grouped


def summarize_group(profile: str, mode: str, rows: List[Dict[str, str]]) -> Dict[str, str]:
    eval_only = [parse_float(row, "mean_eval_only_ms") for row in rows if row.get("status") == "ok"]
    total = [parse_float(row, "mean_total_ms") for row in rows if row.get("status") == "ok"]
    speedup_eval = [
        parse_float(row, "speedup_vs_default_naive_eval_only")
        for row in rows
        if row.get("status") == "ok"
    ]
    speedup_total = [
        parse_float(row, "speedup_vs_default_naive_total")
        for row in rows
        if row.get("status") == "ok"
    ]

    decision_flips = [parse_int(row, "decision_flips") for row in rows if row.get("status") == "ok"]
    max_errors = [parse_float(row, "max_y_error") for row in rows if row.get("status") == "ok"]

    accepted_count = sum(1 for row in rows if parse_bool(row, "profile_accepted"))
    selected_count = sum(1 for row in rows if parse_bool(row, "selected_fastest_accepted"))
    ok_count = sum(1 for row in rows if row.get("status") == "ok")

    return {
        "profile": profile,
        "evaluation_path": mode,
        "runs": str(len(rows)),
        "ok_runs": str(ok_count),
        "accepted_runs": str(accepted_count),
        "selected_fastest_safe_runs": str(selected_count),
        "mean_eval_only_ms": format_float(mean(eval_only)),
        "std_eval_only_ms": format_float(sample_std(eval_only)),
        "best_eval_only_ms": format_float(min(eval_only) if eval_only else 0.0),
        "mean_total_ms": format_float(mean(total)),
        "std_total_ms": format_float(sample_std(total)),
        "best_total_ms": format_float(min(total) if total else 0.0),
        "mean_speedup_eval_only": format_float(mean(speedup_eval)),
        "std_speedup_eval_only": format_float(sample_std(speedup_eval)),
        "best_speedup_eval_only": format_float(max(speedup_eval) if speedup_eval else 0.0),
        "mean_speedup_total": format_float(mean(speedup_total)),
        "std_speedup_total": format_float(sample_std(speedup_total)),
        "best_speedup_total": format_float(max(speedup_total) if speedup_total else 0.0),
        "max_decision_flips": str(max(decision_flips) if decision_flips else 0),
        "max_y_error_observed": format_scientific(max(max_errors) if max_errors else 0.0),
    }


def selected_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []

    for row in rows:
        if not parse_bool(row, "selected_fastest_accepted"):
            continue

        out.append(
            {
                "input_tag": row["input_tag"],
                "profile": row["profile"],
                "evaluation_path": mode_label(row["evaluation_mode"]),
                "mean_eval_only_ms": format_float(parse_float(row, "mean_eval_only_ms")),
                "mean_total_ms": format_float(parse_float(row, "mean_total_ms")),
                "speedup_eval_only": format_float(
                    parse_float(row, "speedup_vs_default_naive_eval_only")
                ),
                "speedup_total": format_float(
                    parse_float(row, "speedup_vs_default_naive_total")
                ),
                "decision_flips": str(parse_int(row, "decision_flips")),
                "max_y_error": format_scientific(parse_float(row, "max_y_error")),
                "profile_accepted": str(parse_bool(row, "profile_accepted")).lower(),
                "decision_safe": str(parse_bool(row, "decision_safe")).lower(),
                "score_error_violation": str(parse_bool(row, "score_error_violation")).lower(),
            }
        )

    return out


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_latex_table(path: Path, summary_rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    selected_rows = [
        row for row in summary_rows if int(row["selected_fastest_safe_runs"]) > 0
    ]
    baseline_rows = [
        row
        for row in summary_rows
        if row["profile"] == "default" and row["evaluation_path"] == "baseline_non_rescale"
    ]
    unsafe_rows = [
        row
        for row in summary_rows
        if row["profile"] == "short_chain_3" and row["evaluation_path"] == "baseline_non_rescale"
    ]

    display_rows = baseline_rows + selected_rows + unsafe_rows

    with path.open("w") as f:
        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{Repeated CKKS speed benchmark summary.}\n")
        f.write("\\label{tab:ckks-repeated-speed-summary}\n")
        f.write("\\begin{tabular}{llrrrr}\n")
        f.write("\\toprule\n")
        f.write("Profile & Evaluation path & Eval-only ms & Total ms & Eval speedup & Total speedup \\\\\n")
        f.write("\\midrule\n")

        for row in display_rows:
            profile = escape_latex(row["profile"])
            path_label = escape_latex(row["evaluation_path"])

            if int(row["selected_fastest_safe_runs"]) > 0:
                profile += "$^{\\star}$"

            f.write(
                f"{profile} & {path_label} & "
                f"{row['mean_eval_only_ms']} $\\pm$ {row['std_eval_only_ms']} & "
                f"{row['mean_total_ms']} $\\pm$ {row['std_total_ms']} & "
                f"{row['mean_speedup_eval_only']} $\\pm$ {row['std_speedup_eval_only']} & "
                f"{row['mean_speedup_total']} $\\pm$ {row['std_speedup_total']} \\\\\n"
            )

        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")


def write_readme(path: Path, summary_rows: List[Dict[str, str]], selected: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    baseline = find_summary(summary_rows, "default", "baseline_non_rescale")
    selected_summary = next(
        (row for row in summary_rows if int(row["selected_fastest_safe_runs"]) > 0),
        None,
    )
    unsafe = find_summary(summary_rows, "short_chain_3", "baseline_non_rescale")

    with path.open("w") as f:
        f.write("FlipGuard repeated CKKS speed benchmark summary\n")
        f.write("================================================\n\n")

        if baseline:
            f.write("Reference path:\n")
            f.write(
                f"- default + baseline_non_rescale: "
                f"eval-only {baseline['mean_eval_only_ms']} ms ± {baseline['std_eval_only_ms']}, "
                f"total {baseline['mean_total_ms']} ms ± {baseline['std_total_ms']}\n\n"
            )

        if selected_summary:
            f.write("Selected fastest safe path:\n")
            f.write(
                f"- {selected_summary['profile']} + {selected_summary['evaluation_path']}: "
                f"eval-only speedup {selected_summary['mean_speedup_eval_only']}x ± {selected_summary['std_speedup_eval_only']}, "
                f"total speedup {selected_summary['mean_speedup_total']}x ± {selected_summary['std_speedup_total']}\n"
            )
            f.write(
                f"- selected in {selected_summary['selected_fastest_safe_runs']} / {selected_summary['runs']} repetitions\n\n"
            )

        if selected:
            best_eval = max(float(row["speedup_eval_only"]) for row in selected)
            best_total = max(float(row["speedup_total"]) for row in selected)
            f.write("Best observed selected safe path:\n")
            f.write(f"- eval-only speedup: {best_eval:.3f}x\n")
            f.write(f"- total speedup: {best_total:.3f}x\n\n")

        if unsafe:
            f.write("Unsafe raw-speed reference:\n")
            f.write(
                f"- short_chain_3 + baseline_non_rescale: "
                f"eval-only speedup {unsafe['mean_speedup_eval_only']}x ± {unsafe['std_speedup_eval_only']}, "
                f"max decision flips {unsafe['max_decision_flips']}, "
                f"max error {unsafe['max_y_error_observed']}\n"
            )
            f.write("- This profile is not selected because it violates the safety guards.\n")


def find_summary(
    rows: List[Dict[str, str]], profile: str, evaluation_path: str
) -> Dict[str, str]:
    for row in rows:
        if row["profile"] == profile and row["evaluation_path"] == evaluation_path:
            return row
    return {}


def escape_latex(value: str) -> str:
    replacements = {
        "\\": "\\textbackslash{}",
        "_": "\\_",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }

    out = value
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out


def format_float(value: float) -> str:
    return f"{value:.4f}"


def format_scientific(value: float) -> str:
    return f"{value:.4e}"


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)

    tags = [tag.strip() for tag in args.input_tags.split(",") if tag.strip()]
    if not tags:
        raise ValueError("at least one input tag is required")

    all_rows: List[Dict[str, str]] = []
    for tag in tags:
        all_rows.extend(read_rows(results_root, tag))

    grouped = group_rows(all_rows)
    summary_rows = [
        summarize_group(profile, mode, rows)
        for (profile, mode), rows in sorted(grouped.items())
    ]
    selected = selected_rows(all_rows)

    output_dir = results_root / "ckks_speed_summary" / args.output_tag

    summary_fields = [
        "profile",
        "evaluation_path",
        "runs",
        "ok_runs",
        "accepted_runs",
        "selected_fastest_safe_runs",
        "mean_eval_only_ms",
        "std_eval_only_ms",
        "best_eval_only_ms",
        "mean_total_ms",
        "std_total_ms",
        "best_total_ms",
        "mean_speedup_eval_only",
        "std_speedup_eval_only",
        "best_speedup_eval_only",
        "mean_speedup_total",
        "std_speedup_total",
        "best_speedup_total",
        "max_decision_flips",
        "max_y_error_observed",
    ]

    selected_fields = [
        "input_tag",
        "profile",
        "evaluation_path",
        "mean_eval_only_ms",
        "mean_total_ms",
        "speedup_eval_only",
        "speedup_total",
        "decision_flips",
        "max_y_error",
        "profile_accepted",
        "decision_safe",
        "score_error_violation",
    ]

    write_csv(output_dir / "summary.csv", summary_rows, summary_fields)
    write_csv(output_dir / "selected_runs.csv", selected, selected_fields)
    write_latex_table(output_dir / "table.tex", summary_rows)
    write_readme(output_dir / "README.txt", summary_rows, selected)

    print("FlipGuard repeated CKKS speed summary")
    print(f"input_tags={','.join(tags)}")
    print(f"rows={len(all_rows)} grouped_rows={len(summary_rows)} selected_rows={len(selected)}")
    print(f"exported={output_dir}")


if __name__ == "__main__":
    main()
