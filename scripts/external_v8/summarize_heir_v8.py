#!/usr/bin/env python3
"""Verify and summarize frozen HEIR shared-polynomial executions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROLES = ("configuration_validation", "locked_audit")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def truth(value: object) -> bool:
    return str(value).lower() in {"1", "true"}


def summarize(rows: list[dict[str, object]], role: str) -> dict[str, object]:
    if len(rows) != 1500:
        raise RuntimeError(f"INTEGRITY_BLOCK: {role} expected 1500 observations, got {len(rows)}")
    row_ids = {str(row["row_id"]) for row in rows}
    contexts = {int(row["context"]) for row in rows}
    if len(row_ids) != 500 or contexts != {1, 2, 3}:
        raise RuntimeError(f"INTEGRITY_BLOCK: {role} input/context coverage drift")
    for row in rows:
        values = [float(row[key]) for key in ("plaintext", "decrypted", "absolute_error", "margin", "normalized_budget_usage")]
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"non-finite HEIR result at {row['row_id']}")
    return {
        "role": role,
        "unique_inputs": len(row_ids),
        "fresh_contexts": len(contexts),
        "raw_observations": len(rows),
        "decision_flips": sum(truth(row["decision_flip"]) for row in rows),
        "reserve_policy_violations": sum(truth(row["reserve_violation"]) for row in rows),
        "max_absolute_error": max(float(row["absolute_error"]) for row in rows),
        "max_normalized_budget_usage": max(float(row["normalized_budget_usage"]) for row in rows),
    }


def parse_lattigo_parameters(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    q_match = re.search(r"Q:\s*\[\]uint64\{([^}]*)\}", source)
    p_match = re.search(r"P:\s*\[\]uint64\{([^}]*)\}", source)
    logn_match = re.search(r"LogN:\s*(\d+)", source)
    scale_match = re.search(r"LogDefaultScale:\s*(\d+)", source)
    if not all((q_match, p_match, logn_match, scale_match)):
        raise RuntimeError("cannot parse generated HEIR Lattigo parameters")
    parse = lambda match: [int(item.strip()) for item in match.group(1).split(",") if item.strip()]
    q = parse(q_match)
    p = parse(p_match)
    log_n = int(logn_match.group(1))
    log_q = sum(math.log2(value) for value in q)
    log_p = sum(math.log2(value) for value in p)
    cap = {12: 106, 13: 214, 14: 430, 15: 868}.get(log_n)
    return {
        "log_n": log_n,
        "q_primes": q,
        "p_primes": p,
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_q + log_p,
        "log_default_scale": int(scale_match.group(1)),
        "security_v2_cap": cap,
        "ciphertext_q_admission": "PASS" if cap is not None and log_q <= cap else "FAIL",
        "evaluation_key_qp_admission": "PASS" if cap is not None and log_q + log_p <= cap else "FAIL",
        "final_admission": "PASS" if cap is not None and log_q + log_p <= cap else "FAIL",
        "headroom_bits": cap - (log_q + log_p) if cap is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    translation = ROOT / "external/v8/translations/heir-shared-polynomial-v8"
    summaries: dict[str, object] = {}
    for runtime, loader, suffix in (("lattigo_v6_2", load_jsonl, "jsonl"), ("openfhe", load_csv, "csv")):
        role_summaries = []
        role_ids: dict[str, set[str]] = {}
        for role in EXPECTED_ROLES:
            rows = loader(output / f"{'lattigo' if runtime.startswith('lattigo') else 'openfhe'}_{role}.{suffix}")
            role_summaries.append(summarize(rows, role))
            role_ids[role] = {str(row["row_id"]) for row in rows}
        if role_ids[EXPECTED_ROLES[0]] & role_ids[EXPECTED_ROLES[1]]:
            raise RuntimeError(f"INTEGRITY_BLOCK: {runtime} validation/audit overlap")
        summaries[runtime] = role_summaries
    parameters = parse_lattigo_parameters(translation / "lattigo_v6_2/sharedpoly/shared_polynomial.go")
    manifest = {
        "schema_version": "flipguard_focused_external_v8_heir_result_v1",
        "status": "PASS",
        "provider": "Google HEIR",
        "provider_commit": "cb7a7a30bb4d995b50e33bb5cd82ff7434db3656",
        "workload": "shared_polynomial_threshold_v8",
        "graph_equivalence": "EXACT_OPERATION_ORDER",
        "validation_unique_inputs": 500,
        "audit_unique_inputs": 500,
        "overlap": 0,
        "fresh_contexts_per_runtime_role": 3,
        "runtime_summaries": summaries,
        "lattigo_v6_2_parameters": parameters,
        "security_policy_v2": "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "retuning": 0,
        "translation_manifest_sha256": sha256(translation / "manifest.json"),
    }
    if parameters["final_admission"] != "PASS":
        raise RuntimeError("INTEGRITY_BLOCK: HEIR Lattigo translation is not Security V2 admitted")
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise RuntimeError("HEIR result manifest drift on resume")
    else:
        partial = manifest_path.with_suffix(".json.partial")
        partial.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        partial.replace(manifest_path)
    checksums = [
        f"{sha256(path)[7:]}  {path.relative_to(output).as_posix()}"
        for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"
    ]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
