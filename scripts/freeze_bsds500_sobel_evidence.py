#!/usr/bin/env python3
"""Freeze and deterministically verify the BSDS500 Sobel evidence pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path(
    "results/thesis_grade_protocol/non_tabular_sobel_holdout_v1/run_6b0409e"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/non_tabular_sobel_holdout_v1"
)
INPUT_ROOT = Path(
    "datasets/vision_suite/bsds500/sobel_edge_score"
)
SOURCE_ARCHIVE = Path(
    "results/source_datasets/bsds500/BSR_bsds500.tgz"
)

SCHEMA_VERSION = "flipguard_non_tabular_sobel_evidence_v1"
EXECUTION_COMMIT = "6b0409e2c05ba416dd87e285005fe30d8e036de0"
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
    "07c196374cea947c5bd9d8d478311e75ba4754f875c4f19ce0387241d55da699"
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
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


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


def close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def validate_candidate_security(candidate: dict[str, Any]) -> None:
    security = candidate["security"]
    if security["envelope_id"] != \
            "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError("candidate security policy changed")
    for field in (
        "admission_status",
        "ciphertext_q_admission",
        "evaluation_key_qp_admission",
        "final_admission",
    ):
        if security[field] != "PASS":
            raise ValueError(
                f"candidate security {field}={security[field]}"
            )
    if security["headroom_bits"] < 0:
        raise ValueError("candidate security headroom is negative")


def validate_ledger(
    trial: dict[str, Any],
    contract: dict[str, Any],
    expected_partition: str,
) -> dict[str, Any]:
    rows = trial["sample_ledger"]
    if len(rows) != trial["encrypted_sample_evaluations"]:
        raise ValueError("sample ledger length mismatch")
    decision = contract["decision"]
    threshold = float(decision["threshold"])
    margin_floor = float(decision["margin_floor"])
    alpha = float(decision["safety_factor"])
    expected_samples = int(decision["validation_samples"])
    expected_keys = int(trial["key_repeats_completed"])
    if len(rows) != expected_samples * expected_keys:
        raise ValueError("sample/key accounting mismatch")

    seen: set[tuple[int, int]] = set()
    per_key: dict[int, set[int]] = {}
    images: set[str] = set()
    certifiable_ids: set[int] = set()
    ambiguous_ids: set[int] = set()
    flips = 0
    violations = 0
    max_error = 0.0
    max_usage = 0.0
    for index, row in enumerate(rows):
        key_run = int(row["key_run"])
        row_id = int(row["row_id"])
        identity = (key_run, row_id)
        if identity in seen:
            raise ValueError(f"duplicate sample identity {identity}")
        seen.add(identity)
        per_key.setdefault(key_run, set()).add(row_id)
        images.add(str(row["image_id"]))
        if row["source_partition"] != expected_partition:
            raise ValueError("ledger source partition changed")

        plain = float(row["plain_score"])
        approx = float(row["ckks_score"])
        observed_threshold = float(row["threshold"])
        if not close(observed_threshold, threshold):
            raise ValueError("ledger threshold changed")
        margin = abs(plain - threshold)
        error = abs(approx - plain)
        certifiable = margin > margin_floor
        plain_decision = plain >= threshold
        approx_decision = approx >= threshold
        flip = plain_decision != approx_decision
        if not close(float(row["margin"]), margin) or \
                not close(float(row["abs_error"]), error) or \
                bool(row["certifiable"]) != certifiable or \
                bool(row["plain_decision"]) != plain_decision or \
                bool(row["ckks_decision"]) != approx_decision or \
                bool(row["decision_flip"]) != flip:
            raise ValueError(
                f"derived ledger fields changed at row {index}"
            )
        for timing in (
            "encode_encrypt_ms",
            "eval_only_ms",
            "decrypt_decode_ms",
            "total_eval_ms",
        ):
            value = float(row[timing])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid timing {timing}")

        if not certifiable:
            ambiguous_ids.add(row_id)
            if float(row["error_budget"]) != 0 or \
                    float(row["error_budget_usage"]) != 0 or \
                    bool(row["error_violation"]):
                raise ValueError("ambiguous observation has a budget")
            continue
        certifiable_ids.add(row_id)
        budget = alpha * margin
        usage = error / budget
        violation = error >= budget
        if not close(float(row["error_budget"]), budget) or \
                not close(
                    float(row["error_budget_usage"]),
                    usage,
                ) or \
                bool(row["error_violation"]) != violation:
            raise ValueError("certifiable observation budget changed")
        flips += int(flip)
        violations += int(violation)
        max_error = max(max_error, error)
        max_usage = max(max_usage, usage)

    if sorted(per_key) != list(range(1, expected_keys + 1)):
        raise ValueError("key-run identities changed")
    reference_rows = per_key[1]
    if any(values != reference_rows for values in per_key.values()):
        raise ValueError("row identity changes across key runs")
    if len(reference_rows) != expected_samples:
        raise ValueError("per-key sample count changed")
    if len(certifiable_ids) != int(trial["v_cert"]) or \
            len(ambiguous_ids) != int(trial["v_amb"]):
        raise ValueError("Vcert/Vamb ledger mismatch")
    if flips != int(trial["decision_flips"]) or \
            violations != int(trial["error_violations"]) or \
            not close(max_error, float(trial["max_observed_error"])) or \
            not close(
                max_usage,
                float(trial["max_error_budget_usage"]),
            ):
        raise ValueError("ledger aggregate mismatch")
    return {
        "observations": len(rows),
        "sample_ids": len(reference_rows),
        "image_clusters": len(images),
        "key_runs": expected_keys,
        "certifiable_samples": len(certifiable_ids),
        "ambiguous_samples": len(ambiguous_ids),
        "decision_flips": flips,
        "error_violations": violations,
        "max_observed_error": max_error,
        "max_error_budget_usage": max_usage,
    }


def validate_run(
    run_root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
] :
    run_manifest = json.loads(
        (run_root / "run_manifest.json").read_text(encoding="ascii")
    )
    selection = json.loads(
        (run_root / "selection.json").read_text(encoding="ascii")
    )
    audit = json.loads(
        (run_root / "locked_audit.json").read_text(encoding="ascii")
    )
    if run_manifest["source_commit"] != EXECUTION_COMMIT or \
            run_manifest["origin_commit"] != EXECUTION_COMMIT or \
            not run_manifest["working_tree_clean"]:
        raise ValueError("execution source provenance changed")
    if run_manifest["direct_policy"]["digest"] != \
            DIRECT_POLICY_DIGEST or \
            run_manifest["security_policy"]["digest"] != \
            SECURITY_POLICY_DIGEST or \
            run_manifest["extraction_policy"]["digest"] != \
            EXTRACTION_POLICY_DIGEST:
        raise ValueError("run policy digest changed")
    if run_manifest["direct_policy"]["modified"]:
        raise ValueError("run claims Direct Policy modification")

    binary_paths = {
        "autotune": run_root / "bin/flipguard-sobel-autotune",
        "audit": run_root / "bin/flipguard-sobel-audit",
    }
    for name, path in binary_paths.items():
        if sha256_path(path) != run_manifest["binary_sha256"][name]:
            raise ValueError(f"{name} binary digest mismatch")
    input_paths = {
        "model": INPUT_ROOT / "model.json",
        "configuration_validation":
            INPUT_ROOT / "configuration_validation.csv",
        "locked_audit_test": INPUT_ROOT / "locked_audit_test.csv",
        "extraction_manifest": INPUT_ROOT / "extraction_manifest.json",
        "source_archive": SOURCE_ARCHIVE,
    }
    for name, path in input_paths.items():
        if sha256_path(path) != run_manifest["inputs"][name]:
            raise ValueError(f"{name} input digest mismatch")

    plan = selection["plan"]
    if selection["execution_adapter"] != \
            "bsds500_sobel_rescale_graph_adapter_v1" or \
            plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError("selection policy or adapter changed")
    if plan["contract"]["model_type"] != "sobel_edge_score" or \
            plan["contract"]["decision"]["validation_samples"] != 400 or \
            plan["contract"]["decision"]["certifiable_samples"] != 400 or \
            plan["contract"]["decision"]["ambiguous_samples"] != 0:
        raise ValueError("selection workload contract changed")
    if selection["outcome"] != "SELECTED" or \
            selection["trials_used"] != 2 or \
            selection["encrypted_key_runs"] != 6 or \
            selection["encrypted_sample_evaluations"] != 2400:
        raise ValueError("selection aggregate changed")
    if [row["status"] for row in selection["trials"]] != \
            ["REJECTED", "SAFE"]:
        raise ValueError("selection trial status sequence changed")

    initial = selection["trials"][0]["candidate"]
    repaired = selection["trials"][1]["candidate"]
    if selection["selected"] != repaired:
        raise ValueError("selected candidate is not final SAFE trial")
    if repaired["parameters"]["log_n"] != \
            initial["parameters"]["log_n"] or \
            repaired["parameters"]["log_p"] != \
            initial["parameters"]["log_p"] or \
            repaired["parameters"]["log_default_scale"] != \
            initial["parameters"]["log_default_scale"] + 4 or \
            repaired["parameters"]["log_q"] != [
                bits + 4
                for bits in initial["parameters"]["log_q"]
            ]:
        raise ValueError("frozen +4-bit numerical repair changed")
    if selection["trials"][0]["failure_signal"] != \
            "NUMERICAL_REJECT":
        raise ValueError("initial rejection signal changed")
    for candidate in (initial, repaired):
        validate_candidate_security(candidate)

    selection_ledgers = [
        validate_ledger(
            trial,
            plan["contract"],
            "val",
        )
        for trial in selection["trials"]
    ]
    if selection_ledgers[0]["error_violations"] == 0 or \
            selection_ledgers[1]["error_violations"] != 0 or \
            selection_ledgers[1]["decision_flips"] != 0:
        raise ValueError("selection rejection/SAFE evidence changed")

    if audit["outcome"] != "LOCKED_AUDIT_PASS" or \
            audit["retuning_performed"] or \
            audit["selected_candidate"] != repaired or \
            audit["audit_trial"]["candidate"] != repaired:
        raise ValueError("locked audit candidate identity changed")
    audit_contract = audit["audit_contract"]
    if audit_contract["decision"]["validation_samples"] != 400 or \
            audit_contract["decision"]["certifiable_samples"] != 399 or \
            audit_contract["decision"]["ambiguous_samples"] != 1:
        raise ValueError("locked audit contract changed")
    audit_ledger = validate_ledger(
        audit["audit_trial"],
        audit_contract,
        "test",
    )
    if audit["audit_trial"]["status"] != "SAFE" or \
            audit_ledger["decision_flips"] != 0 or \
            audit_ledger["error_violations"] != 0:
        raise ValueError("locked audit SAFE evidence changed")

    validation_images = {
        row["image_id"]
        for row in selection["trials"][1]["sample_ledger"]
    }
    audit_images = {
        row["image_id"]
        for row in audit["audit_trial"]["sample_ledger"]
    }
    if validation_images & audit_images or \
            len(validation_images) != 50 or \
            len(audit_images) != 50:
        raise ValueError("validation/audit image clusters overlap")
    derived = {
        "selection_ledgers": selection_ledgers,
        "audit_ledger": audit_ledger,
    }
    return run_manifest, selection, audit, derived


LEDGER_FIELDS = (
    "stage",
    "trial_index",
    "trial_status",
    "candidate_id",
    "key_run",
    "row_id",
    "image_id",
    "source_partition",
    "patch_index",
    "center_x",
    "center_y",
    "plain_score",
    "ckks_score",
    "threshold",
    "margin",
    "abs_error",
    "certifiable",
    "error_budget",
    "error_budget_usage",
    "error_violation",
    "plain_decision",
    "ckks_decision",
    "decision_flip",
    "encode_encrypt_ms",
    "eval_only_ms",
    "decrypt_decode_ms",
    "total_eval_ms",
)


def write_ledger(
    path: Path,
    stage: str,
    trials: list[dict[str, Any]],
) -> None:
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=LEDGER_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        for trial in trials:
            for row in trial["sample_ledger"]:
                output = dict(row)
                output.update({
                    "stage": stage,
                    "trial_index": trial["trial_index"],
                    "trial_status": trial["status"],
                    "candidate_id": trial["candidate"]["id"],
                })
                writer.writerow({
                    field: output[field]
                    for field in LEDGER_FIELDS
                })


def build(
    run_root: Path,
    output_root: Path,
    builder_commit: str,
    force: bool,
) -> None:
    run_manifest, selection, audit, derived = validate_run(run_root)
    if output_root.exists():
        if not force:
            raise FileExistsError(
                f"{output_root} exists; use --force"
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    raw = output_root / "raw"
    inputs = output_root / "inputs"
    raw.mkdir()
    inputs.mkdir()

    for name in (
        "run_manifest.json",
        "execution_source_files.json",
        "selection.json",
        "locked_audit.json",
    ):
        shutil.copyfile(run_root / name, raw / name)
    for name in (
        "model.json",
        "configuration_validation.csv",
        "locked_audit_test.csv",
        "extraction_manifest.json",
        "SHA256SUMS",
    ):
        shutil.copyfile(INPUT_ROOT / name, inputs / name)

    write_ledger(
        output_root / "selection_sample_ledger.csv",
        "configuration_validation",
        selection["trials"],
    )
    write_ledger(
        output_root / "audit_sample_ledger.csv",
        "locked_audit",
        [audit["audit_trial"]],
    )

    initial_trial, safe_trial = selection["trials"]
    audit_trial = audit["audit_trial"]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUPPORTED",
        "paper_claim_allowed": False,
        "block_reason": (
            "manual post-extension claim admission and paper review are pending"
        ),
        "scope": (
            "BSDS500 single-patch Sobel gradient-energy threshold under "
            "scalar-replicated packing"
        ),
        "source": {
            "dataset": "BSDS500",
            "train_threshold_images": 100,
            "validation_images": 50,
            "audit_images": 50,
            "patches_per_image": 8,
            "validation_audit_image_overlap": 0,
        },
        "selection": {
            "outcome": selection["outcome"],
            "trials": selection["trials_used"],
            "repairs": 1,
            "fresh_key_runs": selection["encrypted_key_runs"],
            "encrypted_sample_evaluations":
                selection["encrypted_sample_evaluations"],
            "initial_status": initial_trial["status"],
            "initial_flips": initial_trial["decision_flips"],
            "initial_violations":
                initial_trial["error_violations"],
            "initial_max_budget_usage":
                initial_trial["max_error_budget_usage"],
            "selected_candidate": safe_trial["candidate"]["id"],
            "selected_flips": safe_trial["decision_flips"],
            "selected_violations":
                safe_trial["error_violations"],
            "selected_max_budget_usage":
                safe_trial["max_error_budget_usage"],
        },
        "locked_audit": {
            "outcome": audit["outcome"],
            "status": audit_trial["status"],
            "fresh_key_runs": audit_trial["key_repeats_completed"],
            "encrypted_sample_evaluations":
                audit_trial["encrypted_sample_evaluations"],
            "v_cert": audit_trial["v_cert"],
            "v_amb": audit_trial["v_amb"],
            "flips": audit_trial["decision_flips"],
            "violations": audit_trial["error_violations"],
            "max_budget_usage":
                audit_trial["max_error_budget_usage"],
            "retuning": int(audit["retuning_performed"]),
            "candidate_identity_equal":
                audit["selected_candidate"] ==
                audit_trial["candidate"],
        },
        "accounting": {
            "total_candidate_trials":
                selection["trials_used"] + 1,
            "total_fresh_key_runs":
                selection["encrypted_key_runs"] +
                audit_trial["key_repeats_completed"],
            "total_encrypted_sample_evaluations":
                selection["encrypted_sample_evaluations"] +
                audit_trial["encrypted_sample_evaluations"],
        },
        "claim_boundary": {
            "non_tabular_sobel_holdout":
                "SUPPORTED",
            "structural_generalization":
                "PARTIALLY_SUPPORTED",
            "arbitrary_graph_generalization":
                "NOT_EVALUATED",
            "cnn_generalization": "NOT_EVALUATED",
            "full_image_edge_accuracy": "NOT_EVALUATED",
        },
    }
    (output_root / "summary.json").write_bytes(
        canonical_json(summary)
    )
    failure = {
        "schema_version": SCHEMA_VERSION,
        "scientific_negative_results": [
            {
                "stage": "configuration_validation",
                "trial_index": initial_trial["trial_index"],
                "candidate_id": initial_trial["candidate"]["id"],
                "status": initial_trial["status"],
                "failure_signal": initial_trial["failure_signal"],
                "decision_flips": initial_trial["decision_flips"],
                "error_violations":
                    initial_trial["error_violations"],
                "max_error_budget_usage":
                    initial_trial["max_error_budget_usage"],
                "disposition":
                    "preserved_then_frozen_plus4_bit_repair",
            },
        ],
        "execution_failures": [],
    }
    (output_root / "failure_records.json").write_bytes(
        canonical_json(failure)
    )
    readme = """# Non-Tabular BSDS500 Sobel Holdout Evidence V1

This pack freezes the predeclared BSDS500 Sobel selection and no-retuning
locked audit. The first analysis-derived candidate was numerically rejected;
the single frozen +4-bit repair was SAFE. The byte-identical selected literal
remained SAFE on disjoint test images.

The raw JSON and flattened CSV ledgers retain every patch-by-key CKKS score.
`scripts/freeze_bsds500_sobel_evidence.py --verify` rebuilds this pack and
recomputes all margins, decisions, errors, budgets, flips, violations, and
aggregate maxima.

Claim scope is one Sobel patch graph under scalar-replicated packing. This pack
does not support arbitrary graphs, packed full-image execution, edge-detection
accuracy, or CNN generalization. `paper_claim_allowed` remains false.
"""
    (output_root / "README.md").write_text(
        readme,
        encoding="ascii",
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": "non_tabular_sobel_holdout_v1",
        "execution_commit": EXECUTION_COMMIT,
        "evidence_builder_commit": builder_commit,
        "execution_critical_source_digest":
            run_manifest["execution_critical_source_digest"],
        "binary_sha256": run_manifest["binary_sha256"],
        "policies": {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "extraction_policy": EXTRACTION_POLICY_DIGEST,
        },
        "raw_run": {
            "path": str(run_root),
            "run_manifest_sha256":
                sha256_path(run_root / "run_manifest.json"),
            "selection_sha256":
                sha256_path(run_root / "selection.json"),
            "locked_audit_sha256":
                sha256_path(run_root / "locked_audit.json"),
        },
        "summary": summary,
        "derived_validation": derived,
    }
    (output_root / "manifest.json").write_bytes(
        canonical_json(manifest)
    )
    checksum_names = sorted(
        str(path.relative_to(output_root))
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    checksums = "".join(
        f"{sha256_path(output_root / name).removeprefix('sha256:')}  {name}\n"
        for name in checksum_names
    )
    (output_root / "SHA256SUMS").write_text(
        checksums,
        encoding="ascii",
    )


def verify(run_root: Path, output_root: Path) -> None:
    manifest = json.loads(
        (output_root / "manifest.json").read_text(encoding="ascii")
    )
    builder_commit = manifest["evidence_builder_commit"]
    with tempfile.TemporaryDirectory(
        prefix="flipguard-sobel-evidence-"
    ) as temporary:
        rebuilt = Path(temporary) / "pack"
        build(
            run_root,
            rebuilt,
            builder_commit=builder_commit,
            force=False,
        )
        expected_files = sorted(
            str(path.relative_to(output_root))
            for path in output_root.rglob("*")
            if path.is_file()
        )
        rebuilt_files = sorted(
            str(path.relative_to(rebuilt))
            for path in rebuilt.rglob("*")
            if path.is_file()
        )
        if expected_files != rebuilt_files:
            raise ValueError("evidence file set changed")
        for name in expected_files:
            if (output_root / name).read_bytes() != \
                    (rebuilt / name).read_bytes():
                raise ValueError(
                    f"evidence replay mismatch: {name}"
                )
    print(
        "bsds500_sobel_evidence=PASS "
        f"manifest={sha256_path(output_root / 'manifest.json')} "
        "selection_observations=2400 audit_observations=1200 "
        "audit_status=SAFE retuning=0"
    )


def main() -> None:
    args = parse_args()
    run_root = (REPO_ROOT / args.run_root).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(run_root, output_root)
        return
    builder_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    build(
        run_root,
        output_root,
        builder_commit=builder_commit,
        force=args.force,
    )
    print(
        "bsds500_sobel_evidence=FROZEN "
        f"output={output_root} "
        f"manifest={sha256_path(output_root / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
