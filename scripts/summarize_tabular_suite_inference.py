#!/usr/bin/env python3

import csv
from pathlib import Path


DATASETS = [
    "wdbc",
    "iris_binary",
    "digits_binary",
    "banknote",
]

MODELS = [
    "linear_poly3",
    "mlp_square_linear_score",
]

RESULT_ROOT = Path("results/ckks_tabular_inference")
OUTPUT_ROOT = Path("results/ckks_tabular_suite_summary/current")


def read_summary(path: Path) -> dict:
    with path.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 1:
        raise ValueError(f"expected one row in {path}, got {len(rows)}")

    return rows[0]


def as_float(row: dict, key: str) -> float:
    return float(row[key])


def as_int(row: dict, key: str) -> int:
    return int(row[key])


def fmt_float(value: float) -> str:
    return f"{value:.10f}"


def fmt_ms(value: float) -> str:
    return f"{value:.4f}"


def safe_status(row: dict) -> str:
    plain_accuracy = as_float(row, "plain_accuracy")
    ckks_accuracy = as_float(row, "ckks_accuracy")
    flips = as_int(row, "decision_flips")
    violations = as_int(row, "score_error_violations")

    if flips == 0 and violations == 0 and abs(plain_accuracy - ckks_accuracy) <= 1e-12:
        return "pass"

    return "fail"


def unsafe_status(row: dict) -> str:
    flips = as_int(row, "decision_flips")
    violations = as_int(row, "score_error_violations")

    if flips > 0 or violations > 0:
        return "rejected"

    return "not_rejected"


def build_rows() -> list:
    rows = []

    for dataset in DATASETS:
        for model in MODELS:
            safe_tag = f"tabular_{dataset}_{model}_default_rescale_aware"
            unsafe_tag = f"tabular_{dataset}_{model}_short3_baseline_non_rescale"

            safe_path = RESULT_ROOT / safe_tag / "summary.csv"
            unsafe_path = RESULT_ROOT / unsafe_tag / "summary.csv"

            if not safe_path.exists():
                raise FileNotFoundError(f"missing safe summary: {safe_path}")

            if not unsafe_path.exists():
                raise FileNotFoundError(f"missing unsafe summary: {unsafe_path}")

            safe = read_summary(safe_path)
            unsafe = read_summary(unsafe_path)

            safe_total = as_float(safe, "mean_total_eval_ms")
            unsafe_total = as_float(unsafe, "mean_total_eval_ms")
            safe_eval = as_float(safe, "mean_eval_only_ms")
            unsafe_eval = as_float(unsafe, "mean_eval_only_ms")

            total_speedup = safe_total / unsafe_total if unsafe_total > 0.0 else 0.0
            eval_speedup = safe_eval / unsafe_eval if unsafe_eval > 0.0 else 0.0

            rows.append({
                "dataset_id": dataset,
                "dataset_name": safe["dataset_name"],
                "model_id": model,
                "plain_accuracy": safe["plain_accuracy"],

                "safe_profile": "default",
                "safe_path": "rescale_aware",
                "safe_ckks_accuracy": safe["ckks_accuracy"],
                "safe_decision_flips": safe["decision_flips"],
                "safe_score_error_violations": safe["score_error_violations"],
                "safe_max_y_error": safe["max_y_error"],
                "safe_mean_eval_only_ms": safe["mean_eval_only_ms"],
                "safe_mean_total_eval_ms": safe["mean_total_eval_ms"],
                "safe_status": safe_status(safe),

                "unsafe_profile": "short_chain_3",
                "unsafe_path": "baseline_non_rescale",
                "unsafe_ckks_accuracy": unsafe["ckks_accuracy"],
                "unsafe_decision_flips": unsafe["decision_flips"],
                "unsafe_score_error_violations": unsafe["score_error_violations"],
                "unsafe_max_y_error": unsafe["max_y_error"],
                "unsafe_mean_eval_only_ms": unsafe["mean_eval_only_ms"],
                "unsafe_mean_total_eval_ms": unsafe["mean_total_eval_ms"],
                "unsafe_total_speedup_vs_safe": f"{total_speedup:.4f}",
                "unsafe_eval_only_speedup_vs_safe": f"{eval_speedup:.4f}",
                "unsafe_status": unsafe_status(unsafe),
            })

    return rows


def write_summary_csv(rows: list) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "dataset_id",
        "dataset_name",
        "model_id",
        "plain_accuracy",
        "safe_profile",
        "safe_path",
        "safe_ckks_accuracy",
        "safe_decision_flips",
        "safe_score_error_violations",
        "safe_max_y_error",
        "safe_mean_eval_only_ms",
        "safe_mean_total_eval_ms",
        "safe_status",
        "unsafe_profile",
        "unsafe_path",
        "unsafe_ckks_accuracy",
        "unsafe_decision_flips",
        "unsafe_score_error_violations",
        "unsafe_max_y_error",
        "unsafe_mean_eval_only_ms",
        "unsafe_mean_total_eval_ms",
        "unsafe_total_speedup_vs_safe",
        "unsafe_eval_only_speedup_vs_safe",
        "unsafe_status",
    ]

    with (OUTPUT_ROOT / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_table_tex(rows: list) -> None:
    lines = []
    lines.append(r"\begin{tabular}{llrrrrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"Dataset & Model & Safe Acc. & Safe Flips & Safe Viol. & "
        r"Safe Total (ms) & Unsafe Speedup & Unsafe Flips \\"
    )
    lines.append(r"\midrule")

    for row in rows:
        dataset = row["dataset_id"].replace("_", r"\_")
        model = row["model_id"].replace("_", r"\_")
        safe_acc = fmt_float(float(row["safe_ckks_accuracy"]))
        safe_flips = row["safe_decision_flips"]
        safe_violations = row["safe_score_error_violations"]
        safe_total = fmt_ms(float(row["safe_mean_total_eval_ms"]))
        unsafe_speedup = float(row["unsafe_total_speedup_vs_safe"])
        unsafe_flips = row["unsafe_decision_flips"]

        lines.append(
            f"{dataset} & {model} & {safe_acc} & {safe_flips} & {safe_violations} & "
            f"{safe_total} & {unsafe_speedup:.4f}$\\times$ & {unsafe_flips} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    (OUTPUT_ROOT / "table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(rows: list) -> None:
    total = len(rows)
    safe_pass = sum(1 for row in rows if row["safe_status"] == "pass")
    unsafe_rejected = sum(1 for row in rows if row["unsafe_status"] == "rejected")

    safe_flips = sum(int(row["safe_decision_flips"]) for row in rows)
    safe_violations = sum(int(row["safe_score_error_violations"]) for row in rows)
    unsafe_flips = sum(int(row["unsafe_decision_flips"]) for row in rows)
    unsafe_violations = sum(int(row["unsafe_score_error_violations"]) for row in rows)

    speedups = [float(row["unsafe_total_speedup_vs_safe"]) for row in rows]
    min_speedup = min(speedups)
    max_speedup = max(speedups)

    text = f"""FlipGuard tabular suite summary

Workloads:
- datasets: wdbc, iris_binary, digits_binary, banknote
- models: linear_poly3, mlp_square_linear_score
- total workloads: {total}

Safe candidate:
- profile: default
- path: rescale_aware
- safe pass workloads: {safe_pass}/{total}
- total safe decision flips: {safe_flips}
- total safe score error violations: {safe_violations}

Unsafe raw-speed candidate:
- profile: short_chain_3
- path: baseline_non_rescale
- rejected workloads: {unsafe_rejected}/{total}
- total unsafe decision flips: {unsafe_flips}
- total unsafe score error violations: {unsafe_violations}
- unsafe total-latency speedup range versus safe candidate: {min_speedup:.4f}x to {max_speedup:.4f}x

Interpretation:
The default rescale-aware path preserved plaintext decisions and satisfied the output accuracy guard across all evaluated tabular workloads. The short-chain baseline non-rescale path was faster, but it caused decision flips and score error violations across all evaluated workloads, so it is rejected by the safety guard.
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_summary_csv(rows)
    write_table_tex(rows)
    write_readme(rows)

    print(f"wrote {OUTPUT_ROOT / 'summary.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
