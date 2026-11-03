#!/usr/bin/env python3
"""Build leakage-resistant V17 tabular models before protocol freeze.

This script creates only V17 artifacts. It never reads an encrypted result and
never writes the legacy dataset or evidence roots.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import heapq
import json
import math
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer, load_digits, load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split


REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "results/model_family_expansion_v17/plaintext"
BANKNOTE_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00267/"
    "data_banknote_authentication.txt"
)
MNIST_ARFF = REPO / "results/source_datasets/mnist/mnist_784.arff.gz"
SCHEMA = "flipguard_model_family_expansion_v17_plaintext_v1"
DATASETS = ("banknote", "digits_binary", "iris_binary", "mnist_pool16", "wdbc")
PRIMARY = {
    "linear_poly3": DATASETS,
    "mlp_square_linear_score": DATASETS,
    "mlp_square2_linear_score": ("banknote", "mnist_pool16", "wdbc"),
}
ABLATION = {
    "linear_affine_score": ("banknote", "mnist_pool16", "wdbc"),
    "linear_poly3": ("banknote", "mnist_pool16", "wdbc"),
    "mlp_square_linear_score": ("banknote", "mnist_pool16", "wdbc"),
    "mlp_square_poly3": ("banknote", "mnist_pool16", "wdbc"),
}
TRAINING_SEEDS = (0, 1, 2, 3, 4)
OUTER_FOLDS = 5
SELECTION_FRACTION_OF_OUTER_TRAIN = 0.25
MAX_FEATURES = 16
MARGIN_FLOOR = 0.001


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    name: str
    x: np.ndarray
    y: np.ndarray
    row_ids: np.ndarray
    feature_names: list[str]
    source: str
    source_sha256: str


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("ascii")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload))


def load_banknote(cache: Path) -> Dataset:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        with urllib.request.urlopen(BANKNOTE_URL, timeout=60) as response:
            cache.write_bytes(response.read())
    rows = []
    for line in cache.read_text(encoding="ascii").splitlines():
        if line.strip():
            values = [float(value) for value in line.split(",")]
            if len(values) != 5:
                raise ValueError("invalid banknote source row")
            rows.append(values)
    values = np.asarray(rows, dtype=np.float64)
    return Dataset(
        "banknote",
        "Banknote Authentication",
        values[:, :4],
        values[:, 4].astype(np.int64),
        np.arange(len(values), dtype=np.int64),
        ["variance_wavelet", "skewness_wavelet", "curtosis_wavelet", "entropy_image"],
        BANKNOTE_URL,
        sha256_path(cache),
    )


def load_mnist_pool16(path: Path, per_binary_class: int = 1250) -> Dataset:
    if not path.exists():
        raise FileNotFoundError(path)
    heaps: dict[int, list[tuple[int, int, np.ndarray]]] = {0: [], 1: []}
    in_data = False
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        for source_index, line in enumerate(handle):
            stripped = line.strip()
            if not in_data:
                if stripped.lower() == "@data":
                    in_data = True
                continue
            if not stripped or stripped.startswith("%"):
                continue
            parts = stripped.split(",")
            if len(parts) != 785:
                raise ValueError(f"MNIST ARFF row has {len(parts)} fields")
            digit = int(parts[-1].strip("'\""))
            label = int(digit % 2 == 0)
            rank = int.from_bytes(
                hashlib.sha256(f"v17-mnist-pool16:{source_index}".encode("ascii")).digest()[:8],
                "big",
            )
            pixels = np.fromiter((float(v) for v in parts[:-1]), dtype=np.float64, count=784)
            item = (-rank, source_index, pixels)
            heap = heaps[label]
            if len(heap) < per_binary_class:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
    chosen = []
    for label, heap in heaps.items():
        for negative_rank, source_index, pixels in heap:
            chosen.append((-negative_rank, source_index, label, pixels))
    chosen.sort(key=lambda row: (row[0], row[1]))
    images = np.asarray([row[3] for row in chosen], dtype=np.float64).reshape(-1, 28, 28) / 255.0
    pooled = images.reshape(-1, 4, 7, 4, 7).mean(axis=(2, 4)).reshape(-1, 16)
    return Dataset(
        "mnist_pool16",
        "MNIST pooled 4x4 even-vs-odd classification",
        pooled,
        np.asarray([row[2] for row in chosen], dtype=np.int64),
        np.asarray([row[1] for row in chosen], dtype=np.int64),
        [f"pool4x4_{index}" for index in range(16)],
        path.relative_to(REPO).as_posix(),
        sha256_path(path),
    )


def load_datasets(root: Path) -> dict[str, Dataset]:
    breast = load_breast_cancer()
    digits = load_digits()
    iris = load_iris()
    iris_mask = iris.target < 2
    datasets = {
        "banknote": load_banknote(root / "sources/banknote_authentication.csv"),
        "wdbc": Dataset(
            "wdbc", "WDBC Breast Cancer", breast.data.astype(np.float64),
            breast.target.astype(np.int64), np.arange(len(breast.target)),
            [str(name) for name in breast.feature_names],
            "sklearn.datasets.load_breast_cancer", "sklearn-bundled:wdbc",
        ),
        "iris_binary": Dataset(
            "iris_binary", "Iris binary classification",
            iris.data[iris_mask].astype(np.float64), iris.target[iris_mask].astype(np.int64),
            np.flatnonzero(iris_mask), [str(name) for name in iris.feature_names],
            "sklearn.datasets.load_iris(target<2)", "sklearn-bundled:iris",
        ),
        "digits_binary": Dataset(
            "digits_binary", "Digits even-vs-odd binary classification",
            digits.data.astype(np.float64), (digits.target % 2 == 0).astype(np.int64),
            np.arange(len(digits.target)), [f"pixel_{i}" for i in range(digits.data.shape[1])],
            "sklearn.datasets.load_digits(target parity)", "sklearn-bundled:digits",
        ),
        "mnist_pool16": load_mnist_pool16(MNIST_ARFF),
    }
    return datasets


def sigmoid(values: np.ndarray) -> np.ndarray:
    output = np.empty_like(values)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponent = np.exp(values[~positive])
    output[~positive] = exponent / (1.0 + exponent)
    return output


def train_square_network(x: np.ndarray, y: np.ndarray, hidden: tuple[int, ...], seed: int) -> dict:
    rng = np.random.default_rng(seed)
    dimensions = (x.shape[1],) + hidden + (1,)
    weights = [rng.normal(0.0, 0.08, size=(dimensions[i + 1], dimensions[i])) for i in range(len(dimensions) - 1)]
    biases = [np.zeros(dimensions[i + 1], dtype=np.float64) for i in range(len(dimensions) - 1)]
    moments = [(np.zeros_like(w), np.zeros_like(w)) for w in weights]
    bias_moments = [(np.zeros_like(b), np.zeros_like(b)) for b in biases]
    y_float = y.astype(np.float64)
    for epoch in range(1, 1201):
        activations = [x]
        preactivations = []
        for layer in range(len(hidden)):
            pre = activations[-1] @ weights[layer].T + biases[layer]
            preactivations.append(pre)
            activations.append(np.square(pre))
        logits = (activations[-1] @ weights[-1].T + biases[-1]).reshape(-1)
        delta = ((sigmoid(logits) - y_float) / len(y_float))[:, None]
        grad_w: list[np.ndarray] = [np.empty_like(w) for w in weights]
        grad_b: list[np.ndarray] = [np.empty_like(b) for b in biases]
        grad_w[-1] = delta.T @ activations[-1] + 1e-4 * weights[-1]
        grad_b[-1] = delta.sum(axis=0)
        back = delta @ weights[-1]
        for layer in range(len(hidden) - 1, -1, -1):
            back = back * (2.0 * preactivations[layer])
            grad_w[layer] = back.T @ activations[layer] + 1e-4 * weights[layer]
            grad_b[layer] = back.sum(axis=0)
            if layer:
                back = back @ weights[layer]
        norm = math.sqrt(sum(float(np.sum(g * g)) for g in grad_w + grad_b))
        factor = min(1.0, 5.0 / max(norm, 1e-12))
        for layer in range(len(weights)):
            grad_w[layer] *= factor
            grad_b[layer] *= factor
            mw, vw = moments[layer]
            mb, vb = bias_moments[layer]
            mw[:] = 0.9 * mw + 0.1 * grad_w[layer]
            vw[:] = 0.999 * vw + 0.001 * np.square(grad_w[layer])
            mb[:] = 0.9 * mb + 0.1 * grad_b[layer]
            vb[:] = 0.999 * vb + 0.001 * np.square(grad_b[layer])
            c1, c2 = 1.0 - 0.9**epoch, 1.0 - 0.999**epoch
            weights[layer] -= 0.003 * (mw / c1) / (np.sqrt(vw / c2) + 1e-8)
            biases[layer] -= 0.003 * (mb / c1) / (np.sqrt(vb / c2) + 1e-8)
    return {"weights": weights, "biases": biases}


def network_logits(x: np.ndarray, trained: dict) -> np.ndarray:
    activation = x
    for weights, bias in zip(trained["weights"][:-1], trained["biases"][:-1]):
        activation = np.square(activation @ weights.T + bias)
    return (activation @ trained["weights"][-1].T + trained["biases"][-1]).reshape(-1)


def fit_model(model_id: str, x: np.ndarray, y: np.ndarray, seed: int) -> tuple[dict, np.ndarray]:
    if model_id.startswith("linear_"):
        fitted = LogisticRegression(solver="liblinear", C=1.0, max_iter=2000, random_state=seed).fit(x, y)
        params = {"weights": fitted.coef_[0], "bias": float(fitted.intercept_[0])}
        return params, x @ params["weights"] + params["bias"]
    hidden = (8, 4) if model_id == "mlp_square2_linear_score" else (4,)
    trained = train_square_network(x, y, hidden, seed)
    return trained, network_logits(x, trained)


def scaled_parameters(model_id: str, trained: dict, scale: float) -> dict:
    if model_id.startswith("linear_"):
        return {"weights": (trained["weights"] * scale).tolist(), "bias": trained["bias"] * scale}
    weights, biases = trained["weights"], trained["biases"]
    payload = {
        "hidden_weights": weights[0].tolist(),
        "hidden_bias": biases[0].tolist(),
        "output_weights": (weights[-1].reshape(-1) * scale).tolist(),
        "output_bias": float(biases[-1][0] * scale),
    }
    if len(weights) == 3:
        payload["hidden2_weights"] = weights[1].tolist()
        payload["hidden2_bias"] = biases[1].tolist()
    return payload


def head_formula(model_id: str) -> str:
    return "0.5 + 0.197*z - 0.004*z^3" if model_id.endswith("poly3") else "0.5 + 0.197*z"


def scores(model_id: str, z: np.ndarray) -> np.ndarray:
    return 0.5 + 0.197 * z - 0.004 * z**3 if model_id.endswith("poly3") else 0.5 + 0.197 * z


def write_role_csv(path: Path, dataset: Dataset, indices: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["row_id", "label"] + [f"x_{i}" for i in range(dataset.x.shape[1])]
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fields)
        for index in indices:
            writer.writerow([int(dataset.row_ids[index]), int(dataset.y[index])] + [format(float(v), ".17g") for v in dataset.x[index]])


def quality(y: np.ndarray, z: np.ndarray) -> dict:
    decision = z >= 0
    margins = np.abs(z)
    return {
        "accuracy": float(accuracy_score(y, decision)),
        "balanced_accuracy": float(balanced_accuracy_score(y, decision)),
        "macro_f1": float(f1_score(y, decision, average="macro")),
        "auroc": float(roc_auc_score(y, z)),
        "logit_margin_quantiles": {str(q): float(np.quantile(margins, q)) for q in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1)},
    }


def build_workload(root: Path, dataset: Dataset, model_id: str, fold: int, seed: int, roles: tuple[np.ndarray, np.ndarray, np.ndarray], role: str) -> dict:
    train_idx, selection_idx, evaluation_idx = roles
    mean = dataset.x[train_idx].mean(axis=0)
    std = dataset.x[train_idx].std(axis=0)
    std = np.where(std == 0, 1.0, std)
    normalized_train = (dataset.x[train_idx] - mean) / std
    selector = LogisticRegression(solver="liblinear", max_iter=2000, random_state=seed).fit(normalized_train, dataset.y[train_idx])
    ranked = np.argsort(np.abs(selector.coef_[0]))[::-1]
    selected = np.sort(ranked[: min(MAX_FEATURES, dataset.x.shape[1])])
    x_train = normalized_train[:, selected]
    trained, train_logits = fit_model(model_id, x_train, dataset.y[train_idx], seed)
    max_abs = float(np.max(np.abs(train_logits)))
    logit_scale = 1.0 / max_abs if max_abs else 1.0
    path = root / role / dataset.dataset_id / model_id / f"fold_{fold}" / f"training_seed_{seed}"
    model = {
        "schema_version": SCHEMA,
        "dataset_id": dataset.dataset_id,
        "dataset_name": dataset.name,
        "model_id": model_id,
        "model_type": model_id,
        "task": "binary classification",
        "input_dim": int(len(selected)),
        "train_samples": int(len(train_idx)),
        "test_samples": int(len(evaluation_idx)),
        "outer_fold": fold,
        "training_seed": seed,
        "selected_feature_indices": selected.astype(int).tolist(),
        "selected_feature_names": [dataset.feature_names[i] for i in selected],
        "standardization": {"mean": mean[selected].tolist(), "std": std[selected].tolist()},
        "scaled_model_for_ckks": scaled_parameters(model_id, trained, logit_scale),
        "polynomial_score": {"formula": head_formula(model_id), "decision_threshold": 0.5},
        "training_only_logit_scale": logit_scale,
    }
    write_json(path / "model.json", model)
    write_role_csv(path / "model_training.csv", dataset, train_idx)
    write_role_csv(path / "configuration_selection.csv", dataset, selection_idx)
    write_role_csv(path / "independent_evaluation.csv", dataset, evaluation_idx)
    evaluation_normalized = ((dataset.x[evaluation_idx] - mean) / std)[:, selected]
    evaluation_z = network_logits(evaluation_normalized, trained) if not model_id.startswith("linear_") else evaluation_normalized @ trained["weights"] + trained["bias"]
    evaluation_z *= logit_scale
    evaluation_scores = scores(model_id, evaluation_z)
    manifest = {
        "schema_version": SCHEMA,
        "dataset_id": dataset.dataset_id,
        "model_id": model_id,
        "role": role,
        "outer_fold": fold,
        "training_seed": seed,
        "source": dataset.source,
        "source_sha256": dataset.source_sha256,
        "model_path": path.relative_to(REPO).as_posix() + "/model.json",
        "model_sha256": sha256_path(path / "model.json"),
        "roles": {
            "model_training": {"rows": len(train_idx), "row_ids": sorted(int(dataset.row_ids[i]) for i in train_idx), "sha256": sha256_path(path / "model_training.csv")},
            "configuration_selection": {"rows": len(selection_idx), "row_ids": sorted(int(dataset.row_ids[i]) for i in selection_idx), "sha256": sha256_path(path / "configuration_selection.csv")},
            "independent_evaluation": {"rows": len(evaluation_idx), "row_ids": sorted(int(dataset.row_ids[i]) for i in evaluation_idx), "sha256": sha256_path(path / "independent_evaluation.csv")},
        },
        "row_overlap": 0,
        "quality_independent_evaluation": quality(dataset.y[evaluation_idx], evaluation_z),
        "score_margin_quantiles": {str(q): float(np.quantile(np.abs(evaluation_scores - 0.5), q)) for q in (0, 0.1, 0.25, 0.5, 0.75, 0.9, 1)},
    }
    write_json(path / "manifest.json", manifest)
    return manifest


def split_roles(dataset: Dataset) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    splitter = StratifiedKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=1701)
    roles = []
    for fold, (outer_train, evaluation) in enumerate(splitter.split(dataset.x, dataset.y)):
        train, selection = train_test_split(
            outer_train,
            test_size=SELECTION_FRACTION_OF_OUTER_TRAIN,
            stratify=dataset.y[outer_train],
            random_state=2701 + fold,
        )
        roles.append((np.sort(train), np.sort(selection), np.sort(evaluation)))
    return roles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty V17 plaintext root: {root}")
    datasets = load_datasets(root)
    all_manifests = []
    role_cache = {name: split_roles(dataset) for name, dataset in datasets.items()}
    for model_id, names in PRIMARY.items():
        for name in names:
            for fold, roles in enumerate(role_cache[name]):
                all_manifests.append(build_workload(root, datasets[name], model_id, fold, 0, roles, "primary"))
    for model_id, names in ABLATION.items():
        for name in names:
            if model_id in PRIMARY and name in PRIMARY[model_id]:
                continue
            for fold, roles in enumerate(role_cache[name]):
                all_manifests.append(build_workload(root, datasets[name], model_id, fold, 0, roles, "ablation"))
    for model_id in ("mlp_square_linear_score", "mlp_square2_linear_score"):
        for name in ("banknote", "mnist_pool16", "wdbc"):
            roles = role_cache[name][0]
            for seed in TRAINING_SEEDS:
                if seed == 0:
                    continue
                all_manifests.append(build_workload(root, datasets[name], model_id, 0, seed, roles, "training_seed"))
    summary = {
        "schema_version": SCHEMA,
        "datasets": list(DATASETS),
        "outer_folds": OUTER_FOLDS,
        "selection_fraction_of_outer_train": SELECTION_FRACTION_OF_OUTER_TRAIN,
        "max_features_training_only": MAX_FEATURES,
        "margin_floor": MARGIN_FLOOR,
        "workloads": len(all_manifests),
        "manifests": sorted(m["model_path"].replace("/model.json", "/manifest.json") for m in all_manifests),
        "source_commit": "WORKTREE_PRE_PROTOCOL_FREEZE",
    }
    write_json(root / "summary.json", summary)
    print(json.dumps({"status": "PLAINTEXT_SUITE_BUILT", "workloads": len(all_manifests), "output": str(root.relative_to(REPO))}, sort_keys=True))


if __name__ == "__main__":
    main()
