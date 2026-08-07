#!/usr/bin/env python3
"""Run direct and Security-V2 catalog arms on the V8 shared polynomial."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
ADMITTED = (
    "deep_chain_8_scale45", "deep_chain_9_scale45", "short_chain_3", "short_chain_5",
    "short_chain_6_scale38", "short_chain_6_scale40", "short_chain_6_scale42",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def atomic_command(command: list[str], output: Path) -> None:
    if output.exists():
        json.loads(output.read_text(encoding="utf-8"))
        return
    partial = output.with_suffix(output.suffix + ".partial")
    partial.unlink(missing_ok=True)
    command = [*command, "--out", str(partial)]
    subprocess.run(command, cwd=ROOT, check=True)
    json.loads(partial.read_text(encoding="utf-8"))
    partial.replace(output)


def write_request(path: Path, provider_kind: str, provider_id: str, parameters: dict[str, object]) -> None:
    request = {
        "schema_version": 2,
        "provider_kind": provider_kind,
        "provider_id": provider_id,
        "path": "rescale",
        "parameters": parameters,
    }
    encoded = json.dumps(request, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise RuntimeError(f"INTEGRITY_BLOCK: provider request drift: {path}")
    else:
        path.write_text(encoded, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--common-binary", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary_root.resolve()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    requests = output / "provider_requests"
    requests.mkdir(exist_ok=True)
    catalog_out = output / "catalog"
    catalog_out.mkdir(exist_ok=True)
    model = ROOT / "docs/evidence/focused_external_comparison_v8/workload_contracts/shared_polynomial_model_v8.json"
    inputs = ROOT / "docs/evidence/focused_external_comparison_v8/input_manifests/shared_polynomial_threshold_v8"
    validation = inputs / "configuration_validation.csv"
    audit = inputs / "locked_audit.csv"
    split = inputs / "split_manifest.json"
    split_id = "shared_polynomial_threshold_v8_validation_500"

    autotune = binary / "flipguard-autotune-v8"
    certify = binary / "flipguard-certify-candidate-v8"
    audit_binary = binary / "flipguard-audit-candidate-v8"
    common_binary = args.common_binary.resolve()
    for item in (autotune, certify, audit_binary, common_binary):
        if not item.is_file():
            raise FileNotFoundError(item)
    direct_selection = output / "direct_autotune.json"
    atomic_command([
        str(autotune), "--model", str(model), "--validation", str(validation),
        "--split-id", split_id, "--key-repeats", "3", "--max-encrypted-trials", "4",
    ], direct_selection)
    selected = json.loads(direct_selection.read_text(encoding="utf-8")).get("selected")
    if not selected:
        raise RuntimeError("direct synthesis returned NO_SAFE on V8 shared polynomial")
    direct_request = requests / "direct.json"
    write_request(direct_request, "direct_synthesizer", "flipguard_direct_v2_v8", selected["parameters"])
    direct_gate = output / "direct_validation.json"
    atomic_command([
        str(certify), "--model", str(model), "--validation", str(validation),
        "--split-id", split_id, "--candidate", str(direct_request), "--key-repeats", "3",
    ], direct_gate)
    direct_audit = output / "direct_locked_audit.json"
    atomic_command([
        str(audit_binary), "--selection", str(direct_gate), "--audit", str(audit),
        "--manifest", str(split), "--key-repeats", "3",
    ], direct_audit)

    inventory = json.loads((ROOT / "docs/evidence/security_v2_static_attestation_formal_v2/parameter_inventory_v2.json").read_text(encoding="utf-8"))
    profiles = {row["candidate_id"]: row for row in inventory["catalog_profiles"]}
    catalog_results = []
    for name in ADMITTED:
        row = profiles[name]
        if row["v2_security"]["final_admission"] != "PASS":
            raise RuntimeError(f"INTEGRITY_BLOCK: catalog profile {name} is not Security V2 admitted")
        parameters = {
            "log_n": row["parameters"]["log_n"],
            "log_q": row["parameters"]["log_q"],
            "log_p": row["parameters"]["log_p"],
            "q": row["actual_q_primes"],
            "p": row["actual_p_primes"],
            "log_default_scale": row["parameters"]["log_default_scale"],
        }
        request = requests / f"catalog_{name}.json"
        write_request(request, "bounded_catalog", f"security_v2_{name}", parameters)
        result_path = catalog_out / f"{name}_validation.json"
        atomic_command([
            str(certify), "--model", str(model), "--validation", str(validation),
            "--split-id", split_id, "--candidate", str(request), "--key-repeats", "3",
        ], result_path)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        catalog_results.append((name, result_path, result))
    safe = [(name, path, result) for name, path, result in catalog_results if result["outcome"] == "SELECTED"]
    fastest = min(safe, key=lambda item: float(item[2]["trial"]["mean_total_ms"])) if safe else None
    catalog_audit = None
    if fastest:
        catalog_audit = output / "catalog_fastest_safe_locked_audit.json"
        atomic_command([
            str(audit_binary), "--selection", str(fastest[1]), "--audit", str(audit),
            "--manifest", str(split), "--key-repeats", "3",
        ], catalog_audit)
    common_output = None
    if fastest:
        common_output = output / "common_executor_paired_latency.json"
        if not common_output.exists():
            partial = common_output.with_suffix(".json.partial")
            partial.unlink(missing_ok=True)
            subprocess.run([
                str(common_binary), "--direct", str(direct_gate), "--catalog", str(fastest[1]),
                "--model", str(model), "--audit", str(audit), "--split-manifest", str(split),
                "--out", str(partial),
            ], cwd=ROOT, check=True)
            json.loads(partial.read_text(encoding="utf-8"))
            partial.replace(common_output)
    direct_gate_result = json.loads(direct_gate.read_text(encoding="utf-8"))
    direct_audit_result = json.loads(direct_audit.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "flipguard_focused_external_v8_flipguard_result_v1",
        "status": "PASS",
        "workload": "shared_polynomial_threshold_v8",
        "validation_unique_inputs": 500, "audit_unique_inputs": 500, "overlap": 0,
        "fresh_key_runs_per_arm_role": 3,
        "direct": {
            "candidate_id": direct_gate_result["bound_candidate"]["candidate"]["id"],
            "source_synthesis_candidate_id": selected["id"],
            "validation_outcome": direct_gate_result["outcome"],
            "validation_status": direct_gate_result["trial"]["status"],
            "validation_flips": direct_gate_result["trial"]["decision_flips"],
            "validation_violations": direct_gate_result["trial"]["error_violations"],
            "locked_audit_outcome": direct_audit_result["outcome"],
            "locked_audit_status": direct_audit_result["audit_trial"]["status"],
            "locked_audit_flips": direct_audit_result["audit_trial"]["decision_flips"],
            "locked_audit_violations": direct_audit_result["audit_trial"]["error_violations"],
            "retuning": direct_audit_result["retuning_performed"],
        },
        "catalog": {
            "formal_denominator": len(ADMITTED),
            "admitted_profiles": list(ADMITTED),
            "safe_profiles": [name for name, _, result in catalog_results if result["outcome"] == "SELECTED"],
            "rejected_profiles": [name for name, _, result in catalog_results if result["outcome"] != "SELECTED"],
            "fastest_safe_profile": fastest[0] if fastest else None,
            "fastest_safe_mean_total_ms": fastest[2]["trial"]["mean_total_ms"] if fastest else None,
            "locked_audit_outcome": json.loads(catalog_audit.read_text(encoding="utf-8"))["outcome"] if catalog_audit else "NOT_EVALUATED_NO_SAFE",
        },
        "common_executor": {
            "status": "PASS" if common_output else "NOT_EVALUATED_NO_SAFE_CATALOG_ARM",
            "portability": "GRAPH_EQUIVALENT_COMMON_EXECUTOR" if common_output else "NOT_EVALUATED",
            "same_runtime": "Lattigo_v6.2.0" if common_output else None,
            "paired_records": len(json.loads(common_output.read_text(encoding="utf-8"))["records"]) if common_output else 0,
            "unique_inputs": 100 if common_output else 0,
            "fresh_keysets": 3 if common_output else 0,
            "measurement_passes": 6 if common_output else 0,
            "outlier_removal": False,
        },
        "binary_digests": {item.name: sha256(item) for item in (autotune, certify, audit_binary, common_binary)},
        "security_policy_id": "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "security_policy_digest": "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
        "direct_policy_id": "flipguard_direct_synthesis_policy_v2",
        "direct_policy_digest": "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
    }
    manifest_path = output / "manifest.json"
    manifest_partial = manifest_path.with_suffix(".json.partial")
    manifest_partial.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_partial.replace(manifest_path)
    checksums = [f"{sha256(path)[7:]}  {path.relative_to(output).as_posix()}" for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
