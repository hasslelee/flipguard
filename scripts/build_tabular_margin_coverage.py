#!/usr/bin/env python3

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


TABULAR_SUMMARY = Path("results/ckks_tabular_suite_summary/current/summary.csv")
OUTPUT_ROOT = Path("results/ckks_tabular_margin_coverage/current")

PLAIN_SCORE_CANDIDATES = [
    "plain_y",
    "plain_score",
    "plain_output",
    "plaintext_y",
    "plaintext_score",
    "y_plain",
    "score_plain",
    "expected_y",
    "expected_score",
]

CKKS_SCORE_CANDIDATES = [
    "ckks_y",
    "ckks_score",
    "ckks_output",
    "decrypted_y",
    "decrypted_score",
    "decoded_y",
    "decoded_score",
    "y_ckks",
    "score_ckks",
    "approx_y",
    "approx_score",
]

ABS_ERROR_CANDIDATES = [
    "abs_y_error",
    "y_abs_error",
    "abs_score_error",
    "score_abs_error",
    "absolute_error",
    "abs_error",
    "error_abs",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build decision-margin coverage tables for FlipGuard tabular inference."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=TABULAR_SUMMARY,
        help="Tabular suite summary CSV.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_ROOT,
        help="Output directory.",
    )
    parser.add_argument(
        "--gamma-min",
        type=float,
        default=1e-3,
        help="Default margin floor used to define V_cert and V_amb.",
    )
    parser.add_argument(
        "--safety-factor",
        type=float,
        default=0.5,
        help="Safety factor alpha for alpha * gamma usage reporting.",
    )
    args = parser.parse_args()

    summary_rows = read_csv(args.summary)
    if not summary_rows:
        raise ValueError(f"empty tabular summary: {args.summary}")

    args.output_root.mkdir(parents=True, exist_ok=True)

    coverage_rows = []
    floor_rows = []
    diagnostics_rows = []

    gamma_floors = [
        0.0,
        1e-6,
        1e-5,
        1e-4,
        args.gamma_min,
        5e-3,
        1e-2,
        5e-2,
    ]
    gamma_floors = sorted(set(gamma_floors))

    for row in summary_rows:
        dataset_id = row["dataset_id"]
        model_id = row["model_id"]

        safe_source = Path(row["safe_source"]) if "safe_source" in row else None
        if safe_source is None:
            safe_source = infer_safe_summary_path(dataset_id, model_id)

        records_path = safe_source.parent / "records.csv"
        model_path = Path("datasets/tabular_suite") / dataset_id / model_id / "model.json"

        if not records_path.exists():
            raise FileNotFoundError(f"missing records.csv for {dataset_id}/{model_id}: {records_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"missing model.json for {dataset_id}/{model_id}: {model_path}")

        records = read_csv(records_path)
        if not records:
            raise ValueError(f"empty records file: {records_path}")

        threshold, threshold_source = load_decision_threshold(model_path, records)
        plain_col = detect_column(records[0], PLAIN_SCORE_CANDIDATES, kind="plain score")
        ckks_col = detect_column(records[0], CKKS_SCORE_CANDIDATES, kind="ckks score", required=False)
        abs_error_col = detect_column(records[0], ABS_ERROR_CANDIDATES, kind="absolute error", required=False)

        margins = []
        errors = []

        for record in records:
            plain_score = parse_float(record[plain_col])
            margin = abs(plain_score - threshold)
            margins.append(margin)

            if abs_error_col:
                errors.append(abs(parse_float(record[abs_error_col])))
            elif ckks_col:
                ckks_score = parse_float(record[ckks_col])
                errors.append(abs(ckks_score - plain_score))

        if not errors:
            # Fall back to summary-level max_y_error when the record schema has no CKKS output or error column.
            errors = [parse_float(row["safe_max_y_error"])]

        coverage_rows.append(
            build_coverage_row(
                row=row,
                records_path=records_path,
                model_path=model_path,
                threshold=threshold,
                threshold_source=threshold_source,
                plain_col=plain_col,
                ckks_col=ckks_col or "",
                abs_error_col=abs_error_col or "",
                margins=margins,
                errors=errors,
                gamma_min=args.gamma_min,
                safety_factor=args.safety_factor,
            )
        )

        for floor in gamma_floors:
            floor_rows.append(
                build_floor_row(
                    row=row,
                    threshold=threshold,
                    margins=margins,
                    errors=errors,
                    gamma_min=floor,
                    safety_factor=args.safety_factor,
                )
            )

        diagnostics_rows.append(
            {
                "dataset_id": dataset_id,
                "model_id": model_id,
                "records_path": str(records_path),
                "model_path": str(model_path),
                "record_count": str(len(records)),
                "threshold": fmt_float(threshold),
                "threshold_source": threshold_source,
                "plain_score_column": plain_col,
                "ckks_score_column": ckks_col or "",
                "abs_error_column": abs_error_col or "",
                "record_columns": ",".join(records[0].keys()),
            }
        )

    write_csv(args.output_root / "coverage.csv", coverage_rows)
    write_csv(args.output_root / "coverage_by_gamma_floor.csv", floor_rows)
    write_csv(args.output_root / "diagnostics.csv", diagnostics_rows)

    write_markdown_table(
        args.output_root / "coverage.md",
        "Tabular decision-margin coverage",
        coverage_rows,
        [
            "dataset",
            "model",
            "samples",
            "gamma_min",
            "v_cert",
            "v_amb",
            "coverage_pct",
            "min_gamma",
            "p5_gamma",
            "p10_gamma",
            "median_gamma",
            "min_cert_gamma",
            "max_y_error",
            "max_usage_vs_alpha_margin",
        ],
    )

    write_markdown_table(
        args.output_root / "coverage_by_gamma_floor.md",
        "Coverage sensitivity by margin floor",
        floor_rows,
        [
            "dataset",
            "model",
            "gamma_min",
            "samples",
            "v_cert",
            "v_amb",
            "coverage_pct",
            "min_cert_gamma",
            "max_y_error",
            "max_usage_vs_alpha_margin",
        ],
    )

    write_table_tex(args.output_root / "coverage_table.tex", coverage_rows)
    write_readme(args.output_root / "README.md", coverage_rows, floor_rows, args.gamma_min, args.safety_factor)

    print(f"wrote {args.output_root / 'coverage.csv'}")
    print(f"wrote {args.output_root / 'coverage.md'}")
    print(f"wrote {args.output_root / 'coverage_by_gamma_floor.csv'}")
    print(f"wrote {args.output_root / 'coverage_by_gamma_floor.md'}")
    print(f"wrote {args.output_root / 'diagnostics.csv'}")
    print(f"wrote {args.output_root / 'coverage_table.tex'}")
    print(f"wrote {args.output_root / 'README.md'}")


def infer_safe_summary_path(dataset_id: str, model_id: str) -> Path:
    return (
        Path("results/ckks_tabular_inference")
        / f"tabular_{dataset_id}_{model_id}_default_rescale_aware"
        / "summary.csv"
    )


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


def load_decision_threshold(model_path: Path, records: List[Dict[str, str]]) -> Tuple[float, str]:
    for candidate in ["threshold", "decision_threshold", "tau"]:
        if candidate in records[0] and records[0][candidate] != "":
            return parse_float(records[0][candidate]), f"records.csv:{candidate}"

    with model_path.open() as f:
        model = json.load(f)

    found = find_key_recursive(
        model,
        [
            "decision_threshold",
            "threshold",
            "output_threshold",
            "classification_threshold",
            "tau",
        ],
    )

    if found is None:
        raise KeyError(
            f"could not find decision threshold in {model_path}; "
            "expected one of decision_threshold, threshold, output_threshold, classification_threshold, tau"
        )

    key, value = found
    return float(value), f"model.json:{key}"


def find_key_recursive(obj, keys: Iterable[str], prefix: str = "") -> Optional[Tuple[str, float]]:
    keys = set(keys)

    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in keys and is_number(value):
                return path, float(value)

            found = find_key_recursive(value, keys, path)
            if found is not None:
                return found

    if isinstance(obj, list):
        for i, value in enumerate(obj):
            found = find_key_recursive(value, keys, f"{prefix}[{i}]")
            if found is not None:
                return found

    return None


def is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def detect_column(
    row: Dict[str, str],
    candidates: List[str],
    *,
    kind: str,
    required: bool = True,
) -> Optional[str]:
    columns = list(row.keys())
    normalized = {col.lower(): col for col in columns}

    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]

    # Heuristic fallback for slightly different column names.
    for col in columns:
        name = col.lower()
        if kind == "plain score":
            if "plain" in name and not any(block in name for block in ["decision", "accuracy", "match"]):
                if any(token in name for token in ["score", "y", "output", "value"]):
                    return col
        elif kind == "ckks score":
            if any(prefix in name for prefix in ["ckks", "decrypted", "decoded", "approx"]):
                if not any(block in name for block in ["decision", "accuracy", "match"]):
                    if any(token in name for token in ["score", "y", "output", "value"]):
                        return col
        elif kind == "absolute error":
            if "error" in name and any(token in name for token in ["abs", "absolute", "y", "score"]):
                if not any(block in name for block in ["usage", "cap", "violation"]):
                    return col

    if required:
        raise KeyError(f"could not detect {kind} column. Available columns: {columns}")

    return None


def build_coverage_row(
    *,
    row: Dict[str, str],
    records_path: Path,
    model_path: Path,
    threshold: float,
    threshold_source: str,
    plain_col: str,
    ckks_col: str,
    abs_error_col: str,
    margins: List[float],
    errors: List[float],
    gamma_min: float,
    safety_factor: float,
) -> Dict[str, str]:
    v_cert_margins = [m for m in margins if m >= gamma_min]
    v_amb = len(margins) - len(v_cert_margins)

    min_cert_gamma = min(v_cert_margins) if v_cert_margins else math.nan
    max_y_error = max(errors) if errors else math.nan
    usage = safe_div(max_y_error, safety_factor * min_cert_gamma)

    return {
        "dataset_id": row["dataset_id"],
        "dataset": row["dataset_name"],
        "model_id": row["model_id"],
        "model": model_label(row["model_id"]),
        "samples": str(len(margins)),
        "gamma_min": fmt_sci(gamma_min),
        "v_cert": str(len(v_cert_margins)),
        "v_amb": str(v_amb),
        "coverage_pct": fmt_pct(safe_div(len(v_cert_margins), len(margins)) * 100.0),
        "threshold": fmt_float(threshold),
        "threshold_source": threshold_source,
        "min_gamma": fmt_sci(min(margins)),
        "p1_gamma": fmt_sci(percentile(margins, 0.01)),
        "p5_gamma": fmt_sci(percentile(margins, 0.05)),
        "p10_gamma": fmt_sci(percentile(margins, 0.10)),
        "median_gamma": fmt_sci(percentile(margins, 0.50)),
        "p90_gamma": fmt_sci(percentile(margins, 0.90)),
        "min_cert_gamma": fmt_sci(min_cert_gamma),
        "max_y_error": fmt_sci(max_y_error),
        "p95_y_error": fmt_sci(percentile(errors, 0.95)),
        "max_usage_vs_alpha_margin": fmt_float(usage),
        "safety_factor": fmt_float(safety_factor),
        "plain_score_column": plain_col,
        "ckks_score_column": ckks_col,
        "abs_error_column": abs_error_col,
        "records_path": str(records_path),
        "model_path": str(model_path),
    }


def build_floor_row(
    *,
    row: Dict[str, str],
    threshold: float,
    margins: List[float],
    errors: List[float],
    gamma_min: float,
    safety_factor: float,
) -> Dict[str, str]:
    v_cert_margins = [m for m in margins if m >= gamma_min]
    v_amb = len(margins) - len(v_cert_margins)

    min_cert_gamma = min(v_cert_margins) if v_cert_margins else math.nan
    max_y_error = max(errors) if errors else math.nan
    usage = safe_div(max_y_error, safety_factor * min_cert_gamma)

    return {
        "dataset_id": row["dataset_id"],
        "dataset": row["dataset_name"],
        "model_id": row["model_id"],
        "model": model_label(row["model_id"]),
        "gamma_min": fmt_sci(gamma_min),
        "samples": str(len(margins)),
        "v_cert": str(len(v_cert_margins)),
        "v_amb": str(v_amb),
        "coverage_pct": fmt_pct(safe_div(len(v_cert_margins), len(margins)) * 100.0),
        "threshold": fmt_float(threshold),
        "min_cert_gamma": fmt_sci(min_cert_gamma),
        "max_y_error": fmt_sci(max_y_error),
        "max_usage_vs_alpha_margin": fmt_float(usage),
        "safety_factor": fmt_float(safety_factor),
    }


def percentile(values: List[float], q: float) -> float:
    if not values:
        return math.nan

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]

    weight = pos - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def safe_div(num: float, den: float) -> float:
    if den == 0.0 or math.isnan(den):
        return math.inf
    return num / den


def parse_float(value: str) -> float:
    return float(value)


def fmt_float(value: float) -> str:
    if math.isinf(value):
        return "inf"
    if math.isnan(value):
        return "nan"
    return f"{value:.10f}"


def fmt_sci(value: float) -> str:
    if math.isinf(value):
        return "inf"
    if math.isnan(value):
        return "nan"
    return f"{value:.6e}"


def fmt_pct(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return f"{value:.2f}"


def model_label(model_id: str) -> str:
    labels = {
        "linear_poly3": "Linear+Poly3",
        "mlp_square_linear_score": "MLP-square",
    }
    return labels.get(model_id, model_id)


def write_markdown_table(
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


def write_table_tex(path: Path, rows: List[Dict[str, str]]) -> None:
    lines = []
    lines.append(r"\begin{tabular}{llrrrrrr}")
    lines.append(r"\toprule")
    lines.append(
        r"Dataset & Model & Samples & $V_{\mathrm{cert}}$ & $V_{\mathrm{amb}}$ & "
        r"Coverage & p5 $\gamma$ & Max usage \\"
    )
    lines.append(r"\midrule")

    for row in rows:
        dataset = row["dataset_id"].replace("_", r"\_")
        model = row["model_id"].replace("_", r"\_")
        lines.append(
            f"{dataset} & {model} & {row['samples']} & {row['v_cert']} & {row['v_amb']} & "
            f"{row['coverage_pct']}\\% & {row['p5_gamma']} & {row['max_usage_vs_alpha_margin']} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(
    path: Path,
    coverage_rows: List[Dict[str, str]],
    floor_rows: List[Dict[str, str]],
    gamma_min: float,
    safety_factor: float,
) -> None:
    total = len(coverage_rows)
    total_samples = sum(int(row["samples"]) for row in coverage_rows)
    total_cert = sum(int(row["v_cert"]) for row in coverage_rows)
    total_amb = sum(int(row["v_amb"]) for row in coverage_rows)

    min_coverage = min(float(row["coverage_pct"]) for row in coverage_rows)
    max_usage = max(
        float(row["max_usage_vs_alpha_margin"])
        for row in coverage_rows
        if row["max_usage_vs_alpha_margin"] not in ["inf", "nan"]
    )

    text = f"""FlipGuard tabular decision-margin coverage

This directory summarizes how many evaluated validation records are certifiable under a chosen decision-margin floor.

Definitions:
- gamma(x) = |f(x) - tau|
- V_cert = {{ x : gamma(x) >= gamma_min }}
- V_amb  = {{ x : gamma(x) < gamma_min }}
- epsilon_bud(x) = alpha * gamma(x)

Parameters:
- gamma_min: {gamma_min:.6e}
- safety factor alpha: {safety_factor:.6f}

Summary:
- workloads: {total}
- total evaluated samples: {total_samples}
- total V_cert samples: {total_cert}
- total V_amb samples: {total_amb}
- minimum workload coverage: {min_coverage:.2f}%
- maximum observed max_y_error / (alpha * min_cert_gamma): {max_usage:.10f}

Interpretation:
Coverage is reported separately from the SAFE/REJECTED decision. A workload can have zero observed decision flips while still having a non-empty V_amb set near the decision threshold. The certified claim should be stated over V_cert under the configured gamma_min and safety factor alpha, not over the entire input space.
"""
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
