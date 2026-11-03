#!/usr/bin/env python3
"""Verify the predeclared EVA native-runtime contract and result artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DEFAULT = (
    REPO_ROOT / "experiments/eva_native_runtime_v1/contract.json"
)
ALLOWED_PHASE_STATUS = {"SAFE", "REJECTED", "FAILED", "NOT_EVALUATED"}
DIRECT_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dot_semantic_digest(content: bytes) -> str:
    node_pattern = re.compile(
        r'^([A-Za-z0-9_]+) \[(?:shape=box )?label="([^"]+)"\];$'
    )
    edge_pattern = re.compile(
        r'^([A-Za-z0-9_]+) -> ([A-Za-z0-9_]+)'
        r'(?: \[label="([^"]+)"\])?;$'
    )
    labels: dict[str, str] = {}
    incoming: dict[str, list[tuple[str, str]]] = {}
    outgoing: dict[str, list[tuple[str, str]]] = {}
    for raw_line in content.decode("utf-8").splitlines():
        line = raw_line.strip()
        node_match = node_pattern.match(line)
        if node_match:
            node, label = node_match.groups()
            labels[node] = label
            incoming.setdefault(node, [])
            outgoing.setdefault(node, [])
            continue
        edge_match = edge_pattern.match(line)
        if edge_match:
            source, target, edge_label = edge_match.groups()
            edge_label = edge_label or ""
            incoming.setdefault(target, []).append((source, edge_label))
            outgoing.setdefault(source, []).append((target, edge_label))
            incoming.setdefault(source, [])
            outgoing.setdefault(target, [])
            continue
        if line and not line.startswith("digraph ") and line != "}":
            raise ValueError(f"unsupported EVA DOT line: {line}")
    nodes = set(incoming) | set(outgoing) | set(labels)
    require(nodes and nodes == set(labels), "EVA DOT node inventory changed")
    hashes: dict[str, str] = {}
    remaining = set(nodes)
    while remaining:
        ready = sorted(
            node
            for node in remaining
            if all(source in hashes for source, _ in incoming[node])
        )
        require(ready, "EVA DOT is cyclic or incomplete")
        for node in ready:
            parent_facts = sorted(
                [{
                    "edge": edge_label,
                    "hash": hashes[source],
                }
                for source, edge_label in incoming[node]],
                key=lambda item: (item["edge"], item["hash"]),
            )
            payload = {
                "label": labels[node],
                "incoming": parent_facts,
            }
            hashes[node] = (
                "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()
            )
            remaining.remove(node)
    node_facts = sorted(
        (
            labels[node],
            hashes[node],
            len(incoming[node]),
            len(outgoing[node]),
        )
        for node in nodes
    )
    edge_facts = sorted(
        (
            hashes[source],
            edge_label,
            hashes[target],
        )
        for source in nodes
        for target, edge_label in outgoing[source]
    )
    payload = {
        "schema_version": "eva_dot_semantic_dag_v1",
        "nodes": node_facts,
        "edges": edge_facts,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def resolve(relative: str) -> Path:
    path = REPO_ROOT / relative
    require(path.is_file(), f"missing bound artifact: {relative}")
    return path


def validate_contract(
    contract_path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    require(
        contract["schema_version"]
        == "flipguard_eva_native_runtime_contract_v1",
        "native runtime contract schema changed",
    )
    require(
        contract["status"]
        == "PREDECLARED_BEFORE_NATIVE_ENCRYPTED_EXECUTION",
        "native runtime predeclaration status changed",
    )
    require(contract["paper_claim_allowed"] is False, "paper gate changed")
    upstream = contract["upstream"]
    require(
        upstream["eva_commit"]
        == "4cd3254c9c51340ae30c451495ce5378135758c0",
        "EVA commit changed",
    )
    require(
        upstream["seal_commit"]
        == "0b058d99b7f18a00e5ebb2b80caee593804b0500",
        "SEAL commit changed",
    )
    compiler = contract["compiler_binding"]
    for path_key, digest_key in (
        ("parameter_contract_path", "parameter_contract_sha256"),
        ("compiler_output_path", "compiler_output_sha256"),
        ("compiled_program_path", "compiled_program_sha256"),
    ):
        require(
            sha256_path(resolve(compiler[path_key]))
            == compiler[digest_key],
            f"{path_key} digest changed",
        )
    require(
        dot_semantic_digest(resolve(compiler["compiled_program_path"]).read_bytes())
        == compiler["compiled_program_semantic_sha256"],
        "bound compiled program semantic digest changed",
    )
    compiler_output = load_json(resolve(compiler["compiler_output_path"]))
    candidate_parameters = compiler_output["candidate_request"]["parameters"]
    concrete = compiler_output["concrete_seal_materialization"]
    require(candidate_parameters["q"] == compiler["q"], "bound Q changed")
    require(candidate_parameters["p"] == compiler["p"], "bound P changed")
    require(
        candidate_parameters["log_n"]
        == int(math.log2(compiler["poly_modulus_degree"])),
        "bound LogN changed",
    )
    require(
        concrete["prime_bits"] == compiler["prime_bits"],
        "bound SEAL prime bits changed",
    )
    require(
        concrete["first_context_coeff_modulus"] == compiler["q"],
        "bound ciphertext modulus changed",
    )
    require(
        [concrete["special_modulus"]] == compiler["p"],
        "bound special modulus changed",
    )
    workload = contract["workload"]
    for path_key, digest_key in (
        ("model_path", "model_sha256"),
        ("validation_path", "validation_sha256"),
        ("locked_audit_path", "locked_audit_sha256"),
    ):
        require(
            sha256_path(resolve(workload[path_key]))
            == workload[digest_key],
            f"{path_key} digest changed",
        )
    for path_key, count_key in (
        ("validation_path", "validation_rows"),
        ("locked_audit_path", "locked_audit_rows"),
    ):
        with resolve(workload[path_key]).open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        require(len(rows) == workload[count_key], f"{count_key} changed")
    decision = contract["decision_contract"]
    require(decision["threshold"] == 0.5, "threshold changed")
    require(decision["primary_alpha"] == 0.5, "alpha changed")
    require(
        decision["primary_margin_floor"] == 0.001,
        "margin floor changed",
    )
    protocol = contract["execution_protocol"]
    require(protocol["validation_key_repeats"] == 3, "validation keys changed")
    require(
        protocol["locked_audit_key_repeats"] == 3,
        "audit keys changed",
    )
    require(protocol["candidate_trials"] == 1, "trial budget changed")
    require(protocol["synthesis_calls"] == 0, "synthesis enabled")
    require(protocol["repair_calls"] == 0, "repair enabled")
    require(protocol["retuning"] == 0, "retuning enabled")
    security = contract["security_interpretation"]
    require(
        security["security_policy_digest"] == SECURITY_DIGEST,
        "security digest changed",
    )
    require(
        security["direct_policy_digest"] == DIRECT_DIGEST,
        "direct policy digest changed",
    )
    require(
        security["formal_security_v2_runtime_claim"]
        == "NOT_EVALUATED_DIFFERENT_RUNTIME_DISTRIBUTION",
        "runtime security boundary changed",
    )
    require(
        security["lattigo_xs_xe_distribution_identity"] is False,
        "runtime distribution identity changed",
    )
    require(
        security["native_seal_context_security_enforcement"]
        == "sec_level_type::none",
        "native SEAL context enforcement changed",
    )
    return contract


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    require(checksum_path.is_file(), "missing SHA256SUMS")
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    actual_files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    require(sorted(expected) == actual_files, "checksum file set changed")
    for relative, digest in expected.items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        require(actual == digest, f"checksum mismatch: {relative}")


def verify_ledger(
    path: Path,
    *,
    threshold: float,
    alpha: float,
    margin_floor: float,
) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(rows, f"empty ledger: {path}")
    flips = 0
    violations = 0
    failures = 0
    max_error = 0.0
    max_usage = 0.0
    keys: set[int] = set()
    samples: set[str] = set()
    for row in rows:
        keys.add(int(row["key_repeat"]))
        samples.add(row["row_id"])
        if row["execution_status"] != "OK":
            failures += 1
            continue
        plain = float(row["plaintext_score"])
        score = float(row["native_ckks_score"])
        margin = abs(plain - threshold)
        budget = alpha * margin
        error = abs(score - plain)
        usage = error / budget if budget else math.inf
        certifiable = margin > margin_floor
        plain_decision = plain >= threshold
        ckks_decision = score >= threshold
        flip = certifiable and plain_decision != ckks_decision
        violation = certifiable and error >= budget
        require(
            math.isclose(float(row["decision_margin"]), margin, abs_tol=1e-15),
            "ledger margin mismatch",
        )
        require(
            math.isclose(float(row["error_budget"]), budget, abs_tol=1e-15),
            "ledger budget mismatch",
        )
        require(
            math.isclose(float(row["absolute_error"]), error, abs_tol=1e-15),
            "ledger error mismatch",
        )
        require(
            math.isclose(
                float(row["normalized_budget_usage"]),
                usage,
                rel_tol=1e-12,
                abs_tol=1e-15,
            ),
            "ledger usage mismatch",
        )
        require(
            (row["certifiable"] == "true") == certifiable,
            "ledger certifiable mismatch",
        )
        require(
            (row["decision_flip"] == "true") == flip,
            "ledger flip mismatch",
        )
        require(
            (row["error_violation"] == "true") == violation,
            "ledger violation mismatch",
        )
        flips += int(flip)
        violations += int(violation)
        max_error = max(max_error, error)
        max_usage = max(max_usage, usage)
    return {
        "observations": len(rows),
        "sample_count": len(samples),
        "key_repeats": len(keys),
        "execution_failures": failures,
        "decision_flips": flips,
        "error_violations": violations,
        "max_absolute_error": max_error,
        "max_normalized_budget_usage": max_usage,
    }


def verify_result(
    root: Path,
    contract_path: Path = CONTRACT_DEFAULT,
) -> dict[str, Any]:
    contract = validate_contract(contract_path)
    verify_checksums(root)
    manifest = load_json(root / "manifest.json")
    require(
        manifest["schema_version"]
        == "flipguard_eva_native_runtime_result_v1",
        "native runtime result schema changed",
    )
    require(manifest["paper_claim_allowed"] is False, "result paper gate changed")
    require(
        manifest["contract_sha256"] == sha256_path(contract_path),
        "result contract binding changed",
    )
    require(
        manifest["direct_policy_digest"] == DIRECT_DIGEST,
        "result direct policy changed",
    )
    require(
        manifest["security_policy_digest"] == SECURITY_DIGEST,
        "result security policy changed",
    )
    require(
        manifest["policy_modifications"] == 0,
        "result policy modifications changed",
    )
    compiler = contract["compiler_binding"]
    require(
        manifest["compiler_output_sha256"]
        == compiler["compiler_output_sha256"],
        "result compiler output binding changed",
    )
    require(
        manifest["compiled_program_identity"]["expected_raw_sha256"]
        == compiler["compiled_program_sha256"],
        "result expected compiled program binding changed",
    )
    observed_dot = root / "compiled_program.dot"
    require(
        manifest["compiled_program_identity"]["observed_raw_sha256"]
        == sha256_path(observed_dot),
        "result observed compiled program binding changed",
    )
    require(
        manifest["compiled_program_identity"]["semantic_sha256"]
        == compiler["compiled_program_semantic_sha256"],
        "result compiled program semantic binding changed",
    )
    require(
        dot_semantic_digest(observed_dot.read_bytes())
        == compiler["compiled_program_semantic_sha256"],
        "observed compiled program semantics changed",
    )
    candidate = manifest["candidate"]
    require(
        candidate["poly_modulus_degree"]
        == compiler["poly_modulus_degree"],
        "result candidate degree changed",
    )
    require(candidate["prime_bits"] == compiler["prime_bits"], "prime bits changed")
    require(candidate["q"] == compiler["q"], "result candidate Q changed")
    require(candidate["p"] == compiler["p"], "result candidate P changed")
    require(
        candidate["input_scale_bits"] == compiler["input_scale_bits"],
        "result candidate scale changed",
    )
    require(
        manifest["runtime_security_claim"]
        == contract["security_interpretation"][
            "formal_security_v2_runtime_claim"
        ],
        "result runtime security boundary changed",
    )
    decision = contract["decision_contract"]
    workload = contract["workload"]
    protocol = contract["execution_protocol"]
    validation = verify_ledger(
        root / "validation_ledger.csv",
        threshold=decision["threshold"],
        alpha=decision["primary_alpha"],
        margin_floor=decision["primary_margin_floor"],
    )
    require(
        validation["sample_count"] == workload["validation_rows"],
        "validation sample population changed",
    )
    require(
        validation["key_repeats"]
        == protocol["validation_key_repeats"],
        "validation key population changed",
    )
    require(
        validation["observations"]
        == workload["validation_rows"]
        * protocol["validation_key_repeats"],
        "validation observation population changed",
    )
    require(
        validation == manifest["validation"]["counts"],
        "validation aggregate changed",
    )
    expected_validation = (
        "SAFE"
        if validation["execution_failures"] == 0
        and validation["decision_flips"] == 0
        and validation["error_violations"] == 0
        else (
            "FAILED"
            if validation["execution_failures"] > 0
            else "REJECTED"
        )
    )
    require(
        manifest["validation"]["status"] == expected_validation,
        "validation status changed",
    )
    audit_status = manifest["locked_audit"]["status"]
    require(audit_status in ALLOWED_PHASE_STATUS, "invalid audit status")
    if expected_validation == "SAFE":
        audit = verify_ledger(
            root / "locked_audit_ledger.csv",
            threshold=decision["threshold"],
            alpha=decision["primary_alpha"],
            margin_floor=decision["primary_margin_floor"],
        )
        require(
            audit["sample_count"] == workload["locked_audit_rows"],
            "audit sample population changed",
        )
        require(
            audit["key_repeats"]
            == protocol["locked_audit_key_repeats"],
            "audit key population changed",
        )
        require(
            audit["observations"]
            == workload["locked_audit_rows"]
            * protocol["locked_audit_key_repeats"],
            "audit observation population changed",
        )
        require(
            audit == manifest["locked_audit"]["counts"],
            "audit aggregate changed",
        )
        expected_audit = (
            "SAFE"
            if audit["execution_failures"] == 0
            and audit["decision_flips"] == 0
            and audit["error_violations"] == 0
            else (
                "FAILED"
                if audit["execution_failures"] > 0
                else "REJECTED"
            )
        )
        require(audit_status == expected_audit, "audit status changed")
    else:
        require(
            audit_status == "NOT_EVALUATED",
            "audit ran after non-SAFE validation",
        )
        require(
            not (root / "locked_audit_ledger.csv").exists(),
            "unexpected locked audit ledger",
        )
    expected_overall = (
        "PASS"
        if expected_validation == "SAFE" and audit_status == "SAFE"
        else "PARTIAL_SCIENTIFIC_RESULT"
    )
    require(manifest["status"] == expected_overall, "overall status changed")
    accounting = manifest["accounting"]
    require(accounting["candidate_trials"] == 1, "candidate trial count changed")
    require(accounting["synthesis_calls"] == 0, "synthesis count changed")
    require(accounting["repair_calls"] == 0, "repair count changed")
    require(accounting["retuning"] == 0, "retuning count changed")
    require(
        accounting["validation_key_runs"] == validation["key_repeats"],
        "validation key accounting changed",
    )
    require(
        accounting["validation_encrypted_sample_evaluations"]
        == validation["observations"],
        "validation sample accounting changed",
    )
    expected_audit_counts = manifest["locked_audit"].get("counts", {})
    require(
        accounting["locked_audit_key_runs"]
        == expected_audit_counts.get("key_repeats", 0),
        "audit key accounting changed",
    )
    require(
        accounting["locked_audit_encrypted_sample_evaluations"]
        == expected_audit_counts.get("observations", 0),
        "audit sample accounting changed",
    )
    return {
        "status": manifest["status"],
        "validation_status": expected_validation,
        "locked_audit_status": audit_status,
        "paper_claim_allowed": False,
        "manifest_sha256": sha256_path(root / "manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=CONTRACT_DEFAULT)
    parser.add_argument("--result-root", type=Path)
    args = parser.parse_args()
    contract_path = (
        args.contract
        if args.contract.is_absolute()
        else REPO_ROOT / args.contract
    )
    if args.result_root is None:
        contract = validate_contract(contract_path)
        print(
            json.dumps(
                {
                    "contract_status": contract["status"],
                    "contract_sha256": sha256_path(contract_path),
                    "paper_claim_allowed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    result_root = (
        args.result_root
        if args.result_root.is_absolute()
        else REPO_ROOT / args.result_root
    )
    print(
        json.dumps(
            verify_result(result_root, contract_path),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
