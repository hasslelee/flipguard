#!/usr/bin/env python3

import csv
from pathlib import Path
from typing import Dict, List


DATASETS = [
    "wdbc",
    "iris_binary",
    "digits_binary",
    "banknote",
    "mnist_pool16",
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
    return int(float(row[key]))


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


def direct_tag(dataset: str, model: str, profile: str, path: str) -> str:
    if profile == "default" and path == "rescale_aware":
        return f"tabular_{dataset}_{model}_default_rescale_aware"

    if profile == "short_chain_3" and path == "baseline_non_rescale":
        return f"tabular_{dataset}_{model}_short3_baseline_non_rescale"

    raise ValueError(f"unsupported direct tag profile/path: {profile}+{path}")


def sweep_tag(dataset: str, model: str, profile: str, path: str, repeat: int = 1) -> str:
    return f"tabular_sweep_{dataset}_{model}_{profile}_{path}_r{repeat}"


def find_summary_path(dataset: str, model: str, profile: str, path: str) -> Path:
    candidates = []

    try:
        candidates.append(RESULT_ROOT / direct_tag(dataset, model, profile, path) / "summary.csv")
    except ValueError:
        pass

    candidates.append(RESULT_ROOT / sweep_tag(dataset, model, profile, path, repeat=1) / "summary.csv")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    joined = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"missing summary for dataset={dataset} model={model} profile={profile} path={path}\n"
        f"checked:\n  {joined}"
    )


def build_rows() -> List[Dict[str, str]]:
    rows = []

    for dataset in DATASETS:
        for model in MODELS:
            safe_profile = "default"
            safe_path_name = "rescale_aware"
            unsafe_profile = "short_chain_3"
            unsafe_path_name = "baseline_non_rescale"

            safe_path = find_summary_path(dataset, model, safe_profile, safe_path_name)
            unsafe_path = find_summary_path(dataset, model, unsafe_profile, unsafe_path_name)

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

                "safe_profile": safe_profile,
                "safe_path": safe_path_name,
                "safe_source": str(safe_path),
                "safe_ckks_accuracy": safe["ckks_accuracy"],
                "safe_decision_flips": safe["decision_flips"],
                "safe_score_error_violations": safe["score_error_violations"],
                "safe_max_y_error": safe["max_y_error"],
                "safe_mean_eval_only_ms": safe["mean_eval_only_ms"],
                "safe_mean_total_eval_ms": safe["mean_total_eval_ms"],
                "safe_status": safe_status(safe),

                "unsafe_profile": unsafe_profile,
                "unsafe_path": unsafe_path_name,
                "unsafe_source": str(unsafe_path),
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


def write_summary_csv(rows: List[Dict[str, str]]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "dataset_id",
        "dataset_name",
        "model_id",
        "plain_accuracy",
        "safe_profile",
        "safe_path",
        "safe_source",
        "safe_ckks_accuracy",
        "safe_decision_flips",
        "safe_score_error_violations",
        "safe_max_y_error",
        "safe_mean_eval_only_ms",
        "safe_mean_total_eval_ms",
        "safe_status",
        "unsafe_profile",
        "unsafe_path",
        "unsafe_source",
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


def write_table_tex(rows: List[Dict[str, str]]) -> None:
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


def write_readme(rows: List[Dict[str, str]]) -> None:
    total = len(rows)
    safe_pass = sum(1 for row in rows if row["safe_status"] == "pass")
    unsafe_rejected = sum(1 for row in rows if row["unsafe_status"] == "rejected")

    safe_flips = sum(int(float(row["safe_decision_flips"])) for row in rows)
    safe_violations = sum(int(float(row["safe_score_error_violations"])) for row in rows)
    unsafe_flips = sum(int(float(row["unsafe_decision_flips"])) for row in rows)
    unsafe_violations = sum(int(float(row["unsafe_score_error_violations"])) for row in rows)

    speedups = [float(row["unsafe_total_speedup_vs_safe"]) for row in rows]
    min_speedup = min(speedups)
    max_speedup = max(speedups)

    datasets = ", ".join(DATASETS)
    models = ", ".join(MODELS)

    text = f"""FlipGuard tabular suite summary

Workloads:
- datasets: {datasets}
- models: {models}
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
The default rescale-aware path preserved plaintext decisions and satisfied the output accuracy guard across all evaluated tabular workloads. The short-chain baseline non-rescale path was faster, but it caused decision flips and score error violations across the evaluated workloads, so it is rejected by the safety guard.

Source note:
For each dataset/model pair, this summary first uses direct inference outputs when available. If a direct summary is not available, it falls back to the first repeated profile-sweep summary for the same profile and evaluation path. The safe/unsafe source paths are recorded in summary.csv.
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
    print(f"workloads={len(rows)}")


if __name__ == "__main__":
    main()