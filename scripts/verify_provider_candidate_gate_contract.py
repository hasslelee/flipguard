#!/usr/bin/env python3
"""Verify the predeclared provider-candidate interoperability contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/provider_candidate_gate_v1/contract.json"
)
SCHEMA_VERSION = (
    "flipguard_provider_candidate_gate_interoperability_contract_v2"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
EXPECTED_ARM_ORDER = [
    "manual_literal",
    "bounded_catalog_literal",
    "external_autotuner_format_fixture",
    "direct_synthesizer_literal",
]
EXPECTED_PROVIDER_KINDS = {
    "manual_literal": "manual",
    "bounded_catalog_literal": "bounded_catalog",
    "external_autotuner_format_fixture": "external_autotuner",
    "direct_synthesizer_literal": "direct_synthesizer",
}
REQUEST_KEYS = {
    "schema_version",
    "provider_kind",
    "provider_id",
    "path",
    "parameters",
}
PARAMETER_KEYS = {
    "log_n",
    "log_q",
    "log_p",
    "log_default_scale",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def resolve(relative: str) -> Path:
    path = REPO_ROOT / relative
    require(path.is_file(), f"missing bound artifact: {relative}")
    return path


def verify_bound_file(relative: str, expected: str) -> Path:
    path = resolve(relative)
    require(
        sha256_path(path) == expected,
        f"bound artifact digest changed: {relative}",
    )
    return path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="ascii") as handle:
        return list(csv.DictReader(handle))


def validate_candidate_request(
    arm: dict[str, Any],
) -> dict[str, Any]:
    path = resolve(arm["candidate_path"])
    request = load_json(path)
    require(
        set(request) == REQUEST_KEYS,
        f"{path}: candidate request fields changed",
    )
    require(
        set(request["parameters"]) == PARAMETER_KEYS,
        f"{path}: candidate parameter fields changed",
    )
    require(
        request["schema_version"] == 1,
        f"{path}: schema changed",
    )
    require(
        request["provider_kind"] == arm["provider_kind"] ==
        EXPECTED_PROVIDER_KINDS[arm["arm_id"]],
        f"{path}: provider kind changed",
    )
    require(request["path"] == "rescale", f"{path}: path changed")
    parameters = request["parameters"]
    require(
        isinstance(parameters["log_n"], int) and
        parameters["log_n"] > 0,
        f"{path}: invalid log_n",
    )
    for field in ("log_q", "log_p"):
        require(
            isinstance(parameters[field], list) and
            parameters[field] and
            all(
                isinstance(value, int) and value > 0
                for value in parameters[field]
            ),
            f"{path}: invalid {field}",
        )
    require(
        isinstance(parameters["log_default_scale"], int) and
        parameters["log_default_scale"] > 0,
        f"{path}: invalid default scale",
    )
    return request


def validate_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    if not path.is_absolute():
        path = REPO_ROOT / path
    contract = load_json(path)
    require(
        contract["schema_version"] == SCHEMA_VERSION,
        "provider interoperability schema changed",
    )
    require(
        contract["status"] == "PREDECLARED_BEFORE_ENCRYPTED_EXECUTION",
        "provider interoperability status changed",
    )
    require(
        contract["paper_claim_allowed"] is False,
        "provider interoperability paper gate opened",
    )
    recovery = contract["recovery_from"]
    require(
        recovery["superseded_contract_sha256"] ==
        "sha256:"
        "429dcf909626a4eaaa36e730b134b9d3be9ef71132de0f708e96897a888dd3a7"
        and recovery["reason_code"] ==
        "SELECTION_SPLIT_ID_MANIFEST_MISMATCH"
        and recovery["execution_semantics_changed"] is False
        and recovery["candidate_literals_changed"] is False
        and recovery["policy_changed"] is False
        and recovery["corrected_field"] == "workload.split_id",
        "provider interoperability recovery declaration changed",
    )

    workload = contract["workload"]
    require(
        (
            workload["split_seed"],
            workload["seed_role"],
            workload["dataset_id"],
            workload["model_id"],
            workload["split_id"],
            workload["validation_rows"],
            workload["audit_rows"],
        ) == (
            0,
            "development",
            "iris_binary",
            "linear_poly3",
            "split_seed_0",
            14,
            16,
        ),
        "provider interoperability workload changed",
    )
    model_path = verify_bound_file(
        workload["model_path"],
        workload["model_sha256"],
    )
    validation_path = verify_bound_file(
        workload["validation_path"],
        workload["validation_sha256"],
    )
    audit_path = verify_bound_file(
        workload["audit_path"],
        workload["audit_sha256"],
    )
    split_path = verify_bound_file(
        workload["split_manifest_path"],
        workload["split_manifest_sha256"],
    )
    require(
        len(read_csv_rows(validation_path)) == workload["validation_rows"],
        "validation row count changed",
    )
    require(
        len(read_csv_rows(audit_path)) == workload["audit_rows"],
        "audit row count changed",
    )
    split = load_json(split_path)
    require(
        split["model_artifact_digest"] == workload["model_sha256"] and
        split["configuration_validation"]["csv_digest"] ==
        workload["validation_sha256"] and
        split["locked_audit_test"]["csv_digest"] ==
        workload["audit_sha256"] and
        split["model_artifact"] == workload["model_path"],
        "split manifest binding changed",
    )
    require(model_path.is_file(), "model artifact missing")

    policy = contract["policy"]
    require(
        policy["security_policy_digest"] == SECURITY_POLICY_DIGEST and
        policy["direct_policy_digest"] == DIRECT_POLICY_DIGEST and
        policy["margin_floor"] == 0.001 and
        policy["safety_factor"] == 0.5 and
        policy["validation_key_repeats"] == 3 and
        policy["audit_key_repeats"] == 3 and
        policy["candidate_trials_per_arm"] == 1 and
        policy["synthesis_calls_per_arm"] == 0 and
        policy["repair_calls_per_arm"] == 0 and
        policy["retuning_after_audit"] == 0,
        "provider interoperability policy changed",
    )
    security_policy = load_json(
        REPO_ROOT /
        "docs/evidence/security_v2_static_attestation_formal_v2/"
        "security_policy_v2.json"
    )
    direct_policy = load_json(
        REPO_ROOT /
        "docs/evidence/security_v2_static_attestation_formal_v2/"
        "direct_synthesis_policy_v2.json"
    )
    require(
        security_policy["policy_sha256"] == SECURITY_POLICY_DIGEST and
        direct_policy["policy_sha256"] == DIRECT_POLICY_DIGEST,
        "frozen policy artifact digest changed",
    )

    arms = contract["arms"]
    require(
        [arm["arm_id"] for arm in arms] == EXPECTED_ARM_ORDER,
        "provider interoperability arm order changed",
    )
    requests = {
        arm["arm_id"]: validate_candidate_request(arm)
        for arm in arms
    }

    lineage = contract["source_lineage"]
    direct_path = verify_bound_file(
        lineage["direct_selection_path"],
        lineage["direct_selection_sha256"],
    )
    direct = load_json(direct_path)
    require(
        direct["outcome"] == "SELECTED" and
        direct["selected"]["id"] ==
        lineage["direct_selected_candidate_id"],
        "direct source selection changed",
    )
    direct_parameters = direct["selected"]["parameters"]
    for arm_id in (
        "manual_literal",
        "external_autotuner_format_fixture",
        "direct_synthesizer_literal",
    ):
        require(
            requests[arm_id]["parameters"] == direct_parameters,
            f"{arm_id}: literal differs from frozen direct source",
        )

    oracle_path = verify_bound_file(
        lineage["catalog_oracle_path"],
        lineage["catalog_oracle_sha256"],
    )
    matching = [
        row for row in read_csv_rows(oracle_path)
        if row["split_seed"] == str(workload["split_seed"])
        and row["dataset_id"] == workload["dataset_id"]
        and row["model_id"] == workload["model_id"]
        and float(row["alpha"]) == lineage["catalog_alpha"]
    ]
    require(len(matching) == 1, "catalog lineage row is not unique")
    require(
        matching[0]["oracle_candidate"] ==
        lineage["catalog_selected_candidate_id"],
        "catalog source selection changed",
    )
    inventory = load_json(resolve(lineage["catalog_inventory_path"]))
    profile_id = lineage["catalog_selected_candidate_id"].split("__", 1)[0]
    profiles = [
        row for row in inventory["catalog_profiles"]
        if row["candidate_id"] == profile_id
    ]
    require(len(profiles) == 1, "catalog inventory profile is not unique")
    require(
        profiles[0]["v2_security"]["final_admission"] == "PASS" and
        profiles[0]["parameters"] ==
        requests["bounded_catalog_literal"]["parameters"],
        "catalog literal or Security V2 admission changed",
    )

    rules = contract["execution_rules"]
    require(
        rules["arm_order"] == EXPECTED_ARM_ORDER and
        rules["no_concurrent_ckks_process"] is True and
        rules["continue_after_scientific_negative"] is True and
        rules["stop_on_integrity_block"] is True and
        rules["overwrite_existing_run"] is False and
        rules["result_driven_policy_change"] is False and
        rules["result_driven_candidate_change"] is False,
        "provider interoperability execution rules changed",
    )
    return {
        "contract_path": str(path.relative_to(REPO_ROOT)),
        "contract_sha256": sha256_path(path),
        "arm_count": len(arms),
        "validation_rows": len(read_csv_rows(validation_path)),
        "audit_rows": len(read_csv_rows(audit_path)),
        "paper_claim_allowed": False,
    }


def main() -> int:
    args = parse_args()
    summary = validate_contract(args.contract)
    print(
        "provider_candidate_gate_contract=VERIFIED "
        f"arms={summary['arm_count']} "
        f"validation_rows={summary['validation_rows']} "
        f"audit_rows={summary['audit_rows']} "
        f"digest={summary['contract_sha256']} "
        "paper_claim_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
