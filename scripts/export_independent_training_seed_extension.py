#!/usr/bin/env python3
"""Build deterministic independent-training-seed extension inputs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, NamedTuple, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("datasets/independent_training_seed_suite_v1")
SCHEMA_VERSION = "flipguard_independent_training_seed_suite_v1"
POLICY_ID = "flipguard_independent_training_seed_v1"
SEEDS = (1729, 2718, 3141)
DATASET_IDS = ("iris_binary", "wdbc", "digits_binary")
MODEL_ID = "mlp_square_linear_score"

POLICY = {
    "schema_version": SCHEMA_VERSION,
    "policy_id": POLICY_ID,
    "datasets": list(DATASET_IDS),
    "training_seeds": list(SEEDS),
    "role_assignment": {
        "algorithm": "sha256_stratified_rank_v1",
        "domain": POLICY_ID,
        "evaluation_fraction_per_label": 0.20,
        "maximum_rows_per_label_per_evaluation_role": 48,
        "role_order": [
            "configuration_validation",
            "locked_audit",
            "model_training",
        ],
    },
    "preprocessing": {
        "fit_scope": "model_training_only",
        "standardization": "population_mean_std_zero_safe_v1",
        "maximum_features": 8,
        "feature_rank": "absolute_train_pearson_then_source_index_v1",
    },
    "model": {
        "model_id": MODEL_ID,
        "model_type": MODEL_ID,
        "hidden_units": 4,
        "activation": "square",
        "epochs": 3000,
        "optimizer": "full_batch_adam",
        "learning_rate": 0.01,
        "beta1": 0.9,
        "beta2": 0.999,
        "epsilon": 1e-8,
        "l2_penalty": 1e-4,
        "initialization": "numpy_pcg64_declared_training_seed",
        "max_training_scaled_logit": 1.0,
        "score_formula": "0.5 + 0.197*z",
        "decision_threshold": 0.5,
    },
    "ckks_protocol": {
        "alpha": 0.5,
        "margin_floor": 0.001,
        "key_repeats_selection": 3,
        "key_repeats_audit": 3,
        "maximum_encrypted_trials": 4,
        "direct_policy_digest": (
            "sha256:"
            "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
        ),
        "security_policy_digest": (
            "sha256:"
            "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
        ),
    },
}


class SourceDataset(NamedTuple):
    dataset_id: str
    dataset_name: str
    upstream_name: str
    upstream_path: Path
    upstream_sha256: str
    feature_names: tuple[str, ...]
    row_ids: tuple[int, ...]
    labels: tuple[int, ...]
    features: tuple[tuple[float, ...], ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sklearn-data-root", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def stable_rank(
    seed: int,
    dataset_id: str,
    label: int,
    row_id: int,
) -> str:
    payload = "\0".join(
        [
            POLICY_ID,
            str(seed),
            dataset_id,
            str(label),
            str(row_id),
        ]
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def assign_roles(
    dataset: SourceDataset,
    seed: int,
) -> dict[str, list[int]]:
    grouped: dict[int, list[int]] = {0: [], 1: []}
    for index, label in enumerate(dataset.labels):
        grouped[label].append(index)
    roles = {
        "model_training": [],
        "configuration_validation": [],
        "locked_audit": [],
    }
    for label, indices in sorted(grouped.items()):
        if not indices:
            raise ValueError(
                f"{dataset.dataset_id}: label {label} is empty"
            )
        ordered = sorted(
            indices,
            key=lambda index: stable_rank(
                seed,
                dataset.dataset_id,
                label,
                dataset.row_ids[index],
            ),
        )
        count = min(math.floor(0.20 * len(ordered)), 48)
        if count < 1 or len(ordered) - 2 * count < 1:
            raise ValueError(
                f"{dataset.dataset_id}: insufficient label {label} rows"
            )
        roles["configuration_validation"].extend(ordered[:count])
        roles["locked_audit"].extend(ordered[count:2 * count])
        roles["model_training"].extend(ordered[2 * count:])
    for values in roles.values():
        values.sort(key=lambda index: dataset.row_ids[index])
    observed = set()
    for name, values in roles.items():
        current = set(values)
        if len(current) != len(values) or observed & current:
            raise ValueError(
                f"{dataset.dataset_id}: role overlap at {name}"
            )
        observed.update(current)
    if observed != set(range(len(dataset.row_ids))):
        raise ValueError(f"{dataset.dataset_id}: incomplete role coverage")
    return roles


def resolve_sklearn_data_root(explicit: Path | None) -> tuple[Path, str, str]:
    import numpy
    import sklearn
    import sklearn.datasets

    if explicit is None:
        root = Path(sklearn.datasets.__file__).resolve().parent / "data"
    else:
        root = explicit.resolve()
    if not root.is_dir():
        raise ValueError(f"scikit-learn data root missing: {root}")
    return root, sklearn.__version__, numpy.__version__


def parse_numeric_csv(
    path: Path,
    target_position: str,
) -> tuple[list[list[float]], list[int]]:
    if path.suffix == ".gz":
        handle = gzip.open(
            path,
            "rt",
            encoding="ascii",
            newline="",
        )
    else:
        handle = path.open(
            "r",
            encoding="ascii",
            newline="",
        )
    with handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"empty source payload: {path}")
    if path.name != "digits.csv.gz":
        rows = rows[1:]
    features: list[list[float]] = []
    labels: list[int] = []
    for row_number, row in enumerate(rows, start=1):
        if target_position == "first":
            raw_label = row[0]
            raw_features = row[1:]
        elif target_position == "last":
            raw_label = row[-1]
            raw_features = row[:-1]
        else:
            raise ValueError(f"unsupported target position {target_position}")
        try:
            label = int(raw_label)
            values = [float(value) for value in raw_features]
        except ValueError as exc:
            raise ValueError(
                f"{path}: invalid numeric row {row_number}"
            ) from exc
        if not values or any(not math.isfinite(value) for value in values):
            raise ValueError(f"{path}: invalid features at row {row_number}")
        labels.append(label)
        features.append(values)
    return features, labels


def load_sources(root: Path) -> list[SourceDataset]:
    specifications = {
        "iris_binary": {
            "file": "iris.csv",
            "name": "Iris binary classification",
            "target": "last",
        },
        "wdbc": {
            "file": "breast_cancer.csv",
            "name": "WDBC Breast Cancer",
            "target": "last",
        },
        "digits_binary": {
            "file": "digits.csv.gz",
            "name": "Digits even-vs-odd binary classification",
            "target": "last",
        },
    }
    datasets = []
    for dataset_id in DATASET_IDS:
        specification = specifications[dataset_id]
        path = root / specification["file"]
        if not path.is_file():
            raise ValueError(f"missing source payload: {path}")
        source_features, source_labels = parse_numeric_csv(
            path,
            specification["target"],
        )
        selected_rows = []
        for source_row_id, (values, original_label) in enumerate(
            zip(source_features, source_labels)
        ):
            if dataset_id == "iris_binary":
                if original_label > 1:
                    continue
                label = original_label
            elif dataset_id == "digits_binary":
                label = int(original_label % 2 == 0)
            else:
                label = original_label
            if label not in (0, 1):
                raise ValueError(
                    f"{dataset_id}: non-binary label {label}"
                )
            selected_rows.append((source_row_id, label, values))
        dimensions = {len(row[2]) for row in selected_rows}
        if len(dimensions) != 1:
            raise ValueError(f"{dataset_id}: inconsistent dimensions")
        dimension = dimensions.pop()
        datasets.append(
            SourceDataset(
                dataset_id=dataset_id,
                dataset_name=specification["name"],
                upstream_name=specification["file"],
                upstream_path=path,
                upstream_sha256=sha256_path(path),
                feature_names=tuple(
                    f"source_feature_{index}"
                    for index in range(dimension)
                ),
                row_ids=tuple(row[0] for row in selected_rows),
                labels=tuple(row[1] for row in selected_rows),
                features=tuple(
                    tuple(row[2]) for row in selected_rows
                ),
            )
        )
    return datasets


def train_model(
    dataset: SourceDataset,
    roles: dict[str, list[int]],
    seed: int,
) -> dict[str, Any]:
    import numpy as np

    x = np.asarray(dataset.features, dtype=np.float64)
    y = np.asarray(dataset.labels, dtype=np.float64)
    train_indices = np.asarray(roles["model_training"], dtype=np.int64)
    x_train_raw = x[train_indices]
    y_train = y[train_indices]
    full_mean = x_train_raw.mean(axis=0)
    full_std = x_train_raw.std(axis=0)
    full_std = np.where(full_std == 0.0, 1.0, full_std)
    x_train_std = (x_train_raw - full_mean) / full_std

    centered_y = y_train - y_train.mean()
    y_norm = float(np.linalg.norm(centered_y))
    correlation = []
    for index in range(x_train_std.shape[1]):
        column = x_train_std[:, index]
        denominator = float(np.linalg.norm(column)) * y_norm
        value = (
            abs(float(np.dot(column, centered_y)) / denominator)
            if denominator > 0
            else 0.0
        )
        correlation.append(value)
    ranked = sorted(
        range(x_train_std.shape[1]),
        key=lambda index: (-correlation[index], index),
    )
    selected = sorted(ranked[: min(8, len(ranked))])
    x_train = x_train_std[:, selected]

    rng = np.random.Generator(np.random.PCG64(seed))
    hidden_units = 4
    w1 = rng.normal(0.0, 0.15, size=(hidden_units, len(selected)))
    b1 = np.zeros(hidden_units, dtype=np.float64)
    w2 = rng.normal(0.0, 0.15, size=hidden_units)
    b2 = 0.0
    mw1 = np.zeros_like(w1)
    vw1 = np.zeros_like(w1)
    mb1 = np.zeros_like(b1)
    vb1 = np.zeros_like(b1)
    mw2 = np.zeros_like(w2)
    vw2 = np.zeros_like(w2)
    mb2 = 0.0
    vb2 = 0.0
    beta1 = 0.9
    beta2 = 0.999
    learning_rate = 0.01
    epsilon = 1e-8
    l2 = 1e-4
    count = float(len(y_train))

    for epoch in range(1, 3001):
        affine = x_train @ w1.T + b1
        hidden = affine * affine
        logits = hidden @ w2 + b2
        probabilities = np.empty_like(logits)
        positive = logits >= 0
        probabilities[positive] = (
            1.0 / (1.0 + np.exp(-logits[positive]))
        )
        exponential = np.exp(logits[~positive])
        probabilities[~positive] = exponential / (1.0 + exponential)
        delta = (probabilities - y_train) / count
        grad_w2 = hidden.T @ delta + l2 * w2
        grad_b2 = float(delta.sum())
        grad_hidden = delta[:, None] * w2[None, :]
        grad_affine = grad_hidden * (2.0 * affine)
        grad_w1 = grad_affine.T @ x_train + l2 * w1
        grad_b1 = grad_affine.sum(axis=0)

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
        w1 -= (
            learning_rate
            * (mw1 / correction1)
            / (np.sqrt(vw1 / correction2) + epsilon)
        )
        b1 -= (
            learning_rate
            * (mb1 / correction1)
            / (np.sqrt(vb1 / correction2) + epsilon)
        )
        w2 -= (
            learning_rate
            * (mw2 / correction1)
            / (np.sqrt(vw2 / correction2) + epsilon)
        )
        b2 -= (
            learning_rate
            * (mb2 / correction1)
            / (math.sqrt(vb2 / correction2) + epsilon)
        )

    train_logits = (x_train @ w1.T + b1) ** 2 @ w2 + b2
    max_abs = float(np.max(np.abs(train_logits)))
    scale = 1.0 / max_abs if max_abs > 0 else 1.0
    scaled_w2 = w2 * scale
    scaled_b2 = b2 * scale

    return {
        "selected": selected,
        "selected_mean": full_mean[selected],
        "selected_std": full_std[selected],
        "raw": {
            "hidden_weights": w1,
            "hidden_bias": b1,
            "output_weights": w2,
            "output_bias": b2,
        },
        "scaled": {
            "hidden_weights": w1,
            "hidden_bias": b1,
            "output_weights": scaled_w2,
            "output_bias": scaled_b2,
        },
        "scale": scale,
        "correlation": correlation,
    }


def array_to_json(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return float(value)


def evaluate_rows(
    dataset: SourceDataset,
    indices: Sequence[int],
    trained: dict[str, Any],
) -> list[dict[str, Any]]:
    import numpy as np

    selected = trained["selected"]
    x = np.asarray(
        [
            [dataset.features[index][source] for source in selected]
            for index in indices
        ],
        dtype=np.float64,
    )
    normalized = (
        x - np.asarray(trained["selected_mean"])
    ) / np.asarray(trained["selected_std"])
    scaled = trained["scaled"]
    affine = (
        normalized @ scaled["hidden_weights"].T
        + scaled["hidden_bias"]
    )
    logits = (
        affine * affine
    ) @ scaled["output_weights"] + scaled["output_bias"]
    scores = 0.5 + 0.197 * logits
    rows = []
    for position, source_index in enumerate(indices):
        rows.append(
            {
                "source_index": source_index,
                "row_id": dataset.row_ids[source_index],
                "label": dataset.labels[source_index],
                "raw_selected": x[position].tolist(),
                "scaled_logit": float(logits[position]),
                "score": float(scores[position]),
                "decision": bool(scores[position] >= 0.5),
            }
        )
    return rows


def classification_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(
        int(row["decision"] == bool(row["label"]))
        for row in rows
    )
    margins = sorted(abs(row["score"] - 0.5) for row in rows)
    certifiable = sum(margin > 0.001 for margin in margins)
    return {
        "rows": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows),
        "minimum_margin": margins[0],
        "certifiable_at_margin_floor_0_001": certifiable,
        "ambiguous_at_margin_floor_0_001": len(rows) - certifiable,
    }


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def format_float(value: float) -> str:
    return format(float(value), ".17g")


def artifact_path(path: Path, output_root: Path) -> str:
    relative = path.relative_to(output_root)
    return (DEFAULT_OUTPUT / relative).as_posix()


def write_source_snapshot(root: Path, dataset: SourceDataset) -> Path:
    path = root / "source" / f"{dataset.dataset_id}.csv"
    fieldnames = ["row_id", "label"] + [
        f"x_{index}" for index in range(len(dataset.feature_names))
    ]
    rows = []
    for row_id, label, features in zip(
        dataset.row_ids,
        dataset.labels,
        dataset.features,
    ):
        row = {"row_id": row_id, "label": label}
        row.update(
            {
                f"x_{index}": format_float(value)
                for index, value in enumerate(features)
            }
        )
        rows.append(row)
    write_csv(path, fieldnames, rows)
    return path


def write_role_csv(
    path: Path,
    dataset: SourceDataset,
    rows: Sequence[dict[str, Any]],
    selected: Sequence[int],
) -> None:
    fields = ["row_id", "label"] + [
        f"x_{index}" for index in selected
    ]
    encoded = []
    for row in rows:
        record = {
            "row_id": row["row_id"],
            "label": row["label"],
        }
        record.update(
            {
                f"x_{source}": format_float(value)
                for source, value in zip(
                    selected,
                    row["raw_selected"],
                )
            }
        )
        encoded.append(record)
    write_csv(path, fields, encoded)


def build_suite(
    output_root: Path,
    sklearn_data_root: Path | None,
) -> None:
    data_root, sklearn_version, numpy_version = (
        resolve_sklearn_data_root(sklearn_data_root)
    )
    sources = load_sources(data_root)
    output_root.mkdir(parents=True)
    policy_digest = canonical_digest(POLICY)
    (output_root / "policy.json").write_bytes(
        canonical_json(
            {
                "policy": POLICY,
                "policy_digest": policy_digest,
            }
        )
    )

    source_registry = {
        "schema_version": SCHEMA_VERSION,
        "sklearn_version": sklearn_version,
        "numpy_version": numpy_version,
        "sklearn_data_module_relative_root": "sklearn/datasets/data",
        "sources": [],
    }
    source_snapshots = {}
    for dataset in sources:
        snapshot = write_source_snapshot(output_root, dataset)
        source_snapshots[dataset.dataset_id] = snapshot
        source_registry["sources"].append(
            {
                "dataset_id": dataset.dataset_id,
                "upstream_name": dataset.upstream_name,
                "upstream_sha256": dataset.upstream_sha256,
                "snapshot_path": artifact_path(snapshot, output_root),
                "snapshot_sha256": sha256_path(snapshot),
                "rows": len(dataset.row_ids),
                "features": len(dataset.feature_names),
            }
        )
    (output_root / "source_registry.json").write_bytes(
        canonical_json(source_registry)
    )

    summary_rows = []
    for seed in SEEDS:
        for dataset in sources:
            roles = assign_roles(dataset, seed)
            trained = train_model(dataset, roles, seed)
            target = (
                output_root
                / f"training_seed_{seed}"
                / dataset.dataset_id
                / MODEL_ID
            )
            target.mkdir(parents=True)
            evaluated = {
                role: evaluate_rows(dataset, indices, trained)
                for role, indices in roles.items()
            }
            validation_path = target / "configuration_validation.csv"
            audit_path = target / "locked_audit_test.csv"
            write_role_csv(
                validation_path,
                dataset,
                evaluated["configuration_validation"],
                trained["selected"],
            )
            write_role_csv(
                audit_path,
                dataset,
                evaluated["locked_audit"],
                trained["selected"],
            )
            model_path = target / "model.json"
            validation_summary = classification_summary(
                evaluated["configuration_validation"]
            )
            audit_summary = classification_summary(
                evaluated["locked_audit"]
            )
            training_summary = classification_summary(
                evaluated["model_training"]
            )
            model = {
                "dataset_id": dataset.dataset_id,
                "dataset_name": dataset.dataset_name,
                "model_id": MODEL_ID,
                "model_type": MODEL_ID,
                "task": "binary classification",
                "label_mapping": {
                    "0": "negative",
                    "1": "positive",
                },
                "random_state": seed,
                "training_seed": seed,
                "test_size": (
                    (
                        len(roles["configuration_validation"])
                        + len(roles["locked_audit"])
                    )
                    / len(dataset.row_ids)
                ),
                "train_samples": len(roles["model_training"]),
                "test_samples": (
                    len(roles["configuration_validation"])
                    + len(roles["locked_audit"])
                ),
                "selected_feature_indices": trained["selected"],
                "selected_feature_names": [
                    dataset.feature_names[index]
                    for index in trained["selected"]
                ],
                "input_dim": len(trained["selected"]),
                "standardization": {
                    "mean": [
                        float(value)
                        for value in trained["selected_mean"]
                    ],
                    "std": [
                        float(value)
                        for value in trained["selected_std"]
                    ],
                },
                "raw_model": {
                    name: array_to_json(value)
                    for name, value in trained["raw"].items()
                },
                "scaled_model_for_ckks": {
                    name: array_to_json(value)
                    for name, value in trained["scaled"].items()
                },
                "max_scaled_logit_target": 1.0,
                "polynomial_score": {
                    "formula": "0.5 + 0.197*z",
                    "decision_threshold": 0.5,
                },
                "training_protocol": {
                    "policy_id": POLICY_ID,
                    "policy_digest": policy_digest,
                    "optimizer": "full_batch_adam",
                    "epochs": 3000,
                    "hidden_units": 4,
                    "feature_rank_scores": [
                        float(value)
                        for value in trained["correlation"]
                    ],
                    "output_scale": float(trained["scale"]),
                    "locked_audit_used": False,
                },
                "metrics": {
                    "training": training_summary,
                    "configuration_validation": validation_summary,
                    "locked_audit_descriptive_only": audit_summary,
                },
            }
            model_path.write_bytes(canonical_json(model))
            split_manifest = {
                "schema_version": 1,
                "extension_schema_version": SCHEMA_VERSION,
                "algorithm": "sha256_stratified_rank_v1",
                "policy_id": POLICY_ID,
                "policy_digest": policy_digest,
                "split_seed": seed,
                "training_seed": seed,
                "dataset_id": dataset.dataset_id,
                "model_id": MODEL_ID,
                "source_snapshot": {
                    "path": artifact_path(
                        source_snapshots[dataset.dataset_id],
                        output_root,
                    ),
                    "sha256": sha256_path(
                        source_snapshots[dataset.dataset_id]
                    ),
                },
                "model_artifact": artifact_path(
                    model_path,
                    output_root,
                ),
                "model_artifact_digest": sha256_path(model_path),
                "model_training": {
                    "row_count": len(roles["model_training"]),
                    "row_ids": [
                        dataset.row_ids[index]
                        for index in roles["model_training"]
                    ],
                },
                "configuration_validation": {
                    "path": artifact_path(
                        validation_path,
                        output_root,
                    ),
                    "row_count": len(
                        roles["configuration_validation"]
                    ),
                    "csv_digest": sha256_path(validation_path),
                    "row_ids": [
                        dataset.row_ids[index]
                        for index in roles[
                            "configuration_validation"
                        ]
                    ],
                },
                "locked_audit_test": {
                    "path": artifact_path(
                        audit_path,
                        output_root,
                    ),
                    "row_count": len(roles["locked_audit"]),
                    "csv_digest": sha256_path(audit_path),
                    "row_ids": [
                        dataset.row_ids[index]
                        for index in roles["locked_audit"]
                    ],
                },
            }
            manifest_path = target / "split_manifest.json"
            manifest_path.write_bytes(canonical_json(split_manifest))
            metrics_path = target / "metrics.json"
            metrics_path.write_bytes(
                canonical_json(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "training_seed": seed,
                        "dataset_id": dataset.dataset_id,
                        "model_id": MODEL_ID,
                        "training": training_summary,
                        "configuration_validation":
                            validation_summary,
                        "locked_audit_descriptive_only":
                            audit_summary,
                    }
                )
            )
            summary_rows.append(
                {
                    "training_seed": seed,
                    "dataset_id": dataset.dataset_id,
                    "model_id": MODEL_ID,
                    "model_path": artifact_path(
                        model_path,
                        output_root,
                    ),
                    "model_sha256": sha256_path(model_path),
                    "split_manifest": artifact_path(
                        manifest_path,
                        output_root,
                    ),
                    "split_manifest_sha256": sha256_path(
                        manifest_path
                    ),
                    "training": training_summary,
                    "configuration_validation": validation_summary,
                    "locked_audit_descriptive_only": audit_summary,
                }
            )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "policy_digest": policy_digest,
        "dataset_count": len(DATASET_IDS),
        "training_seed_count": len(SEEDS),
        "instance_count": len(summary_rows),
        "model_id": MODEL_ID,
        "source_registry_sha256": sha256_path(
            output_root / "source_registry.json"
        ),
        "instances": summary_rows,
        "paper_claim_allowed": False,
    }
    (output_root / "summary.json").write_bytes(canonical_json(summary))
    checksum_lines = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            checksum_lines.append(
                f"{sha256_path(path).removeprefix('sha256:')}  "
                f"{path.relative_to(output_root).as_posix()}\n"
            )
    (output_root / "SHA256SUMS").write_text(
        "".join(checksum_lines),
        encoding="ascii",
    )


def main() -> None:
    args = parse_args()
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if output_root.exists() and not args.force:
        raise SystemExit(
            f"refusing to overwrite extension input: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_independent_seed_",
        dir=str(output_root.parent),
    ) as temporary:
        staging = Path(temporary) / "suite"
        build_suite(staging, args.sklearn_data_root)
        if output_root.exists():
            shutil.rmtree(output_root)
        staging.rename(output_root)
    summary = json.loads(
        (output_root / "summary.json").read_text(encoding="ascii")
    )
    print(
        "independent_training_seed_suite=BUILT "
        f"instances={summary['instance_count']} "
        f"policy_digest={summary['policy_digest']} "
        f"summary={sha256_path(output_root / 'summary.json')}"
    )


if __name__ == "__main__":
    main()
