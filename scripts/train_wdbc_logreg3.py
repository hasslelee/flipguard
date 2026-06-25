#!/usr/bin/env python3

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and export a compact 3-feature WDBC logistic model for CKKS evaluation."
    )
    parser.add_argument(
        "--output-dir",
        default="datasets/wdbc_logreg3",
        help="Output directory for model and test data artifacts.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.30,
        help="Test split ratio.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Deterministic train/test split seed.",
    )
    parser.add_argument(
        "--max-scaled-logit",
        type=float,
        default=1.0,
        help="Maximum absolute scaled logit target for polynomial score evaluation.",
    )
    return parser.parse_args()


def standardize_train_test(
    x_train: np.ndarray,
    x_test: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)

    std = np.where(std == 0.0, 1.0, std)

    x_train_std = (x_train - mean) / std
    x_test_std = (x_test - mean) / std

    return x_train_std, x_test_std, mean, std


def select_top_features(
    x_train_std: np.ndarray,
    y_train: np.ndarray,
    feature_names: List[str],
) -> List[int]:
    full_model = LogisticRegression(
        solver="liblinear",
        C=1.0,
        max_iter=1000,
        random_state=0,
    )
    full_model.fit(x_train_std, y_train)

    coefficients = np.abs(full_model.coef_[0])
    ranked_indices = np.argsort(coefficients)[::-1]

    selected = []
    for index in ranked_indices:
        if len(selected) >= 3:
            break
        selected.append(int(index))

    selected.sort()
    return selected


def train_small_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
) -> LogisticRegression:
    model = LogisticRegression(
        solver="liblinear",
        C=1.0,
        max_iter=1000,
        random_state=0,
    )
    model.fit(x_train, y_train)
    return model


def polynomial_score(z: np.ndarray) -> np.ndarray:
    return 0.5 + 0.197 * z - 0.004 * np.power(z, 3)


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_test_csv(
    path: Path,
    x_raw: np.ndarray,
    x_std_selected: np.ndarray,
    y_true: np.ndarray,
    raw_logits: np.ndarray,
    scaled_logits: np.ndarray,
    polynomial_scores: np.ndarray,
    plaintext_decisions: np.ndarray,
    selected_feature_names: List[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "row_id",
        "label",
        "raw_logit",
        "scaled_logit",
        "polynomial_score",
        "plaintext_decision",
    ]

    for feature_name in selected_feature_names:
        safe_name = feature_name.replace(" ", "_").replace("/", "_")
        fieldnames.append(f"std_{safe_name}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row_id in range(x_std_selected.shape[0]):
            row = {
                "row_id": row_id,
                "label": int(y_true[row_id]),
                "raw_logit": format_float(raw_logits[row_id]),
                "scaled_logit": format_float(scaled_logits[row_id]),
                "polynomial_score": format_float(polynomial_scores[row_id]),
                "plaintext_decision": bool(plaintext_decisions[row_id]),
            }

            for j, feature_name in enumerate(selected_feature_names):
                safe_name = feature_name.replace(" ", "_").replace("/", "_")
                row[f"std_{safe_name}"] = format_float(x_std_selected[row_id, j])

            writer.writerow(row)


def write_metrics_csv(path: Path, metrics: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])

        for key in sorted(metrics.keys()):
            writer.writerow([key, format_float(metrics[key])])


def format_float(value: float) -> str:
    return f"{float(value):.12f}"


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    dataset = load_breast_cancer()
    x = dataset.data.astype(np.float64)
    y = dataset.target.astype(np.int64)
    feature_names = [str(name) for name in dataset.feature_names]

    x_train_raw, x_test_raw, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    x_train_std, x_test_std, mean, std = standardize_train_test(
        x_train_raw,
        x_test_raw,
    )

    selected_indices = select_top_features(x_train_std, y_train, feature_names)
    selected_feature_names = [feature_names[i] for i in selected_indices]

    x_train_selected = x_train_std[:, selected_indices]
    x_test_selected = x_test_std[:, selected_indices]

    model = train_small_model(x_train_selected, y_train)

    raw_logits_train = model.decision_function(x_train_selected)
    raw_logits_test = model.decision_function(x_test_selected)

    max_abs_train_logit = float(np.max(np.abs(raw_logits_train)))
    if max_abs_train_logit <= 0.0:
        raise ValueError("invalid non-positive max_abs_train_logit")

    logit_scale = args.max_scaled_logit / max_abs_train_logit

    scaled_logits_train = raw_logits_train * logit_scale
    scaled_logits_test = raw_logits_test * logit_scale

    polynomial_scores_test = polynomial_score(scaled_logits_test)
    plaintext_decisions_test = polynomial_scores_test >= 0.5

    raw_decisions_test = raw_logits_test >= 0.0

    accuracy = accuracy_score(y_test, raw_decisions_test)
    f1 = f1_score(y_test, raw_decisions_test)
    auc = roc_auc_score(y_test, raw_logits_test)

    polynomial_decision_match_rate = accuracy_score(raw_decisions_test, plaintext_decisions_test)

    payload = {
        "dataset": "WDBC Breast Cancer",
        "source": "sklearn.datasets.load_breast_cancer",
        "task": "binary classification",
        "label_mapping": {
            "0": "malignant",
            "1": "benign",
        },
        "model": "3-feature logistic regression",
        "random_state": args.random_state,
        "test_size": args.test_size,
        "selected_feature_indices": selected_indices,
        "selected_feature_names": selected_feature_names,
        "standardization": {
            "mean": [float(mean[i]) for i in selected_indices],
            "std": [float(std[i]) for i in selected_indices],
        },
        "raw_logistic_model": {
            "weights": [float(v) for v in model.coef_[0]],
            "bias": float(model.intercept_[0]),
        },
        "scaled_logit_model_for_ckks": {
            "weights": [float(v * logit_scale) for v in model.coef_[0]],
            "bias": float(model.intercept_[0] * logit_scale),
            "logit_scale": float(logit_scale),
            "max_abs_train_logit": max_abs_train_logit,
            "max_scaled_logit_target": args.max_scaled_logit,
        },
        "polynomial_score": {
            "formula": "0.5 + 0.197*z - 0.004*z^3",
            "decision_threshold": 0.5,
        },
        "metrics": {
            "test_samples": int(len(y_test)),
            "train_samples": int(len(y_train)),
            "raw_logistic_accuracy": float(accuracy),
            "raw_logistic_f1": float(f1),
            "raw_logistic_auc": float(auc),
            "polynomial_decision_match_rate": float(polynomial_decision_match_rate),
            "test_scaled_logit_min": float(np.min(scaled_logits_test)),
            "test_scaled_logit_max": float(np.max(scaled_logits_test)),
            "test_scaled_logit_max_abs": float(np.max(np.abs(scaled_logits_test))),
        },
    }

    metrics = {
        "train_samples": float(len(y_train)),
        "test_samples": float(len(y_test)),
        "raw_logistic_accuracy": float(accuracy),
        "raw_logistic_f1": float(f1),
        "raw_logistic_auc": float(auc),
        "polynomial_decision_match_rate": float(polynomial_decision_match_rate),
        "test_scaled_logit_min": float(np.min(scaled_logits_test)),
        "test_scaled_logit_max": float(np.max(scaled_logits_test)),
        "test_scaled_logit_max_abs": float(np.max(np.abs(scaled_logits_test))),
        "max_abs_train_logit": max_abs_train_logit,
        "logit_scale": float(logit_scale),
    }

    write_json(output_dir / "model.json", payload)
    write_test_csv(
        output_dir / "test.csv",
        x_test_raw[:, selected_indices],
        x_test_selected,
        y_test,
        raw_logits_test,
        scaled_logits_test,
        polynomial_scores_test,
        plaintext_decisions_test,
        selected_feature_names,
    )
    write_metrics_csv(output_dir / "metrics.csv", metrics)

    print("FlipGuard WDBC logistic model export")
    print(f"output_dir={output_dir}")
    print(f"train_samples={len(y_train)} test_samples={len(y_test)}")
    print(f"selected_features={selected_feature_names}")
    print(f"raw_logistic_accuracy={accuracy:.6f}")
    print(f"raw_logistic_f1={f1:.6f}")
    print(f"raw_logistic_auc={auc:.6f}")
    print(f"polynomial_decision_match_rate={polynomial_decision_match_rate:.6f}")
    print(f"test_scaled_logit_range=[{np.min(scaled_logits_test):.6f}, {np.max(scaled_logits_test):.6f}]")


if __name__ == "__main__":
    main()
