#!/usr/bin/env python3
"""Create balanced non-claim-bearing tabular smoke roles from one frozen fold."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/model_family_expansion_v17/plaintext/primary/banknote/mlp_square2_linear_score/fold_0/training_seed_0"
OUTPUT = ROOT / "results/model_family_expansion_v17/smoke/inputs/tabular_p3_banknote_fold0"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def subset(name: str, per_label: int) -> dict:
    source = SOURCE / f"{name}.csv"
    with source.open(newline="", encoding="ascii") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    selected = []
    for label in sorted({row["label"] for row in rows}):
        candidates = [row for row in rows if row["label"] == label]
        candidates.sort(key=lambda row: (hashlib.sha256(f"v17-tabular-smoke:{name}:{row['row_id']}".encode("ascii")).hexdigest(), int(row["row_id"])))
        selected.extend(candidates[:per_label])
    selected.sort(key=lambda row: int(row["row_id"]))
    target = OUTPUT / f"{name}.csv"
    with target.open("x", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)
    return {"role": name, "source": source.relative_to(ROOT).as_posix(), "source_sha256": digest(source), "path": target.relative_to(ROOT).as_posix(), "sha256": digest(target), "rows": len(selected)}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=False)
    roles = [subset("configuration_selection", 4), subset("independent_evaluation", 4)]
    model = SOURCE / "model.json"
    payload = {"schema_version": "flipguard_v17_tabular_smoke_inputs_v1", "purpose": "SMOKE_ONLY_NOT_CLAIM_BEARING", "model": model.relative_to(ROOT).as_posix(), "model_sha256": digest(model), "roles": roles}
    (OUTPUT / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "rows": [item["rows"] for item in roles]}, sort_keys=True))


if __name__ == "__main__":
    main()
