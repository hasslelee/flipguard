#!/usr/bin/env python3
"""Run the predeclared independent-training-seed CKKS extension."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = Path("datasets/independent_training_seed_suite_v1")
RESULT_BASE = Path(
    "results/thesis_grade_protocol/"
    "independent_training_seed_extension_v1"
)
SCHEMA_VERSION = "flipguard_independent_training_seed_run_v1"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
INPUT_POLICY_DIGEST = (
    "sha256:"
    "e9353654e5ec899fc91ce70e8dd501905b95973bcb8493cc1d27f3ffc77af1cb"
)
EXPECTED_SEEDS = (1729, 2718, 3141)
EXPECTED_DATASETS = ("iris_binary", "wdbc", "digits_binary")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight-only", action="store_true")
    action.add_argument("--resume", action="store_true")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--input-root", type=Path, default=INPUT_ROOT)
    parser.add_argument(
        "--python-with-science-deps",
        default=".venv/bin/python",
    )
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().isoformat()


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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def run_checked(
    command: Sequence[str],
    *,
    stdout_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if stdout_path is None:
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="ascii") as handle:
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )


def git_text(*arguments: str) -> str:
    return run_checked(["git", *arguments]).stdout.strip()


def require_clean_provenance() -> tuple[str, str]:
    head = git_text("rev-parse", "HEAD")
    origin = git_text(
        "rev-parse",
        "origin/feature/flipguard-auto-tuner",
    )
    status = git_text("status", "--short")
    if status:
        raise ValueError(
            "INTEGRITY_BLOCK: working tree is not clean:\n" + status
        )
    if head != origin:
        raise ValueError(
            f"INTEGRITY_BLOCK: HEAD {head} != origin {origin}"
        )
    return head, origin


def execution_source_closure() -> tuple[dict[str, str], str]:
    output = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            "cmd",
            "internal",
            "go.mod",
            "go.sum",
        ],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    paths = [
        Path(value.decode("utf-8"))
        for value in output.split(b"\0")
        if value
    ]
    closure = {
        path.as_posix(): sha256_path(REPO_ROOT / path)
        for path in sorted(paths)
    }
    return closure, canonical_digest(closure)


def write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(value)
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_command(path: Path, command: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        " ".join(command) + "\n",
        encoding="ascii",
    )


def load_input_summary(input_root: Path) -> dict[str, Any]:
    summary = json.loads(
        (input_root / "summary.json").read_text(encoding="ascii")
    )
    if summary["policy_digest"] != INPUT_POLICY_DIGEST or \
            summary["instance_count"] != 9 or \
            summary["paper_claim_allowed"]:
        raise ValueError("INTEGRITY_BLOCK: input summary changed")
    expected = {
        (seed, dataset)
        for seed in EXPECTED_SEEDS
        for dataset in EXPECTED_DATASETS
    }
    observed = {
        (
            int(instance["training_seed"]),
            instance["dataset_id"],
        )
        for instance in summary["instances"]
    }
    if observed != expected:
        raise ValueError("INTEGRITY_BLOCK: input matrix changed")
    return summary


def build_binaries(run_root: Path) -> dict[str, dict[str, str]]:
    targets = {
        "materialize": "./cmd/flipguard-materialize-tabular",
        "synthesize": "./cmd/flipguard-synthesize",
        "autotune": "./cmd/flipguard-autotune",
        "audit": "./cmd/flipguard-audit",
    }
    binaries = {}
    for name, target in targets.items():
        path = run_root / "bin" / f"flipguard-{name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        run_checked(["go", "build", "-o", str(path), target])
        binaries[name] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": sha256_path(path),
            "target": target,
        }
    return binaries


def input_instance_paths(instance: dict[str, Any]) -> dict[str, Path]:
    model = REPO_ROOT / instance["model_path"]
    root = model.parent
    return {
        "model": model,
        "validation": root / "configuration_validation.csv",
        "audit": root / "locked_audit_test.csv",
        "manifest": root / "split_manifest.json",
    }


def validate_candidate_security(candidate: dict[str, Any]) -> None:
    security = candidate["security"]
    if security["envelope_id"] != \
            "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError(
            "INTEGRITY_BLOCK: candidate security policy changed"
        )
    for field in (
        "admission_status",
        "ciphertext_q_admission",
        "evaluation_key_qp_admission",
        "final_admission",
    ):
        if security[field] != "PASS":
            raise ValueError(
                "INTEGRITY_BLOCK: inadmissible candidate "
                f"{candidate['id']} {field}={security[field]}"
            )
    if security["headroom_bits"] < 0:
        raise ValueError(
            "INTEGRITY_BLOCK: negative security headroom"
        )


def validate_plan(
    plan: dict[str, Any],
    seed: int,
    dataset: str,
) -> None:
    if plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError("INTEGRITY_BLOCK: frozen policy digest changed")
    contract = plan["contract"]
    if contract["workload_id"] != \
            f"split_seed_{seed}/{dataset}/mlp_square_linear_score" or \
            contract["model_type"] != "mlp_square_linear_score" or \
            contract["decision"]["margin_floor"] != 0.001 or \
            contract["decision"]["safety_factor"] != 0.5 or \
            contract["deployment"]["max_encrypted_trials"] != 4 or \
            contract["deployment"]["validation_key_repeats"] != 3:
        raise ValueError("INTEGRITY_BLOCK: synthesis contract changed")
    candidates = plan["initial_candidates"]
    if len(candidates) != 1:
        raise ValueError(
            "INTEGRITY_BLOCK: expected one direct initial literal"
        )
    validate_candidate_security(candidates[0])


def preflight(
    run_root: Path,
    input_root: Path,
    python_with_science_deps: str,
) -> dict[str, Any]:
    if run_root.exists():
        raise ValueError(
            f"refusing to overwrite existing run root: {run_root}"
        )
    head, origin = require_clean_provenance()
    summary = load_input_summary(input_root)
    run_root.mkdir(parents=True)
    verifier_log = run_root / "preflight/input_replay.log"
    run_checked(
        [
            python_with_science_deps,
            "scripts/verify_independent_training_seed_extension.py",
            "--input-root",
            str(input_root),
        ],
        stdout_path=verifier_log,
    )
    binaries = build_binaries(run_root)
    source_files, source_digest = execution_source_closure()
    plans = []
    for instance in summary["instances"]:
        seed = int(instance["training_seed"])
        dataset = instance["dataset_id"]
        paths = input_instance_paths(instance)
        tag = f"seed{seed}_{dataset}_mlp_square_linear_score"
        prepared = run_root / "preflight/prepared" / f"{tag}.csv"
        materialization = (
            run_root / "preflight/materialization" / f"{tag}.json"
        )
        plan_path = run_root / "preflight/plans" / f"{tag}.json"
        prepared.parent.mkdir(parents=True, exist_ok=True)
        materialization.parent.mkdir(parents=True, exist_ok=True)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        materialize_command = [
            str(run_root / "bin/flipguard-materialize"),
            "--model",
            str(paths["model"].relative_to(REPO_ROOT)),
            "--data",
            str(paths["validation"].relative_to(REPO_ROOT)),
            "--data-space",
            "raw",
            "--out",
            str(prepared.relative_to(REPO_ROOT)),
            "--manifest-out",
            str(materialization.relative_to(REPO_ROOT)),
        ]
        run_checked(materialize_command)
        synthesize_command = [
            str(run_root / "bin/flipguard-synthesize"),
            "--model",
            str(paths["model"].relative_to(REPO_ROOT)),
            "--validation",
            str(prepared.relative_to(REPO_ROOT)),
            "--split-id",
            f"split_seed_{seed}",
            "--margin-floor",
            "0.001",
            "--safety-factor",
            "0.5",
            "--key-repeats",
            "3",
            "--max-encrypted-trials",
            "4",
            "--out",
            str(plan_path.relative_to(REPO_ROOT)),
        ]
        run_checked(synthesize_command)
        plan = json.loads(plan_path.read_text(encoding="ascii"))
        validate_plan(plan, seed, dataset)
        plans.append(
            {
                "training_seed": seed,
                "dataset_id": dataset,
                "tag": tag,
                "model_sha256": sha256_path(paths["model"]),
                "validation_sha256": sha256_path(paths["validation"]),
                "audit_sha256": sha256_path(paths["audit"]),
                "split_manifest_sha256": sha256_path(paths["manifest"]),
                "prepared_validation_sha256": sha256_path(prepared),
                "materialization_sha256": sha256_path(materialization),
                "plan_path": str(plan_path.relative_to(REPO_ROOT)),
                "plan_sha256": sha256_path(plan_path),
                "initial_candidate":
                    plan["initial_candidates"][0],
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "PREFLIGHT_PASS",
        "source_commit": head,
        "origin_commit": origin,
        "working_tree_clean": True,
        "execution_critical_source_files": source_files,
        "execution_critical_source_digest": source_digest,
        "orchestrator": {
            "path": "scripts/run_independent_training_seed_extension.py",
            "sha256": sha256_path(
                REPO_ROOT
                / "scripts/run_independent_training_seed_extension.py"
            ),
        },
        "input_builder_commit": (
            "eb6e53fc6638a0e84e07261112967a22d9bd7615"
        ),
        "input_freeze_commit": (
            "d87ea9e5d1c1e865713b5ff16fddca03404dfc5d"
        ),
        "input_summary_sha256": sha256_path(
            input_root / "summary.json"
        ),
        "input_policy_digest": INPUT_POLICY_DIGEST,
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "protocol": {
            "training_seeds": list(EXPECTED_SEEDS),
            "datasets": list(EXPECTED_DATASETS),
            "model_id": "mlp_square_linear_score",
            "alpha": 0.5,
            "margin_floor": 0.001,
            "maximum_encrypted_trials": 4,
            "selection_key_repeats": 3,
            "audit_key_repeats": 3,
            "first_safe": True,
            "no_retuning": True,
            "catalog_repeated": False,
        },
        "binaries": binaries,
        "versions": {
            "go": run_checked(["go", "version"]).stdout.strip(),
            "python": sys.version.split()[0],
        },
        "host": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "preflight_started_at": now(),
        "plans": plans,
        "paper_claim_allowed": False,
    }
    write_atomic(run_root / "run_manifest.json", manifest)
    (run_root / "run_manifest.sha256").write_text(
        sha256_path(run_root / "run_manifest.json") + "\n",
        encoding="ascii",
    )
    state = {
        "schema_version": SCHEMA_VERSION,
        "run_manifest_sha256": sha256_path(
            run_root / "run_manifest.json"
        ),
        "stage": "PREFLIGHT_PASS",
        "workloads": {
            plan["tag"]: {
                "training_seed": plan["training_seed"],
                "dataset_id": plan["dataset_id"],
                "selection": {"status": "PENDING"},
                "locked_audit": {"status": "PENDING"},
            }
            for plan in plans
        },
        "recoveries": [],
        "paper_claim_allowed": False,
    }
    write_atomic(run_root / "state.json", state)
    return manifest


def verify_resume_gate(
    run_root: Path,
    input_root: Path,
    python_with_science_deps: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    head, origin = require_clean_provenance()
    manifest_path = run_root / "run_manifest.json"
    state_path = run_root / "state.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    state = json.loads(state_path.read_text(encoding="ascii"))
    if manifest["source_commit"] != head or \
            manifest["origin_commit"] != origin or \
            manifest["status"] != "PREFLIGHT_PASS" or \
            manifest["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            manifest["security_policy_digest"] != \
                SECURITY_POLICY_DIGEST or \
            manifest["input_policy_digest"] != INPUT_POLICY_DIGEST or \
            state["run_manifest_sha256"] != sha256_path(manifest_path):
        raise ValueError("INTEGRITY_BLOCK: resume provenance changed")
    if manifest["execution_critical_source_digest"] != \
            execution_source_closure()[1]:
        raise ValueError(
            "INTEGRITY_BLOCK: execution source closure changed"
        )
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError("INTEGRITY_BLOCK: execution binary changed")
    run_checked(
        [
            python_with_science_deps,
            "scripts/verify_independent_training_seed_extension.py",
            "--input-root",
            str(input_root),
        ],
        stdout_path=run_root / "preflight/resume_input_replay.log",
    )
    for plan_record in manifest["plans"]:
        plan_path = REPO_ROOT / plan_record["plan_path"]
        if sha256_path(plan_path) != plan_record["plan_sha256"]:
            raise ValueError("INTEGRITY_BLOCK: static plan changed")
        plan = json.loads(plan_path.read_text(encoding="ascii"))
        validate_plan(
            plan,
            int(plan_record["training_seed"]),
            plan_record["dataset_id"],
        )
    return manifest, state


def execute_with_retries(
    command: Sequence[str],
    log_base: Path,
) -> tuple[bool, int, str]:
    last_error = ""
    for attempt in range(1, 4):
        log_path = log_base.with_name(
            f"{log_base.stem}.attempt{attempt}{log_base.suffix}"
        )
        write_command(
            log_path.with_suffix(".command.txt"),
            command,
        )
        try:
            run_checked(command, stdout_path=log_path)
            return True, attempt, sha256_path(log_path)
        except subprocess.CalledProcessError as exc:
            last_error = (
                f"exit={exc.returncode} log={log_path} "
                f"log_sha256={sha256_path(log_path)}"
            )
    return False, 3, last_error


def validate_selection_result(result: dict[str, Any]) -> str:
    plan = result["plan"]
    if plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError(
            "INTEGRITY_BLOCK: selection policy digest changed"
        )
    outcome = result["outcome"]
    if result["trials_used"] > 4 or len(result["trials"]) > 4:
        raise ValueError(
            "INTEGRITY_BLOCK: selection trial budget exceeded"
        )
    for trial in result["trials"]:
        validate_candidate_security(trial["candidate"])
    if outcome == "SELECTED":
        selected = result["selected"]
        validate_candidate_security(selected)
        if selected != result["trials"][-1]["candidate"] or \
                result["trials"][-1]["status"] != "SAFE":
            raise ValueError(
                "INTEGRITY_BLOCK: first-SAFE identity changed"
            )
    elif outcome != "NO_SAFE":
        raise ValueError(
            f"INTEGRITY_BLOCK: unknown selection outcome {outcome}"
        )
    return outcome


def validate_audit_result(
    audit: dict[str, Any],
    selection: dict[str, Any],
) -> str:
    if audit["retuning_performed"] or \
            audit["selected_candidate"] != selection["selected"] or \
            audit["selection_contract_digest"] != \
                selection["plan"]["contract_digest"]:
        raise ValueError(
            "INTEGRITY_BLOCK: locked-audit identity changed"
        )
    validate_candidate_security(audit["selected_candidate"])
    outcome = audit["outcome"]
    if outcome not in ("LOCKED_AUDIT_PASS", "LOCKED_AUDIT_FAIL"):
        raise ValueError(
            f"INTEGRITY_BLOCK: unknown audit outcome {outcome}"
        )
    return outcome


def execute_extension(
    run_root: Path,
    input_root: Path,
    manifest: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    input_summary = load_input_summary(input_root)
    instances = {
        (
            int(instance["training_seed"]),
            instance["dataset_id"],
        ): instance
        for instance in input_summary["instances"]
    }
    autotune = str(REPO_ROOT / manifest["binaries"]["autotune"]["path"])
    audit_binary = str(REPO_ROOT / manifest["binaries"]["audit"]["path"])
    for plan_record in manifest["plans"]:
        seed = int(plan_record["training_seed"])
        dataset = plan_record["dataset_id"]
        tag = plan_record["tag"]
        workload = state["workloads"][tag]
        instance = instances[(seed, dataset)]
        paths = input_instance_paths(instance)
        selection_path = run_root / "selection/results" / f"{tag}.json"
        prepared_validation = (
            run_root / "selection/prepared" / f"{tag}.csv"
        )
        if workload["selection"]["status"] == "PENDING":
            selection_path.parent.mkdir(parents=True, exist_ok=True)
            prepared_validation.parent.mkdir(parents=True, exist_ok=True)
            command = [
                autotune,
                "--model",
                str(paths["model"].relative_to(REPO_ROOT)),
                "--data",
                str(paths["validation"].relative_to(REPO_ROOT)),
                "--data-space",
                "raw",
                "--prepared-validation-out",
                str(prepared_validation.relative_to(REPO_ROOT)),
                "--split-id",
                f"split_seed_{seed}",
                "--margin-floor",
                "0.001",
                "--safety-factor",
                "0.5",
                "--key-repeats",
                "3",
                "--max-encrypted-trials",
                "4",
                "--out",
                str(selection_path.relative_to(REPO_ROOT)),
            ]
            success, attempts, detail = execute_with_retries(
                command,
                run_root / "selection/logs" / f"{tag}.log",
            )
            if not success:
                workload["selection"] = {
                    "status": "RECOVERABLE_IMPLEMENTATION_FAILURE",
                    "attempts": attempts,
                    "detail": detail,
                }
                workload["locked_audit"] = {
                    "status": "SKIPPED_SELECTION_EXECUTION_FAILURE"
                }
                write_atomic(run_root / "state.json", state)
                continue
            result = json.loads(
                selection_path.read_text(encoding="ascii")
            )
            outcome = validate_selection_result(result)
            workload["selection"] = {
                "status": (
                    "PASS"
                    if outcome == "SELECTED"
                    else "PARTIAL_SCIENTIFIC_RESULT"
                ),
                "outcome": outcome,
                "attempts": attempts,
                "result_path": str(
                    selection_path.relative_to(REPO_ROOT)
                ),
                "result_sha256": sha256_path(selection_path),
                "prepared_validation_sha256":
                    sha256_path(prepared_validation),
                "trials": result["trials_used"],
                "key_runs": result["encrypted_key_runs"],
                "encrypted_sample_evaluations":
                    result["encrypted_sample_evaluations"],
            }
            if outcome == "NO_SAFE":
                workload["locked_audit"] = {
                    "status": "SKIPPED_NO_SAFE"
                }
            write_atomic(run_root / "state.json", state)

        if workload["selection"].get("outcome") != "SELECTED" or \
                workload["locked_audit"]["status"] != "PENDING":
            continue
        selection = json.loads(
            selection_path.read_text(encoding="ascii")
        )
        audit_path = run_root / "audit/results" / f"{tag}.json"
        prepared_audit = run_root / "audit/prepared" / f"{tag}.csv"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        prepared_audit.parent.mkdir(parents=True, exist_ok=True)
        command = [
            audit_binary,
            "--selection",
            str(selection_path.relative_to(REPO_ROOT)),
            "--audit",
            str(paths["audit"].relative_to(REPO_ROOT)),
            "--prepared-audit-out",
            str(prepared_audit.relative_to(REPO_ROOT)),
            "--audit-data-space",
            "raw",
            "--manifest",
            str(paths["manifest"].relative_to(REPO_ROOT)),
            "--key-repeats",
            "3",
            "--out",
            str(audit_path.relative_to(REPO_ROOT)),
        ]
        success, attempts, detail = execute_with_retries(
            command,
            run_root / "audit/logs" / f"{tag}.log",
        )
        if not success:
            workload["locked_audit"] = {
                "status": "RECOVERABLE_IMPLEMENTATION_FAILURE",
                "attempts": attempts,
                "detail": detail,
            }
            write_atomic(run_root / "state.json", state)
            continue
        audit = json.loads(audit_path.read_text(encoding="ascii"))
        outcome = validate_audit_result(audit, selection)
        workload["locked_audit"] = {
            "status": (
                "PASS"
                if outcome == "LOCKED_AUDIT_PASS"
                else "PARTIAL_SCIENTIFIC_RESULT"
            ),
            "outcome": outcome,
            "attempts": attempts,
            "result_path": str(audit_path.relative_to(REPO_ROOT)),
            "result_sha256": sha256_path(audit_path),
            "prepared_audit_sha256": sha256_path(prepared_audit),
            "retuning": 0,
            "key_runs": audit["audit_trial"]["key_repeats_completed"],
            "encrypted_sample_evaluations":
                audit["audit_trial"]["encrypted_sample_evaluations"],
            "flips": audit["audit_trial"]["decision_flips"],
            "violations": audit["audit_trial"]["error_violations"],
        }
        write_atomic(run_root / "state.json", state)

    return summarize_state(run_root, state)


def summarize_state(
    run_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for tag, workload in sorted(state["workloads"].items()):
        selection = workload["selection"]
        audit = workload["locked_audit"]
        rows.append(
            {
                "tag": tag,
                "training_seed": workload["training_seed"],
                "dataset_id": workload["dataset_id"],
                "selection_status": selection["status"],
                "selection_outcome": selection.get("outcome", ""),
                "trials": selection.get("trials", 0),
                "selection_key_runs": selection.get("key_runs", 0),
                "selection_encrypted_sample_evaluations":
                    selection.get("encrypted_sample_evaluations", 0),
                "audit_status": audit["status"],
                "audit_outcome": audit.get("outcome", ""),
                "audit_key_runs": audit.get("key_runs", 0),
                "audit_encrypted_sample_evaluations":
                    audit.get("encrypted_sample_evaluations", 0),
                "audit_flips": audit.get("flips", 0),
                "audit_violations": audit.get("violations", 0),
                "retuning": audit.get("retuning", 0),
            }
        )
    incomplete = [
        row
        for row in rows
        if row["selection_status"] in (
            "PENDING",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
        ) or row["audit_status"] in (
            "PENDING",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
        )
    ]
    scientific_partial = [
        row
        for row in rows
        if row["selection_status"] == "PARTIAL_SCIENTIFIC_RESULT"
        or row["audit_status"] == "PARTIAL_SCIENTIFIC_RESULT"
    ]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "RECOVERABLE_IMPLEMENTATION_FAILURE"
            if incomplete
            else (
                "PARTIAL_SCIENTIFIC_RESULT"
                if scientific_partial
                else "PASS"
            )
        ),
        "instances": len(rows),
        "selection_selected": sum(
            row["selection_outcome"] == "SELECTED" for row in rows
        ),
        "selection_no_safe": sum(
            row["selection_outcome"] == "NO_SAFE" for row in rows
        ),
        "direct_trials": sum(row["trials"] for row in rows),
        "selection_key_runs": sum(
            row["selection_key_runs"] for row in rows
        ),
        "selection_encrypted_sample_evaluations": sum(
            row["selection_encrypted_sample_evaluations"]
            for row in rows
        ),
        "audit_pass": sum(
            row["audit_outcome"] == "LOCKED_AUDIT_PASS"
            for row in rows
        ),
        "audit_rejected": sum(
            row["audit_outcome"] == "LOCKED_AUDIT_FAIL"
            for row in rows
        ),
        "audit_flips": sum(row["audit_flips"] for row in rows),
        "audit_violations": sum(
            row["audit_violations"] for row in rows
        ),
        "retuning": sum(row["retuning"] for row in rows),
        "incomplete_instances": len(incomplete),
        "workloads": rows,
        "paper_claim_allowed": False,
    }
    summary["status"] = str(summary["status"])
    write_atomic(run_root / "summary.json", summary)
    csv_path = run_root / "summary.csv"
    with csv_path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    state["stage"] = summary["status"]
    write_atomic(run_root / "state.json", state)
    return summary


def main() -> None:
    args = parse_args()
    input_root = (
        args.input_root
        if args.input_root.is_absolute()
        else REPO_ROOT / args.input_root
    )
    head = git_text("rev-parse", "HEAD")
    default_run_root = RESULT_BASE / f"run_{head[:7]}"
    run_root = args.run_root or default_run_root
    if not run_root.is_absolute():
        run_root = REPO_ROOT / run_root
    if args.preflight_only:
        manifest = preflight(
            run_root,
            input_root,
            args.python_with_science_deps,
        )
        print(
            "independent_training_seed_preflight=PASS "
            f"commit={manifest['source_commit']} "
            f"source_digest={manifest['execution_critical_source_digest']} "
            f"run_manifest={sha256_path(run_root / 'run_manifest.json')}"
        )
        return
    manifest, state = verify_resume_gate(
        run_root,
        input_root,
        args.python_with_science_deps,
    )
    summary = execute_extension(
        run_root,
        input_root,
        manifest,
        state,
    )
    print(
        "independent_training_seed_extension="
        f"{summary['status']} "
        f"selected={summary['selection_selected']}/9 "
        f"audit_pass={summary['audit_pass']}/9 "
        f"no_safe={summary['selection_no_safe']} "
        f"run_root={run_root.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
