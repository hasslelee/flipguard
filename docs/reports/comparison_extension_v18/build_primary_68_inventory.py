#!/usr/bin/env python3
"""Build the exact V18 primary-68 manuscript inventory from locked ledgers."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs/reports/comparison_extension_v18"
V18 = ROOT / "results/comparison_extension_v18"
V17 = ROOT / "results/model_family_expansion_v17/final_vm1x6"

EXPECTED_V18_PAYLOAD = "884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded"

MODEL_METADATA = {
    "linear_poly3": {
        "model_family": "linear body with cubic output",
        "graph_family": "shallow polynomial binary graph",
        "decision_rule": "binary threshold",
    },
    "mlp_square_linear_score": {
        "model_family": "one-hidden-layer square MLP",
        "graph_family": "shallow nonlinear fully connected graph",
        "decision_rule": "binary threshold",
    },
    "mlp_square2_linear_score": {
        "model_family": "two-hidden-layer square MLP",
        "graph_family": "medium-depth nonlinear fully connected graph",
        "decision_rule": "binary threshold",
    },
    "mnist_mlp_square_784_100_10_v1": {
        "model_family": "MNIST MLP-100",
        "graph_family": "wide multiclass fully connected graph",
        "decision_rule": "multiclass argmax",
    },
    "mnist_lenet5_small_square_v1": {
        "model_family": "FHE-compatible LeNet-5-small",
        "graph_family": "multiclass convolutional graph",
        "decision_rule": "multiclass argmax",
    },
    "packed_cnn_lite_binary01_v17": {
        "model_family": "packed CNN-lite",
        "graph_family": "rotation-heavy packed binary convolutional graph",
        "decision_rule": "binary threshold",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def training_seed(split_id: str) -> str:
    marker = "training_seed_"
    return split_id.split(marker, 1)[1] if marker in split_id else "NOT_SEPARATELY_VARIED_IN_PRIMARY_CASE"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPORT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    cases = [row for row in read_csv(V18 / "case_level_ledger.csv") if row["scope"] == "primary"]
    stability = {row["case_id"]: row for row in read_csv(REPORT / "V18_STABILITY_COST_TABLE.csv")}
    selected_rows = [row for row in read_csv(V17 / "table_07_selected_configurations.csv") if row["phase"] == "primary"]
    selected = {
        f"{row['phase']}|{row['dataset']}|{row['model_id']}|{row['split_id']}": row
        for row in selected_rows
    }
    formal_rows = read_csv(V17 / "table_05_formal_paired_latency.csv")
    formal = {(row["model_id"], row["direct_candidate_id"]): row for row in formal_rows}

    assert len(cases) == len({row["case_id"] for row in cases}) == 68
    assert set(stability) == {row["case_id"] for row in cases}
    assert set(selected) == {row["case_id"] for row in cases}
    assert len(formal_rows) == len(formal) == 68

    inventory: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda row: row["case_id"]):
        case_id = case["case_id"]
        selected_row = selected[case_id]
        cost = stability[case_id]
        formal_row = formal[(case["model_id"], case["c1_candidate_id"])]
        metadata = MODEL_METADATA[case["model_id"]]
        changed = case["c1_candidate_id"] != case["c2_candidate_id"]
        inventory.append(
            {
                "case_id": case_id,
                "dataset": case["dataset"],
                "model_id": case["model_id"],
                "model_family": metadata["model_family"],
                "graph_family": metadata["graph_family"],
                "split_id": case["split_id"],
                "training_seed": training_seed(case["split_id"]),
                "decision_rule": metadata["decision_rule"],
                "packing_strategy": selected_row["packing_strategy"],
                "rotations": int(selected_row["rotations"]),
                "multiplicative_depth": int(selected_row["multiplicative_depth"]),
                "gate_off_candidate": case["c2_candidate_id"],
                "full_method_selected_candidate": case["c1_candidate_id"],
                "configuration_changed": changed,
                "gate_off_candidate_evaluations": int(case["c2_candidate_evaluations"]),
                "full_method_candidate_evaluations": int(case["c1_candidate_evaluations"]),
                "added_candidate_evaluations": int(case["c1_candidate_evaluations"]) - int(case["c2_candidate_evaluations"]),
                "gate_off_selection_flips": int(case["c2_selection_flips"]),
                "gate_off_reserve_policy_violations": int(case["c2_selection_violations"]),
                "gate_off_separate_input_outcome": case["c2_separate_status"],
                "full_method_separate_input_outcome": case["c1_separate_status"],
                "gate_off_log_n": int(cost["gate_off_log_n"]),
                "full_method_log_n": int(cost["full_log_n"]),
                "gate_off_q_bits": cost["gate_off_q_bits"],
                "full_method_q_bits": cost["full_q_bits"],
                "gate_off_q_chain_length": int(cost["gate_off_q_chain_length"]),
                "full_method_q_chain_length": int(cost["full_q_chain_length"]),
                "gate_off_p_bits": cost["gate_off_p_bits"],
                "full_method_p_bits": cost["full_p_bits"],
                "gate_off_scale_bits": int(cost["gate_off_scale_bits"]),
                "full_method_scale_bits": int(cost["full_scale_bits"]),
                "gate_off_path": cost["gate_off_path"],
                "full_method_path": cost["full_path"],
                "formal_latency_row_bound": True,
                "formal_latency_status": formal_row["status"],
                "formal_latency_pairs": int(float(formal_row["pairs"])),
                "formal_latency_record": formal_row["path"],
                "formal_reference_candidate": formal_row["finite_candidate_id"],
            }
        )

    assert sum(row["gate_off_candidate_evaluations"] for row in inventory) == 68
    assert sum(row["full_method_candidate_evaluations"] for row in inventory) == 89
    assert sum(int(row["configuration_changed"]) for row in inventory) == 21
    assert Counter(row["added_candidate_evaluations"] for row in inventory) == Counter({0: 47, 1: 21})
    assert sum(row["full_method_scale_bits"] - row["gate_off_scale_bits"] == 4 for row in inventory) == 21
    assert sum(row["full_method_q_chain_length"] - row["gate_off_q_chain_length"] == 1 for row in inventory) == 0
    assert sum(row["full_method_log_n"] != row["gate_off_log_n"] for row in inventory) == 0
    assert Counter(row["full_method_separate_input_outcome"] for row in inventory) == Counter({"SAFE": 68})
    assert sum(row["formal_latency_row_bound"] for row in inventory) == 68
    assert sum(int(row["c6_finite_evaluations"]) for row in cases) == 537

    write_csv(output / "PRIMARY_68_CASE_INVENTORY.csv", inventory)

    model_counts = Counter((row["model_id"], row["model_family"]) for row in inventory)
    dataset_model_counts = Counter((row["dataset"], row["model_id"]) for row in inventory)
    split_counts = Counter(row["split_id"] for row in inventory)
    model_lines = "\n".join(
        f"| `{model}` | {family} | {count} |"
        for (model, family), count in sorted(model_counts.items())
    )
    dataset_lines = "\n".join(
        f"| `{dataset}` | `{model}` | {count} |"
        for (dataset, model), count in sorted(dataset_model_counts.items())
    )
    split_lines = "\n".join(
        f"| `{split}` | {count} |" for split, count in sorted(split_counts.items())
    )
    markdown = f"""# Primary 68 Case Inventory

Status: `PRIMARY_68_INVENTORY_VERIFIED`

## Unit definition

An evaluation case fixes one dataset, model or computation graph, and split or
training condition, then asks the method to select one CKKS configuration. A
candidate evaluation is a different unit: it executes one candidate over the
case's complete configuration-selection inputs and three independent key sets.
The 68 primary cases therefore do not mean 68 candidate pools or 68 distinct
parameter literals.

## Exact accounting

- Unique primary evaluation cases: **68**
- Gate-off candidate evaluations: **68**
- Full-method candidate evaluations: **89**
- Finite-reference candidate evaluations: **537**
- Changed configurations: **21**
- Exactly one additional candidate evaluation: **21**
- Two or more additional evaluations: **0**
- Scale +4 bit changes: **21**
- Q-prime additions: **0**
- LogN changes: **0**
- Q-chain-length changes: **0**
- Full-method separate-input PASS: **68/68**
- Formal-latency row bindings: **68/68**
- Overall / primary unique parameter literals: **16 / 7**

## Model-family composition

| Internal model ID | Paper-facing family | Cases |
|---|---|---:|
{model_lines}

## Dataset-model composition

| Dataset | Model ID | Cases |
|---|---|---:|
{dataset_lines}

## Split composition

| Split or fixed evaluation condition | Cases |
|---|---:|
{split_lines}

## Binding

- V18 package payload SHA-256: `{EXPECTED_V18_PAYLOAD}`
- Case ledger SHA-256: `{sha256(V18 / 'case_level_ledger.csv')}`
- V17 selected-configuration table SHA-256: `{sha256(V17 / 'table_07_selected_configurations.csv')}`
- V17 formal-latency table SHA-256: `{sha256(V17 / 'table_05_formal_paired_latency.csv')}`

Every exact case ID, before/after candidate identity, selected literal,
selection result, separate-input outcome, and formal-latency record binding is
preserved in `PRIMARY_68_CASE_INVENTORY.csv`.
"""
    (output / "PRIMARY_68_CASE_INVENTORY.md").write_text(markdown, encoding="utf-8")
    print("PRIMARY_68_INVENTORY_BUILD_PASS cases=68 evaluations=89 finite=537 formal=68")


if __name__ == "__main__":
    main()
