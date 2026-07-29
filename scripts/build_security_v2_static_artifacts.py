#!/usr/bin/env python3
"""Build or verify Security Policy V2 static re-attestation artifacts.

This tool performs no encryption. It materializes parameter literals, replays
published-cap admission, and filters the completed bounded-catalog records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/security_v2_static_attestation"
)
DIRECT_RESULTS = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_floor18_keys3/results"
)
ORACLE_SUMMARY = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/"
    "full/summary"
)
PAIRED_ARMS = Path(
    "docs/evidence/paired_latency_pilot_v1/summary/arm_summaries.csv"
)
V2_LIMITS = {12: 106, 13: 214, 14: 430, 15: 868}
OLD_LIMITS = {12: 108, 13: 217, 14: 438, 15: 881}
REFERENCE_CANDIDATE_V2 = "deep_chain_8_scale45__rescale_aware"

CSV_FIELDS = [
    "record_kind",
    "candidate_source",
    "candidate_id",
    "profile",
    "path",
    "split_seed",
    "dataset_id",
    "model_id",
    "log_n",
    "log_q_primes",
    "log_p_primes",
    "log_q",
    "log_p",
    "log_qp",
    "actual_log_q",
    "actual_log_p",
    "actual_log_qp",
    "actual_q_primes",
    "actual_p_primes",
    "xs",
    "xe",
    "old_policy_id",
    "old_limit",
    "old_headroom",
    "old_admission",
    "v2_policy_id",
    "v2_limit",
    "ciphertext_q_admission",
    "evaluation_key_qp_admission",
    "v2_headroom",
    "v2_admission",
    "exact_estimator_status",
    "identity_changed",
    "excluded_from_bounded_oracle",
    "encrypted_rerun_required",
    "reason",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: Iterable[dict[str, Any]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_canonical_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def build_inventory(path: Path) -> dict[str, Any]:
    subprocess.run(
        [
            "go",
            "run",
            "./cmd/flipguard-security-inventory",
            "--direct-results",
            str(DIRECT_RESULTS),
            "--out",
            str(path),
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    if len(value["direct_selected"]) != 50:
        raise ValueError("security inventory must contain 50 direct rows")
    if len(value["catalog_profiles"]) != 11:
        raise ValueError("security inventory must contain 11 catalog profiles")
    return value


def signature(parameters: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(parameters["log_n"]),
        tuple(parameters["log_q"]),
        tuple(parameters["log_p"]),
        int(parameters["log_default_scale"]),
    )


def assess(log_n: int, log_q: int, log_p: int, limits: dict[int, int]):
    limit = limits[log_n]
    log_qp = log_q + log_p
    q_admission = "PASS" if log_q <= limit else "FAIL"
    qp_admission = "PASS" if log_qp <= limit else "FAIL"
    final = (
        "PASS"
        if q_admission == "PASS" and qp_admission == "PASS"
        else "FAIL"
    )
    return {
        "limit": limit,
        "log_qp": log_qp,
        "q_admission": q_admission,
        "qp_admission": qp_admission,
        "admission": final,
        "headroom": limit - log_qp,
    }


def base_row(
    record: dict[str, Any],
    kind: str,
    source: str | None = None,
) -> dict[str, Any]:
    parameters = record["parameters"]
    log_q = sum(parameters["log_q"])
    log_p = sum(parameters["log_p"])
    old = assess(parameters["log_n"], log_q, log_p, OLD_LIMITS)
    v2 = assess(parameters["log_n"], log_q, log_p, V2_LIMITS)
    excluded = source == "catalog" and v2["admission"] == "FAIL"
    return {
        "record_kind": kind,
        "candidate_source": source or record["candidate_source"],
        "candidate_id": record["candidate_id"],
        "profile": record.get("profile", ""),
        "path": record.get("path", ""),
        "split_seed": record.get("split_seed", ""),
        "dataset_id": record.get("dataset_id", ""),
        "model_id": record.get("model_id", ""),
        "log_n": parameters["log_n"],
        "log_q_primes": json.dumps(parameters["log_q"], separators=(",", ":")),
        "log_p_primes": json.dumps(parameters["log_p"], separators=(",", ":")),
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_q + log_p,
        "actual_log_q": f"{record['actual_log_q']:.12g}",
        "actual_log_p": f"{record['actual_log_p']:.12g}",
        "actual_log_qp": f"{record['actual_log_qp']:.12g}",
        "actual_q_primes": json.dumps(record["actual_q_primes"], separators=(",", ":")),
        "actual_p_primes": json.dumps(record["actual_p_primes"], separators=(",", ":")),
        "xs": record["actual_xs"],
        "xe": record["actual_xe"],
        "old_policy_id": "he_security_guidelines_2024_ternary_classical_128",
        "old_limit": old["limit"],
        "old_headroom": old["headroom"],
        "old_admission": old["admission"],
        "v2_policy_id": (
            "security_guidelines_cic2025_table5_2_ternary_128_v2"
        ),
        "v2_limit": v2["limit"],
        "ciphertext_q_admission": v2["q_admission"],
        "evaluation_key_qp_admission": v2["qp_admission"],
        "v2_headroom": v2["headroom"],
        "v2_admission": v2["admission"],
        "exact_estimator_status": "NOT_RUN_INPUT_EXPORTED",
        "identity_changed": "false",
        "excluded_from_bounded_oracle": str(excluded).lower(),
        "encrypted_rerun_required": "false",
        "reason": (
            "static replay only; literal identity unchanged; Q and QP pass"
            if v2["admission"] == "PASS"
            else "QP exceeds the V2 cap; catalog record is retained but excluded"
        ),
    }


def build_reattestation_rows(
    inventory: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    direct = inventory["direct_selected"]
    catalog = inventory["catalog_profiles"]
    by_signature = {
        signature(record["parameters"]): record
        for record in direct + catalog
    }

    for record in direct:
        rows.append(base_row(record, "direct_selected"))

    seen: set[tuple[Any, ...]] = set()
    for record in direct:
        key = signature(record["parameters"])
        if key in seen:
            continue
        seen.add(key)
        item = dict(record)
        item["candidate_id"] = "direct_literal_" + hashlib.sha256(
            json.dumps(key, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        row = base_row(item, "direct_literal_signature")
        row["split_seed"] = ""
        row["dataset_id"] = ""
        row["model_id"] = ""
        rows.append(row)

    for record in catalog:
        rows.append(base_row(record, "catalog_profile"))
        for path in ("baseline_non_rescale", "rescale_aware"):
            item = dict(record)
            item["candidate_id"] = f"{record['profile']}__{path}"
            item["path"] = path
            rows.append(base_row(item, "catalog_profile_path_mapping"))

    default = next(item for item in catalog if item["profile"] == "default")
    reference = dict(default)
    reference["candidate_source"] = "reference"
    reference["candidate_id"] = "default__rescale_aware"
    reference["path"] = "rescale_aware"
    row = base_row(reference, "reference_candidate", "reference")
    row["encrypted_rerun_required"] = "true"
    row["reason"] = (
        "legacy default reference is V2-inadmissible and cannot be used in "
        "final paired latency"
    )
    rows.append(row)

    paired_rows = read_csv(REPO_ROOT / PAIRED_ARMS)
    for arm in paired_rows:
        params = {
            "log_n": int(arm["log_n"]),
            "log_q": json.loads(arm["log_q"]),
            "log_p": json.loads(arm["log_p"]),
            "log_default_scale": int(arm["log_default_scale"]),
        }
        matched = by_signature.get(signature(params))
        if matched is None:
            raise ValueError(
                f"paired arm has unknown literal signature: {arm}"
            )
        item = dict(matched)
        item["parameters"] = params
        item["candidate_id"] = arm["candidate_id"]
        item["profile"] = arm["profile_name"]
        item["path"] = arm["evaluation_mode"]
        item["split_seed"] = int(arm["split_seed"])
        item["dataset_id"] = arm["dataset_id"]
        item["model_id"] = arm["model_id"]
        source = {
            "direct": "direct",
            "catalog": "catalog",
            "reference": "reference",
        }[arm["id"]]
        row = base_row(item, "paired_latency_arm", source)
        if row["v2_admission"] == "FAIL":
            row["encrypted_rerun_required"] = "true"
            row["reason"] = (
                "pilot arm is V2-inadmissible; final paired latency must use "
                "a pre-frozen compliant arm"
            )
        rows.append(row)

    estimator_inputs = []
    seen.clear()
    for record in direct + catalog:
        key = signature(record["parameters"])
        if key in seen:
            continue
        seen.add(key)
        estimator_inputs.append(
            {
                "signature": {
                    "log_n": key[0],
                    "log_q": list(key[1]),
                    "log_p": list(key[2]),
                    "log_default_scale": key[3],
                },
                "exact_q_primes": record["actual_q_primes"],
                "exact_p_primes": record["actual_p_primes"],
                "xs": {
                    "concrete_type": "ring.Ternary",
                    "p": 2.0 / 3.0,
                },
                "xe": {
                    "concrete_type": "ring.DiscreteGaussian",
                    "sigma": 3.2,
                    "bound": 19.2,
                },
                "estimator_status": "NOT_RUN",
                "reason": (
                    "exact lattice-estimator execution is outside this static "
                    "table-cap re-attestation; reproducible inputs are exported"
                ),
            }
        )
    return rows, estimator_inputs


def security_filter_oracle(
    inventory: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    admitted_profiles = {
        item["profile"]
        for item in inventory["catalog_profiles"]
        if item["v2_security"]["final_admission"] == "PASS"
    }
    excluded_profiles = {
        item["profile"]
        for item in inventory["catalog_profiles"]
        if item["v2_security"]["final_admission"] == "FAIL"
    }
    certificates = read_csv(REPO_ROOT / ORACLE_SUMMARY / "candidate_certificates.csv")
    old_oracle = read_csv(REPO_ROOT / ORACLE_SUMMARY / "oracle_selection.csv")
    old_by_key = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["alpha"],
        ): row
        for row in old_oracle
    }
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in certificates:
        if row["profile"] in admitted_profiles:
            groups[
                (
                    row["split_seed"],
                    row["dataset_id"],
                    row["model_id"],
                    row["alpha"],
                )
            ].append(row)

    output_rows = []
    changes = []
    for key in sorted(groups, key=lambda item: (int(item[0]), item[1], item[2], float(item[3]))):
        candidates = groups[key]
        counts = Counter(row["certificate_status"] for row in candidates)
        safe = [row for row in candidates if row["certificate_status"] == "SAFE"]
        selected = min(
            safe,
            key=lambda row: (float(row["mean_total_ms"]), row["candidate_id"]),
        ) if safe else None
        old = old_by_key[key]
        reference = next(
            row
            for row in candidates
            if row["candidate_id"] == REFERENCE_CANDIDATE_V2
        )
        latency_only = min(
            [
                row
                for row in candidates
                if row["run_status"] == "ok"
                and row["mean_total_ms"] != ""
            ],
            key=lambda row: (float(row["mean_total_ms"]), row["candidate_id"]),
        )
        selected_id = selected["candidate_id"] if selected else ""
        changed = selected_id != old["oracle_candidate"]
        if changed:
            changes.append(
                {
                    "split_seed": int(key[0]),
                    "dataset_id": key[1],
                    "model_id": key[2],
                    "alpha": float(key[3]),
                    "old_candidate": old["oracle_candidate"],
                    "v2_candidate": selected_id,
                }
            )
        output_rows.append(
            {
                "split_seed": key[0],
                "dataset_id": key[1],
                "model_id": key[2],
                "alpha": key[3],
                "outcome": "SELECTED" if selected else "NO_SAFE",
                "candidate_count": len(candidates),
                "safe_count": counts["SAFE"],
                "rejected_count": counts["REJECTED"],
                "failed_count": counts["FAILED"],
                "v_cert": selected["v_cert"] if selected else "",
                "v_amb": selected["v_amb"] if selected else "",
                "coverage_rate": selected["coverage_rate"] if selected else "",
                "oracle_candidate": selected_id,
                "oracle_mean_total_ms": (
                    selected["mean_total_ms"] if selected else ""
                ),
                "reference_candidate": REFERENCE_CANDIDATE_V2,
                "reference_mean_total_ms": reference["mean_total_ms"],
                "oracle_speedup_vs_reference": (
                    float(reference["mean_total_ms"])
                    / float(selected["mean_total_ms"])
                    if selected
                    else ""
                ),
                "latency_only_candidate": latency_only["candidate_id"],
                "latency_only_status": latency_only["certificate_status"],
                "latency_only_mean_total_ms": latency_only["mean_total_ms"],
                "v2_oracle_candidate": selected_id,
                "v2_oracle_mean_total_ms": (
                    selected["mean_total_ms"] if selected else ""
                ),
                "pre_security_v2_oracle_candidate": old["oracle_candidate"],
                "selection_changed": str(changed).lower(),
            }
        )

    fields = list(output_rows[0])
    write_csv(output / "oracle_selection_security_v2.csv", output_rows, fields)
    write_csv(output / "oracle_selection.csv", output_rows, fields)
    shutil.copyfile(
        REPO_ROOT / ORACLE_SUMMARY / "validation_coverage.csv",
        output / "validation_coverage.csv",
    )
    write_csv(
        output / "selection_changes_security_v2.csv",
        changes,
        [
            "split_seed",
            "dataset_id",
            "model_id",
            "alpha",
            "old_candidate",
            "v2_candidate",
        ],
    )
    summary = {
        "schema_version": 2,
        "allow_incomplete": False,
        "actual_run_count": 1100,
        "expected_full_run_count": 1100,
        "source_oracle_classification": "PRE_SECURITY_V2",
        "source_encrypted_executions_reused": 1100,
        "new_encrypted_executions": 0,
        "security_policy_id": inventory["security_policy"]["id"],
        "security_policy_digest": inventory["security_policy_digest"],
        "admitted_profiles": sorted(admitted_profiles),
        "excluded_profiles": sorted(excluded_profiles),
        "candidate_identities_per_workload_before": 22,
        "candidate_identities_per_workload_after": 14,
        "workload_partition_instances": 50,
        "alpha_rows": len(output_rows),
        "selection_changes_all_alphas": len(changes),
        "selection_changes_primary_alpha_0_5": sum(
            item["alpha"] == 0.5 for item in changes
        ),
        "selection_changes_by_model": dict(
            sorted(Counter(item["model_id"] for item in changes).items())
        ),
        "outcome_counts": dict(
            Counter(row["outcome"] for row in output_rows)
        ),
        "reference_candidate_pre_security_v2": "default__rescale_aware",
        "reference_candidate_pre_security_v2_admission": "FAIL",
        "reference_candidate_v2": REFERENCE_CANDIDATE_V2,
        "reference_candidate_v2_admission": "PASS",
        "reference_selection_rule": (
            "predeclared smallest admitted built-in Q-chain profile/path that "
            "is SAFE for all 50 existing workload-partition records at alpha=0.5"
        ),
        "latency_claim_allowed": False,
        "latency_evidence_status": "BLOCKED",
    }
    write_json(output / "summary.json", summary)
    return summary


def generate(output: Path, source_commit: str | None) -> None:
    if output.exists():
        raise ValueError(f"{output} already exists; use --force")
    output.mkdir(parents=True)
    inventory_path = output / "parameter_inventory_v2.json"
    inventory = build_inventory(inventory_path)
    bound_source_commit = source_commit or git_text("rev-parse", "HEAD")
    if canonical_digest(inventory["security_policy"]) != inventory["security_policy_digest"]:
        raise ValueError("security policy canonical digest mismatch")
    if canonical_digest(inventory["direct_policy"]) != inventory["direct_policy_digest"]:
        raise ValueError("direct policy canonical digest mismatch")
    rows, estimator = build_reattestation_rows(inventory)
    write_csv(output / "security_reattestation_v2.csv", rows, CSV_FIELDS)
    direct_rows = [row for row in rows if row["record_kind"] == "direct_selected"]
    catalog_rows = [row for row in rows if row["record_kind"] == "catalog_profile"]
    reattestation = {
        "schema_version": 2,
        "classification": "PRELIMINARY",
        "security_policy": inventory["security_policy"],
        "security_policy_digest": inventory["security_policy_digest"],
        "source_commit": bound_source_commit,
        "working_tree_source_digest": sha256_file(
            REPO_ROOT / "internal/ckksplanner/security_policy.go"
        ),
        "exact_estimator_status": "NOT_RUN_INPUT_EXPORTED",
        "counts": {
            "direct_selected_rows": len(direct_rows),
            "direct_literal_signatures": len(
                [row for row in rows if row["record_kind"] == "direct_literal_signature"]
            ),
            "catalog_profiles": len(catalog_rows),
            "catalog_profile_path_mappings": len(
                [row for row in rows if row["record_kind"] == "catalog_profile_path_mapping"]
            ),
            "reference_candidates": len(
                [row for row in rows if row["record_kind"] == "reference_candidate"]
            ),
            "paired_latency_arms": len(
                [row for row in rows if row["record_kind"] == "paired_latency_arm"]
            ),
        },
        "direct_selected": {
            "pass": sum(row["v2_admission"] == "PASS" for row in direct_rows),
            "fail": sum(row["v2_admission"] == "FAIL" for row in direct_rows),
            "minimum_headroom_bits": min(int(row["v2_headroom"]) for row in direct_rows),
            "identity_changes": 0,
            "encrypted_rerun_required": False,
        },
        "catalog_profiles": {
            "admitted": sorted(
                row["profile"] for row in catalog_rows if row["v2_admission"] == "PASS"
            ),
            "excluded": sorted(
                row["profile"] for row in catalog_rows if row["v2_admission"] == "FAIL"
            ),
        },
        "modulus_interpretation": {
            "ciphertext": "Q",
            "evaluation_relinearization_key_switching": "QP",
            "final": "all required objects must pass",
            "decisive_check": (
                "QP is decisive when P is nonempty because Q is a strict subset "
                "of QP; both object checks remain explicitly recorded"
            ),
        },
        "table_runtime_distribution_relation": (
            "Table 5.2 uses sigma=3.19. Lattigo v6.2.0 uses "
            "ring.Ternary{P:2/3} and "
            "ring.DiscreteGaussian{Sigma:3.2, Bound:19.2}; this is a "
            "conservative admission reference, not an identical-distribution claim."
        ),
    }
    write_json(output / "security_reattestation_v2.json", reattestation)
    write_json(
        output / "lattice_estimator_inputs_v2.json",
        {
            "schema_version": 1,
            "security_policy_id": inventory["security_policy"]["id"],
            "estimator_status": "NOT_RUN",
            "inputs": estimator,
        },
    )
    write_canonical_json(
        output / "security_policy_v2.json",
        {
            "artifact_schema_version": 1,
            "generated_at_commit": bound_source_commit,
            "policy": inventory["security_policy"],
            "policy_sha256": inventory["security_policy_digest"],
        },
    )
    write_canonical_json(
        output / "direct_synthesis_policy_v2.json",
        {
            "artifact_schema_version": 1,
            "source_commit": bound_source_commit,
            "policy": inventory["direct_policy"],
            "policy_sha256": inventory["direct_policy_digest"],
        },
    )
    oracle_summary = security_filter_oracle(
        inventory,
        output / "bounded_oracle_security_v2",
    )
    manifest = {
        "schema_version": 1,
        "artifact_id": "security_v2_static_attestation",
        "classification": "PRELIMINARY",
        "encrypted_execution_performed": False,
        "source_commit": bound_source_commit,
        "security_policy_id": inventory["security_policy"]["id"],
        "security_policy_digest": inventory["security_policy_digest"],
        "direct_policy_id": inventory["direct_policy"]["policy_id"],
        "direct_policy_digest": inventory["direct_policy_digest"],
        "oracle_summary": oracle_summary,
        "inputs": {
            str(
                Path(
                    "results/thesis_grade_protocol/"
                    "direct_tabular_autotune_v1/full_floor18_keys3/"
                    "summary/summary.json"
                )
            ): sha256_file(
                REPO_ROOT
                / "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
                "full_floor18_keys3/summary/summary.json"
            ),
            str(ORACLE_SUMMARY / "candidate_certificates.csv"): sha256_file(
                REPO_ROOT / ORACLE_SUMMARY / "candidate_certificates.csv"
            ),
            str(ORACLE_SUMMARY / "oracle_selection.csv"): sha256_file(
                REPO_ROOT / ORACLE_SUMMARY / "oracle_selection.csv"
            ),
            str(PAIRED_ARMS): sha256_file(REPO_ROOT / PAIRED_ARMS),
        },
    }
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output))] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    manifest["files"] = files
    write_json(output / "manifest.json", manifest)


def verify(output: Path) -> None:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        path = output / relative
        if not path.is_file() or sha256_file(path) != expected["sha256"]:
            raise ValueError(f"{path}: digest mismatch")
    for source, expected in manifest["inputs"].items():
        path = REPO_ROOT / source
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"{path}: input digest mismatch")
    with tempfile.TemporaryDirectory(prefix="flipguard-security-v2-", dir="/tmp") as tmp:
        regenerated = Path(tmp) / "artifact"
        generate(regenerated, manifest["source_commit"])
        current = {
            path.relative_to(output): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        rebuilt = {
            path.relative_to(regenerated): path.read_bytes()
            for path in regenerated.rglob("*")
            if path.is_file()
        }
        if current != rebuilt:
            raise ValueError("deterministic security V2 regeneration changed")
    summary = json.loads(
        (output / "security_reattestation_v2.json").read_text(encoding="utf-8")
    )
    print(
        "security_v2_static_artifact=VERIFIED "
        f"direct_pass={summary['direct_selected']['pass']} "
        f"catalog_admitted={len(summary['catalog_profiles']['admitted'])}"
    )


def main() -> int:
    args = parse_args()
    output = REPO_ROOT / args.output_root
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        verify(output)
        return 0
    if output.exists() and args.force:
        shutil.rmtree(output)
    generate(output, args.source_commit)
    print(f"security_v2_static_artifact={output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
