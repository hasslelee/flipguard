#!/usr/bin/env python3
"""Export a deterministic MNIST binary CNN-lite holdout.

The exporter intentionally uses only the Python standard library. The model is
trained from the official MNIST training partition, while the locked audit is
drawn from the official test partition and never enters training, scaling, or
configuration selection.
"""

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
from typing import Any, Iterable, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "results/source_datasets/mnist/mnist_784.arff.gz"
)
DEFAULT_OUTPUT = Path(
    "datasets/vision_suite/mnist/cnn_lite_square_binary01"
)
LOGICAL_OUTPUT = DEFAULT_OUTPUT

SCHEMA_VERSION = "flipguard_mnist_cnn_lite_holdout_v1"
EXTRACTION_POLICY_ID = "mnist_binary01_cnn_lite_export_v1"
MODEL_ID = "cnn_lite_square_binary01"
MODEL_TYPE = "cnn_lite_square_binary01"
GRAPH_ADAPTER_ID = "mnist_cnn_lite_scalar_replicated_graph_adapter_v1"

SOURCE_URL = "https://www.openml.org/d/554"
ORIGINAL_SOURCE_URL = "https://yann.lecun.com/exdb/mnist/"
EXPECTED_SOURCE_SHA256 = (
    "fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78"
)
OFFICIAL_TRAIN_ROWS = 60000
OFFICIAL_TEST_ROWS = 10000

MODEL_DEVELOPMENT_PER_CLASS = 125
CONFIGURATION_VALIDATION_PER_CLASS = 125
LOCKED_AUDIT_PER_CLASS = 125

INPUT_SIDE = 4
POOL_SIDE = 7
FILTER_SIDE = 2
FILTER_COUNT = 4
CONV_SIDE = INPUT_SIDE - FILTER_SIDE + 1
TRAINING_EPOCHS = 24
BATCH_SIZE = 64
LEARNING_RATE = 0.01
ADAM_BETA1 = 0.9
ADAM_BETA2 = 0.999
ADAM_EPSILON = 1e-8
L2_PENALTY = 1e-4
MODEL_SEED = 0x464C495047554152
MAX_ABS_TRAIN_SCORE = 1.0

DIRECT_POLICY_ID = "flipguard_direct_synthesis_policy_v2"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)

PIXEL_COLUMNS = tuple(
    f"pool{row}{column}"
    for row in range(INPUT_SIDE)
    for column in range(INPUT_SIDE)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def policy_spec() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "policy_id": EXTRACTION_POLICY_ID,
        "source_dataset": "MNIST",
        "source_url": SOURCE_URL,
        "original_source_url": ORIGINAL_SOURCE_URL,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "official_partition_boundary": {
            "train_rows": OFFICIAL_TRAIN_ROWS,
            "test_rows": OFFICIAL_TEST_ROWS,
        },
        "task": {
            "included_digits": [0, 1],
            "negative_digit": 0,
            "positive_digit": 1,
            "decision_threshold": 0.0,
        },
        "input_transform": {
            "method": "nonoverlapping_7x7_mean_pool_v1",
            "source_shape": [28, 28],
            "output_shape": [4, 4],
            "normalization": "pixel/255",
        },
        "selection": {
            "method": "label_stratified_sha256_rank_v1",
            "model_development_per_class": (
                MODEL_DEVELOPMENT_PER_CLASS
            ),
            "configuration_validation_per_class": (
                CONFIGURATION_VALIDATION_PER_CLASS
            ),
            "locked_audit_per_class": LOCKED_AUDIT_PER_CLASS,
        },
        "training": {
            "scope": (
                "official_train_digit_0_or_1_excluding_model_development_"
                "and_configuration_validation"
            ),
            "model_seed": MODEL_SEED,
            "epochs": TRAINING_EPOCHS,
            "batch_size": BATCH_SIZE,
            "optimizer": "deterministic_adam_v1",
            "learning_rate": LEARNING_RATE,
            "beta1": ADAM_BETA1,
            "beta2": ADAM_BETA2,
            "epsilon": ADAM_EPSILON,
            "l2_penalty": L2_PENALTY,
            "shuffle": "splitmix64_fisher_yates_v1",
            "score_scaling": {
                "source": "training_rows_only",
                "target_max_abs": MAX_ABS_TRAIN_SCORE,
            },
        },
        "model": {
            "input_shape": [4, 4],
            "convolution_filters": FILTER_COUNT,
            "kernel_shape": [2, 2],
            "stride": 1,
            "padding": "valid",
            "activation": "square",
            "head": "linear_binary_score",
            "packing_scope": "scalar_replicated_per_ciphertext_v1",
        },
        "roles": {
            "model_development": (
                "train_partition_plaintext_diagnostic_only"
            ),
            "configuration_validation": (
                "train_partition_encrypted_candidate_selection"
            ),
            "locked_audit": "test_partition_no_retuning",
        },
    }


def policy_digest() -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json(policy_spec())
    ).hexdigest()


def stable_rank(source_index: int, label: int, role: str) -> bytes:
    return hashlib.sha256(
        (
            EXTRACTION_POLICY_ID
            + "\0"
            + role
            + "\0"
            + str(label)
            + "\0"
            + str(source_index)
        ).encode("ascii")
    ).digest()


def pooled_pixels(raw: Sequence[int]) -> tuple[float, ...]:
    if len(raw) != 28 * 28:
        raise ValueError(f"MNIST row has {len(raw)} pixels, expected 784")
    values: list[float] = []
    for output_row in range(INPUT_SIDE):
        for output_column in range(INPUT_SIDE):
            total = 0
            for row in range(
                output_row * POOL_SIDE,
                (output_row + 1) * POOL_SIDE,
            ):
                start = row * 28 + output_column * POOL_SIDE
                total += sum(raw[start : start + POOL_SIDE])
            values.append(total / (POOL_SIDE * POOL_SIDE * 255.0))
    return tuple(values)


def iter_arff_rows(
    source: Path,
) -> Iterator[tuple[int, tuple[float, ...], int]]:
    data_started = False
    source_index = 0
    with gzip.open(source, "rt", encoding="ascii", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not data_started:
                if stripped.lower() == "@data":
                    data_started = True
                continue
            if not stripped or stripped.startswith("%"):
                continue
            fields = stripped.split(",")
            if len(fields) != 785:
                raise ValueError(
                    f"ARFF line {line_number} has {len(fields)} fields"
                )
            try:
                label = int(fields[-1])
            except ValueError as error:
                raise ValueError(
                    f"invalid MNIST label at ARFF line {line_number}"
                ) from error
            if label in (0, 1):
                try:
                    raw = tuple(int(value) for value in fields[:-1])
                except ValueError as error:
                    raise ValueError(
                        f"invalid MNIST pixel at ARFF line {line_number}"
                    ) from error
                if any(value < 0 or value > 255 for value in raw):
                    raise ValueError(
                        f"out-of-range MNIST pixel at row {source_index}"
                    )
                yield source_index, pooled_pixels(raw), label
            source_index += 1
    expected = OFFICIAL_TRAIN_ROWS + OFFICIAL_TEST_ROWS
    if source_index != expected:
        raise ValueError(
            f"MNIST source has {source_index} rows, expected {expected}"
        )


def split_rows(
    rows: Iterable[tuple[int, tuple[float, ...], int]],
) -> dict[str, list[tuple[int, tuple[float, ...], int]]]:
    train_by_label: dict[int, list[tuple[int, tuple[float, ...], int]]] = {
        0: [],
        1: [],
    }
    test_by_label: dict[int, list[tuple[int, tuple[float, ...], int]]] = {
        0: [],
        1: [],
    }
    for row in rows:
        destination = (
            train_by_label
            if row[0] < OFFICIAL_TRAIN_ROWS
            else test_by_label
        )
        destination[row[2]].append(row)

    result: dict[str, list[tuple[int, tuple[float, ...], int]]] = {
        "training": [],
        "model_development": [],
        "configuration_validation": [],
        "locked_audit": [],
    }
    for label in (0, 1):
        ranked_train = sorted(
            train_by_label[label],
            key=lambda row: stable_rank(
                row[0],
                label,
                "official_train_role_rank",
            ),
        )
        development_end = MODEL_DEVELOPMENT_PER_CLASS
        validation_end = (
            development_end + CONFIGURATION_VALIDATION_PER_CLASS
        )
        if len(ranked_train) <= validation_end:
            raise ValueError(
                f"not enough official training rows for digit {label}"
            )
        result["model_development"].extend(
            ranked_train[:development_end]
        )
        result["configuration_validation"].extend(
            ranked_train[development_end:validation_end]
        )
        result["training"].extend(ranked_train[validation_end:])

        ranked_test = sorted(
            test_by_label[label],
            key=lambda row: stable_rank(
                row[0],
                label,
                "official_test_audit_rank",
            ),
        )
        if len(ranked_test) < LOCKED_AUDIT_PER_CLASS:
            raise ValueError(
                f"not enough official test rows for digit {label}"
            )
        result["locked_audit"].extend(
            ranked_test[:LOCKED_AUDIT_PER_CLASS]
        )

    for role in result:
        result[role].sort(key=lambda row: row[0])
    return result


class SplitMix64:
    def __init__(self, state: int) -> None:
        self.state = state & 0xFFFFFFFFFFFFFFFF

    def next_u64(self) -> int:
        self.state = (
            self.state + 0x9E3779B97F4A7C15
        ) & 0xFFFFFFFFFFFFFFFF
        value = self.state
        value = (
            (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9
        ) & 0xFFFFFFFFFFFFFFFF
        value = (
            (value ^ (value >> 27)) * 0x94D049BB133111EB
        ) & 0xFFFFFFFFFFFFFFFF
        return value ^ (value >> 31)

    def uniform(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))


def shuffled_indices(count: int, epoch: int) -> list[int]:
    indices = list(range(count))
    generator = SplitMix64(MODEL_SEED ^ epoch)
    for upper in range(count - 1, 0, -1):
        selected = generator.next_u64() % (upper + 1)
        indices[upper], indices[selected] = (
            indices[selected],
            indices[upper],
        )
    return indices


def parameter_count() -> int:
    return (
        FILTER_COUNT * FILTER_SIDE * FILTER_SIDE
        + FILTER_COUNT
        + FILTER_COUNT * CONV_SIDE * CONV_SIDE
        + 1
    )


def parameter_offsets() -> tuple[int, int, int, int]:
    filter_weight_end = FILTER_COUNT * FILTER_SIDE * FILTER_SIDE
    filter_bias_end = filter_weight_end + FILTER_COUNT
    output_weight_end = (
        filter_bias_end + FILTER_COUNT * CONV_SIDE * CONV_SIDE
    )
    return 0, filter_weight_end, filter_bias_end, output_weight_end


def initial_parameters() -> list[float]:
    templates = (
        (-0.5, 0.5, -0.5, 0.5),
        (-0.5, -0.5, 0.5, 0.5),
        (0.5, -0.5, -0.5, 0.5),
        (-0.5, 0.5, 0.5, -0.5),
    )
    values = [
        coefficient
        for template in templates
        for coefficient in template
    ]
    values.extend(0.0 for _ in range(FILTER_COUNT))
    generator = SplitMix64(MODEL_SEED)
    output_count = FILTER_COUNT * CONV_SIDE * CONV_SIDE
    values.extend(
        (generator.uniform() - 0.5) * 0.1
        for _ in range(output_count)
    )
    values.append(0.0)
    if len(values) != parameter_count():
        raise AssertionError("CNN-lite parameter count changed")
    return values


def convolution_hidden(
    features: Sequence[float],
    parameters: Sequence[float],
) -> list[float]:
    if len(features) != INPUT_SIDE * INPUT_SIDE:
        raise ValueError("CNN-lite input must contain 16 pooled pixels")
    _, filter_weight_end, _, _ = parameter_offsets()
    hidden: list[float] = []
    for filter_index in range(FILTER_COUNT):
        bias = parameters[filter_weight_end + filter_index]
        weight_base = filter_index * FILTER_SIDE * FILTER_SIDE
        for row in range(CONV_SIDE):
            for column in range(CONV_SIDE):
                value = bias
                for kernel_row in range(FILTER_SIDE):
                    for kernel_column in range(FILTER_SIDE):
                        input_index = (
                            (row + kernel_row) * INPUT_SIDE
                            + column
                            + kernel_column
                        )
                        weight_index = (
                            weight_base
                            + kernel_row * FILTER_SIDE
                            + kernel_column
                        )
                        value += (
                            parameters[weight_index]
                            * features[input_index]
                        )
                hidden.append(value)
    return hidden


def cnn_score(
    features: Sequence[float],
    parameters: Sequence[float],
) -> float:
    hidden = convolution_hidden(features, parameters)
    _, _, output_weight_start, output_bias_index = parameter_offsets()
    score = parameters[output_bias_index]
    for index, value in enumerate(hidden):
        score += parameters[output_weight_start + index] * value * value
    return score


def sigmoid(value: float) -> float:
    if value >= 0:
        factor = math.exp(-value)
        return 1.0 / (1.0 + factor)
    factor = math.exp(value)
    return factor / (1.0 + factor)


def sample_gradient(
    features: Sequence[float],
    label: int,
    parameters: Sequence[float],
) -> list[float]:
    hidden = convolution_hidden(features, parameters)
    _, filter_weight_end, output_weight_start, output_bias_index = (
        parameter_offsets()
    )
    score = parameters[output_bias_index]
    for index, value in enumerate(hidden):
        score += parameters[output_weight_start + index] * value * value
    output_derivative = sigmoid(score) - label

    gradient = [0.0] * len(parameters)
    gradient[output_bias_index] = output_derivative
    for hidden_index, hidden_value in enumerate(hidden):
        output_weight_index = output_weight_start + hidden_index
        gradient[output_weight_index] = (
            output_derivative * hidden_value * hidden_value
        )
        filter_index = hidden_index // (CONV_SIDE * CONV_SIDE)
        position = hidden_index % (CONV_SIDE * CONV_SIDE)
        row = position // CONV_SIDE
        column = position % CONV_SIDE
        hidden_derivative = (
            output_derivative
            * parameters[output_weight_index]
            * 2.0
            * hidden_value
        )
        gradient[filter_weight_end + filter_index] += hidden_derivative
        weight_base = filter_index * FILTER_SIDE * FILTER_SIDE
        for kernel_row in range(FILTER_SIDE):
            for kernel_column in range(FILTER_SIDE):
                input_index = (
                    (row + kernel_row) * INPUT_SIDE
                    + column
                    + kernel_column
                )
                weight_index = (
                    weight_base
                    + kernel_row * FILTER_SIDE
                    + kernel_column
                )
                gradient[weight_index] += (
                    hidden_derivative * features[input_index]
                )
    return gradient


def train_model(
    rows: Sequence[tuple[int, tuple[float, ...], int]],
) -> tuple[list[float], dict[str, Any]]:
    if not rows:
        raise ValueError("CNN-lite training rows are empty")
    parameters = initial_parameters()
    first_moment = [0.0] * len(parameters)
    second_moment = [0.0] * len(parameters)
    update_step = 0
    output_bias_index = parameter_offsets()[3]

    for epoch in range(TRAINING_EPOCHS):
        indices = shuffled_indices(len(rows), epoch)
        for batch_start in range(0, len(indices), BATCH_SIZE):
            batch = indices[batch_start : batch_start + BATCH_SIZE]
            gradient = [0.0] * len(parameters)
            for row_index in batch:
                _, features, label = rows[row_index]
                sample = sample_gradient(features, label, parameters)
                for index, value in enumerate(sample):
                    gradient[index] += value
            inverse_batch = 1.0 / len(batch)
            for index in range(len(gradient)):
                gradient[index] *= inverse_batch
                if index != output_bias_index:
                    gradient[index] += (
                        L2_PENALTY * parameters[index]
                    )

            update_step += 1
            beta1_correction = 1.0 - ADAM_BETA1 ** update_step
            beta2_correction = 1.0 - ADAM_BETA2 ** update_step
            for index, value in enumerate(gradient):
                first_moment[index] = (
                    ADAM_BETA1 * first_moment[index]
                    + (1.0 - ADAM_BETA1) * value
                )
                second_moment[index] = (
                    ADAM_BETA2 * second_moment[index]
                    + (1.0 - ADAM_BETA2) * value * value
                )
                corrected_first = (
                    first_moment[index] / beta1_correction
                )
                corrected_second = (
                    second_moment[index] / beta2_correction
                )
                parameters[index] -= LEARNING_RATE * corrected_first / (
                    math.sqrt(corrected_second) + ADAM_EPSILON
                )

    raw_scores = [
        cnn_score(features, parameters)
        for _, features, _ in rows
    ]
    raw_max_abs = max(abs(value) for value in raw_scores)
    if not math.isfinite(raw_max_abs) or raw_max_abs <= 0:
        raise ValueError("CNN-lite training produced invalid scores")
    score_scale = MAX_ABS_TRAIN_SCORE / raw_max_abs
    for index in range(
        parameter_offsets()[2],
        parameter_offsets()[3] + 1,
    ):
        parameters[index] *= score_scale
    if any(not math.isfinite(value) for value in parameters):
        raise ValueError("CNN-lite training produced non-finite parameter")
    return parameters, {
        "optimizer_updates": update_step,
        "raw_training_max_abs_score": raw_max_abs,
        "score_scale": score_scale,
        "scaled_training_max_abs_score": max(
            abs(cnn_score(features, parameters))
            for _, features, _ in rows
        ),
    }


def classification_metrics(
    rows: Sequence[tuple[int, tuple[float, ...], int]],
    parameters: Sequence[float],
) -> dict[str, Any]:
    scores = [
        cnn_score(features, parameters)
        for _, features, _ in rows
    ]
    correct = sum(
        int((score >= 0.0) == bool(row[2]))
        for score, row in zip(scores, rows)
    )
    margins = sorted(abs(score) for score in scores)
    return {
        "rows": len(rows),
        "accuracy": correct / len(rows),
        "correct": correct,
        "incorrect": len(rows) - correct,
        "positive_labels": sum(row[2] for row in rows),
        "negative_labels": len(rows) - sum(row[2] for row in rows),
        "positive_decisions": sum(score >= 0.0 for score in scores),
        "negative_decisions": sum(score < 0.0 for score in scores),
        "minimum_margin": min(margins),
        "median_margin": margins[len(margins) // 2],
        "maximum_margin": max(margins),
    }


def structured_parameters(
    parameters: Sequence[float],
) -> dict[str, Any]:
    _, filter_weight_end, output_weight_start, output_bias_index = (
        parameter_offsets()
    )
    filters = []
    for filter_index in range(FILTER_COUNT):
        weight_base = filter_index * FILTER_SIDE * FILTER_SIDE
        filters.append(
            {
                "weights": [
                    list(
                        parameters[
                            weight_base + row * FILTER_SIDE :
                            weight_base + (row + 1) * FILTER_SIDE
                        ]
                    )
                    for row in range(FILTER_SIDE)
                ],
                "bias": parameters[
                    filter_weight_end + filter_index
                ],
            }
        )
    output_weights = []
    for filter_index in range(FILTER_COUNT):
        base = (
            output_weight_start
            + filter_index * CONV_SIDE * CONV_SIDE
        )
        output_weights.append(
            [
                list(
                    parameters[
                        base + row * CONV_SIDE :
                        base + (row + 1) * CONV_SIDE
                    ]
                )
                for row in range(CONV_SIDE)
            ]
        )
    return {
        "convolution_filters": filters,
        "output_weights": output_weights,
        "output_bias": parameters[output_bias_index],
    }


def flatten_parameters(model: dict[str, Any]) -> list[float]:
    values: list[float] = []
    learned = model["learned_parameters"]
    for item in learned["convolution_filters"]:
        for row in item["weights"]:
            values.extend(float(value) for value in row)
    values.extend(
        float(item["bias"])
        for item in learned["convolution_filters"]
    )
    for matrix in learned["output_weights"]:
        for row in matrix:
            values.extend(float(value) for value in row)
    values.append(float(learned["output_bias"]))
    if len(values) != parameter_count():
        raise ValueError("serialized CNN-lite parameter count changed")
    return values


def write_partition(
    path: Path,
    rows: Sequence[tuple[int, tuple[float, ...], int]],
    source_partition: str,
    parameters: Sequence[float],
    source_digest: str,
    extraction_digest: str,
) -> None:
    fieldnames = [
        "row_id",
        "sample_id",
        "source_partition",
        "digit_label",
        "binary_label",
        *PIXEL_COLUMNS,
        "plaintext_score",
        "decision_threshold",
        "decision_margin",
        "plaintext_decision",
        "source_sha256",
        "extraction_policy_digest",
    ]
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for source_index, features, label in rows:
            score = cnn_score(features, parameters)
            record: dict[str, Any] = {
                "row_id": source_index,
                "sample_id": f"mnist_{source_index:05d}",
                "source_partition": source_partition,
                "digit_label": label,
                "binary_label": label,
                "plaintext_score": format(score, ".17g"),
                "decision_threshold": "0",
                "decision_margin": format(abs(score), ".17g"),
                "plaintext_decision": (
                    "true" if score >= 0.0 else "false"
                ),
                "source_sha256": source_digest,
                "extraction_policy_digest": extraction_digest,
            }
            for name, value in zip(PIXEL_COLUMNS, features):
                record[name] = format(value, ".17g")
            writer.writerow(record)


def build_artifacts(source: Path, output_root: Path) -> None:
    source_digest = "sha256:" + sha256_path(source)
    if source_digest != "sha256:" + EXPECTED_SOURCE_SHA256:
        raise ValueError(
            f"MNIST source digest changed: {source_digest}"
        )
    partitions = split_rows(iter_arff_rows(source))
    parameters, training_summary = train_model(partitions["training"])
    extraction_digest = policy_digest()

    metrics = {
        "training": classification_metrics(
            partitions["training"],
            parameters,
        ),
        "model_development": classification_metrics(
            partitions["model_development"],
            parameters,
        ),
        "configuration_validation": classification_metrics(
            partitions["configuration_validation"],
            parameters,
        ),
        "locked_audit": classification_metrics(
            partitions["locked_audit"],
            parameters,
        ),
    }
    model = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "mnist_binary01",
        "dataset_name": "MNIST digit 0 versus digit 1",
        "model_id": MODEL_ID,
        "model_type": MODEL_TYPE,
        "graph_adapter_id": GRAPH_ADAPTER_ID,
        "graph_formula": (
            "linear_head(square(valid_conv2x2(mean_pool7x7(image))))"
        ),
        "input_dim": INPUT_SIDE * INPUT_SIDE,
        "input_shape": [INPUT_SIDE, INPUT_SIDE],
        "decision_threshold": 0.0,
        "packing_scope": "scalar_replicated_per_ciphertext_v1",
        "source_archive": {
            "url": SOURCE_URL,
            "original_url": ORIGINAL_SOURCE_URL,
            "sha256": source_digest,
        },
        "extraction_policy_id": EXTRACTION_POLICY_ID,
        "extraction_policy_digest": extraction_digest,
        "architecture": {
            "input_shape": [INPUT_SIDE, INPUT_SIDE],
            "convolution_filters": FILTER_COUNT,
            "kernel_shape": [FILTER_SIDE, FILTER_SIDE],
            "stride": 1,
            "padding": "valid",
            "activation": "square",
            "output_shape_before_head": [
                FILTER_COUNT,
                CONV_SIDE,
                CONV_SIDE,
            ],
            "linear_head_outputs": 1,
        },
        "learned_parameters": structured_parameters(parameters),
        "training": {
            **policy_spec()["training"],
            "training_rows": len(partitions["training"]),
            "model_development_rows": len(
                partitions["model_development"]
            ),
            **training_summary,
            "model_development_metrics": metrics[
                "model_development"
            ],
        },
        "direct_policy_reference": {
            "policy_id": DIRECT_POLICY_ID,
            "policy_digest": DIRECT_POLICY_DIGEST,
            "relationship": (
                "frozen_constants_reused_by_predeclared_graph_adapter;"
                "model_type_not_added_to_policy_supported_models"
            ),
        },
        "claim_scope": {
            "supports": (
                "one scalar-replicated learned MNIST binary CNN-lite graph"
            ),
            "does_not_support": [
                "packed CNN performance",
                "general LeNet support",
                "arbitrary CNN architectures",
                "multiclass encrypted argmax",
                "universal autotuning",
            ],
        },
    }
    model_path = output_root / "model.json"
    model_path.write_bytes(canonical_json(model))
    model_digest = "sha256:" + sha256_path(model_path)

    validation_path = output_root / "configuration_validation.csv"
    audit_path = output_root / "locked_audit_test.csv"
    write_partition(
        validation_path,
        partitions["configuration_validation"],
        "train",
        parameters,
        source_digest,
        extraction_digest,
    )
    write_partition(
        audit_path,
        partitions["locked_audit"],
        "test",
        parameters,
        source_digest,
        extraction_digest,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "extraction_policy_id": EXTRACTION_POLICY_ID,
        "extraction_policy_digest": extraction_digest,
        "source_archive": {
            "path": str(DEFAULT_SOURCE),
            "sha256": source_digest,
        },
        "model": {
            "path": str(LOGICAL_OUTPUT / "model.json"),
            "sha256": model_digest,
        },
        "partitions": {
            "training": {
                "role": "model_training_only",
                "rows": len(partitions["training"]),
                "source_partition": "train",
                "exported": False,
            },
            "model_development": {
                "role": "plaintext_development_diagnostic_only",
                "rows": len(partitions["model_development"]),
                "source_partition": "train",
                "exported": False,
                "metrics": metrics["model_development"],
            },
            "configuration_validation": {
                "role": "encrypted_candidate_selection",
                "path": str(
                    LOGICAL_OUTPUT / "configuration_validation.csv"
                ),
                "sha256": "sha256:" + sha256_path(validation_path),
                "source_partition": "train",
                "metrics": metrics["configuration_validation"],
            },
            "locked_audit_test": {
                "role": "no_retuning_locked_audit",
                "path": str(LOGICAL_OUTPUT / "locked_audit_test.csv"),
                "sha256": "sha256:" + sha256_path(audit_path),
                "source_partition": "test",
                "metrics": metrics["locked_audit"],
            },
        },
        "training_metrics": metrics["training"],
        "audit_noninterference": {
            "training_uses_audit_rows": False,
            "score_scaling_uses_audit_rows": False,
            "hyperparameter_selection_uses_audit_rows": False,
            "candidate_selection_uses_audit_rows": False,
            "audit_result_may_modify_policy": False,
        },
    }
    manifest_path = output_root / "extraction_manifest.json"
    manifest_path.write_bytes(canonical_json(manifest))

    checksums = []
    for name in (
        "configuration_validation.csv",
        "extraction_manifest.json",
        "locked_audit_test.csv",
        "model.json",
    ):
        checksums.append(
            f"{sha256_path(output_root / name)}  {name}\n"
        )
    (output_root / "SHA256SUMS").write_text(
        "".join(checksums),
        encoding="ascii",
    )


def verify(source: Path, output_root: Path) -> None:
    if not output_root.is_dir():
        raise ValueError(f"artifact root is missing: {output_root}")
    with tempfile.TemporaryDirectory(
        prefix="flipguard_mnist_cnn_replay_"
    ) as temporary:
        replay = Path(temporary) / "artifact"
        replay.mkdir()
        build_artifacts(source, replay)
        expected_files = {
            path.relative_to(output_root)
            for path in output_root.rglob("*")
            if path.is_file()
        }
        replay_files = {
            path.relative_to(replay)
            for path in replay.rglob("*")
            if path.is_file()
        }
        if expected_files != replay_files:
            raise ValueError(
                "MNIST CNN-lite replay file set changed: "
                f"expected={sorted(map(str, expected_files))} "
                f"replay={sorted(map(str, replay_files))}"
            )
        for relative in sorted(expected_files):
            expected = output_root / relative
            observed = replay / relative
            if expected.read_bytes() != observed.read_bytes():
                raise ValueError(
                    f"MNIST CNN-lite source replay mismatch: {relative}"
                )


def main() -> None:
    args = parse_args()
    source = (
        args.source
        if args.source.is_absolute()
        else REPO_ROOT / args.source
    )
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if args.verify:
        verify(source, output_root)
        print(
            "mnist_cnn_lite_source_replay=PASS "
            f"policy_digest={policy_digest()}"
        )
        return
    if output_root.exists() and not args.force:
        raise SystemExit(
            f"refusing to overwrite existing artifact: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_mnist_cnn_export_",
        dir=str(output_root.parent),
    ) as temporary:
        staging = Path(temporary) / "artifact"
        staging.mkdir()
        build_artifacts(source, staging)
        if output_root.exists():
            shutil.rmtree(output_root)
        staging.rename(output_root)
    print(
        f"mnist_cnn_lite_artifact={output_root} "
        f"policy_digest={policy_digest()}"
    )


if __name__ == "__main__":
    main()
