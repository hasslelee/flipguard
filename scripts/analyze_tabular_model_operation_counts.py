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

MODELS = [
    "linear_poly3",
    "mlp_square_linear_score",
]

MODEL_ROOT = Path("datasets/tabular_suite")
SELECTED_PATH = Path("results/ckks_tabular_profile_sweep_summary/current/selected_profiles.csv")
OUTPUT_ROOT = Path("results/ckks_tabular_operation_analysis/current")


def read_selected_profiles():
    with SELECTED_PATH.open("r", newline="") as f:
        rows = list(csv.DictReader(f))

    return {
        (row["dataset_id"], row["model_id"]): row
        for row in rows
    }


def load_model(dataset_id, model_id):
    path = MODEL_ROOT / dataset_id / model_id / "model.json"
    return json.loads(path.read_text(encoding="utf-8"))


def count_linear_poly3(model):
    input_dim = int(model["input_dim"])

    return {
        "input_dim": input_dim,
        "hidden_units": 0,
        "encrypted_input_ciphertexts": input_dim,
        "output_ciphertexts": 1,
        "ciphertext_ciphertext_multiplications": 2,
        "ciphertext_plaintext_multiplications": input_dim + 2,
        "ciphertext_additions": input_dim + 2,
        "rotations": 0,
        "approximate_multiplicative_depth": 2,
        "notes": "linear score followed by cubic output polynomial",
    }


def count_mlp_square_linear_score(model):
    input_dim = int(model["input_dim"])
    hidden_units = len(model["scaled_model_for_ckks"]["hidden_weights"])

    return {
        "input_dim": input_dim,
        "hidden_units": hidden_units,
        "encrypted_input_ciphertexts": input_dim,
        "output_ciphertexts": 1,
        "ciphertext_ciphertext_multiplications": hidden_units,
        "ciphertext_plaintext_multiplications": hidden_units * input_dim + hidden_units + 1,
        "ciphertext_additions": hidden_units * input_dim + hidden_units + 1,
        "rotations": 0,
        "approximate_multiplicative_depth": 1,
        "notes": "square-activation MLP with affine output score",
    }


def count_model(model):
    model_type = model["model_type"]

    if model_type == "linear_poly3":
        return count_linear_poly3(model)

    if model_type == "mlp_square_linear_score":
        return count_mlp_square_linear_score(model)

    raise ValueError(f"unsupported model_type: {model_type}")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_latex(rows):
    lines = []
    lines.append(r"\begin{tabular}{llrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Dataset & Model & Input & Hidden & Ct-Ct Mul. & Rot. & Depth \\")
    lines.append(r"\midrule")

    for row in rows:
        dataset = row["dataset_id"].replace("_", r"\_")
        model = row["model_id"].replace("_", r"\_")
        lines.append(
            f"{dataset} & {model} & {row['input_dim']} & {row['hidden_units']} & "
            f"{row['ciphertext_ciphertext_multiplications']} & {row['rotations']} & "
            f"{row['approximate_multiplicative_depth']} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    (OUTPUT_ROOT / "operation_count_table.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_readme(rows):
    text = """FlipGuard tabular operation analysis

This file summarizes logical encrypted inference operation counts for each exported tabular workload.

Important scope:
- The counts are logical operation counts, not measured hardware memory usage.
- Rotations are zero because the current evaluator encrypts one replicated scalar per ciphertext instead of using SIMD-packed vector slots.
- The analysis is useful for explaining model complexity and ciphertext operation structure.
- Actual memory and communication measurement should be added separately if needed.
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    selected = read_selected_profiles()
    rows = []

    for dataset_id in DATASETS:
        for model_id in MODELS:
            model = load_model(dataset_id, model_id)
            counts = count_model(model)
            selected_row = selected.get((dataset_id, model_id), {})

            row = {
                "dataset_id": dataset_id,
                "model_id": model_id,
                "model_type": model["model_type"],
                "selected_profile": selected_row.get("selected_profile", ""),
                "selected_path": selected_row.get("selected_path", ""),
            }
            row.update({key: str(value) for key, value in counts.items()})
            rows.append(row)

    write_rows(OUTPUT_ROOT / "operation_counts.csv", rows)
    write_latex(rows)
    write_readme(rows)

    print(f"wrote {OUTPUT_ROOT / 'operation_counts.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'operation_count_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
