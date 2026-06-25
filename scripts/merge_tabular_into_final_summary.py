#!/usr/bin/env python3

import csv
from pathlib import Path


FINAL_DIR = Path("results/final_research_summary/current")
FINAL_SUMMARY = FINAL_DIR / "summary.csv"
TABULAR_SUMMARY = Path("results/ckks_tabular_suite_summary/current/summary.csv")


def read_rows(path):
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "metric", "value"])
        writer.writeheader()
        writer.writerows(rows)


def add_metric(rows, section, metric, value):
    rows.append({
        "section": section,
        "metric": metric,
        "value": str(value),
    })


def metric_value(rows, section, metric):
    for row in rows:
        if row["section"] == section and row["metric"] == metric:
            return row["value"]
    return ""


def summarize_tabular(rows):
    datasets = sorted({row["dataset_id"] for row in rows})
    models = sorted({row["model_id"] for row in rows})

    safe_pass = sum(1 for row in rows if row["safe_status"] == "pass")
    safe_flips = sum(int(row["safe_decision_flips"]) for row in rows)
    safe_violations = sum(int(row["safe_score_error_violations"]) for row in rows)
    safe_max_error = max(float(row["safe_max_y_error"]) for row in rows)

    unsafe_rejected = sum(1 for row in rows if row["unsafe_status"] == "rejected")
    unsafe_flips = sum(int(row["unsafe_decision_flips"]) for row in rows)
    unsafe_violations = sum(int(row["unsafe_score_error_violations"]) for row in rows)

    total_speedups = [float(row["unsafe_total_speedup_vs_safe"]) for row in rows]
    eval_speedups = [float(row["unsafe_eval_only_speedup_vs_safe"]) for row in rows]

    return {
        "workloads": len(rows),
        "datasets": len(datasets),
        "models": len(models),
        "safe_pass": safe_pass,
        "safe_decision_flips": safe_flips,
        "safe_score_error_violations": safe_violations,
        "safe_max_y_error": f"{safe_max_error:.10f}",
        "unsafe_rejected": unsafe_rejected,
        "unsafe_decision_flips": unsafe_flips,
        "unsafe_score_error_violations": unsafe_violations,
        "unsafe_total_speedup_min": f"{min(total_speedups):.4f}",
        "unsafe_total_speedup_max": f"{max(total_speedups):.4f}",
        "unsafe_eval_only_speedup_min": f"{min(eval_speedups):.4f}",
        "unsafe_eval_only_speedup_max": f"{max(eval_speedups):.4f}",
    }


def write_readme(rows):
    text = f"""FlipGuard final research result summary

Validation:
- status: {metric_value(rows, "validation", "status")}

Boundary stress test:
- total runs: {metric_value(rows, "boundary", "runs")}
- stable runs: {metric_value(rows, "boundary", "stable_runs")}
- stable decision flips: {metric_value(rows, "boundary", "stable_decision_flips")}
- output accuracy violations: {metric_value(rows, "output_accuracy", "score_error_violations")}

Repeated speed benchmark:
- selected safe path: {metric_value(rows, "speed", "selected_profile")}
- selected total speedup: {metric_value(rows, "speed", "selected_total_speedup_mean")}x
- selected evaluation-only speedup: {metric_value(rows, "speed", "selected_eval_only_speedup_mean")}x

WDBC public dataset:
- test samples: {metric_value(rows, "wdbc", "test_samples")}
- plaintext accuracy: {metric_value(rows, "wdbc", "plain_accuracy")}
- encrypted accuracy: {metric_value(rows, "wdbc", "ckks_accuracy")}
- decision flips: {metric_value(rows, "wdbc", "decision_flips")}
- score error violations: {metric_value(rows, "wdbc", "score_error_violations")}

Tabular multi-dataset suite:
- workloads: {metric_value(rows, "tabular_suite", "workloads")}
- datasets: {metric_value(rows, "tabular_suite", "datasets")}
- model families: {metric_value(rows, "tabular_suite", "models")}
- safe pass workloads: {metric_value(rows, "tabular_suite", "safe_pass")}
- safe decision flips: {metric_value(rows, "tabular_suite", "safe_decision_flips")}
- safe score error violations: {metric_value(rows, "tabular_suite", "safe_score_error_violations")}
- rejected unsafe workloads: {metric_value(rows, "tabular_suite", "unsafe_rejected")}
- unsafe decision flips: {metric_value(rows, "tabular_suite", "unsafe_decision_flips")}
- unsafe score error violations: {metric_value(rows, "tabular_suite", "unsafe_score_error_violations")}
- unsafe total-latency speedup range: {metric_value(rows, "tabular_suite", "unsafe_total_speedup_min")}x to {metric_value(rows, "tabular_suite", "unsafe_total_speedup_max")}x

Interpretation:
The safe path preserved plaintext decisions and satisfied the output accuracy guard across all evaluated workloads. The faster unsafe path reduced latency, but it caused decision flips and output accuracy violations, so it was rejected by the safety guard.
"""

    (FINAL_DIR / "README.txt").write_text(text, encoding="utf-8")


def write_latex(rows):
    text = r"""\begin{tabular}{llr}
\toprule
Category & Metric & Value \\
\midrule
Boundary & Total CKKS runs & """ + metric_value(rows, "boundary", "runs") + r""" \\
Boundary & Stable decision flips & """ + metric_value(rows, "boundary", "stable_decision_flips") + r""" \\
Boundary & Output accuracy violations & """ + metric_value(rows, "output_accuracy", "score_error_violations") + r""" \\
Speed & Selected total speedup & """ + metric_value(rows, "speed", "selected_total_speedup_mean") + r"""$\times$ \\
WDBC & Encrypted accuracy & """ + metric_value(rows, "wdbc", "ckks_accuracy") + r""" \\
WDBC & Decision flips & """ + metric_value(rows, "wdbc", "decision_flips") + r""" \\
Tabular suite & Workloads & """ + metric_value(rows, "tabular_suite", "workloads") + r""" \\
Tabular suite & Safe decision flips & """ + metric_value(rows, "tabular_suite", "safe_decision_flips") + r""" \\
Tabular suite & Safe score error violations & """ + metric_value(rows, "tabular_suite", "safe_score_error_violations") + r""" \\
Tabular suite & Rejected unsafe workloads & """ + metric_value(rows, "tabular_suite", "unsafe_rejected") + r""" \\
Tabular suite & Unsafe decision flips & """ + metric_value(rows, "tabular_suite", "unsafe_decision_flips") + r""" \\
Tabular suite & Unsafe total speedup range & """ + metric_value(rows, "tabular_suite", "unsafe_total_speedup_min") + r"""--""" + metric_value(rows, "tabular_suite", "unsafe_total_speedup_max") + r"""$\times$ \\
\bottomrule
\end{tabular}
"""

    (FINAL_DIR / "paper_results.tex").write_text(text, encoding="utf-8")


def main():
    final_rows = read_rows(FINAL_SUMMARY)
    tabular_rows = read_rows(TABULAR_SUMMARY)
    tabular = summarize_tabular(tabular_rows)

    final_rows = [
        row for row in final_rows
        if row["section"] != "tabular_suite"
    ]

    add_metric(final_rows, "tabular_suite", "workloads", tabular["workloads"])
    add_metric(final_rows, "tabular_suite", "datasets", tabular["datasets"])
    add_metric(final_rows, "tabular_suite", "models", tabular["models"])
    add_metric(final_rows, "tabular_suite", "safe_profile", "default+rescale_aware")
    add_metric(final_rows, "tabular_suite", "safe_pass", tabular["safe_pass"])
    add_metric(final_rows, "tabular_suite", "safe_decision_flips", tabular["safe_decision_flips"])
    add_metric(final_rows, "tabular_suite", "safe_score_error_violations", tabular["safe_score_error_violations"])
    add_metric(final_rows, "tabular_suite", "safe_max_y_error", tabular["safe_max_y_error"])
    add_metric(final_rows, "tabular_suite", "unsafe_profile", "short_chain_3+baseline_non_rescale")
    add_metric(final_rows, "tabular_suite", "unsafe_rejected", tabular["unsafe_rejected"])
    add_metric(final_rows, "tabular_suite", "unsafe_decision_flips", tabular["unsafe_decision_flips"])
    add_metric(final_rows, "tabular_suite", "unsafe_score_error_violations", tabular["unsafe_score_error_violations"])
    add_metric(final_rows, "tabular_suite", "unsafe_total_speedup_min", tabular["unsafe_total_speedup_min"])
    add_metric(final_rows, "tabular_suite", "unsafe_total_speedup_max", tabular["unsafe_total_speedup_max"])
    add_metric(final_rows, "tabular_suite", "unsafe_eval_only_speedup_min", tabular["unsafe_eval_only_speedup_min"])
    add_metric(final_rows, "tabular_suite", "unsafe_eval_only_speedup_max", tabular["unsafe_eval_only_speedup_max"])

    write_rows(FINAL_SUMMARY, final_rows)
    write_readme(final_rows)
    write_latex(final_rows)

    print(f"updated {FINAL_SUMMARY}")
    print(f"updated {FINAL_DIR / 'README.txt'}")
    print(f"updated {FINAL_DIR / 'paper_results.tex'}")


if __name__ == "__main__":
    main()
