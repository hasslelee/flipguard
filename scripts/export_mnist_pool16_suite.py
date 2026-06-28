#!/usr/bin/env python3

import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
from sklearn.datasets import fetch_openml
from sklearn.model_selection import train_test_split


def load_exporter_module():
    exporter_path = Path(__file__).with_name("export_tabular_suite.py")
    spec = importlib.util.spec_from_file_location("tabular_suite_exporter", exporter_path)
    module = importlib.util.module_from_spec(spec)

    if spec.loader is None:
        raise RuntimeError("failed to load export_tabular_suite.py")

    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export a pooled MNIST benchmark for FlipGuard CKKS tabular inference."
    )
    parser.add_argument(
        "--output-root",
        default="datasets/tabular_suite",
        help="Output root directory.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=2500,
        help="Maximum MNIST samples to use before train/test split.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.20,
        help="Test split ratio.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Deterministic seed.",
    )
    parser.add_argument(
        "--hidden-units",
        type=int,
        default=4,
        help="Hidden units for square-activation MLP.",
    )
    parser.add_argument(
        "--max-scaled-logit",
        type=float,
        default=1.0,
        help="Maximum absolute scaled logit target.",
    )
    parser.add_argument(
        "--mlp-epochs",
        type=int,
        default=2500,
        help="Training epochs for square-activation MLP.",
    )
    return parser.parse_args()


def load_mnist_pool16(max_samples, random_state):
    dataset = fetch_openml("mnist_784", version=1, as_frame=False, parser="auto")

    x = dataset.data.astype(np.float64) / 255.0
    y_digits = dataset.target.astype(int)
    y = (y_digits % 2 == 0).astype(np.int64)

    rng = np.random.default_rng(random_state)

    if max_samples > 0 and max_samples < x.shape[0]:
        indices = rng.choice(x.shape[0], size=max_samples, replace=False)
        x = x[indices]
        y = y[indices]

    images = x.reshape((-1, 28, 28))
    pooled = images.reshape((-1, 4, 7, 4, 7)).mean(axis=(2, 4))
    features = pooled.reshape((-1, 16))

    feature_names = [f"pool4x4_{i}" for i in range(16)]

    return features, y, feature_names


def derive_mlp_linear_score(src_dir, dst_dir):
    dst_dir.mkdir(parents=True, exist_ok=True)

    model = json.loads((src_dir / "model.json").read_text(encoding="utf-8"))
    model["model_id"] = "mlp_square_linear_score"
    model["model_type"] = "mlp_square_linear_score"
    model["polynomial_score"] = {
        "formula": "0.5 + 0.197*z",
        "decision_threshold": 0.5,
    }

    rows = []
    with (src_dir / "test.csv").open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        for row in reader:
            z = float(row["scaled_logit"])
            score = 0.5 + 0.197 * z
            row["polynomial_score"] = f"{score:.12f}"
            row["plaintext_decision"] = str(score >= 0.5)
            rows.append(row)

    raw_decisions = [float(row["scaled_logit"]) >= 0.0 for row in rows]
    score_decisions = [row["plaintext_decision"].lower() == "true" for row in rows]
    match_count = sum(1 for a, b in zip(raw_decisions, score_decisions) if a == b)
    match_rate = match_count / len(rows) if rows else 0.0

    metrics = {}
    with (src_dir / "metrics.csv").open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metrics[row["metric"]] = row["value"]

    metrics["polynomial_decision_match_rate"] = f"{match_rate:.12f}"

    (dst_dir / "model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")

    with (dst_dir / "test.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with (dst_dir / "metrics.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key in sorted(metrics.keys()):
            writer.writerow([key, metrics[key]])


def main():
    args = parse_args()
    exporter = load_exporter_module()

    dataset_id = "mnist_pool16"
    dataset_name = "MNIST pooled 4x4 even-vs-odd classification"

    x, y, feature_names = load_mnist_pool16(args.max_samples, args.random_state)

    x_train_raw, x_test_raw, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    x_train_std, x_test_std, mean, std = exporter.standardize_train_test(
        x_train_raw,
        x_test_raw,
    )

    selected_indices = list(range(x_train_std.shape[1]))
    x_train_selected = x_train_std[:, selected_indices]
    x_test_selected = x_test_std[:, selected_indices]

    dataset_root = Path(args.output_root) / dataset_id

    linear_params = exporter.train_linear_model(x_train_selected, y_train)
    linear_train_logits = exporter.linear_logits(x_train_selected, linear_params)
    linear_test_logits = exporter.linear_logits(x_test_selected, linear_params)
    linear_scale = exporter.compute_logit_scale(linear_train_logits, args.max_scaled_logit)
    linear_scaled_params = exporter.scale_linear_params(linear_params, linear_scale)
    linear_scaled_test_logits = linear_test_logits * linear_scale

    exporter.export_model_artifacts(
        dataset_root / "linear_poly3",
        dataset_id,
        dataset_name,
        "linear_poly3",
        "linear_poly3",
        feature_names,
        selected_indices,
        mean,
        std,
        linear_params,
        linear_scaled_params,
        linear_test_logits,
        linear_scaled_test_logits,
        x_test_selected,
        y_test,
        args.random_state,
        args.test_size,
        args.max_scaled_logit,
        len(y_train),
    )

    mlp_params = exporter.train_square_mlp(
        x_train_selected,
        y_train,
        args.hidden_units,
        args.mlp_epochs,
        args.random_state,
    )
    mlp_train_logits = exporter.square_mlp_logits(x_train_selected, mlp_params)
    mlp_test_logits = exporter.square_mlp_logits(x_test_selected, mlp_params)
    mlp_scale = exporter.compute_logit_scale(mlp_train_logits, args.max_scaled_logit)
    mlp_scaled_params = exporter.scale_square_mlp_params(mlp_params, mlp_scale)
    mlp_scaled_test_logits = mlp_test_logits * mlp_scale

    exporter.export_model_artifacts(
        dataset_root / "mlp_square_poly3",
        dataset_id,
        dataset_name,
        "mlp_square_poly3",
        "mlp_square_poly3",
        feature_names,
        selected_indices,
        mean,
        std,
        mlp_params,
        mlp_scaled_params,
        mlp_test_logits,
        mlp_scaled_test_logits,
        x_test_selected,
        y_test,
        args.random_state,
        args.test_size,
        args.max_scaled_logit,
        len(y_train),
    )

    derive_mlp_linear_score(
        dataset_root / "mlp_square_poly3",
        dataset_root / "mlp_square_linear_score",
    )

    print("FlipGuard MNIST pooled benchmark export")
    print(f"dataset_id={dataset_id}")
    print(f"output_root={dataset_root}")
    print(f"train_samples={len(y_train)} test_samples={len(y_test)}")


if __name__ == "__main__":
    main()
