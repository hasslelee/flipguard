#!/usr/bin/env python3
"""Verify the predeclared actual-Orion adapter audit contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/orion_external_adapter_v1/contract.json"
)
SCHEMA_VERSION = "flipguard_orion_external_adapter_contract_v1"
ORION_COMMIT = "be8a827350a147d610fe3bb998b5bea8de814ff8"
ORION_BACKEND_COMMIT = "a9699d924dcc2628153b1ca3bf41d65b26299a86"
TARGET_BACKEND_COMMIT = "c1fd095f08602e2d4ef571db015fc553fdd2d845"
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
EXPECTED_CONFIGS = {
    "orion_mlp_public_config": {
        "RING_TYPE_MISMATCH",
        "SECRET_DISTRIBUTION_MISMATCH",
        "ERROR_DISTRIBUTION_NOT_SERIALIZED",
        "BACKEND_IMPLEMENTATION_NOT_IDENTICAL",
        "SECURITY_V2_INADMISSIBLE",
    },
    "orion_lola_public_config": {
        "RING_TYPE_MISMATCH",
        "SECRET_DISTRIBUTION_MISMATCH",
        "ERROR_DISTRIBUTION_NOT_SERIALIZED",
        "BACKEND_IMPLEMENTATION_NOT_IDENTICAL",
        "SECURITY_V2_INADMISSIBLE",
    },
    "orion_resnet_public_config": {
        "SECRET_DISTRIBUTION_MISMATCH",
        "ERROR_DISTRIBUTION_NOT_SERIALIZED",
        "BACKEND_IMPLEMENTATION_NOT_IDENTICAL",
        "SECURITY_POLICY_UNSUPPORTED_LOGN",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def validate_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    if not path.is_absolute():
        path = REPO_ROOT / path
    contract = load_json(path)
    require(contract["schema_version"] == SCHEMA_VERSION, "schema changed")
    require(
        contract["status"] == "PREDECLARED_BEFORE_STATIC_AUDIT",
        "contract status changed",
    )
    require(
        contract["adapter_id"] == "orion_lattigo_config_adapter_v1",
        "adapter ID changed",
    )
    require(
        contract["paper_claim_allowed"] is False,
        "paper claim gate opened",
    )

    upstream = contract["upstream"]
    require(upstream["commit"] == ORION_COMMIT, "Orion commit changed")
    require(
        upstream["backend_commit"] == ORION_BACKEND_COMMIT,
        "Orion backend commit changed",
    )
    require(
        upstream["comparison_backend_commit"] == TARGET_BACKEND_COMMIT,
        "target backend commit changed",
    )
    require(
        upstream["backend_module"] ==
        "github.com/baahl-nyu/lattigo/v6",
        "Orion backend module changed",
    )
    require(
        upstream["comparison_backend_module"] ==
        "github.com/tuneinsight/lattigo/v6",
        "target backend module changed",
    )

    sources = contract["sources"]
    require(len(sources) == 9, "source inventory changed")
    source_ids = {entry["source_id"] for entry in sources}
    require(len(source_ids) == 9, "source IDs are not unique")
    for source in sources:
        digest = source["sha256"]
        require(
            isinstance(digest, str) and digest.startswith("sha256:") and
            len(digest) == 71,
            f"{source['source_id']}: invalid digest",
        )
        require(
            source["repository"] in {
                "orion",
                "orion_lattigo",
                "comparison_lattigo",
            },
            f"{source['source_id']}: unsupported repository",
        )

    configs = contract["configurations"]
    require(len(configs) == 3, "configuration inventory changed")
    seen: set[str] = set()
    for config in configs:
        config_id = config["config_id"]
        require(config_id in EXPECTED_CONFIGS, "unexpected configuration")
        require(config_id not in seen, "duplicate configuration")
        seen.add(config_id)
        require(
            config["source_id"] in source_ids,
            f"{config_id}: source missing",
        )
        require(
            config["predicted_status"] ==
            "BLOCKED_SEMANTIC_MISMATCH",
            f"{config_id}: predicted status changed",
        )
        require(
            set(config["predicted_reasons"]) ==
            EXPECTED_CONFIGS[config_id],
            f"{config_id}: predicted reasons changed",
        )
    require(seen == set(EXPECTED_CONFIGS), "configuration set changed")

    policies = contract["frozen_policies"]
    require(
        policies["security_policy_digest"] == SECURITY_POLICY_DIGEST,
        "Security V2 digest changed",
    )
    require(
        policies["direct_policy_digest"] == DIRECT_POLICY_DIGEST,
        "Direct V2 digest changed",
    )
    require(
        policies["policy_modification_allowed"] is False,
        "policy modification was enabled",
    )
    execution = contract["execution"]
    require(
        execution["encrypted_execution_allowed"] is False,
        "encrypted execution was enabled",
    )
    require(
        execution["candidate_request_emission_requires_exact_semantics"]
        is True,
        "exactness gate was disabled",
    )
    require(
        execution["existing_evidence_overwrite_allowed"] is False,
        "evidence overwrite was enabled",
    )
    require(
        contract["claim_boundary"]["third_party_autotuner_integration"] ==
        "NOT_EVALUATED because Orion's public YAML files are compiler "
        "configurations, not outputs attributed to an autotuning run",
        "autotuner claim boundary changed",
    )
    return {
        "schema_version": contract["schema_version"],
        "source_count": len(sources),
        "configuration_count": len(configs),
        "encrypted_execution_allowed": False,
        "paper_claim_allowed": False,
    }


def main() -> int:
    args = parse_args()
    summary = validate_contract(args.contract)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
