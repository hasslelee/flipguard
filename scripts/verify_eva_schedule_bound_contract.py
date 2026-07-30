#!/usr/bin/env python3
"""Verify the predeclared EVA schedule-bound adapter contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/eva_schedule_bound_adapter_v1/contract.json"
)
EXPECTED_SCHEMA = "flipguard_eva_schedule_bound_adapter_contract_v1"
SECURITY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
DIRECT_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args()


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


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


def verify(contract_path: Path) -> dict[str, Any]:
    contract_path = absolute(contract_path)
    contract = load_json(contract_path)
    require(
        contract["schema_version"] == EXPECTED_SCHEMA,
        "contract schema changed",
    )
    require(
        contract["status"] ==
        "PREDECLARED_BEFORE_ENCRYPTED_EXECUTION",
        "contract is not predeclared",
    )
    require(contract["paper_claim_allowed"] is False, "paper gate opened")
    policy = contract["policy"]
    require(
        policy["security_policy_digest"] == SECURITY_DIGEST,
        "Security V2 digest changed",
    )
    require(
        policy["direct_policy_digest"] == DIRECT_DIGEST,
        "Direct Policy V2 digest changed",
    )
    require(
        policy["margin_floor"] == 0.001
        and policy["safety_factor"] == 0.5
        and policy["validation_key_repeats"] == 3
        and policy["audit_key_repeats"] == 3
        and policy["candidate_trials"] == 1
        and policy["synthesis_calls"] == 0
        and policy["repair_calls"] == 0
        and policy["retuning"] == 0,
        "execution policy changed",
    )

    schedule_meta = contract["schedule"]
    schedule_path = absolute(Path(schedule_meta["contract_path"]))
    require(
        sha256_path(schedule_path) == schedule_meta["contract_sha256"],
        "schedule contract digest changed",
    )
    schedule = load_json(schedule_path)
    request = load_json(
        absolute(Path(schedule_meta["candidate_request_path"]))
    )
    require(request["schema_version"] == 3, "request is not schema v3")
    require(
        request["execution_schedule"]["contract_artifact"]["sha256"]
        == schedule_meta["contract_sha256"],
        "request does not bind the schedule contract",
    )
    require(
        request["execution_schedule"]["schedule_id"]
        == schedule["schedule_id"]
        == schedule_meta["schedule_id"],
        "schedule ID mismatch",
    )
    require(
        request["parameters"] == schedule["parameters"],
        "request and schedule literals differ",
    )
    require(
        schedule["compiled_program"]["sha256"]
        == schedule_meta["compiled_program_sha256"],
        "compiled-program declaration changed",
    )
    require(
        schedule["compiler_output"]["sha256"]
        == schedule_meta["compiler_output_sha256"],
        "compiler-output declaration changed",
    )
    for field in ("compiled_program", "compiler_output"):
        binding = schedule[field]
        require(
            sha256_path(absolute(Path(binding["path"])))
            == binding["sha256"],
            f"{field} artifact digest changed",
        )
    workload = contract["workload"]
    for field, digest_field in (
        ("model_path", "model_sha256"),
        ("validation_path", "validation_sha256"),
        ("audit_path", "audit_sha256"),
        ("split_manifest_path", "split_manifest_sha256"),
    ):
        require(
            sha256_path(absolute(Path(workload[field])))
            == workload[digest_field],
            f"{field} digest changed",
        )
    require(
        schedule["model_artifact_sha256"] == workload["model_sha256"],
        "schedule model binding changed",
    )
    require(
        schedule["required_q_primes"] == 3
        and schedule["rescale_levels"] == 2
        and schedule["input_scale_bits"] == 20
        and schedule["output_scale_bits"] == 20
        and schedule["retuning"] == 0,
        "schedule requirements changed",
    )
    q = schedule["parameters"]["q"]
    p = schedule["parameters"]["p"]
    require(len(q) == 3 and len(p) == 1, "exact Q/P counts changed")
    log_q = sum(value.bit_length() for value in q)
    log_p = sum(value.bit_length() for value in p)
    require(
        log_q == 180 and log_p == 60 and log_q + log_p == 240,
        "exact modulus accounting changed",
    )
    require(240 <= 430, "EVA literal is Security V2 inadmissible")
    dot = absolute(Path(schedule["compiled_program"]["path"])).read_text(
        encoding="ascii"
    )
    require(dot.count('label="Rescale(60)"') == 2, "rescale count changed")
    for token in (
        'label="ModSwitch"',
        'label="Relinearize"',
        'label="scale=20"',
        'label="scale=40"',
        'label="scale=60"',
    ):
        require(token in dot, f"compiled schedule token missing: {token}")
    return {
        "schema_version": EXPECTED_SCHEMA,
        "status": "PASS",
        "contract_sha256": sha256_path(contract_path),
        "schedule_contract_sha256": sha256_path(schedule_path),
        "schedule_id": schedule["schedule_id"],
        "log_q": log_q,
        "log_p": log_p,
        "log_qp": log_q + log_p,
        "security_v2_cap": 430,
        "security_v2_headroom_bits": 190,
        "rescale_levels": schedule["rescale_levels"],
        "required_q_primes": schedule["required_q_primes"],
        "paper_claim_allowed": False,
    }


def main() -> None:
    summary = verify(parse_args().contract)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
