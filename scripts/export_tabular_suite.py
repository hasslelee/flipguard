#!/usr/bin/env python3

import argparse
import csv
import json
import math
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.datasets import load_breast_cancer, load_iris, load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split


BANKNOTE_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00267/data_banknote_authentication.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a common tabular benchmark suite for CKKS encrypted inference."
    )
    parser.add_argument(
        "--output-root",
        default="datasets/tabular_suite",
        help="Output root directory.",
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
        "--max-features",
        type=int,
        default=8,
        help="Maximum selected input features per dataset.",
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
        default=3000,
        help="Training epochs for square-activation MLP.",
    )
    return parser.parse_args()


def load_dataset(dataset_id: str) -> Tuple[np.ndarray, np.ndarray, List[str], str]:
    if dataset_id == "wdbc":
        data = load_breast_cancer()
        return (
            data.data.astype(np.float64),
            data.target.astype(np.int64),
            [str(name) for name in data.feature_names],
            "WDBC Breast Cancer",
        )

    if dataset_id == "iris_binary":
        data = load_iris()
        mask = data.target < 2
        x = data.data[mask].astype(np.float64)
        y = data.target[mask].astype(np.int64)
        return (
            x,
            y,
            [str(name) for name in data.feature_names],
            "Iris binary classification",
        )

    if dataset_id == "digits_binary":
        data = load_digits()
        x = data.data.astype(np.float64)
        y = (data.target % 2 == 0).astype(np.int64)
        return (
            x,
            y,
            [f"pixel_{i}" for i in range(x.shape[1])],
            "Digits even-vs-odd binary classification",
        )

    if dataset_id == "banknote":
        return load_banknote_dataset()

    raise ValueError(f"unsupported dataset_id: {dataset_id}")


def load_banknote_dataset() -> Tuple[np.ndarray, np.ndarray, List[str], str]:
    try:
        with urllib.request.urlopen(BANKNOTE_URL, timeout=30) as response:
            text = response.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(
            "failed to download Banknote Authentication dataset from UCI"
        ) from exc

    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = [float(value) for value in line.split(",")]
        if len(parts) != 5:
            raise ValueError(f"invalid banknote row with {len(parts)} columns")
        rows.append(parts)

    array = np.array(rows, dtype=np.float64)
    x = array[:, :4]
    y = array[:, 4].astype(np.int64)

    feature_names = [
        "variance_wavelet",
        "skewness_wavelet",
        "curtosis_wavelet",
        "entropy_image",
    ]

    return x, y, feature_names, "Banknote Authentication"


def standardize_train_test(
    x_train: np.ndarray,
    x_test: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std = np.where(std == 0.0, 1.0, std)

    return (x_train - mean) / std, (x_test - mean) / std, mean, std


def select_features(
    x_train_std: np.ndarray,
    y_train: np.ndarray,
    max_features: int,
) -> List[int]:
    if x_train_std.shape[1] <= max_features:
        return list(range(x_train_std.shape[1]))

    model = LogisticRegression(
        solver="liblinear",
        C=1.0,
        max_iter=1000,
        random_state=0,
    )
    model.fit(x_train_std, y_train)

    coefficients = np.abs(model.coef_[0])
    ranked = np.argsort(coefficients)[::-1]
    selected = sorted(int(index) for index in ranked[:max_features])
    return selected


def polynomial_score(z: np.ndarray) -> np.ndarray:
    return 0.5 + 0.197 * z - 0.004 * np.power(z, 3)


def sigmoid_stable(z: np.ndarray) -> np.ndarray:
    out = np.empty_like(z, dtype=np.float64)
    positive = z >= 0
    out[positive] = 1.0 / (1.0 + np.exp(-z[positive]))
    exp_z = np.exp(z[~positive])
    out[~positive] = exp_z / (1.0 + exp_z)
    return out


def train_linear_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
) -> Dict:
    model = LogisticRegression(
        solver="liblinear",
        C=1.0,
        max_iter=1000,
        random_state=0,
    )
    model.fit(x_train, y_train)

    return {
        "weights": model.coef_[0].astype(np.float64),
        "bias": float(model.intercept_[0]),
    }


def linear_logits(x: np.ndarray, params: Dict) -> np.ndarray:
    return x @ params["weights"] + params["bias"]


def train_square_mlp(
    x_train: np.ndarray,
    y_train: np.ndarray,
    hidden_units: int,
    epochs: int,
    random_state: int,
) -> Dict:
    rng = np.random.default_rng(random_state)

    n, d = x_train.shape
    h = hidden_units

    w1 = rng.normal(0.0, 0.15, size=(h, d))
    b1 = np.zeros(h, dtype=np.float64)
    w2 = rng.normal(0.0, 0.15, size=h)
    b2 = 0.0

    mw1 = np.zeros_like(w1)
    vw1 = np.zeros_like(w1)
    mb1 = np.zeros_like(b1)
    vb1 = np.zeros_like(b1)
    mw2 = np.zeros_like(w2)
    vw2 = np.zeros_like(w2)
    mb2 = 0.0
    vb2 = 0.0

    lr = 0.01
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    l2 = 1e-4

    y = y_train.astype(np.float64)

    for epoch in range(1, epochs + 1):
        a = x_train @ w1.T + b1
        hidden = a * a
        z = hidden @ w2 + b2
        p = sigmoid_stable(z)

        dz = (p - y) / float(n)

        grad_w2 = hidden.T @ dz + l2 * w2
        grad_b2 = float(np.sum(dz))

        grad_hidden = dz[:, None] * w2[None, :]
        grad_a = grad_hidden * (2.0 * a)

        grad_w1 = grad_a.T @ x_train + l2 * w1
        grad_b1 = np.sum(grad_a, axis=0)

        mw1 = beta1 * mw1 + (1.0 - beta1) * grad_w1
        vw1 = beta2 * vw1 + (1.0 - beta2) * (grad_w1 * grad_w1)
        mb1 = beta1 * mb1 + (1.0 - beta1) * grad_b1
        vb1 = beta2 * vb1 + (1.0 - beta2) * (grad_b1 * grad_b1)
        mw2 = beta1 * mw2 + (1.0 - beta1) * grad_w2
        vw2 = beta2 * vw2 + (1.0 - beta2) * (grad_w2 * grad_w2)
        mb2 = beta1 * mb2 + (1.0 - beta1) * grad_b2
        vb2 = beta2 * vb2 + (1.0 - beta2) * (grad_b2 * grad_b2)

        correction1 = 1.0 - beta1 ** epoch
        correction2 = 1.0 - beta2 ** epoch

        w1 -= lr * (mw1 / correction1) / (np.sqrt(vw1 / correction2) + eps)
        b1 -= lr * (mb1 / correction1) / (np.sqrt(vb1 / correction2) + eps)
        w2 -= lr * (mw2 / correction1) / (np.sqrt(vw2 / correction2) + eps)
        b2 -= lr * (mb2 / correction1) / (math.sqrt(vb2 / correction2) + eps)

    return {
        "hidden_weights": w1.astype(np.float64),
        "hidden_bias": b1.astype(np.float64),
        "output_weights": w2.astype(np.float64),
        "output_bias": float(b2),
    }


def square_mlp_logits(x: np.ndarray, params: Dict) -> np.ndarray:
    a = x @ params["hidden_weights"].T + params["hidden_bias"]
    hidden = a * a
    return hidden @ params["output_weights"] + params["output_bias"]


def scale_linear_params(params: Dict, scale: float) -> Dict:
    return {
        "weights": (params["weights"] * scale).astype(np.float64),
        "bias": float(params["bias"] * scale),
    }


def scale_square_mlp_params(params: Dict, scale: float) -> Dict:
    return {
        "hidden_weights": params["hidden_weights"].astype(np.float64),
        "hidden_bias": params["hidden_bias"].astype(np.float64),
        "output_weights": (params["output_weights"] * scale).astype(np.float64),
        "output_bias": float(params["output_bias"] * scale),
    }


def export_model_artifacts(
    output_dir: Path,
    dataset_id: str,
    dataset_name: str,
    model_id: str,
    model_type: str,
    feature_names: List[str],
    selected_indices: List[int],
    standardization_mean: np.ndarray,
    standardization_std: np.ndarray,
    params_raw: Dict,
    params_scaled: Dict,
    raw_logits_test: np.ndarray,
    scaled_logits_test: np.ndarray,
    x_test_selected: np.ndarray,
    y_test: np.ndarray,
    random_state: int,
    test_size: float,
    max_scaled_logit: float,
    train_samples: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    scores = polynomial_score(scaled_logits_test)
    plain_decisions = scores >= 0.5
    raw_decisions = raw_logits_test >= 0.0

    accuracy = accuracy_score(y_test, raw_decisions)
    f1 = f1_score(y_test, raw_decisions)

    try:
        auc = roc_auc_score(y_test, raw_logits_test)
    except ValueError:
        auc = 0.0

    polynomial_match = accuracy_score(raw_decisions, plain_decisions)

    selected_feature_names = [feature_names[i] for i in selected_indices]

    model_payload = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "model_id": model_id,
        "model_type": model_type,
        "task": "binary classification",
        "label_mapping": {
            "0": "negative",
            "1": "positive",
        },
        "random_state": random_state,
        "test_size": test_size,
        "train_samples": train_samples,
        "test_samples": int(len(y_test)),
        "selected_feature_indices": selected_indices,
        "selected_feature_names": selected_feature_names,
        "input_dim": int(x_test_selected.shape[1]),
        "standardization": {
            "mean": [float(standardization_mean[i]) for i in selected_indices],
            "std": [float(standardization_std[i]) for i in selected_indices],
        },
        "raw_model": convert_params_for_json(params_raw),
        "scaled_model_for_ckks": convert_params_for_json(params_scaled),
        "max_scaled_logit_target": float(max_scaled_logit),
        "polynomial_score": {
            "formula": "0.5 + 0.197*z - 0.004*z^3",
            "decision_threshold": 0.5,
        },
        "metrics": {
            "raw_accuracy": float(accuracy),
            "raw_f1": float(f1),
            "raw_auc": float(auc),
            "polynomial_decision_match_rate": float(polynomial_match),
            "test_scaled_logit_min": float(np.min(scaled_logits_test)),
            "test_scaled_logit_max": float(np.max(scaled_logits_test)),
            "test_scaled_logit_max_abs": float(np.max(np.abs(scaled_logits_test))),
        },
    }

    write_json(output_dir / "model.json", model_payload)
    write_test_csv(
        output_dir / "test.csv",
        x_test_selected,
        y_test,
        raw_logits_test,
        scaled_logits_test,
        scores,
        plain_decisions,
    )
    write_metrics_csv(
        output_dir / "metrics.csv",
        {
            "train_samples": train_samples,
            "test_samples": int(len(y_test)),
            "raw_accuracy": float(accuracy),
            "raw_f1": float(f1),
            "raw_auc": float(auc),
            "polynomial_decision_match_rate": float(polynomial_match),
            "test_scaled_logit_min": float(np.min(scaled_logits_test)),
            "test_scaled_logit_max": float(np.max(scaled_logits_test)),
            "test_scaled_logit_max_abs": float(np.max(np.abs(scaled_logits_test))),
        },
    )


def convert_params_for_json(params: Dict) -> Dict:
    converted = {}
    for key, value in params.items():
        if isinstance(value, np.ndarray):
            converted[key] = value.tolist()
        else:
            converted[key] = float(value)
    return converted


def write_json(path: Path, payload: Dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_test_csv(
    path: Path,
    x_test_selected: np.ndarray,
    y_test: np.ndarray,
    raw_logits: np.ndarray,
    scaled_logits: np.ndarray,
    scores: np.ndarray,
    plain_decisions: np.ndarray,
) -> None:
    fieldnames = [
        "row_id",
        "label",
        "raw_logit",
        "scaled_logit",
        "polynomial_score",
        "plaintext_decision",
    ]
    fieldnames.extend([f"x_{i}" for i in range(x_test_selected.shape[1])])

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row_id in range(x_test_selected.shape[0]):
            row = {
                "row_id": row_id,
                "label": int(y_test[row_id]),
                "raw_logit": format_float(raw_logits[row_id]),
                "scaled_logit": format_float(scaled_logits[row_id]),
                "polynomial_score": format_float(scores[row_id]),
                "plaintext_decision": bool(plain_decisions[row_id]),
            }

            for i in range(x_test_selected.shape[1]):
                row[f"x_{i}"] = format_float(x_test_selected[row_id, i])

            writer.writerow(row)


def write_metrics_csv(path: Path, metrics: Dict[str, float]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for key in sorted(metrics.keys()):
            writer.writerow([key, format_float(metrics[key])])


def format_float(value: float) -> str:
    return f"{float(value):.12f}"


def export_dataset(
    args: argparse.Namespace,
    dataset_id: str,
) -> None:
    x, y, feature_names, dataset_name = load_dataset(dataset_id)

    x_train_raw, x_test_raw, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    x_train_std, x_test_std, mean, std = standardize_train_test(x_train_raw, x_test_raw)
    selected_indices = select_features(x_train_std, y_train, args.max_features)

    x_train_selected = x_train_std[:, selected_indices]
    x_test_selected = x_test_std[:, selected_indices]

    dataset_root = Path(args.output_root) / dataset_id

    linear_params = train_linear_model(x_train_selected, y_train)
    linear_train_logits = linear_logits(x_train_selected, linear_params)
    linear_test_logits = linear_logits(x_test_selected, linear_params)
    linear_scale = compute_logit_scale(linear_train_logits, args.max_scaled_logit)
    linear_scaled_params = scale_linear_params(linear_params, linear_scale)
    linear_scaled_test_logits = linear_test_logits * linear_scale

    export_model_artifacts(
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

    mlp_params = train_square_mlp(
        x_train_selected,
        y_train,
        args.hidden_units,
        args.mlp_epochs,
        args.random_state,
    )
    mlp_train_logits = square_mlp_logits(x_train_selected, mlp_params)
    mlp_test_logits = square_mlp_logits(x_test_selected, mlp_params)
    mlp_scale = compute_logit_scale(mlp_train_logits, args.max_scaled_logit)
    mlp_scaled_params = scale_square_mlp_params(mlp_params, mlp_scale)
    mlp_scaled_test_logits = mlp_test_logits * mlp_scale

    export_model_artifacts(
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


def compute_logit_scale(train_logits: np.ndarray, max_scaled_logit: float) -> float:
    max_abs = float(np.max(np.abs(train_logits)))
    if max_abs <= 0.0:
        return 1.0
    return max_scaled_logit / max_abs


def main() -> None:
    args = parse_args()

    dataset_ids = [
        "wdbc",
        "iris_binary",
        "digits_binary",
        "banknote",
    ]

    print("FlipGuard common tabular suite export")
    print(f"output_root={args.output_root}")

    for dataset_id in dataset_ids:
        print(f"exporting dataset={dataset_id}")
        export_dataset(args, dataset_id)

    print("done")


if __name__ == "__main__":
    main()
