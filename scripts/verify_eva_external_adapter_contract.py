#!/usr/bin/env python3
"""Verify the predeclared Microsoft EVA compiler replay contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/eva_external_adapter_v1/contract.json"
)
SCHEMA_VERSION = "flipguard_eva_external_adapter_contract_v1"
EVA_COMMIT = "4cd3254c9c51340ae30c451495ce5378135758c0"
SEAL_COMMIT = "0b058d99b7f18a00e5ebb2b80caee593804b0500"
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
EXPECTED_SOURCES = {
    "eva_parameter_selector": (
        "sha256:"
        "4dfc0c61b78346cfa78bca7ce4bc35ea039a99cbf42b179423acfbc42823a615"
    ),
    "eva_ckks_compiler": (
        "sha256:"
        "fe26b7677978e8f8f4e190dbf0f066b6d54433877f3fdee880c502fc526f7ba0"
    ),
    "eva_ckks_config": (
        "sha256:"
        "aae75d5738e85682b3cde14cfb438df1ff1ad1e90eeeebb113e05de1c61399ca"
    ),
    "eva_seal_materialization": (
        "sha256:"
        "15a5a80b6320a691db0b44a55f74c4922d95099c280cda102d08c349829a3651"
    ),
    "eva_python_binding": (
        "sha256:"
        "3ed82bbaca999b69a3eb88a249e47cd53f2cfdc643868096c68baf52ba2ecc69"
    ),
    "eva_build_binding": (
        "sha256:"
        "4b26da6a5534dff399aa6e924857bf8f37a1549fca8535c8fd7a58f2a9e97385"
    ),
    "seal_context_chain": (
        "sha256:"
        "8d0f66ab47825857d4a0aaa50111ce46efe6591411212d73c8570ded65cf1582"
    ),
    "seal_coeff_modulus_create": (
        "sha256:"
        "bfbc867b5f0cf04ddc49e46d9ae000b7399bcd60c6b7af86e855c2bd28b2f87b"
    ),
    "seal_ntt_prime_search": (
        "sha256:"
        "b79e34c11fb8153f9e61a8f9fa4c33f8a042693ca4376921bcf6368572ec8b77"
    ),
    "seal_runtime_sampling": (
        "sha256:"
        "fdd6cd39a8f428ae053d3e65d7f3dea8e10f7527d336687e2b3166487bf305ca"
    ),
    "seal_security_caps": (
        "sha256:"
        "985f9b3c32b3f5fdaa0659eb8861249171195a0de6c8f502c71ca888313f0b26"
    ),
    "seal_noise_sampler_switch": (
        "sha256:"
        "2506aafb654d7946386fbb6472adf39a4156a5d5676ba30d8503c9b3d9dedd7d"
    ),
    "seal_build_defaults": (
        "sha256:"
        "9c5d700d6310dbc67d2969f76cda72159300718eff4d5676c47452e5c706c3ed"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--compiler-only",
        action="store_true",
        help=(
            "verify the source-replay/compiler closure without requiring "
            "git-ignored validation and audit artifacts"
        ),
    )
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


def validate_contract(
    path: Path = DEFAULT_CONTRACT,
    *,
    require_runtime_artifacts: bool = True,
) -> dict[str, Any]:
    path = path if path.is_absolute() else REPO_ROOT / path
    contract = load_json(path)
    require(contract["schema_version"] == SCHEMA_VERSION, "schema changed")
    require(
        contract["status"] ==
        "PREDECLARED_BEFORE_COMPILER_REPLAY_OR_ENCRYPTED_EXECUTION",
        "contract status changed",
    )
    require(
        contract["classification"] ==
        "SOURCE_REPLAYED_PUBLIC_COMPILER_PARAMETER_OUTPUT",
        "classification changed",
    )
    require(
        contract["paper_claim_allowed"] is False,
        "paper claim gate opened",
    )

    upstream = contract["upstream"]
    require(upstream["eva_tag"] == "v1.0.1", "EVA tag changed")
    require(upstream["eva_commit"] == EVA_COMMIT, "EVA commit changed")
    require(upstream["seal_tag"] == "v3.6.4", "SEAL tag changed")
    require(upstream["seal_commit"] == SEAL_COMMIT, "SEAL commit changed")

    sources = contract["sources"]
    require(len(sources) == len(EXPECTED_SOURCES), "source count changed")
    actual_sources = {
        source["source_id"]: source["sha256"] for source in sources
    }
    require(actual_sources == EXPECTED_SOURCES, "source inventory changed")
    require(
        {source["repository"] for source in sources} == {"eva", "seal"},
        "source repository set changed",
    )
    require(
        all(
            source["sha256"].startswith("sha256:") and
            len(source["sha256"]) == 71
            for source in sources
        ),
        "source digest format changed",
    )

    compiler = contract["compiler_input"]
    require(compiler["program_id"] == "iris_linear_poly3_scalar_v1",
            "program ID changed")
    require(compiler["vector_size"] == 1, "vector size changed")
    require(
        compiler["input_names"] == ["x_0", "x_1", "x_2", "x_3"],
        "compiler input names changed",
    )
    require(compiler["input_scale_bits"] == 20, "input scale changed")
    require(compiler["output_range_bits"] == 1, "output range changed")
    require(
        compiler["compiler_config"] == {
            "balance_reductions": True,
            "rescaler": "lazy_waterline",
            "lazy_relinearize": True,
            "security_level": 128,
            "quantum_safe": False,
            "warn_vec_size": True,
        },
        "EVA compiler configuration changed",
    )

    translation = contract["translation_contract"]
    require(
        translation["candidate_lineage"] ==
        "EVA_COMPILER_MODULUS_PROPOSAL_REPLAYED_ON_LATTIGO",
        "candidate lineage changed",
    )
    require(translation["path"] == "rescale", "execution path changed")
    require(translation["ring_type"] == "standard", "ring type changed")
    require(translation["required_q_primes"] == 7,
            "graph Q-prime requirement changed")
    require(translation["required_slots"] == 1,
            "slot requirement changed")
    for field in (
        "prime_padding_allowed",
        "prime_reordering_allowed",
        "scale_adjustment_allowed",
        "compiler_config_adjustment_allowed",
    ):
        require(translation[field] is False, f"{field} was enabled")
    for field in ("synthesis_calls", "repair_calls", "retuning"):
        require(translation[field] == 0, f"{field} was enabled")

    runtime = contract["runtime_boundary"]
    require(
        runtime["native_eva_seal_execution"] == "NOT_EVALUATED",
        "native EVA execution state changed",
    )
    require(
        runtime["seal_default_error"] ==
        "centered_binomial_stddev_3.2",
        "SEAL error semantics changed",
    )
    require(
        runtime["lattigo_replay_error"] ==
        "ring.DiscreteGaussian{Sigma:3.2,Bound:19.2}",
        "Lattigo error semantics changed",
    )
    require(
        runtime["distribution_identity_required"] is False,
        "proposal-only runtime boundary changed",
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
    artifact_names = ["model"]
    if require_runtime_artifacts:
        artifact_names.extend(
            ("validation", "audit", "split_manifest")
        )
    for name in artifact_names:
        artifact = REPO_ROOT / workload[f"{name}_path"]
        require(artifact.is_file(), f"{name} artifact is missing")
        require(
            sha256_path(artifact) == workload[f"{name}_sha256"],
            f"{name} artifact digest changed",
        )
    expected_range = max(
        1,
        math.ceil(
            math.log2(max(1.0, workload["max_plaintext_output_abs"]))
        ),
    )
    require(
        expected_range == compiler["output_range_bits"],
        "output range derivation changed",
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
        policy["security_v2_caps"] ==
        {"12": 106, "13": 214, "14": 430, "15": 868},
        "Security V2 caps changed",
    )
    require(
        policy["direct_policy_digest"] == DIRECT_POLICY_DIGEST,
        "Direct V2 digest changed",
    )
    require(policy["primary_alpha"] == 0.5, "primary alpha changed")
    require(
        policy["primary_margin_floor"] == 0.001,
        "primary margin floor changed",
    )
    require(policy["validation_key_repeats"] == 3,
            "validation repeats changed")
    require(policy["audit_key_repeats"] == 3, "audit repeats changed")
    require(policy["candidate_trials"] == 1, "candidate trials changed")
    require(policy["paper_claim_allowed"] is False,
            "policy paper claim gate opened")

    outcome = contract["outcome_policy"]
    require(
        outcome["security_v2_failure"] ==
        "BLOCK_ENCRYPTED_EXECUTION_AND_PRESERVE_STATIC_RESULT",
        "security failure handling changed",
    )
    require(
        outcome["graph_compatibility_failure"] ==
        "BLOCK_ENCRYPTED_EXECUTION_AND_PRESERVE_STATIC_RESULT",
        "graph failure handling changed",
    )
    require(
        outcome["audit_negative"] ==
        "preserve scientific negative and do not retune",
        "negative result handling changed",
    )

    return {
        "schema_version": contract["schema_version"],
        "source_count": len(sources),
        "program_id": compiler["program_id"],
        "input_scale_bits": compiler["input_scale_bits"],
        "output_range_bits": compiler["output_range_bits"],
        "required_q_primes": translation["required_q_primes"],
        "candidate_trials": policy["candidate_trials"],
        "runtime_artifacts_verified": require_runtime_artifacts,
        "paper_claim_allowed": False,
        "contract_sha256": sha256_path(path),
    }


def main() -> None:
    args = parse_args()
    summary = validate_contract(
        args.contract,
        require_runtime_artifacts=not args.compiler_only,
    )
    print(
        "eva_external_adapter_contract=VERIFIED "
        f"sources={summary['source_count']} "
        f"program={summary['program_id']} "
        f"scale={summary['input_scale_bits']} "
        f"range={summary['output_range_bits']} "
        f"required_q={summary['required_q_primes']} "
        f"runtime_artifacts={str(summary['runtime_artifacts_verified']).lower()} "
        f"digest={summary['contract_sha256']}"
    )


if __name__ == "__main__":
    main()
