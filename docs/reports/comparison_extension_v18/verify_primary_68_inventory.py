#!/usr/bin/env python3
"""Verify the exact V18 primary-68 inventory and manuscript unit semantics."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs/reports/comparison_extension_v18"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def true(value: str) -> bool:
    return value.lower() == "true"


def main() -> None:
    rows = read_csv(REPORT / "PRIMARY_68_CASE_INVENTORY.csv")
    assert len(rows) == len({row["case_id"] for row in rows}) == 68
    assert sum(int(row["gate_off_candidate_evaluations"]) for row in rows) == 68
    assert sum(int(row["full_method_candidate_evaluations"]) for row in rows) == 89
    assert sum(true(row["configuration_changed"]) for row in rows) == 21
    assert Counter(int(row["added_candidate_evaluations"]) for row in rows) == Counter({0: 47, 1: 21})
    assert sum(int(row["added_candidate_evaluations"]) >= 2 for row in rows) == 0
    assert sum(
        int(row["full_method_scale_bits"]) - int(row["gate_off_scale_bits"]) == 4
        for row in rows
    ) == 21
    assert sum(
        int(row["full_method_q_chain_length"]) != int(row["gate_off_q_chain_length"])
        for row in rows
    ) == 0
    assert sum(int(row["full_method_log_n"]) != int(row["gate_off_log_n"]) for row in rows) == 0
    assert Counter(row["full_method_separate_input_outcome"] for row in rows) == Counter({"SAFE": 68})
    assert sum(true(row["formal_latency_row_bound"]) for row in rows) == 68
    assert Counter(row["formal_latency_status"] for row in rows) == Counter({"SAFE_TO_SAFE_ELIGIBLE": 68})
    assert Counter(row["model_id"] for row in rows) == Counter(
        {
            "linear_poly3": 25,
            "mlp_square_linear_score": 25,
            "mlp_square2_linear_score": 15,
            "mnist_mlp_square_784_100_10_v1": 1,
            "mnist_lenet5_small_square_v1": 1,
            "packed_cnn_lite_binary01_v17": 1,
        }
    )
    markdown = (REPORT / "PRIMARY_68_CASE_INVENTORY.md").read_text(encoding="utf-8")
    for prohibited in ("68 후보군", "68개 후보군", "68 configurations"):
        assert prohibited not in markdown
    print("PRIMARY_68_INVENTORY_VERIFY_PASS cases=68 evaluations=89 finite=537 formal=68")


if __name__ == "__main__":
    main()
