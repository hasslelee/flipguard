#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and validate the final FlipGuard research result summary."
    )
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--boundary-tag", default="boundary_1001x10")
    parser.add_argument("--speed-tag", default="speed_repetition_summary")
    parser.add_argument("--wdbc-inference-tag", default="wdbc_default_rescale_aware")
    parser.add_argument("--wdbc-profile-tag", default="wdbc_profile_sweep")
    parser.add_argument("--output-tag", default="current")
    return parser.parse_args()


def read_single_csv(path: Path) -> Dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")

    with path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 1:
        raise ValueError(f"expected exactly one row in {path}, got {len(rows)}")

    return rows[0]


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")

    with path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise ValueError(f"expected at least one row in {path}")

    return rows


def get_value(row: Dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] != "":
            return row[key]
    raise KeyError(f"missing required key among: {', '.join(keys)}")


def get_float(row: Dict[str, str], *keys: str) -> float:
    return float(get_value(row, *keys))


def get_int(row: Dict[str, str], *keys: str) -> int:
    return int(float(get_value(row, *keys)))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def find_profile_row(
    rows: List[Dict[str, str]],
    profile: str,
    evaluation_path: str,
) -> Dict[str, str]:
    for row in rows:
        if row.get("profile") == profile and row.get("evaluation_path") == evaluation_path:
            return row
    raise KeyError(f"missing profile row: {profile}+{evaluation_path}")


def add_metric(metrics: List[Dict[str, str]], section: str, metric: str, value) -> None:
    metrics.append(
        {
            "section": section,
            "metric": metric,
            "value": str(value),
        }
    )


def format_float(value: float, digits: int = 10) -> str:
    return f"{value:.{digits}f}"


def build_summary(args: argparse.Namespace) -> List[Dict[str, str]]:
    root = Path(args.results_root)

    audit = read_single_csv(
        root / "ckks_certificate_audit" / args.boundary_tag / "summary.csv"
    )
    output_accuracy = read_single_csv(
        root / "ckks_output_accuracy" / args.boundary_tag / "summary.csv"
    )
    speed_rows = read_csv_rows(
        root / "ckks_speed_summary" / args.speed_tag / "summary.csv"
    )
    wdbc_inference = read_single_csv(
        root / "ckks_wdbc_inference" / args.wdbc_inference_tag / "summary.csv"
    )
    wdbc_profile_rows = read_csv_rows(
        root / "ckks_wdbc_profile_summary" / args.wdbc_profile_tag / "summary.csv"
    )

    speed_baseline = find_profile_row(speed_rows, "default", "baseline_non_rescale")
    speed_selected = find_profile_row(speed_rows, "default", "rescale_aware")
    speed_unsafe = find_profile_row(speed_rows, "short_chain_3", "baseline_non_rescale")

    wdbc_baseline = find_profile_row(wdbc_profile_rows, "default", "baseline_non_rescale")
    wdbc_selected = find_profile_row(wdbc_profile_rows, "default", "rescale_aware")
    wdbc_unsafe = find_profile_row(wdbc_profile_rows, "short_chain_3", "baseline_non_rescale")

    require(get_int(audit, "runs", "total_runs") == 10010, "boundary run count must be 10010")
    require(get_int(audit, "stable_runs") == 9900, "stable run count must be 9900")
    require(get_int(audit, "stable_flips") == 0, "stable decision flips must be zero")
    require(get_int(audit, "stable_violations") == 0, "stable violations must be zero")

    require(
        get_int(output_accuracy, "score_error_violations") == 0,
        "stable score error violations must be zero",
    )

    if "all_score_error_violations" in output_accuracy:
        require(
            get_int(output_accuracy, "all_score_error_violations") == 0,
            "all score error violations must be zero",
        )

    require(
        get_int(speed_selected, "selected_fastest_safe_runs") == 5,
        "default rescale-aware path must be selected in all speed repetitions",
    )
    require(
        get_int(speed_selected, "max_decision_flips") == 0,
        "selected speed path must have zero decision flips",
    )
    require(
        get_float(speed_selected, "mean_speedup_total") > 1.0,
        "selected speed path must improve total latency",
    )
    require(
        get_int(speed_unsafe, "accepted_runs") == 0,
        "unsafe speed profile must not be accepted",
    )
    require(
        get_int(speed_unsafe, "max_decision_flips") > 0,
        "unsafe speed profile must show decision flips",
    )

    require(
        get_int(wdbc_inference, "evaluated_rows") == 171,
        "WDBC inference row count must be 171",
    )
    require(
        get_int(wdbc_inference, "decision_flips") == 0,
        "WDBC default rescale-aware decision flips must be zero",
    )
    require(
        get_int(wdbc_inference, "score_error_violations") == 0,
        "WDBC default rescale-aware score error violations must be zero",
    )
    require(
        abs(get_float(wdbc_inference, "plain_accuracy") - get_float(wdbc_inference, "ckks_accuracy")) < 1e-12,
        "WDBC plain and CKKS accuracy must match",
    )

    require(
        wdbc_selected["selected_fastest_safe"] == "true",
        "WDBC default rescale-aware must be selected fastest safe",
    )
    require(
        wdbc_selected["accepted"] == "true",
        "WDBC selected profile must be accepted",
    )
    require(
        get_int(wdbc_selected, "decision_flips") == 0,
        "WDBC selected profile must have zero decision flips",
    )
    require(
        get_int(wdbc_selected, "score_error_violations") == 0,
        "WDBC selected profile must have zero score error violations",
    )
    require(
        get_int(wdbc_unsafe, "decision_flips") > 0,
        "WDBC unsafe profile must show decision flips",
    )
    require(
        get_int(wdbc_unsafe, "score_error_violations") > 0,
        "WDBC unsafe profile must show score error violations",
    )

    metrics: List[Dict[str, str]] = []

    add_metric(metrics, "validation", "status", "pass")

    add_metric(metrics, "boundary", "tag", args.boundary_tag)
    add_metric(metrics, "boundary", "runs", get_int(audit, "runs", "total_runs"))
    add_metric(metrics, "boundary", "stable_runs", get_int(audit, "stable_runs"))
    add_metric(metrics, "boundary", "ambiguous_runs", get_int(audit, "ambiguous_runs"))
    add_metric(metrics, "boundary", "stable_decision_flips", get_int(audit, "stable_flips"))
    add_metric(metrics, "boundary", "stable_violations", get_int(audit, "stable_violations"))
    add_metric(metrics, "boundary", "max_y_error", get_value(audit, "max_y_error"))

    add_metric(metrics, "output_accuracy", "score_error_violations", get_int(output_accuracy, "score_error_violations"))
    if "all_score_error_violations" in output_accuracy:
        add_metric(metrics, "output_accuracy", "all_score_error_violations", get_int(output_accuracy, "all_score_error_violations"))
    add_metric(metrics, "output_accuracy", "max_y_error", get_value(output_accuracy, "max_y_error"))

    add_metric(metrics, "speed", "tag", args.speed_tag)
    add_metric(metrics, "speed", "baseline_profile", "default+baseline_non_rescale")
    add_metric(metrics, "speed", "baseline_eval_only_ms_mean", get_value(speed_baseline, "mean_eval_only_ms"))
    add_metric(metrics, "speed", "baseline_eval_only_ms_std", get_value(speed_baseline, "std_eval_only_ms"))
    add_metric(metrics, "speed", "baseline_total_ms_mean", get_value(speed_baseline, "mean_total_ms"))
    add_metric(metrics, "speed", "baseline_total_ms_std", get_value(speed_baseline, "std_total_ms"))

    add_metric(metrics, "speed", "selected_profile", "default+rescale_aware")
    add_metric(metrics, "speed", "selected_runs", get_int(speed_selected, "selected_fastest_safe_runs"))
    add_metric(metrics, "speed", "selected_eval_only_ms_mean", get_value(speed_selected, "mean_eval_only_ms"))
    add_metric(metrics, "speed", "selected_eval_only_ms_std", get_value(speed_selected, "std_eval_only_ms"))
    add_metric(metrics, "speed", "selected_total_ms_mean", get_value(speed_selected, "mean_total_ms"))
    add_metric(metrics, "speed", "selected_total_ms_std", get_value(speed_selected, "std_total_ms"))
    add_metric(metrics, "speed", "selected_eval_only_speedup_mean", get_value(speed_selected, "mean_speedup_eval_only"))
    add_metric(metrics, "speed", "selected_eval_only_speedup_std", get_value(speed_selected, "std_speedup_eval_only"))
    add_metric(metrics, "speed", "selected_total_speedup_mean", get_value(speed_selected, "mean_speedup_total"))
    add_metric(metrics, "speed", "selected_total_speedup_std", get_value(speed_selected, "std_speedup_total"))
    add_metric(metrics, "speed", "best_eval_only_speedup", get_value(speed_selected, "best_speedup_eval_only"))
    add_metric(metrics, "speed", "best_total_speedup", get_value(speed_selected, "best_speedup_total"))

    add_metric(metrics, "speed_unsafe", "profile", "short_chain_3+baseline_non_rescale")
    add_metric(metrics, "speed_unsafe", "eval_only_speedup_mean", get_value(speed_unsafe, "mean_speedup_eval_only"))
    add_metric(metrics, "speed_unsafe", "total_speedup_mean", get_value(speed_unsafe, "mean_speedup_total"))
    add_metric(metrics, "speed_unsafe", "max_decision_flips", get_int(speed_unsafe, "max_decision_flips"))
    add_metric(metrics, "speed_unsafe", "max_y_error", get_value(speed_unsafe, "max_y_error_observed"))

    add_metric(metrics, "wdbc", "inference_tag", args.wdbc_inference_tag)
    add_metric(metrics, "wdbc", "test_samples", get_int(wdbc_inference, "evaluated_rows"))
    add_metric(metrics, "wdbc", "plain_accuracy", get_value(wdbc_inference, "plain_accuracy"))
    add_metric(metrics, "wdbc", "ckks_accuracy", get_value(wdbc_inference, "ckks_accuracy"))
    add_metric(metrics, "wdbc", "decision_match_rate", get_value(wdbc_inference, "decision_match_rate"))
    add_metric(metrics, "wdbc", "decision_flips", get_int(wdbc_inference, "decision_flips"))
    add_metric(metrics, "wdbc", "score_error_violations", get_int(wdbc_inference, "score_error_violations"))
    add_metric(metrics, "wdbc", "max_y_error", get_value(wdbc_inference, "max_y_error"))
    add_metric(metrics, "wdbc", "mean_eval_only_ms", get_value(wdbc_inference, "mean_eval_only_ms"))
    add_metric(metrics, "wdbc", "mean_total_ms", get_value(wdbc_inference, "mean_total_eval_ms"))

    add_metric(metrics, "wdbc_profile", "tag", args.wdbc_profile_tag)
    add_metric(metrics, "wdbc_profile", "selected_profile", "default+rescale_aware")
    add_metric(metrics, "wdbc_profile", "selected_ckks_accuracy", get_value(wdbc_selected, "ckks_accuracy"))
    add_metric(metrics, "wdbc_profile", "selected_decision_flips", get_int(wdbc_selected, "decision_flips"))
    add_metric(metrics, "wdbc_profile", "selected_score_error_violations", get_int(wdbc_selected, "score_error_violations"))
    add_metric(metrics, "wdbc_profile", "selected_eval_only_ms", get_value(wdbc_selected, "mean_eval_only_ms"))
    add_metric(metrics, "wdbc_profile", "selected_total_ms", get_value(wdbc_selected, "mean_total_eval_ms"))
    add_metric(metrics, "wdbc_profile", "selected_eval_only_speedup", get_value(wdbc_selected, "speedup_vs_baseline_eval_only"))
    add_metric(metrics, "wdbc_profile", "selected_total_speedup", get_value(wdbc_selected, "speedup_vs_baseline_total"))

    add_metric(metrics, "wdbc_unsafe", "profile", "short_chain_3+baseline_non_rescale")
    add_metric(metrics, "wdbc_unsafe", "ckks_accuracy", get_value(wdbc_unsafe, "ckks_accuracy"))
    add_metric(metrics, "wdbc_unsafe", "decision_flips", get_int(wdbc_unsafe, "decision_flips"))
    add_metric(metrics, "wdbc_unsafe", "score_error_violations", get_int(wdbc_unsafe, "score_error_violations"))
    add_metric(metrics, "wdbc_unsafe", "max_y_error", get_value(wdbc_unsafe, "max_y_error"))
    add_metric(metrics, "wdbc_unsafe", "eval_only_speedup", get_value(wdbc_unsafe, "speedup_vs_baseline_eval_only"))
    add_metric(metrics, "wdbc_unsafe", "total_speedup", get_value(wdbc_unsafe, "speedup_vs_baseline_total"))

    return metrics


def metric_value(metrics: List[Dict[str, str]], section: str, metric: str) -> str:
    for row in metrics:
        if row["section"] == section and row["metric"] == metric:
            return row["value"]
    raise KeyError(f"missing metric {section}.{metric}")


def write_summary_csv(path: Path, metrics: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "metric", "value"])
        writer.writeheader()
        writer.writerows(metrics)


def write_readme(path: Path, metrics: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as f:
        f.write("FlipGuard final research result summary\n")
        f.write("=======================================\n\n")
        f.write(f"validation_status={metric_value(metrics, 'validation', 'status')}\n\n")

        f.write("Boundary stress test:\n")
        f.write(f"- runs: {metric_value(metrics, 'boundary', 'runs')}\n")
        f.write(f"- stable runs: {metric_value(metrics, 'boundary', 'stable_runs')}\n")
        f.write(f"- stable decision flips: {metric_value(metrics, 'boundary', 'stable_decision_flips')}\n")
        f.write(f"- output accuracy violations: {metric_value(metrics, 'output_accuracy', 'score_error_violations')}\n\n")

        f.write("Repeated speed benchmark:\n")
        f.write(
            f"- selected path: {metric_value(metrics, 'speed', 'selected_profile')}\n"
            f"- eval-only speedup: {metric_value(metrics, 'speed', 'selected_eval_only_speedup_mean')}x "
            f"± {metric_value(metrics, 'speed', 'selected_eval_only_speedup_std')}\n"
            f"- total speedup: {metric_value(metrics, 'speed', 'selected_total_speedup_mean')}x "
            f"± {metric_value(metrics, 'speed', 'selected_total_speedup_std')}\n"
            f"- best observed total speedup: {metric_value(metrics, 'speed', 'best_total_speedup')}x\n\n"
        )

        f.write("WDBC encrypted inference:\n")
        f.write(
            f"- test samples: {metric_value(metrics, 'wdbc', 'test_samples')}\n"
            f"- CKKS accuracy: {metric_value(metrics, 'wdbc', 'ckks_accuracy')}\n"
            f"- decision flips: {metric_value(metrics, 'wdbc', 'decision_flips')}\n"
            f"- score error violations: {metric_value(metrics, 'wdbc', 'score_error_violations')}\n\n"
        )

        f.write("WDBC profile sweep:\n")
        f.write(
            f"- selected path: {metric_value(metrics, 'wdbc_profile', 'selected_profile')}\n"
            f"- selected total speedup: {metric_value(metrics, 'wdbc_profile', 'selected_total_speedup')}x\n"
            f"- unsafe reference: {metric_value(metrics, 'wdbc_unsafe', 'profile')}\n"
            f"- unsafe decision flips: {metric_value(metrics, 'wdbc_unsafe', 'decision_flips')}\n"
            f"- unsafe score error violations: {metric_value(metrics, 'wdbc_unsafe', 'score_error_violations')}\n"
        )


def write_latex(path: Path, metrics: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w") as f:
        f.write("% Auto-generated FlipGuard final result snippets.\n\n")

        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{Final FlipGuard result summary.}\n")
        f.write("\\label{tab:flipguard-final-summary}\n")
        f.write("\\begin{tabular}{lrrr}\n")
        f.write("\\toprule\n")
        f.write("Experiment & Runs/Samples & Flips & Violations \\\\\n")
        f.write("\\midrule\n")
        f.write(
            f"Boundary stress test & {metric_value(metrics, 'boundary', 'runs')} & "
            f"{metric_value(metrics, 'boundary', 'stable_decision_flips')} & "
            f"{metric_value(metrics, 'output_accuracy', 'score_error_violations')} \\\\\n"
        )
        f.write(
            f"WDBC encrypted inference & {metric_value(metrics, 'wdbc', 'test_samples')} & "
            f"{metric_value(metrics, 'wdbc', 'decision_flips')} & "
            f"{metric_value(metrics, 'wdbc', 'score_error_violations')} \\\\\n"
        )
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n\n")

        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{Speed and profile-selection results.}\n")
        f.write("\\label{tab:flipguard-speed-profile-summary}\n")
        f.write("\\begin{tabular}{lrrr}\n")
        f.write("\\toprule\n")
        f.write("Setting & Eval-only speedup & Total speedup & Decision flips \\\\\n")
        f.write("\\midrule\n")
        f.write(
            f"Repeated speed selected path & "
            f"{metric_value(metrics, 'speed', 'selected_eval_only_speedup_mean')}x & "
            f"{metric_value(metrics, 'speed', 'selected_total_speedup_mean')}x & 0 \\\\\n"
        )
        f.write(
            f"Repeated speed unsafe reference & "
            f"{metric_value(metrics, 'speed_unsafe', 'eval_only_speedup_mean')}x & "
            f"{metric_value(metrics, 'speed_unsafe', 'total_speedup_mean')}x & "
            f"{metric_value(metrics, 'speed_unsafe', 'max_decision_flips')} \\\\\n"
        )
        f.write(
            f"WDBC selected path & "
            f"{metric_value(metrics, 'wdbc_profile', 'selected_eval_only_speedup')}x & "
            f"{metric_value(metrics, 'wdbc_profile', 'selected_total_speedup')}x & 0 \\\\\n"
        )
        f.write(
            f"WDBC unsafe reference & "
            f"{metric_value(metrics, 'wdbc_unsafe', 'eval_only_speedup')}x & "
            f"{metric_value(metrics, 'wdbc_unsafe', 'total_speedup')}x & "
            f"{metric_value(metrics, 'wdbc_unsafe', 'decision_flips')} \\\\\n"
        )
        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")


def main() -> None:
    args = parse_args()
    metrics = build_summary(args)

    output_dir = Path(args.results_root) / "final_research_summary" / args.output_tag

    write_summary_csv(output_dir / "summary.csv", metrics)
    write_readme(output_dir / "README.txt", metrics)
    write_latex(output_dir / "paper_results.tex", metrics)

    print("FlipGuard final research summary")
    print(f"validation_status={metric_value(metrics, 'validation', 'status')}")
    print(f"exported={output_dir}")


if __name__ == "__main__":
    main()
