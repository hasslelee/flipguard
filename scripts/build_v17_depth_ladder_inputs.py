#!/usr/bin/env python3
"""Freeze the D1/D2/D4/D6/D8 bounded-domain plaintext stress inputs."""

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/model_family_expansion_v17/depth_ladder/inputs"
DEPTHS = (1, 2, 4, 6, 8)
INPUTS = (-0.02, -0.015, -0.01, -0.005, 0.005, 0.01, 0.015, 0.02)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = []
    for depth in DEPTHS:
        directory = OUTPUT / f"D{depth}"
        directory.mkdir(parents=True, exist_ok=True)
        model_path = directory / "model.json"
        data_path = directory / "configuration_selection.csv"
        if model_path.exists() or data_path.exists():
            raise FileExistsError(directory)
        model = {
            "schema_version": "flipguard_v17_depth_ladder_v1",
            "model_id": f"v17_depth_ladder_d{depth}",
            "multiplicative_depth": depth,
            "graph": "repeated_square(x)",
            "input_domain": [0.98, 1.02],
            "input_semantics": "x_0 is the repeated-square base",
            "decision_threshold": 1.0,
            "decision_rule": "score>=1.0",
        }
        model_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="ascii")
        with data_path.open("w", newline="", encoding="ascii") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["row_id", "x_0", "plaintext_score", "plaintext_decision"])
            for row_id, delta in enumerate(INPUTS):
                base = 1.0 + delta
                score = base ** (2**depth)
                writer.writerow([row_id, format(base, ".17g"), format(score, ".17g"), str(score >= 1).lower()])
        records.append({
            "depth": depth,
            "model": model_path.relative_to(ROOT).as_posix(),
            "model_sha256": digest(model_path),
            "data": data_path.relative_to(ROOT).as_posix(),
            "data_sha256": digest(data_path),
            "rows": len(INPUTS),
        })
    manifest = OUTPUT / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "flipguard_v17_depth_ladder_inputs_v1",
        "depths": list(DEPTHS),
        "shared_delta_domain": list(INPUTS),
        "decision_threshold": 1.0,
        "records": records,
        "result_independent": True,
    }, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "depths": list(DEPTHS), "rows_per_depth": len(INPUTS)}, sort_keys=True))


if __name__ == "__main__":
    main()
