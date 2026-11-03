#!/usr/bin/env python3
"""Freeze validation-only analysis rules before reading locked-audit results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA = "flipguard_journal_multiclass_analysis_plan_v1"
PROTOCOL_DIGEST = "sha256:caf39e2b38f8c1a46bb1fece30d68d758b613e2459e51e6af9898e535620b269"
MODELS = {
    "mlp_100": "mnist_mlp_square_784_100_10_v1",
    "lenet5_small": "mnist_lenet5_small_square_v1",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validation_gaps(key_run: dict) -> list[float]:
    if key_run["key_run"] != 1:
        raise ValueError("analysis-plan source must be fresh-key run 1")
    records = key_run["records"]
    if len(records) != 500:
        raise ValueError(f"expected 500 validation records, found {len(records)}")
    if {record["role"] for record in records} != {"configuration_validation"}:
        raise ValueError("analysis-plan source includes a non-validation row")
    sample_ids = [record["sample_id"] for record in records]
    if len(set(sample_ids)) != 500:
        raise ValueError("validation sample identity is not unique")
    return sorted(float(record["top_two_gap"]) for record in records)


def midpoint_boundaries(values: list[float], bins: int = 5) -> list[float]:
    if len(values) % bins:
        raise ValueError("equal-count bins require a divisible validation population")
    stride = len(values) // bins
    boundaries = []
    for index in range(1, bins):
        left = values[index * stride - 1]
        right = values[index * stride]
        boundaries.append(left + (right - left) / 2.0)
    return boundaries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="docs/evidence/journal_multiclass_analysis_plan_v1",
    )
    parser.add_argument("--selection-source-commit", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing analysis plan {output}")
    encrypted = root / "results/journal_multiclass_extension_v1/encrypted"

    models = {}
    inputs = {}
    for short_name, model_id in MODELS.items():
        result_root = encrypted / model_id
        selection_path = result_root / "selection_result.json"
        selection = load(selection_path)
        if selection["source_commit"] != args.selection_source_commit:
            raise SystemExit(f"{short_name} selection source commit mismatch")
        selected = selection["result"]["selected"]
        trial_root = result_root / f"trial_01_{selected['id']}"
        key_path = trial_root / "key_run_01.json"
        gaps = validation_gaps(load(key_path))
        boundaries = midpoint_boundaries(gaps)
        models[short_name] = {
            "model_id": model_id,
            "candidate_id": selected["id"],
            "validation_sample_count": len(gaps),
            "target_samples_per_bin": len(gaps) // 5,
            "top_two_gap_min": gaps[0],
            "top_two_gap_max": gaps[-1],
            "boundary_values": boundaries,
            "interval_rule": "(-inf,b1],(b1,b2],...,(b4,+inf)",
        }
        inputs[short_name] = {
            "selection_result": {
                "path": str(selection_path.relative_to(root)),
                "sha256": sha256(selection_path),
            },
            "validation_key_run_01": {
                "path": str(key_path.relative_to(root)),
                "sha256": sha256(key_path),
            },
        }

    plan = {
        "schema_version": SCHEMA,
        "status": "FROZEN_BEFORE_LOCKED_AUDIT_ANALYSIS",
        "selection_execution_commit": args.selection_source_commit,
        "protocol_manifest_digest": PROTOCOL_DIGEST,
        "audit_artifact_used_to_choose_rules": False,
        "gap_bin_policy": {
            "id": "validation_plaintext_gap_empirical_quintiles_v1",
            "bin_count": 5,
            "derivation_population": "500 unique configuration-validation samples per model",
            "key_repeat_accounting": "fresh-key run 1 only; repeated keys are not independent samples",
            "boundary_method": "midpoint between adjacent order statistics at ranks 100, 200, 300, and 400",
            "audit_policy": "replay frozen model-specific boundaries without rebucketing",
        },
        "models": models,
        "reported_metrics": [
            "sample_count",
            "fresh_key_observations",
            "plaintext_accuracy",
            "ckks_accuracy",
            "argmax_flips",
            "reserve_policy_rejections",
            "maximum_pairwise_error",
            "maximum_cap_required",
        ],
        "classwise_policy": "report all ten plaintext classes; do not suppress an empty or negative class row",
        "natural_activation_outcomes": [
            "A_LITERAL_EFFECT_SUPPORTED",
            "B_ADMISSION_EFFECT_ONLY",
            "C_NO_OBSERVED_ACTIVATION",
        ],
        "inputs": inputs,
    }

    output.mkdir(parents=True)
    write_json(output / "analysis_plan.json", plan)
    manifest = {
        "schema_version": SCHEMA,
        "publication_role": "validation-derived analysis overlay; no encrypted evidence is modified",
        "selection_execution_commit": args.selection_source_commit,
        "analysis_plan": {
            "path": "analysis_plan.json",
            "sha256": sha256(output / "analysis_plan.json"),
        },
    }
    write_json(output / "manifest.json", manifest)
    checksum_names = ["analysis_plan.json", "manifest.json"]
    lines = [f"{sha256(output / name)[7:]}  {name}" for name in checksum_names]
    (output / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"wrote {output.relative_to(root)}")
    print("analysis_plan_sha256=" + sha256(output / "analysis_plan.json"))


if __name__ == "__main__":
    main()
