#!/usr/bin/env python3
"""Freeze the EVA schedule-bound replay and its preserved negative result."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOVERY_RUN = Path(
    "results/thesis_grade_protocol/eva_schedule_bound_adapter_v1/"
    "run_441af726"
)
DEFAULT_CORRECTED_RUN = Path(
    "results/thesis_grade_protocol/eva_schedule_bound_adapter_v1/"
    "run_1a1c4f8d"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/eva_schedule_bound_adapter_replay_v1"
)
CONTRACT = Path(
    "experiments/eva_schedule_bound_adapter_v1/contract.json"
)
PROTOCOL = Path(
    "docs/research/step_7g10_eva_schedule_bound_adapter_protocol.md"
)
SCHEMA = "flipguard_eva_schedule_bound_adapter_evidence_v1"
EXPECTED_RECOVERY_COMMIT = (
    "441af726e9c240b71408468b297cc18fac6a6920"
)
EXPECTED_CORRECTED_COMMIT = (
    "1a1c4f8d8c4b5daf6e66b24bcc155dcb2f99d9ed"
)

VERIFIER_PATH = REPO_ROOT / (
    "scripts/verify_eva_schedule_bound_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_schedule_bound_for_freezer",
    VERIFIER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--recovery-run",
        type=Path,
        default=DEFAULT_RECOVERY_RUN,
    )
    parser.add_argument(
        "--corrected-run",
        type=Path,
        default=DEFAULT_CORRECTED_RUN,
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


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


def save_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
    )
    try:
        with open(descriptor, "wb", closefd=True) as handle:
            handle.write(canonical_json(value))
            handle.flush()
        Path(temporary).replace(path)
    finally:
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "EVA schedule evidence freeze requires a clean tree:\n"
            + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(f"HEAD {head} does not match origin {origin}")
    return head


def validate_run(
    root: Path,
    expected_commit: str,
) -> dict[str, Any]:
    manifest = load_json(root / "run_manifest.json")
    state = load_json(root / "state.json")
    selection = load_json(root / "smoke_selection.json")
    ledger_value = json.loads(
        (root / "stage_ledger.json").read_text(encoding="ascii")
    )
    if not isinstance(ledger_value, list) or len(ledger_value) != 1:
        raise ValueError(f"{root}: unexpected stage ledger")
    if (
        manifest["source_commit"] != expected_commit
        or manifest["origin_commit"] != expected_commit
        or manifest["working_tree_clean"] is not True
        or manifest["security_policy_digest"] !=
            VERIFIER.SECURITY_DIGEST
        or manifest["direct_policy_digest"] != VERIFIER.DIRECT_DIGEST
        or manifest["formal_candidate_trials"] != 1
        or manifest["diagnostic_candidate_trials"] != 1
        or manifest["synthesis_calls"] != 0
        or manifest["repair_calls"] != 0
        or manifest["retuning"] != 0
    ):
        raise ValueError(f"{root}: run provenance changed")
    for binary in manifest["binaries"].values():
        if sha256_path(absolute(Path(binary["path"]))) != binary["sha256"]:
            raise ValueError(f"{root}: execution binary changed")
    if (
        state["smoke"] != "RECOVERABLE_IMPLEMENTATION_FAILURE"
        or state["selection"] != "PENDING"
        or state["audit"] != "PENDING"
        or state["diagnostic_candidate_trials_started"] != 1
        or state["formal_candidate_trials_started"] != 0
        or state["audit_trials_started"] != 0
        or state["paper_claim_allowed"] is not False
    ):
        raise ValueError(f"{root}: fail-closed state changed")
    trial = selection["trial"]
    bound = selection["bound_candidate"]
    schedule = bound["execution_schedule"]
    if (
        selection["outcome"] != "NO_SAFE"
        or selection["trials_used"] != 1
        or selection["encrypted_key_runs"] != 1
        or trial["status"] != "REJECTED"
        or trial["key_repeats_completed"] != 1
        or trial["encrypted_sample_evaluations"] != 1
        or trial["decision_flips"] not in (0, 1)
        or trial["error_violations"] != 1
        or len(trial["sample_ledger"]) != 1
        or bound["candidate"]["security"]["final_admission"] != "PASS"
        or schedule["required_q_primes"] != 3
        or schedule["rescale_levels"] != 2
        or schedule["policy_retuning"] != 0
    ):
        raise ValueError(f"{root}: smoke result changed")
    sample = trial["sample_ledger"][0]
    if (
        sample["error_violation"] is not True
        or sample["certifiable"] is not True
        or sample["absolute_error"] != trial["max_observed_error"]
        or sample["normalized_budget_usage"] !=
            trial["max_error_budget_usage"]
    ):
        raise ValueError(f"{root}: smoke sample arithmetic changed")
    ledger = ledger_value[0]
    if (
        ledger["artifact_sha256"] !=
            sha256_path(root / "smoke_selection.json")
        or ledger["status"] !=
            "RECOVERABLE_IMPLEMENTATION_FAILURE"
    ):
        raise ValueError(f"{root}: smoke ledger binding changed")
    return {
        "manifest": manifest,
        "state": state,
        "selection": selection,
        "sample": sample,
    }


def build_summary(
    recovery: dict[str, Any],
    corrected: dict[str, Any],
) -> dict[str, Any]:
    first_trial = recovery["selection"]["trial"]
    final_trial = corrected["selection"]["trial"]
    return {
        "schema_version": SCHEMA,
        "status": "PARTIAL_SCIENTIFIC_RESULT",
        "classification":
            "SOURCE_REPLAYED_PUBLIC_COMPILER_SCHEDULE",
        "evaluation_role": "seed0_development_interoperability_control",
        "schedule_id": corrected["selection"]["bound_candidate"][
            "execution_schedule"
        ]["schedule_id"],
        "security_v2": {
            "status": "PASS",
            "log_n": 14,
            "log_q": 180,
            "log_p": 60,
            "log_qp": 240,
            "cap": 430,
            "headroom_bits": 190,
        },
        "recovery_attempt": {
            "source_commit": recovery["manifest"]["source_commit"],
            "execution_critical_source_digest":
                recovery["manifest"]["execution_critical_source_digest"],
            "binary_sha256":
                recovery["manifest"]["binaries"]["certify_candidate"][
                    "sha256"
                ],
            "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
            "reason":
                "cubic coefficient sign was negated before an explicit "
                "subtraction",
            "status": first_trial["status"],
            "key_runs": first_trial["key_repeats_completed"],
            "flips": first_trial["decision_flips"],
            "violations": first_trial["error_violations"],
            "max_error": first_trial["max_observed_error"],
            "max_budget_usage": first_trial[
                "max_error_budget_usage"
            ],
        },
        "corrected_smoke": {
            "source_commit": corrected["manifest"]["source_commit"],
            "execution_critical_source_digest":
                corrected["manifest"]["execution_critical_source_digest"],
            "binary_sha256":
                corrected["manifest"]["binaries"]["certify_candidate"][
                    "sha256"
                ],
            "classification": "PARTIAL_SCIENTIFIC_RESULT",
            "reason_code":
                "LATTIGO_RUNTIME_NUMERICAL_REJECT_AFTER_EXACT_SCHEDULE_REPLAY",
            "status": final_trial["status"],
            "candidate_trials": final_trial["trial_index"],
            "key_runs": final_trial["key_repeats_completed"],
            "encrypted_sample_evaluations":
                final_trial["encrypted_sample_evaluations"],
            "flips": final_trial["decision_flips"],
            "violations": final_trial["error_violations"],
            "max_error": final_trial["max_observed_error"],
            "max_budget_usage": final_trial["max_error_budget_usage"],
            "security_admission": corrected["selection"][
                "bound_candidate"
            ]["candidate"]["security"]["final_admission"],
        },
        "formal_validation": {
            "status": "NOT_EVALUATED",
            "candidate_trials": 0,
            "key_runs": 0,
            "encrypted_sample_evaluations": 0,
            "reason":
                "the corrected one-row diagnostic was REJECTED, so the "
                "predeclared smoke gate blocked the 14-row trial",
        },
        "locked_audit": {
            "status": "NOT_EVALUATED",
            "trials": 0,
            "key_runs": 0,
            "retuning": 0,
            "reason": "validation did not establish a SAFE candidate",
        },
        "interpretation": {
            "supported":
                "the schedule-bound schema and Lattigo lowering executed "
                "the source-replayed literal fail-closed",
            "not_supported":
                "the candidate could not be certified decision-preserving "
                "under the frozen Lattigo v6.2.0 Xs/Xe runtime",
            "native_eva_seal_inference":
                "NOT_EVALUATED; cross-runtime rejection does not establish "
                "native EVA/SEAL behavior",
            "retuning_performed": False,
        },
        "accounting": {
            "preserved_diagnostic_candidate_trials": 2,
            "preserved_diagnostic_key_runs": 2,
            "formal_candidate_trials": 0,
            "formal_key_runs": 0,
            "formal_encrypted_sample_evaluations": 0,
            "synthesis_calls": 0,
            "repair_calls": 0,
            "retuning": 0,
        },
        "claim_states": {
            "schedule_bound_external_candidate_import": "SUPPORTED",
            "encrypted_external_candidate_certification": "BLOCKED",
            "locked_audit_external_schedule_replay": "NOT_EVALUATED",
            "native_eva_seal_runtime_execution": "NOT_EVALUATED",
            "general_external_compiler_interoperability":
                "PARTIALLY_SUPPORTED",
        },
        "paper_claim_allowed": False,
        "block_reason":
            "development-only single compiler/workload replay; corrected "
            "Lattigo-runtime smoke was numerically REJECTED and native "
            "EVA/SEAL execution was not evaluated",
    }


def selected_run_files(root: Path) -> list[Path]:
    fixed = [
        "run_manifest.json",
        "state.json",
        "stage_ledger.json",
        "smoke_validation.csv",
        "smoke_selection.json",
        "logs/smoke.log",
        "snapshots/contract.json",
        "snapshots/execution_schedule.json",
        "snapshots/candidate_request.json",
    ]
    return [root / relative for relative in fixed]


def copy_run(source: Path, destination: Path) -> None:
    for path in selected_run_files(source):
        if not path.is_file():
            raise ValueError(f"missing EVA run artifact: {path}")
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def write_attempts_csv(
    path: Path,
    recovery: dict[str, Any],
    corrected: dict[str, Any],
) -> None:
    rows = []
    for attempt_id, classification, item in (
        (
            "recovery_sign_error",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
            recovery,
        ),
        (
            "corrected_schedule",
            "PARTIAL_SCIENTIFIC_RESULT",
            corrected,
        ),
    ):
        trial = item["selection"]["trial"]
        sample = item["sample"]
        rows.append({
            "attempt_id": attempt_id,
            "classification": classification,
            "source_commit": item["manifest"]["source_commit"],
            "execution_critical_source_digest":
                item["manifest"]["execution_critical_source_digest"],
            "binary_sha256": item["manifest"]["binaries"][
                "certify_candidate"
            ]["sha256"],
            "candidate_id": trial["candidate"]["id"],
            "status": trial["status"],
            "key_runs": trial["key_repeats_completed"],
            "encrypted_sample_evaluations":
                trial["encrypted_sample_evaluations"],
            "plaintext_score": sample["plaintext_score"],
            "ckks_score": sample["ckks_score"],
            "absolute_error": sample["absolute_error"],
            "normalized_budget_usage":
                sample["normalized_budget_usage"],
            "decision_flip": sample["decision_flip"],
            "error_violation": sample["error_violation"],
            "formal_result": False,
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_checksums(root: Path) -> None:
    expected = {}
    for line in (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
        digest, relative = line.split("  ", 1)
        expected[relative] = f"sha256:{digest}"
    actual = {
        path.relative_to(root).as_posix(): sha256_path(path)
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != expected:
        raise ValueError("frozen EVA schedule evidence checksums changed")


def verify_frozen(root: Path) -> dict[str, Any]:
    verify_checksums(root)
    recovery = validate_run(
        root / "runs/recovery_sign_error",
        EXPECTED_RECOVERY_COMMIT,
    )
    corrected = validate_run(
        root / "runs/corrected_schedule",
        EXPECTED_CORRECTED_COMMIT,
    )
    summary = load_json(root / "summary.json")
    if summary != build_summary(recovery, corrected):
        raise ValueError("frozen EVA schedule summary changed")
    manifest = load_json(root / "manifest.json")
    if (
        manifest["schema_version"] != SCHEMA
        or manifest["summary_sha256"] !=
            sha256_path(root / "summary.json")
        or manifest["paper_claim_allowed"] is not False
    ):
        raise ValueError("frozen EVA schedule manifest changed")
    return {
        "status": summary["status"],
        "manifest_sha256": sha256_path(root / "manifest.json"),
        "summary_sha256": sha256_path(root / "summary.json"),
        "corrected_smoke_status":
            summary["corrected_smoke"]["status"],
        "formal_candidate_trials":
            summary["formal_validation"]["candidate_trials"],
        "paper_claim_allowed": False,
    }


def freeze(
    recovery_root: Path,
    corrected_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    head = require_clean_origin()
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA schedule evidence: {output_root}"
        )
    VERIFIER.verify(CONTRACT)
    recovery = validate_run(
        recovery_root,
        EXPECTED_RECOVERY_COMMIT,
    )
    corrected = validate_run(
        corrected_root,
        EXPECTED_CORRECTED_COMMIT,
    )
    output_root.mkdir(parents=True)
    copy_run(
        recovery_root,
        output_root / "runs/recovery_sign_error",
    )
    copy_run(
        corrected_root,
        output_root / "runs/corrected_schedule",
    )
    shutil.copy2(CONTRACT, output_root / "contract.json")
    shutil.copy2(PROTOCOL, output_root / "protocol.md")
    summary = build_summary(recovery, corrected)
    save_atomic(output_root / "summary.json", summary)
    write_attempts_csv(
        output_root / "attempts.csv",
        recovery,
        corrected,
    )
    recovery_diff = git(
        "diff",
        "--no-ext-diff",
        EXPECTED_RECOVERY_COMMIT,
        EXPECTED_CORRECTED_COMMIT,
        "--",
        "internal/ckksbackend/eva_execution_schedule.go",
    )
    (output_root / "recovery_semantic_diff.patch").write_text(
        recovery_diff + "\n",
        encoding="ascii",
    )
    readme = (
        "# EVA Schedule-Bound Adapter Replay V1\n\n"
        "This pack preserves a source-replayed Microsoft EVA compiled "
        "schedule evaluated as an untrusted external candidate under "
        "FlipGuard's frozen Lattigo v6.2.0 runtime. The first smoke exposed "
        "and preserves a lowering sign error. After the exact sign repair, "
        "the corrected one-row smoke remained REJECTED because its error "
        "exceeded the decision-margin budget. No formal 14-row validation, "
        "locked audit, synthesis, repair, or retuning followed.\n\n"
        "The result supports schedule-bound import and fail-closed "
        "certification behavior. It does not support native EVA/SEAL "
        "runtime equivalence or broad external compiler interoperability.\n"
    )
    (output_root / "README.md").write_text(readme, encoding="ascii")
    save_atomic(output_root / "manifest.json", {
        "schema_version": SCHEMA,
        "status": summary["status"],
        "freezer_commit": head,
        "recovery_execution_commit": EXPECTED_RECOVERY_COMMIT,
        "corrected_execution_commit": EXPECTED_CORRECTED_COMMIT,
        "contract_sha256": sha256_path(CONTRACT),
        "protocol_sha256": sha256_path(PROTOCOL),
        "summary_sha256": sha256_path(output_root / "summary.json"),
        "attempts_sha256": sha256_path(output_root / "attempts.csv"),
        "security_policy_digest": VERIFIER.SECURITY_DIGEST,
        "direct_policy_digest": VERIFIER.DIRECT_DIGEST,
        "schedule_contract_digest":
            corrected["manifest"]["schedule_contract_digest"],
        "claim_states": summary["claim_states"],
        "paper_claim_allowed": False,
    })
    write_checksums(output_root)
    return verify_frozen(output_root)


def main() -> None:
    args = parse_args()
    output_root = absolute(args.output_root)
    if args.verify:
        result = verify_frozen(output_root)
    else:
        result = freeze(
            absolute(args.recovery_run),
            absolute(args.corrected_run),
            output_root,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
