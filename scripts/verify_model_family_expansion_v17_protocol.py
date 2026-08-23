#!/usr/bin/env python3
"""Fail-closed verifier for the frozen V17 protocol."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/protocols/model_family_expansion_v17"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = ["protocol.json", "protocol.md", "model_suite.csv", "candidate_space.json", "latency_subsets.json", "split_plan.csv", "AMENDMENTS.md", "SHA256SUMS"]
    for name in required:
        if not (PACK / name).is_file(): raise RuntimeError(f"missing {name}")
    for line in (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        if sha(PACK / name) != "sha256:" + expected: raise RuntimeError(f"checksum mismatch: {name}")
    protocol = json.loads((PACK / "protocol.json").read_text(encoding="ascii"))
    if protocol["protocol_state"] != "PROTOCOL_FROZEN" or protocol["rho"] != 0.5 or protocol["margin_floor"] != 0.001: raise RuntimeError("policy binding mismatch")
    if protocol["max_encrypted_candidate_evaluations"] != 4 or protocol["numerical_repair_scale_bits"] != 4 or protocol["level_repair_q_primes"] != 1: raise RuntimeError("direct repair policy mismatch")
    if protocol.get("expected_run_ledger_rows") != 204 or protocol.get("expected_maximum_candidate_evaluations") != 3496:
        raise RuntimeError("declared execution population mismatch")
    if "repeated_key_instability" not in protocol.get("all_required_metrics", []):
        raise RuntimeError("repeated-key instability metric is not frozen")
    for name, item in protocol.get("smoke_gate", {}).items():
        path = ROOT / item.get("path", "")
        if not path.is_file() or sha(path) != item.get("sha256"):
            raise RuntimeError(f"smoke artifact drift: {name}")
    candidates = json.loads((PACK / "candidate_space.json").read_text(encoding="ascii"))
    if candidates["B3_scale_offsets_bits"] != [0, 4, 8, 12] or candidates["B3_level_guards"] != [0, 1] or candidates["model_name_lookup"]: raise RuntimeError("candidate generator mismatch")
    if candidates.get("B0_profile") != "default__rescale" or candidates.get("B2_rows_per_tabular_case") != 14 or candidates.get("B2_paths") != ["rescale", "non-rescale"]:
        raise RuntimeError("legacy baseline declaration mismatch")
    with (PACK / "model_suite.csv").open(newline="", encoding="ascii") as handle: models = list(csv.DictReader(handle))
    if len(models) != 8 or sum(row["role"].startswith("PRIMARY_P") for row in models) != 6: raise RuntimeError("model suite incomplete")
    with (PACK / "split_plan.csv").open(newline="", encoding="ascii") as handle: splits = list(csv.DictReader(handle))
    if len(splits) != 119: raise RuntimeError(f"split plan has {len(splits)} rows")
    for row in splits:
        path = ROOT / row["manifest"]
        if sha(path) != row["manifest_sha256"]: raise RuntimeError(f"split manifest drift: {path}")
        parent = path.parent
        for filename, field in (
            ("model.json", "model_sha256"),
            ("configuration_selection.csv", "selection_sha256"),
            ("independent_evaluation.csv", "independent_sha256"),
        ):
            artifact = parent / filename
            if not artifact.is_file() or sha(artifact) != row[field]:
                raise RuntimeError(f"split-bound artifact drift: {artifact}")
    payload = "".join(f"{item['path']}\0{item['sha256']}\n" for item in protocol["execution_critical_sources"]).encode("ascii")
    if "sha256:" + hashlib.sha256(payload).hexdigest() != protocol["execution_critical_source_digest"]: raise RuntimeError("source closure digest mismatch")
    for item in protocol["execution_critical_sources"]:
        if sha(ROOT / item["path"]) != item["sha256"]: raise RuntimeError(f"execution source drift: {item['path']}")
    expected_binaries = {
        "flipguard-v17-tabular-case", "flipguard-v17-depth-ladder",
        "flipguard-v17-packed-cnn-case", "flipguard-v17-multiclass-exhaustive",
        "flipguard-v17-multiclass-seed-case",
        "flipguard-v17-tabular-paired-latency",
        "flipguard-v17-primary-paired-latency",
    }
    binaries = protocol.get("execution_binaries", [])
    if {item["name"] for item in binaries} != expected_binaries:
        raise RuntimeError("execution binary inventory mismatch")
    for item in binaries:
        path = ROOT / item["path"]
        if not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            raise RuntimeError(f"execution binary drift: {item['name']}")
    for item in protocol.get("input_bindings", []):
        path = ROOT / item["path"]
        if not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            raise RuntimeError(f"bound input drift: {item['path']}")
    if len(protocol.get("input_bindings", [])) != 67:
        raise RuntimeError("bound input inventory mismatch")
    analysis_binaries = protocol.get("analysis_binaries", [])
    if {item.get("name") for item in analysis_binaries} != {"flipguard-v17-mnist-train", "flipguard-v17-plaintext-quality"}:
        raise RuntimeError("analysis binary inventory mismatch")
    for item in analysis_binaries:
        path = ROOT / item["path"]
        if item.get("encrypted_execution") is not False or not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            raise RuntimeError(f"analysis binary drift: {item.get('name')}")
    subsets = json.loads((PACK / "latency_subsets.json").read_text(encoding="ascii"))
    if subsets.get("result_independent") is not True or len(subsets.get("subsets", [])) != 3:
        raise RuntimeError("P4/P5/P6 latency subset declaration mismatch")
    for subset in subsets["subsets"]:
        if len(subset.get("row_ids", [])) != 20 or len(set(subset["row_ids"])) != 20:
            raise RuntimeError(f"latency subset population mismatch: {subset.get('id')}")
        data = ROOT / subset["data_path"]
        if not data.is_file() or sha(data) != subset["data_sha256"]:
            raise RuntimeError(f"latency subset data drift: {subset.get('id')}")
    normalization = json.loads((ROOT / "results/model_family_expansion_v17/plaintext/multiclass_training_seed/path_normalization_manifest.json").read_text(encoding="ascii"))
    if normalization.get("model_count") != 6:
        raise RuntimeError("multiclass path-normalization population mismatch")
    for record in normalization.get("records", []):
        if record.get("semantic_sha256") != record.get("semantic_sha256_after") or not record.get("numeric_payload_unchanged"):
            raise RuntimeError("multiclass path normalization changed model semantics")
        model = json.loads((ROOT / record["path"]).read_text(encoding="ascii"))
        split_field = "split_manifest" if "split_manifest" in model else "input_split_manifest"
        if Path(model["source"]["path"]).is_absolute() or Path(model[split_field]["path"]).is_absolute():
            raise RuntimeError("absolute local path remains in multiclass model artifact")
    status_path = ROOT / "results/model_family_expansion_v17/plaintext/multiclass_training_seed/run_status.csv"
    if sha(status_path) != normalization.get("run_status_sha256_after"):
        raise RuntimeError("multiclass training status drift after path normalization")
    with status_path.open(newline="", encoding="utf-8") as handle:
        status_rows = list(csv.DictReader(handle))
    if len(status_rows) != 6:
        raise RuntimeError("multiclass training status population mismatch")
    for row in status_rows:
        if sha(ROOT / row["model_path"]) != row["model_sha256"]:
            raise RuntimeError(f"multiclass training status model digest mismatch: {row['model_path']}")
    training_summary = json.loads((ROOT / "results/model_family_expansion_v17/plaintext/multiclass_training_seed/summary.json").read_text(encoding="ascii"))
    trainer = next(item for item in analysis_binaries if item.get("name") == "flipguard-v17-mnist-train")
    if training_summary.get("binary_sha256") != trainer.get("sha256"):
        raise RuntimeError("multiclass training binary binding mismatch")
    print(f"PASS: V17 protocol {sha(PACK / 'protocol.json')}")


if __name__ == "__main__":
    main()
