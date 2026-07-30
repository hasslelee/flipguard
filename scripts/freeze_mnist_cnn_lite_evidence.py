#!/usr/bin/env python3
"""Freeze and verify the MNIST CNN-lite holdout evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path(
    "results/thesis_grade_protocol/"
    "non_tabular_mnist_cnn_lite_holdout_v1/run_515d5dd"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1"
)
INPUT_ROOT = Path(
    "datasets/vision_suite/mnist/cnn_lite_square_binary01"
)
SOURCE_ARCHIVE = Path(
    "results/source_datasets/mnist/mnist_784.arff.gz"
)
INPUT_VERIFIER_PATH = (
    REPO_ROOT / "scripts/verify_mnist_cnn_lite_holdout.py"
)
INPUT_VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_mnist_cnn_lite_holdout",
    INPUT_VERIFIER_PATH,
)
INPUT_VERIFIER = importlib.util.module_from_spec(
    INPUT_VERIFIER_SPEC
)
assert INPUT_VERIFIER_SPEC.loader is not None
INPUT_VERIFIER_SPEC.loader.exec_module(INPUT_VERIFIER)

SCHEMA_VERSION = "flipguard_non_tabular_mnist_cnn_lite_evidence_v1"
EXECUTION_COMMIT = "515d5dd680b09dfb454b5d4b900ab7f52c84373e"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXTRACTION_POLICY_DIGEST = (
    "sha256:"
    "06c795514837759cfb8a75a0390964f1e3cf252ceda233ee42b2de3023a8bab5"
)
EXECUTION_ADAPTER = (
    "mnist_cnn_lite_scalar_replicated_graph_adapter_v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def git_blob(commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def verify_historical_source_map(
    source_commit: str,
    source_files: dict[str, str],
) -> None:
    for relative, expected in source_files.items():
        if sha256_bytes(git_blob(source_commit, relative)) != expected:
            raise ValueError(
                "CNN-lite historical execution source changed: "
                f"{relative}"
            )


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def nearest_rank(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = math.ceil(fraction * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def read_input_rows(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="ascii") as handle:
        rows = list(csv.DictReader(handle))
    result = {int(row["row_id"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate input row in {path}")
    return result


def validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate["path"] != "rescale":
        raise ValueError("CNN-lite candidate path changed")
    security = candidate["security"]
    if security["envelope_id"] != \
            "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError("CNN-lite candidate security policy changed")
    for field in (
        "admission_status",
        "ciphertext_q_admission",
        "evaluation_key_qp_admission",
        "final_admission",
    ):
        if security[field] != "PASS":
            raise ValueError(
                f"CNN-lite candidate {field}={security[field]}"
            )
    if security["headroom_bits"] < 0:
        raise ValueError("CNN-lite candidate security headroom is negative")


def validate_trial(
    trial: dict[str, Any],
    contract: dict[str, Any],
    inputs: dict[int, dict[str, str]],
    expected_partition: str,
) -> dict[str, Any]:
    rows = trial["sample_ledger"]
    decision = contract["decision"]
    threshold = float(decision["threshold"])
    margin_floor = float(decision["margin_floor"])
    alpha = float(decision["safety_factor"])
    expected_samples = int(decision["validation_samples"])
    expected_keys = int(trial["key_repeats_completed"])
    if len(rows) != trial["encrypted_sample_evaluations"] or \
            len(rows) != expected_samples * expected_keys:
        raise ValueError("CNN-lite sample/key ledger mismatch")
    if expected_samples != len(inputs):
        raise ValueError("CNN-lite input/contract sample count changed")

    seen: set[tuple[int, int]] = set()
    per_key: dict[int, set[int]] = {}
    flips = 0
    violations = 0
    certifiable_ids: set[int] = set()
    ambiguous_ids: set[int] = set()
    max_error = 0.0
    max_usage = 0.0
    latencies: list[float] = []
    for index, row in enumerate(rows):
        key_run = int(row["key_run"])
        row_id = int(row["row_id"])
        identity = (key_run, row_id)
        if identity in seen:
            raise ValueError(f"duplicate CNN-lite observation {identity}")
        seen.add(identity)
        per_key.setdefault(key_run, set()).add(row_id)
        source = inputs.get(row_id)
        if source is None:
            raise ValueError(f"ledger row {row_id} is outside input CSV")
        if row["sample_id"] != source["sample_id"] or \
                row["source_partition"] != expected_partition or \
                row["source_partition"] != source["source_partition"] or \
                int(row["digit_label"]) != int(source["digit_label"]):
            raise ValueError(
                f"CNN-lite identity changed at observation {index}"
            )
        plain = float(row["plain_score"])
        approx = float(row["ckks_score"])
        if not close(plain, float(source["plaintext_score"])):
            raise ValueError(
                f"CNN-lite plaintext score changed at row {row_id}"
            )
        observed_threshold = float(row["threshold"])
        if not close(observed_threshold, threshold):
            raise ValueError("CNN-lite threshold changed")
        margin = abs(plain - threshold)
        error = abs(approx - plain)
        certifiable = margin > margin_floor
        budget = alpha * margin if certifiable else 0.0
        usage = error / budget if certifiable else 0.0
        violation = error >= budget if certifiable else False
        plain_decision = plain >= threshold
        ckks_decision = approx >= threshold
        flip = plain_decision != ckks_decision
        if not close(float(row["margin"]), margin) or \
                not close(float(row["abs_error"]), error) or \
                bool(row["certifiable"]) != certifiable or \
                not close(float(row["error_budget"]), budget) or \
                not close(float(row["error_budget_usage"]), usage) or \
                bool(row["error_violation"]) != violation or \
                bool(row["plain_decision"]) != plain_decision or \
                bool(row["ckks_decision"]) != ckks_decision or \
                bool(row["decision_flip"]) != flip:
            raise ValueError(
                f"CNN-lite derived fields changed at observation {index}"
            )
        for name in (
            "encode_encrypt_ms",
            "eval_only_ms",
            "decrypt_decode_ms",
            "total_eval_ms",
        ):
            value = float(row[name])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid CNN-lite timing {name}")
        latencies.append(float(row["total_eval_ms"]))
        if certifiable:
            certifiable_ids.add(row_id)
        else:
            ambiguous_ids.add(row_id)
        flips += int(flip)
        violations += int(violation)
        max_error = max(max_error, error)
        max_usage = max(max_usage, usage)

    expected_ids = set(inputs)
    if set(per_key) != set(range(1, expected_keys + 1)) or \
            any(ids != expected_ids for ids in per_key.values()):
        raise ValueError("CNN-lite per-key input coverage changed")
    mean = sum(latencies) / len(latencies)
    median = nearest_rank(latencies, 0.50)
    p95 = nearest_rank(latencies, 0.95)
    if flips != trial["decision_flips"] or \
            violations != trial["error_violations"] or \
            len(certifiable_ids) != trial["v_cert"] or \
            len(ambiguous_ids) != trial["v_amb"] or \
            not close(max_error, float(trial["max_observed_error"])) or \
            not close(
                max_usage,
                float(trial["max_error_budget_usage"]),
            ) or not close(mean, float(trial["mean_total_ms"])) or \
            not close(median, float(trial["median_total_ms"])) or \
            not close(p95, float(trial["p95_total_ms"])):
        raise ValueError("CNN-lite trial aggregate changed")
    return {
        "samples": expected_samples,
        "key_runs": expected_keys,
        "encrypted_sample_evaluations": len(rows),
        "certifiable": len(certifiable_ids),
        "ambiguous": len(ambiguous_ids),
        "flips": flips,
        "violations": violations,
        "max_error": max_error,
        "max_budget_usage": max_usage,
        "mean_total_ms": mean,
        "median_total_ms": median,
        "p95_total_ms": p95,
    }


def validate_run(
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_manifest = json.loads(
        (run_root / "run_manifest.json").read_text(encoding="ascii")
    )
    selection = json.loads(
        (run_root / "selection.json").read_text(encoding="ascii")
    )
    audit = json.loads(
        (run_root / "locked_audit.json").read_text(encoding="ascii")
    )
    stage_ledger = json.loads(
        (run_root / "stage_ledger.json").read_text(encoding="ascii")
    )
    if run_manifest["execution_commit"] != EXECUTION_COMMIT or \
            run_manifest["source_commit"] != EXECUTION_COMMIT or \
            run_manifest["origin_commit"] != EXECUTION_COMMIT or \
            not run_manifest["working_tree_clean"]:
        raise ValueError("CNN-lite execution provenance changed")
    if run_manifest["execution_critical_source_digest"] != \
            canonical_digest(run_manifest["execution_source_files"]):
        raise ValueError("CNN-lite source closure digest changed")
    verify_historical_source_map(
        run_manifest["execution_commit"],
        run_manifest["execution_source_files"],
    )
    if run_manifest["direct_policy"]["digest"] != \
            DIRECT_POLICY_DIGEST or \
            run_manifest["security_policy"]["digest"] != \
            SECURITY_POLICY_DIGEST or \
            run_manifest["extraction_policy"]["digest"] != \
            EXTRACTION_POLICY_DIGEST or \
            run_manifest["direct_policy"]["modified"] or \
            run_manifest["security_policy"]["modified"]:
        raise ValueError("CNN-lite frozen policy binding changed")
    if run_manifest["graph_adapter"]["id"] != EXECUTION_ADAPTER:
        raise ValueError("CNN-lite execution adapter changed")

    binaries = {
        "autotune": run_root / "bin/flipguard-cnn-lite-autotune",
        "audit": run_root / "bin/flipguard-cnn-lite-audit",
    }
    for name, path in binaries.items():
        if sha256_path(path) != \
                run_manifest["binary_sha256"][name]:
            raise ValueError(f"CNN-lite {name} binary changed")
    input_paths = {
        "model": INPUT_ROOT / "model.json",
        "configuration_validation":
            INPUT_ROOT / "configuration_validation.csv",
        "locked_audit_test": INPUT_ROOT / "locked_audit_test.csv",
        "input_manifest": INPUT_ROOT / "extraction_manifest.json",
        "source_archive": SOURCE_ARCHIVE,
    }
    for name, path in input_paths.items():
        if sha256_path(REPO_ROOT / path) != \
                run_manifest["inputs"][name]:
            raise ValueError(f"CNN-lite {name} input changed")

    plan = selection["plan"]
    contract = plan["contract"]
    if selection["execution_adapter"] != EXECUTION_ADAPTER or \
            plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError("CNN-lite selection policy or adapter changed")
    if contract["model_type"] != "cnn_lite_square_binary01" or \
            contract["graph"]["multiplicative_depth"] != 1 or \
            contract["deployment"]["rescale_levels_consumed"] != 3 or \
            contract["deployment"]["terminal_scale_exponent"] != 2 or \
            contract["deployment"]["required_q_primes"] != 5 or \
            contract["decision"]["validation_samples"] != 250 or \
            contract["decision"]["certifiable_samples"] != 250 or \
            contract["decision"]["ambiguous_samples"] != 0:
        raise ValueError("CNN-lite selection contract changed")
    if selection["outcome"] != "SELECTED" or \
            selection["trials_used"] != 1 or \
            len(selection["trials"]) != 1:
        raise ValueError("CNN-lite first-SAFE selection changed")
    selected = selection["selected"]
    trial = selection["trials"][0]
    validate_candidate(selected)
    if selected != trial["candidate"] or \
            trial["status"] != "SAFE" or \
            trial["key_repeats_completed"] != 3 or \
            selection["encrypted_key_runs"] != 3 or \
            selection["encrypted_sample_evaluations"] != 750:
        raise ValueError("CNN-lite selection accounting changed")

    validation_rows = read_input_rows(
        REPO_ROOT / INPUT_ROOT / "configuration_validation.csv"
    )
    audit_rows = read_input_rows(
        REPO_ROOT / INPUT_ROOT / "locked_audit_test.csv"
    )
    if set(validation_rows) & set(audit_rows):
        raise ValueError("CNN-lite validation/audit rows overlap")
    selection_summary = validate_trial(
        trial,
        contract,
        validation_rows,
        "train",
    )
    if audit["outcome"] != "LOCKED_AUDIT_PASS" or \
            audit["retuning_performed"] or \
            audit["selected_candidate"] != selected or \
            audit["selection_contract_digest"] != \
                plan["contract_digest"] or \
            audit["audit_trial"]["status"] != "SAFE":
        raise ValueError("CNN-lite locked audit identity changed")
    audit_contract = audit["audit_contract"]
    if audit_contract["model_artifact"] != \
            contract["model_artifact"] or \
            audit_contract["source_data"] != contract["source_data"] or \
            audit_contract["deployment"]["max_encrypted_trials"] != 1 or \
            audit_contract["decision"]["validation_samples"] != 250:
        raise ValueError("CNN-lite locked audit contract changed")
    audit_summary = validate_trial(
        audit["audit_trial"],
        audit_contract,
        audit_rows,
        "test",
    )
    if stage_ledger["selection"]["sha256"] != \
            sha256_path(run_root / "selection.json") or \
            stage_ledger["locked_audit"]["sha256"] != \
                sha256_path(run_root / "locked_audit.json"):
        raise ValueError("CNN-lite stage ledger digest changed")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": (
            "scalar-replicated learned MNIST digit-0-vs-1 CNN-lite"
        ),
        "status": "SUPPORTED",
        "structural_generalization": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "paper_claim_block_reason": (
            "one CNN-lite graph does not establish packed, LeNet, or "
            "arbitrary-CNN generalization; paper admission remains external"
        ),
        "plaintext_task": {
            "validation_accuracy": 0.98,
            "audit_accuracy": 0.992,
            "task_accuracy_is_not_decision_integrity": True,
        },
        "selection": {
            "outcome": selection["outcome"],
            "candidate_id": selected["id"],
            "candidate_parameters": selected["parameters"],
            "security": selected["security"],
            "trials": selection["trials_used"],
            "repairs": selection["trials_used"] - 1,
            **selection_summary,
        },
        "locked_audit": {
            "outcome": audit["outcome"],
            "candidate_byte_identical": True,
            "retuning": 0,
            **audit_summary,
        },
        "policy_modification_count": 0,
        "claim_limits": [
            "no packed CNN performance claim",
            "no general LeNet claim",
            "no arbitrary CNN graph claim",
            "no multiclass encrypted argmax claim",
            "no universal autotuning claim",
        ],
    }
    return run_manifest, selection, audit, summary


def write_ledger(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise ValueError("cannot write empty CNN-lite ledger")
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_pack(run_root: Path, output_root: Path) -> None:
    run_manifest, selection, audit, summary = validate_run(run_root)
    output_root.mkdir(parents=True)
    raw = output_root / "raw"
    inputs = output_root / "inputs"
    recovery = raw / "recovery"
    raw.mkdir()
    inputs.mkdir()
    recovery.mkdir()
    for source, destination in (
        (run_root / "run_manifest.json", raw / "run_manifest.json"),
        (run_root / "run_manifest.sha256", raw / "run_manifest.sha256"),
        (run_root / "selection.json", raw / "selection.json"),
        (run_root / "locked_audit.json", raw / "locked_audit.json"),
        (run_root / "stage_ledger.json", raw / "stage_ledger.json"),
        (
            run_root / "selection_command.txt",
            raw / "selection_command.txt",
        ),
        (
            run_root / "locked_audit_command.txt",
            raw / "locked_audit_command.txt",
        ),
        (
            run_root / "selection_execution.log",
            raw / "selection_execution.log",
        ),
        (
            run_root / "locked_audit_execution.log",
            raw / "locked_audit_execution.log",
        ),
    ):
        shutil.copy2(source, destination)
    for path in sorted((run_root / "recovery").iterdir()):
        shutil.copy2(path, recovery / path.name)
    (raw / "execution_source_files.json").write_bytes(
        canonical_json(run_manifest["execution_source_files"])
    )
    for name in (
        "SHA256SUMS",
        "configuration_validation.csv",
        "extraction_manifest.json",
        "locked_audit_test.csv",
        "model.json",
    ):
        shutil.copy2(REPO_ROOT / INPUT_ROOT / name, inputs / name)
    write_ledger(
        output_root / "selection_sample_ledger.csv",
        selection["trials"][0]["sample_ledger"],
    )
    write_ledger(
        output_root / "audit_sample_ledger.csv",
        audit["audit_trial"]["sample_ledger"],
    )
    (output_root / "summary.json").write_bytes(
        canonical_json(summary)
    )
    failure_records = {
        "schema_version": SCHEMA_VERSION,
        "scientific_failures": [],
        "pre_execution_recoveries": [
            json.loads(
                (
                    run_root
                    / "recovery/recovery_record.json"
                ).read_text(encoding="ascii")
            )
        ],
    }
    (output_root / "failure_records.json").write_bytes(
        canonical_json(failure_records)
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "execution_commit": EXECUTION_COMMIT,
        "execution_critical_source_digest":
            run_manifest["execution_critical_source_digest"],
        "binary_sha256": run_manifest["binary_sha256"],
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "extraction_policy_digest": EXTRACTION_POLICY_DIGEST,
        "execution_adapter": EXECUTION_ADAPTER,
        "input_digests": run_manifest["inputs"],
        "run_manifest_sha256": sha256_path(
            run_root / "run_manifest.json"
        ),
        "selection_sha256": sha256_path(
            run_root / "selection.json"
        ),
        "locked_audit_sha256": sha256_path(
            run_root / "locked_audit.json"
        ),
        "summary_sha256": sha256_path(
            output_root / "summary.json"
        ),
        "selection_observations": 750,
        "audit_observations": 750,
        "claim_status": "SUPPORTED",
        "structural_generalization": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
    }
    (output_root / "manifest.json").write_bytes(
        canonical_json(manifest)
    )
    readme = """# MNIST CNN-Lite Holdout Evidence V1

This pack freezes one predeclared scalar-replicated MNIST digit-0-vs-1
CNN-lite execution. The first synthesized candidate was SAFE on 250
configuration-validation images under three fresh keys and remained SAFE on
250 official-test locked-audit images under three new keys. No repair or
retuning occurred.

The result supports only the declared one-convolution, square-activation,
linear-head graph. It does not support packed CNN performance, general LeNet
configuration, arbitrary CNNs, multiclass encrypted argmax, or universal
autotuning. `paper_claim_allowed` remains false.
"""
    (output_root / "README.md").write_text(
        readme,
        encoding="ascii",
    )
    checksum_lines = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            relative = path.relative_to(output_root)
            checksum_lines.append(
                f"{sha256_path(path).removeprefix('sha256:')}  "
                f"{relative.as_posix()}\n"
            )
    (output_root / "SHA256SUMS").write_text(
        "".join(checksum_lines),
        encoding="ascii",
    )


def verify_pack(run_root: Path, output_root: Path) -> None:
    validate_run(run_root)
    if not output_root.is_dir():
        raise ValueError(f"evidence pack missing: {output_root}")
    with tempfile.TemporaryDirectory(
        prefix="flipguard_mnist_cnn_evidence_"
    ) as temporary:
        replay = Path(temporary) / "pack"
        build_pack(run_root, replay)
        expected = {
            path.relative_to(output_root)
            for path in output_root.rglob("*")
            if path.is_file()
        }
        observed = {
            path.relative_to(replay)
            for path in replay.rglob("*")
            if path.is_file()
        }
        if expected != observed:
            raise ValueError("CNN-lite evidence file set changed")
        for relative in sorted(expected):
            if (output_root / relative).read_bytes() != \
                    (replay / relative).read_bytes():
                raise ValueError(
                    f"CNN-lite evidence changed: {relative}"
                )


def main() -> None:
    args = parse_args()
    run_root = (
        args.run_root
        if args.run_root.is_absolute()
        else REPO_ROOT / args.run_root
    )
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    INPUT_VERIFIER.verify(
        REPO_ROOT / INPUT_ROOT,
        False,
        SOURCE_ARCHIVE,
    )
    if args.verify:
        verify_pack(run_root, output_root)
        print(
            "mnist_cnn_lite_evidence=PASS "
            f"manifest={sha256_path(output_root / 'manifest.json')}"
        )
        return
    if output_root.exists() and not args.force:
        raise SystemExit(
            f"refusing to overwrite evidence pack: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_mnist_cnn_freeze_",
        dir=str(output_root.parent),
    ) as temporary:
        staging = Path(temporary) / "pack"
        build_pack(run_root, staging)
        if output_root.exists():
            shutil.rmtree(output_root)
        staging.rename(output_root)
    print(
        "mnist_cnn_lite_evidence=FROZEN "
        f"manifest={sha256_path(output_root / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
