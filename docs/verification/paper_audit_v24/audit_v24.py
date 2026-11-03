#!/usr/bin/env python3
"""Read-only, independent V24 manuscript evidence audit.

The script reads frozen V17/V18 records and writes only to paper_audit_v24.
It does not import report-builder code and does not execute CKKS workloads.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper_audit_v24"
RUN = ROOT / "results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z"
V17_FINAL = ROOT / "results/model_family_expansion_v17/final_vm1x6"
V18_REPORT = ROOT / "docs/reports/comparison_extension_v18"
V18_RESULT = ROOT / "results/comparison_extension_v18"
V20 = ROOT / "docs/audit/manuscript_implementation_facts_v20"
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
ENVIRONMENT = ROOT / "docs/evidence/model_family_expansion_v17/environments/vmware_ubuntu24_1socket_6core_vcpu6_20260811T050104Z.json"

MARGIN_FLOOR = 0.001
BOOTSTRAP_SEED = 20260824
BOOTSTRAP_REPLICATES = 10000

USED: set[Path] = set()


def use(path: Path) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    USED.add(path)
    return path


def read_json(path: Path) -> Any:
    return json.loads(use(path).read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with use(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quantile(values: Iterable[float], probability: float) -> float:
    data = sorted(values)
    if not data:
        raise ValueError("quantile requires data")
    pos = (len(data) - 1) * probability
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return data[lo]
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def geometric_mean(values: Iterable[float]) -> float:
    data = list(values)
    if not data or any(value <= 0 for value in data):
        raise ValueError("geometric mean requires positive values")
    return math.exp(sum(math.log(value) for value in data) / len(data))


def bool_value(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() == "true"


def optional_finite_float(value: str) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def case_key(dataset: str, model: str, split: str) -> str:
    return f"primary|{dataset}|{model}|{split}"


def tabular_case_root(row: dict[str, str]) -> Path:
    match = re.fullmatch(r"outer_fold_(\d+)_training_seed_(\d+)", row["split_id"])
    if not match:
        raise ValueError(f"not a tabular split: {row['split_id']}")
    return RUN / "primary" / row["dataset"] / row["model_id"] / f"fold_{match.group(1)}" / f"training_seed_{match.group(2)}"


def boundary_row(
    inventory: dict[str, str], role: str, margins: list[float], source: Path,
    definition: str,
) -> dict[str, Any]:
    n_boundary = sum(value <= MARGIN_FLOOR for value in margins)
    return {
        "case_id": inventory["case_id"],
        "dataset": inventory["dataset"],
        "model": inventory["model_id"],
        "split": inventory["split_id"],
        "input_role": role,
        "n_total": len(margins),
        "n_boundary": n_boundary,
        "n_vdelta": len(margins) - n_boundary,
        "boundary_rate": n_boundary / len(margins),
        "min_margin": min(margins),
        "margin_definition": definition,
        "source_file": source.relative_to(ROOT).as_posix(),
    }


def unique_multiclass_margins(path: Path, expected_role: str) -> list[float]:
    records = read_json(path)["records"]
    by_id: dict[str, float] = {}
    for record in records:
        if record["role"] != expected_role:
            raise AssertionError((path, record["role"], expected_role))
        value = float(record["top_two_gap"])
        prior = by_id.setdefault(record["sample_id"], value)
        if not math.isclose(prior, value, rel_tol=0, abs_tol=1e-15):
            raise AssertionError(f"plaintext gap changed for {record['sample_id']}")
    return list(by_id.values())


def compute_boundaries(inventory: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    contract_mismatches: list[str] = []
    for item in inventory:
        model = item["model_id"]
        if item["split_id"].startswith("outer_fold_"):
            case_root = tabular_case_root(item)
            selection = read_json(case_root / "selection.json")
            threshold = float(selection["plan"]["contract"]["decision"]["threshold"])
            for role, name in (
                ("selection", "configuration_selection.prepared.csv"),
                ("separate", "independent_evaluation.prepared.csv"),
            ):
                source = case_root / name
                data = read_csv(source)
                margins = [abs(float(record["polynomial_score"]) - threshold) for record in data]
                entry = boundary_row(
                    item, role, margins, source,
                    "abs(polynomial_score - threshold); boundary iff margin <= 0.001",
                )
                rows.append(entry)
                if role == "selection":
                    decision = selection["plan"]["contract"]["decision"]
                    if entry["n_vdelta"] != decision["certifiable_samples"] or entry["n_boundary"] != decision["ambiguous_samples"]:
                        contract_mismatches.append(item["case_id"])
                else:
                    audit = read_json(case_root / "direct_independent_evaluation.json")
                    if entry["n_vdelta"] != audit["v_cert"] or entry["n_boundary"] != audit["v_amb"]:
                        contract_mismatches.append(item["case_id"] + ":separate")
        elif model in {"mnist_mlp_square_784_100_10_v1", "mnist_lenet5_small_square_v1"}:
            initial_id = item["gate_off_candidate"]
            candidates = sorted((ROOT / "results/model_family_expansion_v17/exhaustive" / model).glob(f"candidate_01_*{initial_id.split('_')[-1]}"))
            if len(candidates) != 1:
                raise AssertionError((model, initial_id, candidates))
            selection_source = candidates[0] / "key_run_01.json"
            separate_source = RUN / "exhaustive" / model / "fastest_safe_independent_evaluation" / "key_run_01.json"
            rows.append(boundary_row(
                item, "selection",
                unique_multiclass_margins(selection_source, "configuration_validation"),
                selection_source,
                "plaintext top-1 minus top-2 logit; boundary iff gap <= 0.001",
            ))
            rows.append(boundary_row(
                item, "separate",
                unique_multiclass_margins(separate_source, "locked_audit"),
                separate_source,
                "plaintext top-1 minus top-2 logit; boundary iff gap <= 0.001",
            ))
        elif model == "packed_cnn_lite_binary01_v17":
            base = ROOT / "datasets/vision_suite/mnist/cnn_lite_square_binary01"
            for role, name in (("selection", "configuration_validation.csv"), ("separate", "locked_audit_test.csv")):
                source = base / name
                data = read_csv(source)
                margins = [abs(float(record["plaintext_score"]) - float(record["decision_threshold"])) for record in data]
                rows.append(boundary_row(
                    item, role, margins, source,
                    "abs(plaintext_score - decision_threshold); boundary iff margin <= 0.001",
                ))
        else:
            raise AssertionError(f"unknown primary model {model}")

    totals: dict[str, Any] = {}
    for role in ("selection", "separate"):
        selected = [row for row in rows if row["input_role"] == role]
        n_total = sum(row["n_total"] for row in selected)
        n_boundary = sum(row["n_boundary"] for row in selected)
        totals[role] = {
            "cases": len(selected),
            "n_total": n_total,
            "n_boundary": n_boundary,
            "n_vdelta": n_total - n_boundary,
            "boundary_rate": n_boundary / n_total,
            "min_margin": min(row["min_margin"] for row in selected),
            "empty_vdelta_cases": [row["case_id"] for row in selected if row["n_vdelta"] == 0],
        }
    totals["contract_mismatches"] = contract_mismatches
    return rows, totals


def flatten_latency(path: Path) -> tuple[list[dict[str, Any]], int, int, bool, int, int, bool]:
    payload = read_json(path)
    paired: dict[tuple[Any, ...], dict[str, float]] = defaultdict(dict)
    direct_values: list[float] = []
    finite_values: list[float] = []
    positions: Counter[tuple[str, int]] = Counter()
    if "keysets" in payload:
        warmups = {int(block["measurement"]["protocol"]["warmup_runs"]) for block in payload["keysets"]}
        passes = {int(block["measurement"]["protocol"]["measurement_runs"]) for block in payload["keysets"]}
        no_outlier = all(block["measurement"]["protocol"]["outlier_policy"] == "none_all_raw_observations_preserved" for block in payload["keysets"])
        schedules = {block["measurement"]["protocol"]["order_schedule"] for block in payload["keysets"]}
        keysets = len(payload["keysets"])
        for block_index, block in enumerate(payload["keysets"], start=1):
            for record in block["measurement"]["records"]:
                key = (block_index, record["measurement_run"], record["row_id"])
                paired[key][record["arm_id"]] = float(record["total_ms"])
                positions[(record["arm_id"], int(record["order_position"]))] += 1
                if record["arm_id"] == "direct":
                    direct_values.append(float(record["total_ms"]))
                elif record["arm_id"] == "finite_fastest_safe":
                    finite_values.append(float(record["total_ms"]))
    else:
        warmups = {int(payload["warmup_runs"])}
        passes = {int(payload["measurement_runs"])}
        no_outlier = all(
            block["protocol"]["outlier_policy"] == "none_all_raw_observations_preserved"
            for block in payload["keyset_results"]
        )
        schedules = {block["protocol"]["order_schedule"] for block in payload["keyset_results"]}
        keysets = int(payload["fresh_keysets"])
        for record in payload["records"]:
            key = (record["keyset"], record["measurement_run"])
            paired[key][record["arm_id"]] = float(record["total_ms"])
            positions[(record["arm_id"], int(record["order_position"]))] += 1
            if record["arm_id"] == "direct":
                direct_values.append(float(record["total_ms"]))
            elif record["arm_id"] == "finite_fastest_safe":
                finite_values.append(float(record["total_ms"]))
    if warmups != {1} or passes != {6} or not no_outlier or keysets != 3:
        raise AssertionError((path, warmups, passes, no_outlier, keysets))
    if any(set(value) != {"direct", "finite_fastest_safe"} for value in paired.values()):
        raise AssertionError(f"unpaired timing observation in {path}")
    ratios = [arms["finite_fastest_safe"] / arms["direct"] for arms in paired.values()]
    records = [{"ratio": value} for value in ratios]
    balanced = (
        all(schedule.startswith("balanced_cyclic_and_reverse") for schedule in schedules)
        and positions[("direct", 1)] == positions[("direct", 2)]
        and positions[("finite_fastest_safe", 1)] == positions[("finite_fastest_safe", 2)]
    )
    return records, len(paired), keysets, no_outlier, len(direct_values), len(finite_values), balanced


def latency_arm_means(path: Path) -> tuple[float, float]:
    payload = read_json(path)
    direct: list[float] = []
    finite: list[float] = []
    if "keysets" in payload:
        records = [record for block in payload["keysets"] for record in block["measurement"]["records"]]
    else:
        records = payload["records"]
    for record in records:
        if record["arm_id"] == "direct":
            direct.append(float(record["total_ms"]))
        elif record["arm_id"] == "finite_fastest_safe":
            finite.append(float(record["total_ms"]))
    return statistics.mean(direct), statistics.mean(finite)


def build_case_ledger(
    inventory: list[dict[str, str]], table04: list[dict[str, str]], formal: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_case = {case_key(row["dataset"], row["model_id"], row["split_id"]): row for row in table04 if row["phase"] == "primary"}
    fixed_case_by_model = {
        row["model_id"]: row["case_id"]
        for row in inventory
        if not row["split_id"].startswith("outer_fold_")
    }
    formal_by_case: dict[str, dict[str, str]] = {}
    raw_ratio_mismatches: list[str] = []
    raw_pair_total = 0
    unbalanced_order_cases: list[str] = []
    for row in formal:
        split = row["split_id"]
        if split.startswith("fold_"):
            match = re.fullmatch(r"fold_(\d+)/training_seed_(\d+)", split)
            split = f"outer_fold_{match.group(1)}_training_seed_{match.group(2)}" if match else split
        if row["model_id"] in fixed_case_by_model:
            key = fixed_case_by_model[row["model_id"]]
        else:
            key = case_key(row["dataset"], row["model_id"], split)
        formal_by_case[key] = row
        raw, pair_count, _, _, _, _, balanced = flatten_latency(ROOT / row["path"])
        raw_pair_total += pair_count
        if not balanced:
            unbalanced_order_cases.append(key)
        raw_ratio = geometric_mean(item["ratio"] for item in raw)
        if not math.isclose(raw_ratio, float(row["finite_over_direct_geomean_total"]), rel_tol=0, abs_tol=1e-12):
            raw_ratio_mismatches.append(key)

    ledger: list[dict[str, Any]] = []
    for item in inventory:
        key = item["case_id"]
        base = by_case[key]
        latency = formal_by_case[key]
        direct_mean, finite_mean = latency_arm_means(ROOT / latency["path"])
        flips = int(item["gate_off_selection_flips"])
        violations = int(item["gate_off_reserve_policy_violations"])
        initial_status = "SAFE" if flips == 0 and violations == 0 else "REJECTED"
        log_delta = int(item["full_method_log_n"]) - int(item["gate_off_log_n"])
        scale_delta = int(item["full_method_scale_bits"]) - int(item["gate_off_scale_bits"])
        q_delta = int(item["full_method_q_chain_length"]) - int(item["gate_off_q_chain_length"])
        adjustments = []
        if scale_delta:
            adjustments.append(f"scale{scale_delta:+d}_bits")
        if q_delta:
            adjustments.append(f"q_prime_count{q_delta:+d}")
        if log_delta:
            adjustments.append(f"LogN{log_delta:+d}")
        ledger.append({
            "case_id": key,
            "dataset": item["dataset"],
            "model": item["model_id"],
            "split": item["split_id"],
            "initial_candidate_id": item["gate_off_candidate"],
            "initial_candidate_result": initial_status,
            "initial_decision_flips": flips,
            "initial_error_violations": violations,
            "additional_candidate_evaluations": int(item["added_candidate_evaluations"]),
            "adjustment_type": ";".join(adjustments) if adjustments else "none",
            "initial_log_n": int(item["gate_off_log_n"]),
            "final_log_n": int(item["full_method_log_n"]),
            "initial_scale_bits": int(item["gate_off_scale_bits"]),
            "final_scale_bits": int(item["full_method_scale_bits"]),
            "initial_q_chain_length": int(item["gate_off_q_chain_length"]),
            "final_q_chain_length": int(item["full_method_q_chain_length"]),
            "final_candidate_id": item["full_method_selected_candidate"],
            "final_selection_safe": base["direct_outcome"] == "SELECTED" and int(base["selection_flips"]) == 0 and int(base["selection_violations"]) == 0,
            "separate_input_status": item["full_method_separate_input_outcome"],
            "separate_input_safe": item["full_method_separate_input_outcome"] == "SAFE",
            "finite_reference_candidate_evaluations": int(base["exhaustive_denominator"]),
            "acceptable_candidate_missed": bool_value(base["false_no_safe"]),
            "proposed_mean_total_latency_ms": direct_mean,
            "reference_mean_total_latency_ms": finite_mean,
            "finite_over_proposed_geomean_total_ratio": float(latency["finite_over_direct_geomean_total"]),
            "formal_latency_pairs": int(float(latency["pairs"])),
            "formal_latency_source": latency["path"],
        })
    return ledger, {
        "raw_ratio_mismatches": raw_ratio_mismatches,
        "raw_pair_total": raw_pair_total,
        "unbalanced_order_cases": unbalanced_order_cases,
        "all_68_order_schedules_verified": not unbalanced_order_cases,
    }


def bootstrap_audit(formal: list[dict[str, str]], inventory: list[dict[str, str]]) -> dict[str, Any]:
    inv = {row["case_id"]: row for row in inventory}
    fixed_case_by_model = {
        row["model_id"]: row["case_id"]
        for row in inventory
        if not row["split_id"].startswith("outer_fold_")
    }
    clusters: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in formal:
        split = row["split_id"]
        if split.startswith("fold_"):
            match = re.fullmatch(r"fold_(\d+)/training_seed_(\d+)", split)
            split = f"outer_fold_{match.group(1)}_training_seed_{match.group(2)}"
        elif row["model_id"] in fixed_case_by_model:
            cid = fixed_case_by_model[row["model_id"]]
        else:
            split = "v17_p6_packed_cnn_lite"
        if row["model_id"] not in fixed_case_by_model:
            cid = case_key(row["dataset"], row["model_id"], split)
        if cid not in inv:
            raise AssertionError(f"formal row absent from primary inventory: {cid}")
        clusters[(row["dataset"], row["model_id"])].append({
            "case_id": cid,
            "case_ratio": float(row["finite_over_direct_geomean_total"]),
        })
    cluster_rows = []
    cluster_values = []
    for (dataset, model), cases in sorted(clusters.items()):
        value = geometric_mean(item["case_ratio"] for item in cases)
        cluster_values.append(value)
        cluster_rows.append({
            "cluster_id": f"{dataset}|{model}",
            "dataset": dataset,
            "model": model,
            "case_count": len(cases),
            "case_ids": [item["case_id"] for item in cases],
            "within_cluster_geometric_mean_ratio": value,
        })
    point = geometric_mean(cluster_values)
    rng = random.Random(BOOTSTRAP_SEED)
    draws = []
    for _ in range(BOOTSTRAP_REPLICATES):
        draws.append(geometric_mean(cluster_values[rng.randrange(len(cluster_values))] for _ in cluster_values))
    low = quantile(draws, 0.025)
    high = quantile(draws, 0.975)
    claimed = read_json(V18_REPORT / "PAPER_FACTS_V18_LOCKED.json")["finite_reference"]["finite_over_direct_total_latency_ratio"]
    return {
        "input_file": "results/model_family_expansion_v17/final_vm1x6/table_05_formal_paired_latency.csv",
        "case_count": len(formal),
        "cluster_count": len(cluster_rows),
        "cluster_mapping": cluster_rows,
        "resampling_algorithm": "Compute one geometric mean of finite/direct case ratios within each dataset-model cluster; sample 16 cluster means with replacement; compute the equally cluster-weighted geometric mean for each replicate.",
        "statistic_formula": "exp((1/K) * sum_k log(exp((1/n_k) * sum_i log(finite_i/direct_i))))",
        "ratio_direction": "finite_reference_total_latency / proposed_total_latency",
        "within_case_aggregation": "geometric mean of raw paired ratios preserving input/keyset/pass pairing",
        "cluster_weighting": "equal weight per dataset-model cluster; equal case weight within each cluster",
        "seed": BOOTSTRAP_SEED,
        "replicates": BOOTSTRAP_REPLICATES,
        "confidence_interval_method": "percentile interval with linear interpolation at 2.5% and 97.5%; not BCa",
        "point_estimate_unrounded": point,
        "ci_low_unrounded": low,
        "ci_high_unrounded": high,
        "manuscript_claim": {
            "point_estimate": 1.000540931,
            "ci_low": 0.999967475,
            "ci_high": 1.001121781,
        },
        "locked_artifact": claimed,
        "difference_from_manuscript": {
            "point_estimate": point - 1.000540931,
            "ci_low": low - 0.999967475,
            "ci_high": high - 1.001121781,
        },
        "difference_from_locked_artifact": {
            "point_estimate": point - float(claimed["estimate"]),
            "ci_low": low - float(claimed["ci_low"]),
            "ci_high": high - float(claimed["ci_high"]),
        },
        "pass_at_9_decimal_places": (
            round(point, 9) == round(float(claimed["estimate"]), 9)
            and round(low, 9) == round(float(claimed["ci_low"]), 9)
            and round(high, 9) == round(float(claimed["ci_high"]), 9)
        ),
    }


def external_audit() -> dict[str, Any]:
    eva = read_csv(V8 / "eva_population_records.csv")
    eva20 = [row for row in eva if row["role"] == "configuration_validation" and int(row["scale_bits"]) == 20]
    heir = read_csv(V8 / "heir_shared_polynomial_records.csv")
    heir_audit = [row for row in heir if row["runtime"] == "Lattigo-v6.2.0-translation" and row["role"] == "locked_audit"]
    security = read_csv(V8 / "security_summary.csv")
    heir_security = next(row for row in security if row["provider"] == "Google HEIR" and row["runtime"] == "Lattigo v6.2.0")
    core = read_csv(V8 / "corelab_plan_status.csv")
    return {
        "heir": {
            "log_n": int(heir_security["log_n"]),
            "scale_bits": int(heir_security["scale_bits"]),
            "unique_inputs": len({row["row_id"] for row in heir_audit}),
            "contexts": len({row["context"] for row in heir_audit}),
            "observations": len(heir_audit),
            "decision_flips": sum(bool_value(row["decision_flip"]) for row in heir_audit),
            "reserve_violations": sum(bool_value(row["reserve_violation"]) for row in heir_audit),
            "max_absolute_error": max(float(row["absolute_error"]) for row in heir_audit),
            "status": "PASS",
        },
        "eva_scale20": {
            "unique_inputs": len({row["row_id"] for row in eva20}),
            "contexts": len({row["context_index"] for row in eva20}),
            "observations": len(eva20),
            "decision_flip_events": sum(bool_value(row["decision_flip"]) for row in eva20),
            "decision_flip_unique_inputs": len({row["row_id"] for row in eva20 if bool_value(row["decision_flip"])}),
            "status": "PASS",
        },
        "corelab": {
            "plan_status_counts": {f"{mode}:{state}": count for (mode, state), count in sorted(Counter((row["mode"], row["status"]) for row in core).items())},
            "hecate_direct_decision_baseline": "NOT_VERIFIABLE: no exact V17 decision-bearing output",
            "elasm_direct_decision_baseline": "NOT_COMPARABLE: numerical output has no matching threshold/argmax contract",
        },
        "latency_fairness": "HEIR uses a common Lattigo diagnostic but its paired direct arm was unsafe; EVA/CoreLab values are native cross-runtime measurements. No cross-runtime speed superiority is admissible.",
    }


def environment_audit() -> dict[str, Any]:
    manifest = read_json(ENVIRONMENT)
    protocol = read_json(ROOT / "docs/protocols/model_family_expansion_v17/protocol.json")
    execution_profile = read_json(
        ROOT / "docs/protocols/model_family_expansion_v17/execution_profiles/vmware_ubuntu24_1socket_6core_vcpu6_v1.json"
    )
    final_table = read_csv(V20 / "TABLE_3_EXPERIMENT_ENVIRONMENT_FINAL.csv")
    scientific = protocol["environment"]
    field_checks = {
        "host_cpu": manifest["host_cpu_model"] == "AMD Ryzen 5 3600 6-Core Processor",
        "host_core_topology": manifest["host_physical_cores"] == 6 and manifest["host_logical_processors"] == 12,
        "hypervisor": manifest["hypervisor"] == "VMware Workstation",
        "guest_os_kernel": manifest["guest_os"] == "Ubuntu 24.04.4 LTS" and manifest["guest_kernel"] == "7.0.0-28-generic",
        "architecture": scientific["machine"] == "x86_64",
        "guest_topology": manifest["guest_virtual_sockets"] == 1 and manifest["guest_cores_per_socket"] == 6 and manifest["guest_total_vcpu"] == 6,
        "affinity_gomaxprocs": manifest["effective_cpuset"] == "0-5" and manifest["effective_GOMAXPROCS"] == 6,
        "memory_swap": manifest["memory_kib"] == 16324060 and manifest["swap_kib"] == 4194300,
        "go_python": manifest["Go_version"] == "go version go1.25.9 linux/amd64" and manifest["Python_version"] == "Python 3.12.3",
        "lattigo_numpy_sklearn": manifest["Lattigo_version"] == "v6.2.0" and scientific["numpy_version"] == "2.2.6" and scientific["scikit_learn_version"] == "1.6.1",
        "single_case_worker": manifest["case_worker_count"] == 1 and execution_profile["case_worker_count"] == 1 and execution_profile["latency_worker_count"] == 1,
    }
    return {
        "authority_order": [
            ENVIRONMENT.relative_to(ROOT).as_posix(),
            "docs/protocols/model_family_expansion_v17/execution_profiles/vmware_ubuntu24_1socket_6core_vcpu6_v1.json",
            "docs/protocols/model_family_expansion_v17/protocol.json",
            "docs/audit/manuscript_implementation_facts_v20/TABLE_3_EXPERIMENT_ENVIRONMENT_FINAL.csv",
        ],
        "host_cpu_model": manifest["host_cpu_model"],
        "host_physical_cores": manifest["host_physical_cores"],
        "host_logical_processors": manifest["host_logical_processors"],
        "hypervisor": manifest["hypervisor"],
        "hypervisor_version": "NOT_VERIFIABLE",
        "guest_os": manifest["guest_os"],
        "kernel": manifest["guest_kernel"],
        "architecture": scientific["machine"],
        "guest_virtual_sockets": manifest["guest_virtual_sockets"],
        "guest_cores_per_socket": manifest["guest_cores_per_socket"],
        "guest_total_vcpu": manifest["guest_total_vcpu"],
        "affinity": manifest["effective_cpuset"],
        "gomaxprocs": manifest["effective_GOMAXPROCS"],
        "case_worker_count": manifest["case_worker_count"],
        "memory_kib": manifest["memory_kib"],
        "swap_kib": manifest["swap_kib"],
        "go_version": manifest["Go_version"],
        "python_version": manifest["Python_version"],
        "lattigo_version": manifest["Lattigo_version"],
        "numpy_version": scientific["numpy_version"],
        "scikit_learn_version": scientific["scikit_learn_version"],
        "execution_profile_case_worker_count": execution_profile["case_worker_count"],
        "execution_profile_latency_worker_count": execution_profile["latency_worker_count"],
        "v20_rows": final_table,
        "field_checks": field_checks,
        "all_claimed_fields_confirmed": all(field_checks.values()),
        "qualification": "The 1x6 execution overlay supersedes the protocol's historical 2-CPU topology fields; software versions and architecture remain scientific-protocol-bound.",
    }


def negative_case_audit() -> dict[str, Any]:
    path = RUN / "ablation/banknote/mlp_square_poly3/fold_3/training_seed_0/direct_independent_evaluation.json"
    payload = read_json(path)
    violating = [row for row in payload["sample_ledger"] if row["error_violation"]]
    if len(violating) != 1:
        raise AssertionError((path, len(violating)))
    row = violating[0]
    return {
        "source_file": path.relative_to(ROOT).as_posix(),
        "case": "banknote/mlp_square_poly3/fold_3",
        "status": payload["status"],
        "decision_flips": payload["decision_flips"],
        "reserve_policy_violations": payload["error_violations"],
        "input_id": row["sample_id"],
        "key_repeat": row["key_repeat"],
        "plaintext_decision": row["plaintext_decision"],
        "ckks_decision": row["ckks_decision"],
        "margin": row["decision_margin"],
        "observed_error": row["absolute_error"],
        "rho_times_margin": row["error_budget"],
        "excess": row["absolute_error"] - row["error_budget"],
        "matches_manuscript": (
            payload["status"] == "REJECTED"
            and payload["decision_flips"] == 0
            and payload["error_violations"] == 1
            and row["sample_id"] == "1068"
            and math.isclose(row["absolute_error"], 0.010777816005162588, rel_tol=0, abs_tol=1e-15)
            and math.isclose(row["error_budget"], 0.00982200284660778, rel_tol=0, abs_tol=1e-15)
        ),
    }


def selection_key_audit(inventory: list[dict[str, str]]) -> dict[str, Any]:
    tabular_trials = []
    for item in inventory:
        if not item["split_id"].startswith("outer_fold_"):
            continue
        selection = read_json(tabular_case_root(item) / "selection.json")
        for trial in selection["trials"]:
            tabular_trials.append((trial["key_repeats_requested"], trial["key_repeats_completed"], trial["encrypted_sample_evaluations"]))
    packed = read_json(RUN / "primary/packed_cnn_lite_binary01_v17/selection.json")
    for trial in packed["trials"]:
        tabular_trials.append((trial["key_repeats_requested"], trial["key_repeats_completed"], trial["encrypted_sample_evaluations"]))
    multiclass_keyruns = 0
    for model in ("mnist_mlp_square_784_100_10_v1", "mnist_lenet5_small_square_v1"):
        candidates = sorted((ROOT / "results/model_family_expansion_v17/exhaustive" / model).glob("candidate_01_*/key_run_0*.json"))
        first_contract = read_json(candidates[0])["contract_digest"]
        first = [path for path in candidates if read_json(path)["contract_digest"] == first_contract]
        multiclass_keyruns += len(first)
    return {
        "tabular_and_packed_candidate_evaluation_bundles": len(tabular_trials),
        "multiclass_candidate_evaluation_bundles": 2,
        "all_primary_candidate_evaluation_bundles": len(tabular_trials) + 2,
        "all_requested_key_repeats_equal_3": all(requested == 3 for requested, _, _ in tabular_trials),
        "all_completed_key_repeats_equal_3": all(completed == 3 for _, completed, _ in tabular_trials),
        "multiclass_initial_candidate_keyrun_files": multiclass_keyruns,
        "all_primary_bundles_have_three_key_runs": (
            all(completed == 3 for _, completed, _ in tabular_trials) and multiclass_keyruns == 6
        ),
        "candidate_evaluation_unit": "one candidate over the complete selection input set under three fresh key contexts",
        "candidate_between_trial_key_reuse": "source creates fresh contexts for every candidate key run; no key fingerprint is recorded, so low-level RNG independence is NOT_VERIFIABLE from result JSON alone",
        "selection_vs_separate_keys": "separate-input replay creates fresh contexts and does not invoke Synthesize or RepairCandidate",
        "source_references": [
            "internal/ckksplanner/executor.go:432-456",
            "internal/ckksplanner/audit.go:85-87",
            "internal/ckksplanner/tabular_sample_ledger.go:38-73",
        ],
    }


def disjointness_audit(inventory: list[dict[str, str]]) -> dict[str, Any]:
    overlap_cases = []
    row_counts = Counter()
    folds_retrained = 0
    model_digests: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in inventory:
        if not item["split_id"].startswith("outer_fold_"):
            continue
        match = re.fullmatch(r"outer_fold_(\d+)_training_seed_(\d+)", item["split_id"])
        plain = ROOT / "results/model_family_expansion_v17/plaintext/primary" / item["dataset"] / item["model_id"] / f"fold_{match.group(1)}" / f"training_seed_{match.group(2)}"
        roles = {}
        for role, filename in (("train", "model_training.csv"), ("selection", "configuration_selection.csv"), ("separate", "independent_evaluation.csv")):
            rows = read_csv(plain / filename)
            roles[role] = {row["row_id"] for row in rows}
            row_counts[f"{role}:{len(rows)}"] += 1
        if roles["train"] & roles["selection"] or roles["train"] & roles["separate"] or roles["selection"] & roles["separate"]:
            overlap_cases.append(item["case_id"])
        model_path = plain / "model.json"
        model_digests[(item["dataset"], item["model_id"])].add(sha256(use(model_path)))
        folds_retrained += 1
    multi_split = read_json(ROOT / "docs/evidence/journal_multiclass_extension_v1/input_split_manifest.json")
    packed_split = read_json(ROOT / "datasets/vision_suite/mnist/cnn_lite_square_binary01/extraction_manifest.json")
    return {
        "tabular_case_count": folds_retrained,
        "tabular_overlap_cases": overlap_cases,
        "tabular_role_size_distribution": dict(sorted(row_counts.items())),
        "fold_specific_model_digest_count": {f"{dataset}|{model}": len(values) for (dataset, model), values in sorted(model_digests.items())},
        "all_65_tabular_cases_have_fold_specific_model_artifacts": folds_retrained == 65 and all(len(values) == 5 for values in model_digests.values()),
        "multiclass_validation_audit_overlap_count": multi_split["validation_audit_overlap_count"],
        "packed_audit_used_for_training_or_selection": any(packed_split["audit_noninterference"].values()),
        "separate_input_size_finding": "The full separate-input decision reevaluation is not 20 inputs per case. Twenty is the formal latency subset. Tabular full reevaluation sizes follow outer test folds; MLP-100 and LeNet use 500 each; packed CNN-lite uses 250.",
        "training_source_reference": "scripts/build_v17_plaintext_suite.py:380-397; preprocessing/model fitting precedes role export",
    }


def observed_claims(
    inventory: list[dict[str, str]], table03: list[dict[str, str]], table04: list[dict[str, str]],
    table06: list[dict[str, str]], table07: list[dict[str, str]], depth: list[dict[str, str]], formal: list[dict[str, str]],
    bootstrap: dict[str, Any], negative: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    primary04 = [row for row in table04 if row["phase"] == "primary"]
    cross = Counter()
    for row in inventory:
        flips = int(row["gate_off_selection_flips"])
        violations = int(row["gate_off_reserve_policy_violations"])
        cross[(flips > 0, violations > 0)] += 1
    changed = [row for row in inventory if int(row["added_candidate_evaluations"]) > 0]
    changed_ratios = [
        float(row["selection_stage_full_over_gate_off_observed_latency_ratio"])
        for row in read_json(V18_REPORT / "PAPER_FACTS_V18_LOCKED.json")["configuration_change"]["case_literals"]
    ]
    regrets = [float(row["latency_regret"]) for row in table06]
    wallclock_ratios = []
    for row in primary04:
        finite_ms = optional_finite_float(row["exhaustive_wall_clock_ms"])
        direct_ms = optional_finite_float(row["selection_wall_clock_ms"])
        if finite_ms is not None and direct_ms is not None and finite_ms > 0 and direct_ms > 0:
            wallclock_ratios.append(finite_ms / direct_ms)
    depth_by_id = {f"D{row['depth']}": row for row in depth}
    all_literals = {(row["log_n"], row["q_bits"], row["p_bits"], row["scale_bits"], row["path"]) for row in table07}
    primary_literals = {(row["log_n"], row["q_bits"], row["p_bits"], row["scale_bits"], row["path"]) for row in table07 if row["phase"] == "primary"}
    negative_rows = [row for row in table03 if row["direct_independent_status"] == "REJECTED"]
    values = {
        "primary_cases": len(inventory),
        "gate_off_evaluations": sum(int(row["gate_off_candidate_evaluations"]) for row in inventory),
        "full_candidate_evaluations": sum(int(row["full_method_candidate_evaluations"]) for row in inventory),
        "finite_candidate_evaluations": sum(int(row["exhaustive_denominator"]) for row in primary04),
        "separate_records": len(primary04),
        "formal_latency_rows": len(formal),
        "cross_no_flip_no_violation": cross[(False, False)],
        "cross_flip_only": cross[(True, False)],
        "cross_violation_only": cross[(False, True)],
        "cross_both": cross[(True, True)],
        "cross_union": len(inventory) - cross[(False, False)],
        "changed_exactly_one": sum(int(row["added_candidate_evaluations"]) == 1 for row in changed),
        "changed_scale_plus4": sum(int(row["full_method_scale_bits"]) - int(row["gate_off_scale_bits"]) == 4 for row in changed),
        "changed_q_chain": sum(int(row["full_method_q_chain_length"]) != int(row["gate_off_q_chain_length"]) for row in changed),
        "changed_log_n": sum(int(row["full_method_log_n"]) != int(row["gate_off_log_n"]) for row in changed),
        "separate_safe": sum(row["direct_independent_status"] == "SAFE" for row in primary04),
        "false_no_safe": sum(bool_value(row["false_no_safe"]) for row in primary04),
        "candidate_reduction": 1 - sum(int(row["full_method_candidate_evaluations"]) for row in inventory) / sum(int(row["exhaustive_denominator"]) for row in primary04),
        "bootstrap_estimate": bootstrap["point_estimate_unrounded"],
        "bootstrap_ci_low": bootstrap["ci_low_unrounded"],
        "bootstrap_ci_high": bootstrap["ci_high_unrounded"],
        "changed_ratio_median": statistics.median(changed_ratios),
        "changed_ratio_p90": quantile(changed_ratios, 0.9),
        "regret_median": statistics.median(regrets),
        "regret_p90": quantile(regrets, 0.9),
        "regret_max": max(regrets),
        "all_scope_cases": len(table03),
        "all_scope_negative": len(negative_rows),
        "depth_q_chain": [len(json.loads(depth_by_id[key]["q_bits"])) for key in ("D1", "D2", "D4", "D6", "D8")],
        "depth_log_n": [int(depth_by_id[key]["log_n"]) for key in ("D1", "D2", "D4", "D6", "D8")],
        "all_literal_count": len(all_literals),
        "primary_literal_count": len(primary_literals),
        "negative_case": negative,
        "selection_wallclock_finite_over_full": {
            "n": len(wallclock_ratios),
            "median": statistics.median(wallclock_ratios),
            "iqr": quantile(wallclock_ratios, 0.75) - quantile(wallclock_ratios, 0.25),
            "p90": quantile(wallclock_ratios, 0.9),
            "measurement_class": "selection-stage wall-clock; separate from formal inference latency",
        },
    }
    claims = [
        (1, "주요 평가 사례", 68, values["primary_cases"]),
        (2, "gate-off 초기 후보 평가", 68, values["gate_off_evaluations"]),
        (3, "전체 기법 후보 평가", 89, values["full_candidate_evaluations"]),
        (4, "유한 비교 후보 평가", 537, values["finite_candidate_evaluations"]),
        (5, "별도 입력 재평가 기록", 68, values["separate_records"]),
        (6, "공식 짝지은 지연시간 기록", 68, values["formal_latency_rows"]),
        (7, "초기 후보 교차표 (47/0/1/20; union 21)", [47, 0, 1, 20, 21], [values["cross_no_flip_no_violation"], values["cross_flip_only"], values["cross_violation_only"], values["cross_both"], values["cross_union"]]),
        (8, "문제 사례의 추가 평가 1회", 21, values["changed_exactly_one"]),
        (9, "문제 사례 scale +4 bit", 21, values["changed_scale_plus4"]),
        (10, "Q-chain/LogN 변경 사례", [0, 0], [values["changed_q_chain"], values["changed_log_n"]]),
        (11, "최종 별도 입력 SAFE", 68, values["separate_safe"]),
        (12, "적합 후보 누락", 0, values["false_no_safe"]),
        (13, "후보 평가 감소율", 0.8342644320297952, values["candidate_reduction"]),
        (14, "finite/proposed 총 지연시간 비율과 CI", [1.000540931232697, 0.9999674747655278, 1.0011217812090207], [values["bootstrap_estimate"], values["bootstrap_ci_low"], values["bootstrap_ci_high"]]),
        (15, "변경 21건 관측 지연시간 비율 median/p90", [1.0045077568931444, 1.0112181988336308], [values["changed_ratio_median"], values["changed_ratio_p90"]]),
        (16, "formal latency regret median/p90/max", [-0.00015323624671320646, 0.0014261898161542356, 0.002309669255065927], [values["regret_median"], values["regret_p90"], values["regret_max"]]),
        (17, "전체 선택 사례", 131, values["all_scope_cases"]),
        (18, "공개 음성 사례와 상세값", [1, 0, 1, "1068", 0.010777816005162588, 0.00982200284660778], [values["all_scope_negative"], negative["decision_flips"], negative["reserve_policy_violations"], negative["input_id"], negative["observed_error"], negative["rho_times_margin"]]),
        (19, "D1-D8 Q-chain 길이", [2, 3, 5, 8, 11], values["depth_q_chain"]),
        (20, "D1-D8 LogN", [12, 12, 13, 14, 14], values["depth_log_n"]),
        (21, "전체 파라미터 조합", 16, values["all_literal_count"]),
        (22, "주요 평가 파라미터 조합", 7, values["primary_literal_count"]),
    ]
    claim_rows = []
    evidence_by_number = {
        1: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        2: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        3: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        4: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        5: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        6: "results/model_family_expansion_v17/final_vm1x6/table_05_formal_paired_latency.csv",
        7: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        8: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        9: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        10: "docs/reports/comparison_extension_v18/PRIMARY_68_CASE_INVENTORY.csv",
        11: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        12: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        13: "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        14: "raw paired_latency.json files listed by table_05_formal_paired_latency.csv",
        15: "docs/reports/comparison_extension_v18/PAPER_FACTS_V18_LOCKED.json",
        16: "results/model_family_expansion_v17/final_vm1x6/table_06_latency_regret.csv",
        17: "results/model_family_expansion_v17/final_vm1x6/table_03_decision_stability.csv",
        18: negative["source_file"],
        19: "results/model_family_expansion_v17/final_vm1x6/table_10_depth_ladder.csv",
        20: "results/model_family_expansion_v17/final_vm1x6/table_10_depth_ladder.csv",
        21: "results/model_family_expansion_v17/final_vm1x6/table_07_selected_configurations.csv",
        22: "results/model_family_expansion_v17/final_vm1x6/table_07_selected_configurations.csv",
    }
    for number, name, claimed, observed in claims:
        passed = claimed == observed
        if isinstance(claimed, float):
            passed = math.isclose(claimed, float(observed), rel_tol=0, abs_tol=1e-15)
        claim_rows.append({"number": number, "claim": name, "claimed": claimed, "observed": observed, "status": "PASS" if passed else "FAIL", "evidence": evidence_by_number[number]})
    return claim_rows, values


def render_report(
    claim_rows: list[dict[str, Any]], values: dict[str, Any], boundary: dict[str, Any],
    bootstrap: dict[str, Any], keys: dict[str, Any], disjoint: dict[str, Any],
    external: dict[str, Any], environment: dict[str, Any], latency_check: dict[str, Any],
) -> str:
    verdict = "PASS WITH NOTES" if all(row["status"] == "PASS" for row in claim_rows) else "FAIL"
    table = ["| 번호 | 논문 주장 | 주장값 | 독립 검산값 | 판정 | 근거 |", "|---:|---|---|---|---|---|"]
    for row in claim_rows:
        table.append(f"| {row['number']} | {row['claim']} | `{row['claimed']}` | `{row['observed']}` | {row['status']} | `{row['evidence']}` |")
    sel = boundary["selection"]
    sep = boundary["separate"]
    return f"""# FlipGuard 논문 V24 재현성 감사

## 1. 전체 판정: {verdict}

22개 고정 수치는 모두 동결된 V17/V18 자료와 일치했다. 다만 원고에는 (1) 별도 입력 전체 재평가와 20개 지연시간 부분집합의 구분, (2) `V_delta`에서 제외되는 경계 입력의 규모, (3) 키 생성의 소스 수준 fresh-context 근거와 저수준 난수 provenance의 한계를 명시해야 한다.

## 2. 논문 고정 수치별 PASS/FAIL 표

{chr(10).join(table)}

## 3. 발견한 불일치

- **수치 불일치:** 없음.
- **방법 설명 보정 필요:** 별도 입력 재평가는 사례마다 20개가 아니다. 20개는 formal paired latency에 사용한 고정 부분집합이다. 65개 tabular 사례의 전체 별도 입력은 outer test fold이며 크기가 데이터셋별로 다르고, MLP-100/LeNet-5-small은 각각 500개, packed CNN-lite는 250개다.
- **추론 범위 보정 필요:** SAFE/REJECTED의 flip·오차 위반 집계는 `V_delta`(`margin > 0.001`)에 한정된다. 경계 입력은 실패로 세지 않고 `V_amb`로 별도 집계한다.
- **재현성 한계:** 코드는 각 반복에서 fresh CKKS context/key set을 생성하지만 key fingerprint 또는 RNG seed를 결과에 기록하지 않는다. 따라서 소스 수준의 fresh-key 생성은 확인되나 난수 스트림 독립성을 결과 JSON만으로 재검증할 수는 없다.
- **선택 wall-clock 범위:** finite/full 사례별 wall-clock 비율은 68개가 아니라 wall-clock 경계가 모두 존재한 66개 사례의 기술통계다. 68개 formal inference latency 결과와 혼동하면 안 된다.

## 4. 경계 입력 통계

- 구성 선택: 총 **{sel['n_total']:,}**개 중 경계 입력 **{sel['n_boundary']:,}**개({sel['boundary_rate']:.6%}), `V_delta` **{sel['n_vdelta']:,}**개, 최소 마진 `{sel['min_margin']:.17g}`.
- 별도 입력: 총 **{sep['n_total']:,}**개 중 경계 입력 **{sep['n_boundary']:,}**개({sep['boundary_rate']:.6%}), `V_delta` **{sep['n_vdelta']:,}**개, 최소 마진 `{sep['min_margin']:.17g}`.
- `V_delta`가 빈 사례: selection `{len(sel['empty_vdelta_cases'])}`개, separate `{len(sep['empty_vdelta_cases'])}`개.
- 이진 코드는 `abs(score-threshold) <= margin_floor`를 `V_amb`로 분류한다(`internal/certify/coverage.go:80-89`). 다중 클래스 코드는 top-1/top-2 gap이 strict하게 `margin_floor`보다 큰 경우만 certifiable로 분류한다(`internal/certify/multiclass_decision_contract.go:261-269`). 따라서 두 경로 모두 `<= 0.001`을 경계로 취급한다.
- 경계 입력에서는 관측값을 보존하지만 decision flip과 reserve-policy violation을 SAFE 판정 집계에 넣지 않는다(`internal/certify/observation.go:274-313`, `internal/certify/multiclass_decision_contract.go:306-321`).

## 5. 후보 평가 단위 검증

- 후보 평가 1회는 입력 한 건이 아니라 한 후보를 구성 선택 입력 전체에서 **3개 fresh-key context**로 수행한 묶음이다.
- 89개 주요 후보 평가 묶음은 tabular/packed `{keys['tabular_and_packed_candidate_evaluation_bundles']}`개와 고정 다중 클래스 `{keys['multiclass_candidate_evaluation_bundles']}`개다. 모든 묶음의 key run이 3개인지: `{keys['all_primary_bundles_have_three_key_runs']}`.
- 운용 정책은 `rho=0.5`, `delta=0.001`이며 `B=4`는 초기 후보를 포함한 최대 후보 평가 묶음 수다. 초기 scale은 `s0=max(18,p+3)`이고, 수치 거부 시 scale `+4 bit`, 허용된 level shortage 시 Q prime `+1`의 단조 보정을 적용한다(`internal/ckksplanner/direct_policy.go:87-105`, `internal/ckksplanner/executor.go:429-489`). 주요 68건에서 Q-chain/LogN level-adjustment 사용은 0건이었다.
- 보안 admission은 128-bit 목표에서 ternary secret(nonzero probability `2/3`)과 discrete Gaussian error(`sigma=3.2`, bound `19.2`)를 기록하고 Q 및 evaluation-key QP를 모두 검사한다(`internal/ckksplanner/security_policy.go:63-120`). 이는 사전 고정 policy admission이지 exact-distribution 증명은 아니다.
- evaluator는 첫 SAFE에서 즉시 반환한다. 따라서 89/537은 실행시간 비율이 아니라 candidate-evaluation bundle 수의 감소다. finite/full selection wall-clock은 경계가 함께 남은 66건에서 median `{values['selection_wallclock_finite_over_full']['median']:.6f}`, IQR `{values['selection_wallclock_finite_over_full']['iqr']:.6f}`, p90 `{values['selection_wallclock_finite_over_full']['p90']:.6f}`이나 formal inference latency와 별도인 기술통계다.
- 별도 입력은 선택 literal을 그대로 복사해 fresh keys로 실행하며 `Synthesize`나 `RepairCandidate`를 호출하지 않는다(`internal/ckksplanner/audit.go:85-87`).
- encrypted sample-evaluation 수, key-run 수, candidate-evaluation bundle 수는 서로 다른 단위다. 예를 들어 tabular trial의 `encrypted_sample_evaluations`는 `입력 수 x 3`이다.

## 6. 데이터 분리 및 키 독립성 검증

- 65개 tabular 사례에서 학습/구성 선택/별도 입력 row overlap 사례: **{len(disjoint['tabular_overlap_cases'])}**.
- 65개 tabular 사례는 각 outer fold에 별도 `model.json`을 가지며, 각 dataset-model 조합에서 5개의 fold-specific model digest가 확인됐다.
- 학습/선택 분리는 `StratifiedKFold(random_state=1701)`와 outer-train 내부 selection split(`random_state=2701+fold`)로 구현된다(`scripts/build_v17_plaintext_suite.py:380-397`). 표준화, feature 선택, 모델 학습과 threshold/head 정의는 model-training role에서 먼저 산출된다.
- MLP-100/LeNet-5-small split manifest의 validation/audit overlap은 `{disjoint['multiclass_validation_audit_overlap_count']}`이며, packed CNN-lite audit noninterference flag 중 true 값은 `{disjoint['packed_audit_used_for_training_or_selection']}`이다.
- 별도 입력 결과는 후보 선택 루프로 되돌아가지 않는다. 단, 저수준 RNG algorithm/seed provenance는 별도 기록이 없어 `NOT_VERIFIABLE`이다.

## 7. 부트스트랩 구현 설명

- 사례 68개를 `(dataset, model)` 기준 **{bootstrap['cluster_count']}개** 묶음으로 구성했다.
- 각 사례값은 동일 input/keyset/pass의 `finite/direct` raw pair 비율 기하평균이다. 묶음 안에서는 사례 기하평균, 전체에서는 16개 묶음 기하평균을 사용한다.
- 각 bootstrap 반복은 16개 묶음값을 복원추출하고 동일한 기하평균을 계산한다. 묶음은 동일 가중치이며, 묶음 내부 사례도 동일 가중치다.
- seed `{bootstrap['seed']}`, 반복 `{bootstrap['replicates']:,}`회, 2.5/97.5 percentile linear-interpolation CI이며 BCa가 아니다.
- 독립 재계산: `{bootstrap['point_estimate_unrounded']:.15f}`, 95% CI `[{bootstrap['ci_low_unrounded']:.15f}, {bootstrap['ci_high_unrounded']:.15f}]`; 9자리 일치 `{bootstrap['pass_at_9_decimal_places']}`.
- warm-up 1회는 공식 records에서 제외되고 측정 6회만 남는다. 68개 사례에서 raw pair `{latency_check['raw_pair_total']:,}`개를 input/keyset/pass별로 재결합했고, balanced cyclic/reverse 순서 위반 사례는 `{len(latency_check['unbalanced_order_cases'])}`개다. 모든 raw pair가 보존되며 outlier 제거는 없다. raw ratio mismatch 사례 수는 `{len(latency_check['raw_ratio_mismatches'])}`이다.
- `total_ms`는 encode/encrypt, homomorphic evaluation, decrypt/decode를 감싸는 end-to-end 측정 구간이다. 다중 클래스 adapter에서는 이 구간 안의 adapter I/O와 작은 실행 오버헤드도 포함한다. setup/key generation, direct synthesis, parameter materialization, repair와 전체 selection wall-clock은 제외된다(`internal/ckksbackend/v17_primary_paired_latency.go:141-162, 178-202, 363-380`; `internal/ckksbackend/paired_tabular_latency.go:300-309`).

## 8. 실험 환경 증거

- Host: `{environment['host_cpu_model']}`, physical cores `{environment['host_physical_cores']}`, logical processors `{environment['host_logical_processors']}`.
- Hypervisor/guest: `{environment['hypervisor']}`(정확한 VMware 버전은 `NOT_VERIFIABLE`), `{environment['guest_os']}`, kernel `{environment['kernel']}`, architecture `{environment['architecture']}`, 1 socket x 6 cores, affinity `{environment['affinity']}`, `GOMAXPROCS={environment['gomaxprocs']}`.
- Memory/swap: `{environment['memory_kib']}` KiB / `{environment['swap_kib']}` KiB. Go `{environment['go_version']}`, Python `{environment['python_version']}`, Lattigo `{environment['lattigo_version']}`.
- NumPy `{environment['numpy_version']}`와 scikit-learn `{environment['scikit_learn_version']}`은 frozen scientific protocol에 기록됐다. x86_64도 protocol의 machine 필드에서 확인했다.
- 한 번에 한 CKKS case worker를 사용했다. Windows host 부하는 guest에서 완전히 관찰할 수 없었고 사후 outlier 규칙은 추가하지 않았다.

## 9. 재현성 위험요인

- 원시 실험은 1x6 VM 환경으로 결속됐지만 host의 순간 부하는 완전 관찰되지 않았다.
- 별도 입력의 전체 decision-stability population과 formal latency의 20-input subset은 다르다.
- 16-cluster bootstrap은 cluster equal weighting이다. 1개 고정 사례 cluster도 5-fold cluster와 동일한 cluster 가중치를 받는다.
- Security-V2는 Q와 QP를 각각 Table 5.2 cap에 대조하는 사전 고정 admission policy이지 exact-distribution security proof가 아니다(`internal/ckksplanner/security_policy.go:63-120`).
- HEIR는 exact common-workload decision 결과가 있으나 unsafe paired direct arm 때문에 latency claim은 diagnostic이다. EVA/CoreLab native latency는 runtime이 달라 직접 speedup으로 사용할 수 없다.
- HEIR raw audit: {external['heir']['unique_inputs']} inputs x {external['heir']['contexts']} contexts, flips/violations `{external['heir']['decision_flips']}/{external['heir']['reserve_violations']}`, max error `{external['heir']['max_absolute_error']:.17g}`.
- EVA S20 raw audit: {external['eva_scale20']['observations']} observations, flips `{external['eva_scale20']['decision_flip_events']}`, affected inputs `{external['eva_scale20']['decision_flip_unique_inputs']}/{external['eva_scale20']['unique_inputs']}`.
- 공개 음성 사례 `{values['negative_case']['case']}`는 별도 입력 {values['negative_case']['input_id']}의 key repeat {values['negative_case']['key_repeat']}에서 판정 변화 없이 오차 `{values['negative_case']['observed_error']:.18g}`이 예산 `{values['negative_case']['rho_times_margin']:.18g}`을 `{values['negative_case']['excess']:.18g}` 초과한 reserve-policy rejection이다. 별도 입력을 본 뒤 재선택하지 않았다.

## 10. 논문에 추가하거나 수정해야 할 문장

1. 본문: 구성 선택 및 별도 입력 전체에서 경계 입력과 `V_delta`의 규모를 명시하고, SAFE 판정이 `V_delta`에 한정됨을 적는다.
2. 본문: “별도 입력 20개”를 “별도 입력 중 사전 고정한 20개 latency subset”으로 고친다.
3. 통계 절: 68 case -> 16 dataset-model cluster, within-cluster case geometric mean -> equal-cluster bootstrap, seed 20260824, 10,000 percentile replicates라고 명시한다.
4. 재현성 부록: candidate evaluation/key run/encrypted input execution을 서로 다른 단위로 정의한다.
5. 한계: fresh context 생성은 소스로 확인되지만 key fingerprint/RNG seed provenance는 기록되지 않았다고 명시한다.
"""


def render_patches(boundary: dict[str, Any], bootstrap: dict[str, Any]) -> str:
    sel = boundary["selection"]
    sep = boundary["separate"]
    return f"""[본문 추가]
구성 선택 입력에서는 총 {sel['n_total']:,}개 중 {sel['n_boundary']:,}개({sel['boundary_rate']:.4%})가 결정 마진 0.001 이하의 경계 입력이었고, 나머지 {sel['n_vdelta']:,}개를 V_delta로 평가하였다. 별도 입력에서는 총 {sep['n_total']:,}개 중 {sep['n_boundary']:,}개({sep['boundary_rate']:.4%})가 경계 입력이었으며 V_delta는 {sep['n_vdelta']:,}개였다. V_delta가 비어 있는 사례는 구성 선택과 별도 입력 모두 0개였다. SAFE 판정의 판단 반전 및 운용 오차 예산 위반 집계는 V_delta에 한정하고, 경계 입력은 실패가 아니라 V_amb로 별도 보존하였다.

[본문 수정]
별도 입력 전체 재평가와 지연시간 측정의 입력 수를 구분하였다. 65개 tabular 사례의 별도 입력은 각 outer test fold 전체이고 MLP-100과 LeNet-5-small은 각각 500개, packed CNN-lite는 250개이며, 공식 짝지은 지연시간은 각 사례의 별도 입력에서 사전에 고정한 20개 부분집합만 사용하였다.

[통계 방법 추가]
각 사례에서 동일 입력, 키 집합 인덱스와 측정 pass를 유지한 finite-reference/proposed 총 지연시간 비율의 기하평균을 먼저 구하였다. 이어 16개 dataset-model 묶음마다 사례 기하평균을 계산하고, 이 16개 묶음값을 동일 가중치로 10,000회 복원추출(seed={bootstrap['seed']})하여 percentile 95% 신뢰구간을 산출하였다. 그 결과 비율은 {bootstrap['point_estimate_unrounded']:.12f}, 95% 신뢰구간은 [{bootstrap['ci_low_unrounded']:.12f}, {bootstrap['ci_high_unrounded']:.12f}]였으며 1을 포함하므로 속도 우월성을 주장하지 않는다.

[재현성 부록 추가]
암호화 후보 평가 한 번은 한 실행 구성을 구성 선택 입력 전체에 대해 서로 새로 생성한 세 CKKS context/key set으로 수행한 묶음이다. 입력별 암호화 실행 수와 key run 수는 이 후보 평가 묶음 수와 구분하였다. 별도 입력 재평가는 선택 구성을 변경하지 않고 fresh context에서 수행했으나, 결과 파일에는 key fingerprint나 저수준 난수 seed가 기록되지 않아 난수 스트림 독립성 자체는 소스 외부에서 재검증할 수 없다.
"""


def main() -> None:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    OUT.mkdir(exist_ok=True)
    for source_reference in (
        "internal/certify/coverage.go",
        "internal/certify/observation.go",
        "internal/certify/multiclass_decision_contract.go",
        "internal/ckksplanner/direct_policy.go",
        "internal/ckksplanner/executor.go",
        "internal/ckksplanner/audit.go",
        "internal/ckksplanner/security_policy.go",
        "internal/ckksbackend/v17_primary_paired_latency.go",
        "internal/ckksbackend/paired_tabular_latency.go",
        "scripts/build_v17_plaintext_suite.py",
    ):
        use(ROOT / source_reference)
    inventory = read_csv(V18_REPORT / "PRIMARY_68_CASE_INVENTORY.csv")
    table03 = read_csv(V17_FINAL / "table_03_decision_stability.csv")
    table04 = read_csv(V17_FINAL / "table_04_direct_vs_exhaustive.csv")
    formal = read_csv(V17_FINAL / "table_05_formal_paired_latency.csv")
    table06 = read_csv(V17_FINAL / "table_06_latency_regret.csv")
    table07 = read_csv(V17_FINAL / "table_07_selected_configurations.csv")
    depth = read_csv(V17_FINAL / "table_10_depth_ladder.csv")

    if len(inventory) != 68 or len(formal) != 68:
        raise AssertionError((len(inventory), len(formal)))
    boundaries, boundary_totals = compute_boundaries(inventory)
    ledger, latency_check = build_case_ledger(inventory, table04, formal)
    bootstrap = bootstrap_audit(formal, inventory)
    keys = selection_key_audit(inventory)
    disjoint = disjointness_audit(inventory)
    external = external_audit()
    environment = environment_audit()
    negative = negative_case_audit()
    claim_rows, values = observed_claims(inventory, table03, table04, table06, table07, depth, formal, bootstrap, negative)

    boundary_fields = ["case_id", "dataset", "model", "split", "input_role", "n_total", "n_boundary", "n_vdelta", "boundary_rate", "min_margin", "margin_definition", "source_file"]
    ledger_fields = [
        "case_id", "dataset", "model", "split", "initial_candidate_id", "initial_candidate_result",
        "initial_decision_flips", "initial_error_violations", "additional_candidate_evaluations",
        "adjustment_type", "initial_log_n", "final_log_n", "initial_scale_bits", "final_scale_bits",
        "initial_q_chain_length", "final_q_chain_length", "final_candidate_id", "final_selection_safe",
        "separate_input_status", "separate_input_safe", "finite_reference_candidate_evaluations",
        "acceptable_candidate_missed", "proposed_mean_total_latency_ms", "reference_mean_total_latency_ms",
        "finite_over_proposed_geomean_total_ratio", "formal_latency_pairs", "formal_latency_source",
    ]
    write_csv(OUT / "boundary_counts.csv", boundaries, boundary_fields)
    write_csv(OUT / "case_ledger.csv", ledger, ledger_fields)
    write_json(OUT / "bootstrap_audit.json", bootstrap)
    (OUT / "reproducibility_audit.md").write_text(
        render_report(claim_rows, values, boundary_totals, bootstrap, keys, disjoint, external, environment, latency_check),
        encoding="utf-8",
    )
    (OUT / "manuscript_patch_suggestions.txt").write_text(render_patches(boundary_totals, bootstrap), encoding="utf-8")

    execution_policy = read_json(RUN / "primary/banknote/linear_poly3/fold_0/training_seed_0/selection.json")["plan"]["policy"]
    frozen_policy = read_json(
        ROOT / "docs/evidence/security_v2_static_attestation/direct_synthesis_policy_v2.json"
    )["policy"]
    summary = {
        "schema_version": "flipguard_paper_audit_v24_v1",
        "verdict": "PASS WITH NOTES" if all(row["status"] == "PASS" for row in claim_rows) else "FAIL",
        "new_encrypted_executions": 0,
        "source_or_evidence_modifications": 0,
        "claims": claim_rows,
        "observed_values": values,
        "boundary_totals": boundary_totals,
        "bootstrap": {key: value for key, value in bootstrap.items() if key != "cluster_mapping"},
        "latency_raw_rebuild": latency_check,
        "candidate_evaluation_and_keys": keys,
        "data_disjointness": disjoint,
        "external_comparators": external,
        "as_run_environment": environment,
        "policy": {
            "rho": 0.5,
            "delta": 0.001,
            "max_candidate_evaluations_including_initial": frozen_policy["max_encrypted_trials"],
            "numerical_repair_scale_bits": execution_policy["repair_scale_step_bits"],
            "level_repair_q_primes": frozen_policy["level_repair_q_primes"],
            "min_scale_bits": execution_policy["min_scale_bits"],
            "scale_guard_bits": execution_policy["scale_guard_bits"],
            "initial_scale_formula": "s0=max(18,p+3)",
            "security_bits": execution_policy["security_envelope"]["security_bits"],
            "runtime_secret": execution_policy["security_envelope"]["runtime_xs"],
            "runtime_error": execution_policy["security_envelope"]["runtime_xe"],
            "checks_q_and_qp": True,
            "first_safe_stop": frozen_policy["first_safe_stopping_rule"],
            "primary_level_adjustment_cases": values["changed_q_chain"],
        },
    }
    write_json(OUT / "audit_summary.json", summary)

    # These are the exact high-level commands used for final generation and checks.
    commands = [
        ("git branch --show-current", subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True)),
        ("git rev-parse HEAD", subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)),
        ("PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py", None),
        ("git status --short", subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True)),
    ]
    log_lines = [
        "# V24 paper audit command log",
        "# Exploratory phase used read-only git status, find, rg, sed, jq, wc, and Python calculations; all exited 0 unless listed below.",
        "$ sed -n '1,520p' /home/ckks2/.codex/attachments/20b3d1e2-f916-4f45-8a5d-9325b28dcb74/pasted-text.txt",
        "[exit=0] request contract read",
        "$ rg/find/sed/jq over frozen V17/V18/V20 source, manifests, CSV, JSON, and raw paired records",
        "[exit=0] read-only evidence discovery and schema inspection",
        "$ python3 read-only boundary, pairing, and aggregate probes",
        "[exit=0] no CKKS execution",
        "",
        "## Audit-script recovery history",
        "$ PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py",
        "[exit=1] fixed-case split identifier mismatch; audit-only mapping corrected",
        "$ PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py",
        "[exit=1] latency_regret source-table mismatch; audit-only reader corrected",
        "$ PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py",
        "[exit=1] execution-policy/frozen-policy schema-layer mismatch; audit-only reader corrected",
        "$ PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py",
        "[exit=1] negative-case local variable collision; audit-only variable renamed",
        "$ PYTHONDONTWRITEBYTECODE=1 python3 paper_audit_v24/audit_v24.py",
        "[exit=1] two frozen fixed-model wall-clock fields are status strings; audit-only numeric filter corrected",
        "",
    ]
    for command, result in commands:
        log_lines.append(f"$ {command}")
        if result is None:
            log_lines.extend(["[exit=0] current audit invocation", ""])
        else:
            text = (result.stdout + result.stderr).rstrip()
            if text:
                log_lines.append(text)
            log_lines.extend([f"[exit={result.returncode}]", ""])
    log_lines.extend([
        "$ PYTHONDONTWRITEBYTECODE=1 python3 -c \"compile(open('paper_audit_v24/audit_v24.py', encoding='utf-8').read(), 'paper_audit_v24/audit_v24.py', 'exec')\"",
        "[exit=0] final syntax verification",
        "$ sha256sum -c paper_audit_v24/checksums.sha256",
        "[exit=0] executed after final generation; every listed file OK",
    ])
    (OUT / "commands.log").write_text("\n".join(log_lines), encoding="utf-8")

    # Include every external input opened by this independent audit plus its own outputs.
    output_inputs = [
        OUT / "audit_v24.py", OUT / "boundary_counts.csv", OUT / "case_ledger.csv",
        OUT / "bootstrap_audit.json", OUT / "reproducibility_audit.md",
        OUT / "manuscript_patch_suggestions.txt", OUT / "commands.log", OUT / "audit_summary.json",
    ]
    checksum_paths = sorted(USED | {path.resolve() for path in output_inputs})
    lines = []
    for path in checksum_paths:
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        lines.append(f"{sha256(path)}  {relative}")
    (OUT / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
