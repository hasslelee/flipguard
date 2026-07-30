#!/usr/bin/env python3
"""Run the predeclared schedule-bound Microsoft EVA development control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/eva_schedule_bound_adapter_v1/contract.json"
)
DEFAULT_OUTPUT_PARENT = Path(
    "results/thesis_grade_protocol/eva_schedule_bound_adapter_v1"
)
RUN_SCHEMA = "flipguard_eva_schedule_bound_adapter_run_v1"

VERIFIER_PATH = REPO_ROOT / (
    "scripts/verify_eva_schedule_bound_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_eva_schedule_bound_for_runner",
    VERIFIER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def save_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def command(
    arguments: list[str],
    *,
    check: bool = True,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if log_path is None:
        return subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="ascii") as handle:
        return subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            check=check,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )


def git(*arguments: str) -> str:
    return command(["git", *arguments]).stdout.strip()


def require_clean_origin() -> tuple[str, str, str]:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "INTEGRITY_BLOCK: EVA schedule replay requires a clean tree:\n"
            + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if not branch:
        raise ValueError("INTEGRITY_BLOCK: detached HEAD")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(
            f"INTEGRITY_BLOCK: HEAD {head} != origin/{branch} {origin}"
        )
    return head, origin, branch


def execution_source_closure() -> tuple[dict[str, str], str]:
    packages = [
        "./cmd/flipguard-certify-candidate",
        "./cmd/flipguard-audit-candidate",
    ]
    listed = command([
        "go",
        "list",
        "-deps",
        "-f",
        "{{if not .Standard}}{{.Dir}}{{end}}",
        *packages,
    ]).stdout
    directories: set[Path] = set()
    for line in listed.splitlines():
        if not line:
            continue
        path = Path(line).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        directories.add(path)
    relative_paths = {"go.mod", "go.sum"}
    for directory in directories:
        for path in directory.glob("*.go"):
            relative_paths.add(path.relative_to(REPO_ROOT).as_posix())
    closure = {
        relative: sha256_path(REPO_ROOT / relative)
        for relative in sorted(relative_paths)
    }
    return closure, canonical_digest(closure)


def host_metadata() -> dict[str, Any]:
    cpu_model = ""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(
            encoding="ascii",
            errors="replace",
        ).splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    memory_kib = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        first = meminfo.read_text(encoding="ascii").splitlines()[0]
        if first.startswith("MemTotal:"):
            memory_kib = int(first.split()[1])
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_model": cpu_model,
        "memory_kib": memory_kib,
        "python_version": platform.python_version(),
        "go_version": command(["go", "version"]).stdout.strip(),
    }


def build_binary(package: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command([
        "go",
        "build",
        "-buildvcs=false",
        "-trimpath",
        "-o",
        str(output),
        package,
    ])


def create_smoke_validation(source: Path, output: Path) -> None:
    with source.open("r", encoding="ascii", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise ValueError("validation source has no row for smoke diagnostic")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows[:2])


def default_output_root(head: str) -> Path:
    return DEFAULT_OUTPUT_PARENT / f"run_{head[:8]}"


def initialize(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
    branch: str,
) -> None:
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite EVA schedule replay: {output_root}"
        )
    VERIFIER.verify(contract_path)
    contract = load_json(contract_path)
    for directory in ("bin", "logs", "snapshots"):
        (output_root / directory).mkdir(parents=True, exist_ok=True)
    snapshot_sources = {
        "contract.json": contract_path,
        "execution_schedule.json": absolute(Path(
            contract["schedule"]["contract_path"]
        )),
        "candidate_request.json": absolute(Path(
            contract["schedule"]["candidate_request_path"]
        )),
    }
    snapshot_digests = {}
    for name, source in snapshot_sources.items():
        destination = output_root / "snapshots" / name
        shutil.copyfile(source, destination)
        snapshot_digests[name] = sha256_path(destination)

    validation = absolute(Path(contract["workload"]["validation_path"]))
    smoke = output_root / "smoke_validation.csv"
    create_smoke_validation(validation, smoke)

    certify = output_root / "bin/flipguard-certify-candidate"
    audit = output_root / "bin/flipguard-audit-candidate"
    build_binary("./cmd/flipguard-certify-candidate", certify)
    build_binary("./cmd/flipguard-audit-candidate", audit)
    closure, closure_digest = execution_source_closure()
    manifest = {
        "schema_version": RUN_SCHEMA,
        "status": "PREFLIGHT_PASS",
        "source_commit": head,
        "origin_commit": origin,
        "branch": branch,
        "working_tree_clean": True,
        "contract_path": contract_path.as_posix(),
        "contract_sha256": sha256_path(contract_path),
        "snapshot_digests": snapshot_digests,
        "smoke_validation": {
            "path": smoke.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_path(smoke),
            "rows": 1,
            "role": "BACKEND_DIAGNOSTIC_ONLY",
        },
        "execution_critical_source_files": closure,
        "execution_critical_source_digest": closure_digest,
        "binaries": {
            "certify_candidate": {
                "path": certify.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_path(certify),
            },
            "audit_candidate": {
                "path": audit.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_path(audit),
            },
        },
        "security_policy_digest":
            contract["policy"]["security_policy_digest"],
        "direct_policy_digest":
            contract["policy"]["direct_policy_digest"],
        "schedule_contract_digest":
            contract["schedule"]["contract_sha256"],
        "formal_candidate_trials": 1,
        "diagnostic_candidate_trials": 1,
        "synthesis_calls": 0,
        "repair_calls": 0,
        "retuning": 0,
        "host": host_metadata(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "paper_claim_allowed": False,
    }
    save_atomic(output_root / "run_manifest.json", manifest)
    save_atomic(output_root / "state.json", {
        "schema_version": RUN_SCHEMA,
        "stage": "PREFLIGHT_PASS",
        "smoke": "PENDING",
        "selection": "PENDING",
        "audit": "PENDING",
        "formal_candidate_trials_started": 0,
        "diagnostic_candidate_trials_started": 0,
        "audit_trials_started": 0,
        "paper_claim_allowed": False,
    })
    save_atomic(output_root / "stage_ledger.json", [])


def verify_preflight(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
) -> dict[str, Any]:
    VERIFIER.verify(contract_path)
    contract = load_json(contract_path)
    manifest = load_json(output_root / "run_manifest.json")
    state = load_json(output_root / "state.json")
    closure, closure_digest = execution_source_closure()
    if (
        manifest["source_commit"] != head
        or manifest["origin_commit"] != origin
        or manifest["contract_sha256"] != sha256_path(contract_path)
        or manifest["execution_critical_source_files"] != closure
        or manifest["execution_critical_source_digest"] != closure_digest
        or manifest["security_policy_digest"] !=
            contract["policy"]["security_policy_digest"]
        or manifest["direct_policy_digest"] !=
            contract["policy"]["direct_policy_digest"]
        or manifest["schedule_contract_digest"] !=
            contract["schedule"]["contract_sha256"]
    ):
        raise ValueError(
            "INTEGRITY_BLOCK: EVA schedule preflight provenance changed"
        )
    for name, digest in manifest["snapshot_digests"].items():
        if sha256_path(output_root / "snapshots" / name) != digest:
            raise ValueError(
                f"INTEGRITY_BLOCK: EVA schedule snapshot changed: {name}"
            )
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError(
                "INTEGRITY_BLOCK: EVA schedule binary changed"
            )
    smoke = manifest["smoke_validation"]
    if sha256_path(REPO_ROOT / smoke["path"]) != smoke["sha256"]:
        raise ValueError(
            "INTEGRITY_BLOCK: EVA smoke validation changed"
        )
    return state


def append_ledger(
    output_root: Path,
    stage: str,
    status: str,
    reason: str,
    command_line: list[str] | None = None,
    artifact: Path | None = None,
) -> None:
    path = output_root / "stage_ledger.json"
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, list):
        raise ValueError("stage ledger is not a list")
    value.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": status,
        "reason": reason,
        "command": command_line,
        "artifact": (
            artifact.relative_to(output_root).as_posix()
            if artifact is not None and artifact.is_file()
            else None
        ),
        "artifact_sha256": (
            sha256_path(artifact)
            if artifact is not None and artifact.is_file()
            else None
        ),
    })
    save_atomic(path, value)


def certify_command(
    contract: dict[str, Any],
    output_root: Path,
    validation_path: Path,
    output_path: Path,
    key_repeats: int,
) -> list[str]:
    binary = output_root / "bin/flipguard-certify-candidate"
    return [
        str(binary),
        "--model",
        contract["workload"]["model_path"],
        "--validation",
        validation_path.as_posix(),
        "--split-id",
        contract["workload"]["split_id"],
        "--candidate",
        contract["schedule"]["candidate_request_path"],
        "--margin-floor",
        str(contract["policy"]["margin_floor"]),
        "--safety-factor",
        str(contract["policy"]["safety_factor"]),
        "--key-repeats",
        str(key_repeats),
        "--out",
        output_path.as_posix(),
    ]


def execute_smoke(
    contract: dict[str, Any],
    output_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    if state["smoke"] == "PASS":
        return load_json(output_root / "smoke_selection.json")
    if state["smoke"] != "PENDING":
        raise ValueError(
            f"EVA smoke is not resumable from state {state['smoke']}"
        )
    state["diagnostic_candidate_trials_started"] = 1
    state["stage"] = "SMOKE_RUNNING"
    save_atomic(output_root / "state.json", state)
    output = output_root / "smoke_selection.json"
    arguments = certify_command(
        contract,
        output_root,
        output_root / "smoke_validation.csv",
        output,
        1,
    )
    completed = command(
        arguments,
        check=False,
        log_path=output_root / "logs/smoke.log",
    )
    if completed.returncode != 0 or not output.is_file():
        state["smoke"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["stage"] = "SMOKE_FAILED"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "smoke",
            state["smoke"],
            f"command exit={completed.returncode}",
            arguments,
        )
        raise RuntimeError(
            "RECOVERABLE_IMPLEMENTATION_FAILURE: EVA schedule smoke failed"
        )
    result = load_json(output)
    if result["trial"]["status"] != "SAFE":
        state["smoke"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["stage"] = "SMOKE_FAILED"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "smoke",
            state["smoke"],
            f"diagnostic returned {result['trial']['status']}",
            arguments,
            output,
        )
        raise RuntimeError(
            "RECOVERABLE_IMPLEMENTATION_FAILURE: "
            f"EVA schedule smoke returned {result['trial']['status']}"
        )
    state["smoke"] = "PASS"
    state["stage"] = "SMOKE_PASS"
    save_atomic(output_root / "state.json", state)
    append_ledger(
        output_root,
        "smoke",
        "PASS",
        "one-row backend diagnostic certified SAFE",
        arguments,
        output,
    )
    return result


def execute_selection(
    contract: dict[str, Any],
    output_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    if state["selection"] in ("SAFE", "REJECTED", "FAILED"):
        return load_json(output_root / "selection.json")
    if state["selection"] != "PENDING" or state["smoke"] != "PASS":
        raise ValueError("EVA validation is not resumable")
    state["formal_candidate_trials_started"] = 1
    state["stage"] = "SELECTION_RUNNING"
    save_atomic(output_root / "state.json", state)
    output = output_root / "selection.json"
    arguments = certify_command(
        contract,
        output_root,
        Path(contract["workload"]["validation_path"]),
        output,
        contract["policy"]["validation_key_repeats"],
    )
    completed = command(
        arguments,
        check=False,
        log_path=output_root / "logs/selection.log",
    )
    if completed.returncode != 0 or not output.is_file():
        state["selection"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["stage"] = "SELECTION_FAILED"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "selection",
            state["selection"],
            f"command exit={completed.returncode}",
            arguments,
        )
        raise RuntimeError(
            "RECOVERABLE_IMPLEMENTATION_FAILURE: "
            "EVA schedule validation command failed"
        )
    result = load_json(output)
    status = result["trial"]["status"]
    if status not in ("SAFE", "REJECTED", "FAILED"):
        raise ValueError(f"unexpected EVA validation status {status}")
    state["selection"] = status
    state["stage"] = "SELECTION_COMPLETE"
    save_atomic(output_root / "state.json", state)
    append_ledger(
        output_root,
        "selection",
        "PASS" if status == "SAFE" else "PARTIAL_SCIENTIFIC_RESULT",
        f"one-literal validation returned {status}",
        arguments,
        output,
    )
    return result


def execute_audit(
    contract: dict[str, Any],
    output_root: Path,
    state: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any] | None:
    if selection["trial"]["status"] != "SAFE":
        state["audit"] = "NOT_RUN_VALIDATION_NOT_SAFE"
        state["stage"] = "COMPLETE"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "locked_audit",
            "NOT_EVALUATED",
            "validation did not certify the candidate SAFE",
        )
        return None
    if state["audit"] in ("PASS", "REJECTED", "FAILED"):
        return load_json(output_root / "locked_audit.json")
    if state["audit"] != "PENDING":
        raise ValueError("EVA locked audit is not resumable")
    state["audit_trials_started"] = 1
    state["stage"] = "AUDIT_RUNNING"
    save_atomic(output_root / "state.json", state)
    output = output_root / "locked_audit.json"
    binary = output_root / "bin/flipguard-audit-candidate"
    arguments = [
        str(binary),
        "--selection",
        (output_root / "selection.json").as_posix(),
        "--audit",
        contract["workload"]["audit_path"],
        "--manifest",
        contract["workload"]["split_manifest_path"],
        "--key-repeats",
        str(contract["policy"]["audit_key_repeats"]),
        "--out",
        output.as_posix(),
    ]
    completed = command(
        arguments,
        check=False,
        log_path=output_root / "logs/locked_audit.log",
    )
    if completed.returncode != 0 or not output.is_file():
        state["audit"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["stage"] = "AUDIT_FAILED"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "locked_audit",
            state["audit"],
            f"command exit={completed.returncode}",
            arguments,
        )
        raise RuntimeError(
            "RECOVERABLE_IMPLEMENTATION_FAILURE: "
            "EVA schedule locked audit command failed"
        )
    result = load_json(output)
    status = result["audit_trial"]["status"]
    state["audit"] = (
        "PASS" if result["outcome"] == "LOCKED_AUDIT_PASS" else status
    )
    state["stage"] = "COMPLETE"
    save_atomic(output_root / "state.json", state)
    append_ledger(
        output_root,
        "locked_audit",
        (
            "PASS"
            if result["outcome"] == "LOCKED_AUDIT_PASS"
            else "PARTIAL_SCIENTIFIC_RESULT"
        ),
        f"byte-identical schedule replay returned {status}",
        arguments,
        output,
    )
    return result


def build_summary(
    smoke: dict[str, Any],
    selection: dict[str, Any],
    audit: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = selection["trial"]["status"] == "SAFE"
    audit_pass = (
        audit is not None
        and audit["outcome"] == "LOCKED_AUDIT_PASS"
    )
    return {
        "schema_version": RUN_SCHEMA,
        "status": (
            "PASS"
            if selected and audit_pass
            else "PARTIAL_SCIENTIFIC_RESULT"
        ),
        "classification": "SOURCE_REPLAYED_PUBLIC_COMPILER_SCHEDULE",
        "evaluation_role": "seed0_development_interoperability_control",
        "diagnostic_smoke": {
            "status": smoke["trial"]["status"],
            "candidate_trials": smoke["trials_used"],
            "key_runs": smoke["encrypted_key_runs"],
            "rows_per_key": smoke["trial"]["v_cert"],
        },
        "selection": {
            "outcome": selection["outcome"],
            "status": selection["trial"]["status"],
            "candidate_trials": selection["trials_used"],
            "key_runs": selection["encrypted_key_runs"],
            "encrypted_sample_evaluations":
                selection["trial"]["encrypted_sample_evaluations"],
            "flips": selection["trial"]["decision_flips"],
            "violations": selection["trial"]["error_violations"],
            "max_error": selection["trial"]["max_observed_error"],
            "max_budget_usage":
                selection["trial"]["max_error_budget_usage"],
        },
        "locked_audit": {
            "outcome": None if audit is None else audit["outcome"],
            "status": (
                None if audit is None else audit["audit_trial"]["status"]
            ),
            "key_runs": (
                0
                if audit is None
                else audit["audit_trial"]["key_repeats_completed"]
            ),
            "encrypted_sample_evaluations": (
                0
                if audit is None
                else audit["audit_trial"][
                    "encrypted_sample_evaluations"
                ]
            ),
            "flips": (
                None
                if audit is None
                else audit["audit_trial"]["decision_flips"]
            ),
            "violations": (
                None
                if audit is None
                else audit["audit_trial"]["error_violations"]
            ),
            "retuning": (
                None if audit is None else audit["retuning_performed"]
            ),
        },
        "accounting": {
            "formal_candidate_trials": selection["trials_used"],
            "diagnostic_candidate_trials": smoke["trials_used"],
            "formal_key_runs": selection["encrypted_key_runs"],
            "diagnostic_key_runs": smoke["encrypted_key_runs"],
            "audit_key_runs": (
                0
                if audit is None
                else audit["audit_trial"]["key_repeats_completed"]
            ),
            "synthesis_calls": 0,
            "repair_calls": 0,
            "retuning": 0,
        },
        "claim_states": {
            "schedule_bound_external_candidate_import": "SUPPORTED",
            "encrypted_external_candidate_certification": (
                "SUPPORTED" if selected else "BLOCKED"
            ),
            "locked_audit_external_schedule_replay": (
                "SUPPORTED"
                if audit_pass
                else "NOT_EVALUATED"
                if audit is None
                else "PARTIALLY_SUPPORTED"
            ),
            "native_eva_seal_runtime_execution": "NOT_EVALUATED",
            "general_external_compiler_interoperability":
                "PARTIALLY_SUPPORTED",
        },
        "paper_claim_allowed": False,
        "block_reason": (
            "development-only single compiler/workload schedule replay; "
            "native EVA/SEAL runtime and broad external compiler population "
            "are not evaluated"
        ),
    }


def finalize(
    output_root: Path,
    smoke: dict[str, Any],
    selection: dict[str, Any],
    audit: dict[str, Any] | None,
) -> None:
    summary = build_summary(smoke, selection, audit)
    save_atomic(output_root / "summary.json", summary)
    manifest = load_json(output_root / "run_manifest.json")
    files = {}
    for path in sorted(
        item
        for item in output_root.rglob("*")
        if item.is_file()
        and "bin" not in item.relative_to(output_root).parts
        and item.name != "completion_manifest.json"
    ):
        files[path.relative_to(output_root).as_posix()] = sha256_path(path)
    save_atomic(output_root / "completion_manifest.json", {
        "schema_version": RUN_SCHEMA,
        "status": summary["status"],
        "source_commit": manifest["source_commit"],
        "execution_critical_source_digest":
            manifest["execution_critical_source_digest"],
        "schedule_contract_digest":
            manifest["schedule_contract_digest"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "paper_claim_allowed": False,
    })


def verify_completed(output_root: Path) -> dict[str, Any]:
    manifest = load_json(output_root / "run_manifest.json")
    completion = load_json(output_root / "completion_manifest.json")
    for relative, digest in completion["files"].items():
        if sha256_path(output_root / relative) != digest:
            raise ValueError(
                f"EVA schedule completed artifact changed: {relative}"
            )
    selection = load_json(output_root / "selection.json")
    smoke = load_json(output_root / "smoke_selection.json")
    audit = (
        load_json(output_root / "locked_audit.json")
        if (output_root / "locked_audit.json").is_file()
        else None
    )
    if load_json(output_root / "summary.json") != build_summary(
        smoke,
        selection,
        audit,
    ):
        raise ValueError("EVA schedule summary changed")
    if completion["source_commit"] != manifest["source_commit"]:
        raise ValueError("EVA schedule completion provenance changed")
    return {
        "status": completion["status"],
        "source_commit": completion["source_commit"],
        "completion_manifest_sha256":
            sha256_path(output_root / "completion_manifest.json"),
        "selection_status": selection["trial"]["status"],
        "audit_status": (
            None if audit is None else audit["audit_trial"]["status"]
        ),
        "paper_claim_allowed": False,
    }


def run() -> None:
    args = parse_args()
    contract_path = absolute(args.contract)
    head, origin, branch = require_clean_origin()
    output_root = (
        absolute(args.output_root)
        if args.output_root is not None
        else absolute(default_output_root(head))
    )
    if args.verify:
        print(json.dumps(
            verify_completed(output_root),
            indent=2,
            sort_keys=True,
        ))
        return
    if not output_root.exists():
        initialize(contract_path, output_root, head, origin, branch)
    elif not args.resume:
        raise FileExistsError(
            f"output exists; use --resume: {output_root}"
        )
    state = verify_preflight(
        contract_path,
        output_root,
        head,
        origin,
    )
    if args.preflight_only:
        print(json.dumps({
            "status": "PREFLIGHT_PASS",
            "output_root": output_root.relative_to(REPO_ROOT).as_posix(),
            "source_commit": head,
            "execution_critical_source_digest": load_json(
                output_root / "run_manifest.json"
            )["execution_critical_source_digest"],
        }, indent=2, sort_keys=True))
        return
    contract = load_json(contract_path)
    smoke = execute_smoke(contract, output_root, state)
    state = load_json(output_root / "state.json")
    selection = execute_selection(contract, output_root, state)
    state = load_json(output_root / "state.json")
    audit = execute_audit(
        contract,
        output_root,
        state,
        selection,
    )
    finalize(output_root, smoke, selection, audit)
    print(json.dumps(
        verify_completed(output_root),
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    run()
