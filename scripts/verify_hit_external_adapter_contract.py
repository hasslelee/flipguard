#!/usr/bin/env python3
"""Verify the predeclared AWS HIT parameter-selector replay contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/hit_external_adapter_v1/contract.json"
)
SCHEMA_VERSION = "flipguard_hit_external_adapter_contract_v1"
HIT_COMMIT = "902e87e0b96a2d270f4cc010ab1742aa062aa198"
WRAPPER_COMMIT = "826c9d1f33594b790c40d578a5ec3b2268fe762c"
LATTIGO_V2_COMMIT = "c629f0c9518f6117141f54e441d6ca5d765f8868"
LATTIGO_V6_COMMIT = "c1fd095f08602e2d4ef571db015fc553fdd2d845"
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
EXPECTED_SOURCES = {
    "hit_parameter_formula": (
        "sha256:"
        "57875a14ab215d3f1aa3c30ab9bbb95449fedccc4d82bde01b2cc8917ea76785"
    ),
    "hit_wrapper_pin": (
        "sha256:"
        "418afc453c8d0423c6ab1e36702e88219b0b7ddc1071a507455fa71f412b78e8"
    ),
    "wrapper_materializer": (
        "sha256:"
        "e39c99bcc880d203f491660ca8b296f75472222bcf38cc9d43f40d96b17d8fb6"
    ),
    "wrapper_go_module": (
        "sha256:"
        "3b15acc305e6577a847cc56898d9a11c9b0f2c9ba8665b126e2bd8250f088bf8"
    ),
    "lattigo_v2_keygen": (
        "sha256:"
        "7fab7633de0b08b98dd07ee086bea992b280665e5466b579c64715e4f9b754f4"
    ),
    "lattigo_v2_params": (
        "sha256:"
        "bd9669070e95dfbe451475ca6b3d6465e702156964521e335ddeab17715a9d28"
    ),
    "lattigo_v6_params": (
        "sha256:"
        "972f08d26e63e884c0e3b4ffb100fe9345ea92d3d8bae966cfad78af55c60b7f"
    ),
    "lattigo_v6_sampler": (
        "sha256:"
        "e4755efef7d55b33ab92442fc64c14fc937b53c24efc4771a7b255394c8721b9"
    ),
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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    path = path if path.is_absolute() else REPO_ROOT / path
    contract = load_json(path)
    require(contract["schema_version"] == SCHEMA_VERSION, "schema changed")
    require(
        contract["status"] ==
        "PREDECLARED_BEFORE_SOURCE_REPLAY_OR_ENCRYPTED_EXECUTION",
        "contract status changed",
    )
    require(
        contract["classification"] ==
        "SOURCE_REPLAYED_PUBLIC_PARAMETER_SELECTOR",
        "candidate classification changed",
    )
    require(
        contract["paper_claim_allowed"] is False,
        "paper claim gate opened",
    )

    upstream = contract["upstream"]
    require(upstream["hit_commit"] == HIT_COMMIT, "HIT commit changed")
    require(
        upstream["wrapper_commit"] == WRAPPER_COMMIT,
        "wrapper commit changed",
    )
    require(
        upstream["lattigo_v2_commit"] == LATTIGO_V2_COMMIT,
        "Lattigo v2 commit changed",
    )
    require(
        upstream["lattigo_v6_commit"] == LATTIGO_V6_COMMIT,
        "Lattigo v6 commit changed",
    )

    sources = contract["sources"]
    require(len(sources) == len(EXPECTED_SOURCES), "source count changed")
    actual_sources = {
        source["source_id"]: source["sha256"] for source in sources
    }
    require(actual_sources == EXPECTED_SOURCES, "source inventory changed")
    require(
        all(
            source["repository"]
            in {"hit", "wrapper", "lattigo_v2", "lattigo_v6"}
            for source in sources
        ),
        "unsupported source repository",
    )

    candidate_input = contract["candidate_input"]
    require(
        candidate_input == {
            "num_slots": 8192,
            "max_ct_level": 6,
            "log_scale": 20,
            "num_ks_primes": 1,
        },
        "HIT candidate input changed",
    )
    literal = contract["expected_literal"]
    require(literal["log_n"] == 14, "expected LogN changed")
    require(
        literal["log_q"] == [60, 20, 20, 20, 20, 20, 20],
        "expected LogQ changed",
    )
    require(literal["log_p"] == [61], "expected LogP changed")
    require(literal["log_default_scale"] == 20, "scale changed")
    require(literal["declared_log_qp"] == 241, "declared LogQP changed")
    require(
        literal["concrete_product_log_qp"] == 242,
        "concrete-product LogQP changed",
    )
    require(
        literal["security_v2_headroom_bits"] == 188,
        "Security V2 headroom changed",
    )

    translation = contract["exact_translation_requirements"]
    required_translation = {
        "concrete_import_q_identical",
        "concrete_import_p_identical",
        "scale_identical",
        "ring_identical",
        "xs_identical",
        "xe_identical",
        "native_v6_log_materialization_is_diagnostic_only",
    }
    require(
        set(translation) == required_translation and
        all(translation.values()),
        "exact translation gate changed",
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
        "development workload changed",
    )
    for name in ("model", "validation", "audit", "split_manifest"):
        artifact = REPO_ROOT / workload[f"{name}_path"]
        require(artifact.is_file(), f"{name} artifact is missing")
        require(
            sha256_path(artifact) == workload[f"{name}_sha256"],
            f"{name} artifact digest changed",
        )

    policy = contract["policy"]
    require(
        policy["security_policy_id"] ==
        "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "Security V2 ID changed",
    )
    require(
        policy["security_policy_digest"] == SECURITY_POLICY_DIGEST,
        "Security V2 digest changed",
    )
    require(
        policy["direct_policy_digest"] == DIRECT_POLICY_DIGEST,
        "Direct V2 digest changed",
    )
    require(policy["security_v2_log_n_14_cap"] == 430, "cap changed")
    require(policy["margin_floor"] == 0.001, "margin floor changed")
    require(policy["safety_factor"] == 0.5, "safety factor changed")
    require(policy["validation_key_repeats"] == 3, "repeats changed")
    require(policy["audit_key_repeats"] == 3, "audit repeats changed")
    require(policy["candidate_trials"] == 1, "trial count changed")
    require(policy["synthesis_calls"] == 0, "synthesis was enabled")
    require(policy["repair_calls"] == 0, "repair was enabled")
    require(policy["retuning"] == 0, "retuning was enabled")

    outcome = contract["outcome_policy"]
    require(
        outcome["audit_negative"] ==
        "preserve scientific negative and do not retune",
        "negative-result policy changed",
    )
    require(
        outcome["translation_or_security_failure"] ==
        "block encrypted execution",
        "integrity gate changed",
    )

    go_mod = (
        REPO_ROOT /
        "tools/lattigo-cross-version-materializer/go.mod"
    ).read_text(encoding="ascii")
    require(
        "github.com/ldsec/lattigo/v2 v2.2.0" in go_mod,
        "materializer Lattigo v2 pin changed",
    )
    require(
        "github.com/tuneinsight/lattigo/v6 v6.2.0" in go_mod,
        "materializer Lattigo v6 pin changed",
    )
    return {
        "schema_version": contract["schema_version"],
        "classification": contract["classification"],
        "source_count": len(sources),
        "candidate_trials": policy["candidate_trials"],
        "encrypted_execution_predeclared": True,
        "paper_claim_allowed": False,
    }


def main() -> int:
    args = parse_args()
    print(json.dumps(validate_contract(args.contract), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
