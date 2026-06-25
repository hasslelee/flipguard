#!/usr/bin/env python3

import csv
import json
from pathlib import Path


DATASETS = [
    "wdbc",
    "iris_binary",
    "digits_binary",
    "banknote",
]


def format_float(value: float) -> str:
    return f"{float(value):.12f}"


def derive_dataset(dataset_id: str) -> None:
    src_dir = Path("datasets/tabular_suite") / dataset_id / "mlp_square_poly3"
    dst_dir = Path("datasets/tabular_suite") / dataset_id / "mlp_square_linear_score"

    if not src_dir.exists():
        raise FileNotFoundError(f"missing source directory: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    model = json.loads((src_dir / "model.json").read_text(encoding="utf-8"))
    model["model_id"] = "mlp_square_linear_score"
    model["model_type"] = "mlp_square_linear_score"
    model["polynomial_score"] = {
        "formula": "0.5 + 0.197*z",
        "decision_threshold": 0.5,
    }

    test_rows = []
    with (src_dir / "test.csv").open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        for row in reader:
            z = float(row["scaled_logit"])
            score = 0.5 + 0.197 * z
            row["polynomial_score"] = format_float(score)
            row["plaintext_decision"] = str(score >= 0.5)
            test_rows.append(row)

    raw_decisions = [float(row["scaled_logit"]) >= 0.0 for row in test_rows]
    score_decisions = [row["plaintext_decision"].lower() == "true" for row in test_rows]
    match_count = sum(1 for a, b in zip(raw_decisions, score_decisions) if a == b)
    match_rate = match_count / len(test_rows) if test_rows else 0.0

    metrics = {}
    with (src_dir / "metrics.csv").open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics[row["metric"]] = row["value"]

    metrics["polynomial_decision_match_rate"] = format_float(match_rate)

    (dst_dir / "model.json").write_text(
        json.dumps(model, indent=2),
        encoding="utf-8",
    )

    with (dst_dir / "test.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_rows)

    with (dst_dir / "metrics.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key in sorted(metrics.keys()):
            writer.writerow([key, metrics[key]])

    print(f"derived {dst_dir}")


def main() -> None:
    for dataset_id in DATASETS:
        derive_dataset(dataset_id)


if __name__ == "__main__":
    main()
