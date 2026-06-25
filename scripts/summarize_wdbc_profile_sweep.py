#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path
from typing import Dict, List


PROFILES = [
    "default",
    "scale42",
    "scale40",
    "scale38",
    "short_chain_6_scale42",
    "short_chain_6_scale40",
    "short_chain_6_scale38",
    "short_chain_5",
    "short_chain_3",
]

PATHS = [
    ("baseline_non_rescale", "naive"),
    ("rescale_aware", "rescale"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize WDBC CKKS profile sweep results."
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Repository-local results directory.",
    )
    parser.add_argument(
        "--output-tag",
        default="wdbc_profile_sweep",
        help="Output tag under results/ckks_wdbc_profile_summary/.",
    )
    return parser.parse_args()


def read_summary(path: Path) -> Dict[str, str]:
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) != 1:
        raise ValueError(f"expected exactly one row in {path}, got {len(rows)}")

    return rows[0]


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


def is_safe(row: Dict[str, str]) -> bool:
    return (
        row["status"] == "ok"
        and parse_int(row, "decision_flips") == 0
        and parse_int(row, "score_error_violations") == 0
    )


def build_rows(results_root: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    for profile in PROFILES:
        for canonical_path, raw_path in PATHS:
            tag = f"wdbc_{profile}_{canonical_path}"
            summary_path = results_root / "ckks_wdbc_inference" / tag / "summary.csv"

            if not summary_path.exists():
                rows.append(
                    {
                        "profile": profile,
                        "evaluation_path": canonical_path,
                        "source_tag": tag,
                        "status": "missing_or_failed",
                        "evaluated_rows": "0",
                        "plain_accuracy": "0.0000000000",
                        "ckks_accuracy": "0.0000000000",
                        "decision_match_rate": "0.0000000000",
                        "decision_flips": "0",
                        "score_error_violations": "0",
                        "max_y_error": "0.0000000000",
                        "mean_eval_only_ms": "0.0000000000",
                        "mean_total_eval_ms": "0.0000000000",
                        "median_total_eval_ms": "0.0000000000",
                        "p95_total_eval_ms": "0.0000000000",
                        "accepted": "false",
                        "selected_fastest_safe": "false",
                        "speedup_vs_baseline_eval_only": "0.0000000000",
                        "speedup_vs_baseline_total": "0.0000000000",
                    }
                )
                continue

            source = read_summary(summary_path)
            rows.append(
                {
                    "profile": profile,
                    "evaluation_path": canonical_path,
                    "source_tag": tag,
                    "status": "ok",
                    "evaluated_rows": source["evaluated_rows"],
                    "plain_accuracy": source["plain_accuracy"],
                    "ckks_accuracy": source["ckks_accuracy"],
                    "decision_match_rate": source["decision_match_rate"],
                    "decision_flips": source["decision_flips"],
                    "score_error_violations": source["score_error_violations"],
                    "max_y_error": source["max_y_error"],
                    "mean_eval_only_ms": source["mean_eval_only_ms"],
                    "mean_total_eval_ms": source["mean_total_eval_ms"],
                    "median_total_eval_ms": source["median_total_eval_ms"],
                    "p95_total_eval_ms": source["p95_total_eval_ms"],
                    "accepted": "false",
                    "selected_fastest_safe": "false",
                    "speedup_vs_baseline_eval_only": "0.0000000000",
                    "speedup_vs_baseline_total": "0.0000000000",
                }
            )

    apply_acceptance_and_speedups(rows)
    return rows


def apply_acceptance_and_speedups(rows: List[Dict[str, str]]) -> None:
    baseline = None
    for row in rows:
        if row["profile"] == "default" and row["evaluation_path"] == "baseline_non_rescale":
            if row["status"] == "ok":
                baseline = row
            break

    if baseline is None:
        raise ValueError("missing default baseline_non_rescale WDBC result")

    baseline_eval = parse_float(baseline, "mean_eval_only_ms")
    baseline_total = parse_float(baseline, "mean_total_eval_ms")

    safe_rows = []

    for row in rows:
        if row["status"] == "ok" and baseline_eval > 0 and baseline_total > 0:
            eval_ms = parse_float(row, "mean_eval_only_ms")
            total_ms = parse_float(row, "mean_total_eval_ms")

            if eval_ms > 0:
                row["speedup_vs_baseline_eval_only"] = f"{baseline_eval / eval_ms:.10f}"

            if total_ms > 0:
                row["speedup_vs_baseline_total"] = f"{baseline_total / total_ms:.10f}"

        if is_safe(row):
            row["accepted"] = "true"
            safe_rows.append(row)

    if safe_rows:
        selected = min(safe_rows, key=lambda r: parse_float(r, "mean_total_eval_ms"))
        selected["selected_fastest_safe"] = "true"


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "profile",
        "evaluation_path",
        "source_tag",
        "status",
        "evaluated_rows",
        "plain_accuracy",
        "ckks_accuracy",
        "decision_match_rate",
        "decision_flips",
        "score_error_violations",
        "max_y_error",
        "mean_eval_only_ms",
        "mean_total_eval_ms",
        "median_total_eval_ms",
        "p95_total_eval_ms",
        "accepted",
        "selected_fastest_safe",
        "speedup_vs_baseline_eval_only",
        "speedup_vs_baseline_total",
    ]

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_latex(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    display_rows = [
        row
        for row in rows
        if (
            row["profile"] == "default"
            or row["profile"] == "short_chain_3"
            or row["selected_fastest_safe"] == "true"
        )
    ]

    with path.open("w") as f:
        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{WDBC CKKS profile sweep summary.}\n")
        f.write("\\label{tab:wdbc-ckks-profile-sweep}\n")
        f.write("\\begin{tabular}{llrrrrr}\n")
        f.write("\\toprule\n")
        f.write("Profile & Evaluation path & Acc. & Flips & Viol. & Total ms & Speedup \\\\\n")
        f.write("\\midrule\n")

        for row in display_rows:
            if row["status"] != "ok":
                continue

            profile = escape_latex(row["profile"])
            if row["selected_fastest_safe"] == "true":
                profile += "$^{\\star}$"

            f.write(
                f"{profile} & {escape_latex(row['evaluation_path'])} & "
                f"{float(row['ckks_accuracy']):.4f} & "
                f"{row['decision_flips']} & "
                f"{row['score_error_violations']} & "
                f"{float(row['mean_total_eval_ms']):.2f} & "
                f"{float(row['speedup_vs_baseline_total']):.3f}x \\\\\n"
            )

        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")


def write_readme(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    selected = next((row for row in rows if row["selected_fastest_safe"] == "true"), None)
    unsafe = next(
        (
            row
            for row in rows
            if row["profile"] == "short_chain_3"
            and row["evaluation_path"] == "baseline_non_rescale"
            and row["status"] == "ok"
        ),
        None,
    )

    safe_count = sum(1 for row in rows if row["accepted"] == "true")
    ok_count = sum(1 for row in rows if row["status"] == "ok")
    failed_count = sum(1 for row in rows if row["status"] != "ok")

    with path.open("w") as f:
        f.write("FlipGuard WDBC CKKS profile sweep summary\n")
        f.write("=========================================\n\n")
        f.write(f"ok_rows={ok_count}\n")
        f.write(f"missing_or_failed_rows={failed_count}\n")
        f.write(f"accepted_safe_rows={safe_count}\n\n")

        if selected:
            f.write("Selected fastest safe profile:\n")
            f.write(
                f"- {selected['profile']} + {selected['evaluation_path']}\n"
                f"- CKKS accuracy: {float(selected['ckks_accuracy']):.6f}\n"
                f"- decision flips: {selected['decision_flips']}\n"
                f"- score error violations: {selected['score_error_violations']}\n"
                f"- mean eval-only latency: {float(selected['mean_eval_only_ms']):.6f} ms\n"
                f"- mean total latency: {float(selected['mean_total_eval_ms']):.6f} ms\n"
                f"- total speedup vs baseline: {float(selected['speedup_vs_baseline_total']):.6f}x\n\n"
            )

        if unsafe:
            f.write("Unsafe raw-speed reference:\n")
            f.write(
                f"- {unsafe['profile']} + {unsafe['evaluation_path']}\n"
                f"- CKKS accuracy: {float(unsafe['ckks_accuracy']):.6f}\n"
                f"- decision flips: {unsafe['decision_flips']}\n"
                f"- score error violations: {unsafe['score_error_violations']}\n"
                f"- mean total latency: {float(unsafe['mean_total_eval_ms']):.6f} ms\n"
                f"- total speedup vs baseline: {float(unsafe['speedup_vs_baseline_total']):.6f}x\n"
                f"- This profile is rejected by the safety guards.\n"
            )


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


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)
    output_dir = results_root / "ckks_wdbc_profile_summary" / args.output_tag

    rows = build_rows(results_root)

    write_csv(output_dir / "summary.csv", rows)
    write_latex(output_dir / "table.tex", rows)
    write_readme(output_dir / "README.txt", rows)

    selected = next((row for row in rows if row["selected_fastest_safe"] == "true"), None)

    print("FlipGuard WDBC CKKS profile sweep summary")
    print(f"exported={output_dir}")
    if selected:
        print(
            "selected_fastest_safe="
            f"{selected['profile']}+{selected['evaluation_path']} "
            f"total_ms={float(selected['mean_total_eval_ms']):.6f} "
            f"speedup={float(selected['speedup_vs_baseline_total']):.6f}x"
        )


if __name__ == "__main__":
    main()
