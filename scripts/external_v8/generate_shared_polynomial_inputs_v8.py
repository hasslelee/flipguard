#!/usr/bin/env python3
"""Generate the frozen V8 shared-polynomial validation and audit inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


SEED = "flipguard-focused-external-v8-shared-polynomial-20260807"
TOTAL = 1000
ROLE_SIZE = 500
THRESHOLD = 0.5


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def uniform(counter: int, coordinate: int) -> float:
    payload = f"{SEED}:{counter:04d}:{coordinate}".encode("ascii")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return 2.0 * (integer + 0.5) / 2**64 - 1.0


def row(index: int) -> dict[str, object]:
    values = [uniform(index, coordinate) for coordinate in range(3)]
    z = 0.8 * values[0] - 0.5 * values[1] + 1.2 * values[2] - 0.3
    score = 0.5 + 0.197 * z - 0.004 * z**3
    if not all(math.isfinite(value) for value in (*values, z, score)):
        raise ValueError(f"non-finite generated row {index}")
    decision = score >= THRESHOLD
    return {
        "row_id": index,
        "label": int(decision),
        "raw_logit": format(z, ".17g"),
        "scaled_logit": format(z, ".17g"),
        "polynomial_score": format(score, ".17g"),
        "plaintext_decision": str(decision),
        "x_0": format(values[0], ".17g"),
        "x_1": format(values[1], ".17g"),
        "x_2": format(values[2], ".17g"),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0])
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite frozen V8 inputs: {output}")
    output.mkdir(parents=True)

    rows = [row(index) for index in range(TOTAL)]
    validation = rows[:ROLE_SIZE]
    audit = rows[ROLE_SIZE:]
    validation_path = output / "configuration_validation.csv"
    audit_path = output / "locked_audit.csv"
    write_csv(validation_path, validation)
    write_csv(audit_path, audit)

    validation_ids = {str(item["row_id"]) for item in validation}
    audit_ids = {str(item["row_id"]) for item in audit}
    overlap = sorted(validation_ids & audit_ids)
    if overlap:
        raise ValueError(f"validation/audit overlap: {overlap[:3]}")
    if len(validation_ids) != ROLE_SIZE or len(audit_ids) != ROLE_SIZE:
        raise ValueError("generated input IDs are not unique")

    latency_indices = [index * (ROLE_SIZE - 1) // 99 for index in range(100)]
    latency_ids = [str(ROLE_SIZE + index) for index in latency_indices]
    manifest = {
        "schema_version": "flipguard_focused_external_v8_input_manifest_v1",
        "workload_id": "shared_polynomial_threshold_v8",
        "generator": "sha256_counter_uniform_open_interval_v1",
        "seed": SEED,
        "domain": {"x_0": [-1.0, 1.0], "x_1": [-1.0, 1.0], "x_2": [-1.0, 1.0]},
        "total_unique_inputs": TOTAL,
        "validation_unique_inputs": ROLE_SIZE,
        "audit_unique_inputs": ROLE_SIZE,
        "overlap": 0,
        "assignment": "ordered rows 0000-0499 validation; 0500-0999 locked audit",
        "validation": {"path": validation_path.name, "sha256": sha256_path(validation_path)},
        "audit": {"path": audit_path.name, "sha256": sha256_path(audit_path)},
        "latency_subset": {
            "role": "locked_audit",
            "selection_rule": "100 evenly spaced ordered rows including both endpoints",
            "unique_inputs": 100,
            "row_ids": latency_ids,
        },
        "threshold": THRESHOLD,
        "result_independent": True,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    model_path = output.parents[1] / "workload_contracts/shared_polynomial_model_v8.json"
    split_manifest = {
        "schema_version": 1,
        "split_seed": 20260807,
        "dataset_id": "shared_polynomial_threshold_v8",
        "model_id": "shared_polynomial_linear_poly3_v8",
        "model_artifact_digest": sha256_path(model_path),
        "configuration_validation": {
            "path": str(validation_path.relative_to(Path.cwd())),
            "csv_digest": sha256_path(validation_path),
            "row_ids": sorted(validation_ids),
        },
        "locked_audit_test": {
            "path": str(audit_path.relative_to(Path.cwd())),
            "csv_digest": sha256_path(audit_path),
            "row_ids": sorted(audit_ids),
        },
        "latency_subset": {
            "source_partition": "locked_audit_test",
            "selection_rule": "100 evenly spaced ordered rows including both endpoints",
            "row_ids": latency_ids,
        },
    }
    split_path = output / "split_manifest.json"
    split_path.write_text(
        json.dumps(split_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums = [
        f"{sha256_path(path).removeprefix('sha256:')}  {path.name}"
        for path in (validation_path, audit_path, manifest_path, split_path)
    ]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
