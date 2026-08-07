#!/usr/bin/env python3
"""Deadline-bound serial master for the focused V8 external comparison."""

from __future__ import annotations

import datetime as dt
import json
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import traceback


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v8/status"
LOGS = ROOT / "external/v8/logs"
UTC = dt.timezone.utc
STAGES = (
    ("binding", "scripts/external_v8/verify_v7_binding_v8.py"),
    ("eva", "scripts/external_v8/run_eva_v8.sh"),
    ("heir", "scripts/external_v8/run_heir_v8.sh"),
    ("flipguard", "scripts/external_v8/run_flipguard_v8.sh"),
    ("corelab", "scripts/external_v8/run_corelab_v8.sh"),
)


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def timestamp(value: dt.datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")


def read_or_create_deadline() -> tuple[dt.datetime, dt.datetime]:
    start_path = STATUS / "autonomous_start_timestamp.txt"
    deadline_path = STATUS / "hard_pause_timestamp.txt"
    if start_path.exists() != deadline_path.exists():
        raise RuntimeError("INTEGRITY_BLOCK: partial V8 deadline state")
    if start_path.exists():
        start = dt.datetime.fromisoformat(start_path.read_text().strip())
        deadline = dt.datetime.fromisoformat(deadline_path.read_text().strip())
    else:
        start = now()
        deadline = start + dt.timedelta(hours=24)
        atomic_write(start_path, timestamp(start) + "\n")
        atomic_write(deadline_path, timestamp(deadline) + "\n")
        atomic_write(STATUS / "autonomous_start_timestamp_utc.txt", start.astimezone(UTC).isoformat(timespec="seconds") + "\n")
        atomic_write(STATUS / "hard_pause_timestamp_utc.txt", deadline.astimezone(UTC).isoformat(timespec="seconds") + "\n")
    if deadline - start != dt.timedelta(hours=24):
        raise RuntimeError("INTEGRITY_BLOCK: V8 deadline is not exactly 24 hours")
    return start, deadline


def resource_state() -> dict[str, object]:
    disk = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    meminfo = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith(("MemAvailable:", "SwapTotal:", "SwapFree:"))
    }
    free_gib = disk.free / 1024**3
    inode_free_pct = 100 * stat.f_favail / stat.f_files
    return {
        "timestamp": timestamp(),
        "disk_free_bytes": disk.free,
        "disk_free_gib": free_gib,
        "inode_free_pct": inode_free_pct,
        "memory_available_kib": meminfo["MemAvailable"],
        "swap_used_kib": meminfo["SwapTotal"] - meminfo["SwapFree"],
        "gate": "HARD_RESOURCE_STOP" if free_gib < 25 or inode_free_pct < 10 else "PASS",
    }


def command_output(command: list[str]) -> str:
    return subprocess.run(
        command, cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip()


def source_closure_digest() -> str:
    paths = command_output([
        "git", "ls-files", "cmd/flipguard-external-v8-common",
        "internal/ckksbackend/external_v8_bridge.go", "scripts/external_v8",
        "docs/evidence/focused_external_comparison_v8",
    ]).splitlines()
    digest = hashlib.sha256()
    for relative in sorted(path for path in paths if path and not path.endswith("SHA256SUMS")):
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256((ROOT / relative).read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def bind_run_manifest(start: dt.datetime, deadline: dt.datetime) -> None:
    branch = command_output(["git", "branch", "--show-current"])
    if branch != "experiments/focused-external-closure-v8":
        raise RuntimeError(f"INTEGRITY_BLOCK: unexpected V8 branch {branch}")
    status = command_output(["git", "status", "--short"])
    if status:
        raise RuntimeError(f"INTEGRITY_BLOCK: V8 execution source is dirty: {status}")
    head = command_output(["git", "rev-parse", "HEAD"])
    origin = command_output(["git", "rev-parse", f"origin/{branch}"])
    if head != origin:
        raise RuntimeError(f"INTEGRITY_BLOCK: V8 HEAD/origin mismatch: {head} != {origin}")
    manifest = {
        "schema_version": "flipguard_focused_external_v8_run_manifest_v1",
        "source_commit": head, "origin_commit": origin, "branch": branch,
        "working_tree_clean": True, "execution_critical_source_digest": source_closure_digest(),
        "autonomous_start_timestamp": timestamp(start), "hard_pause_timestamp": timestamp(deadline),
        "security_policy_id": "security_guidelines_cic2025_table5_2_ternary_128_v2",
        "security_policy_digest": "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055",
        "direct_policy_id": "flipguard_direct_synthesis_policy_v2",
        "direct_policy_digest": "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603",
        "threshold": 0.5, "margin_utilization_cap": 0.5, "margin_floor": 0.001,
        "validation_inputs": 500, "audit_inputs": 500, "latency_subset_inputs": 100,
        "fresh_key_contexts": 3, "latency_warmup_passes": 1, "latency_measurement_passes": 6,
        "retuning": 0, "no_concurrent_ckks_process": True,
    }
    path = ROOT / "external/v8/manifests/run_manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise RuntimeError("INTEGRITY_BLOCK: V8 run manifest changed on resume")
    else:
        atomic_json(path, manifest)


def main() -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    start, deadline = read_or_create_deadline()
    bind_run_manifest(start, deadline)
    stopped = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    completed = set()
    completed_path = STATUS / "completed_stages.jsonl"
    if completed_path.exists():
        completed = {json.loads(line)["stage"] for line in completed_path.read_text().splitlines() if line.strip()}

    for stage, command in STAGES:
        if stopped or stage in completed:
            continue
        remaining = (deadline - now()).total_seconds()
        if remaining <= 1800:
            break
        resources = resource_state()
        atomic_json(STATUS / "resource_state.json", resources)
        if resources["gate"] != "PASS":
            atomic_json(STATUS / "master_state.json", {"state": resources["gate"], "stage": stage, "timestamp": timestamp()})
            return 3
        state = {"state": "RUNNING", "stage": stage, "command": command, "start": timestamp(), "deadline": timestamp(deadline), "pid": os.getpid()}
        atomic_json(STATUS / "master_state.json", state)
        result = None
        terminal = state
        for attempt in range(1, 4):
            log_path = LOGS / f"{stage}.log"
            with log_path.open("ab") as log:
                result = subprocess.run([str(ROOT / command)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
            terminal = {**state, "attempt": attempt, "end": timestamp(), "exit_code": result.returncode, "classification": "PASS" if result.returncode == 0 else "RECOVERABLE_IMPLEMENTATION_FAILURE"}
            with (STATUS / "stage_attempts.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(terminal, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if result.returncode == 0:
                break
            time.sleep(30 * attempt)
        assert result is not None
        if result.returncode == 0:
            with completed_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"stage": stage, "timestamp": timestamp()}, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        else:
            atomic_json(STATUS / f"{stage}_failure.json", {**terminal, "classification": "FINAL_VERIFIED_LIMITATION_AFTER_RETRY_BUDGET"})
    while not stopped and now() < deadline:
        remaining = (deadline - now()).total_seconds()
        atomic_json(STATUS / "master_state.json", {"state": "WAITING_FOR_24H_CHECKPOINT", "remaining_seconds": max(0, int(remaining)), "timestamp": timestamp(), "deadline": timestamp(deadline)})
        atomic_json(STATUS / "resource_state.json", resource_state())
        time.sleep(min(300, max(1, remaining)))
    if not stopped:
        state = {"state": "FINALIZING", "stage": "normalize", "command": "scripts/external_v8/finalize_v8.py", "start": timestamp(), "deadline": timestamp(deadline), "pid": os.getpid()}
        atomic_json(STATUS / "master_state.json", state)
        with (LOGS / "normalize.log").open("ab") as log:
            result = subprocess.run([str(ROOT / "scripts/external_v8/finalize_v8.py")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0:
            atomic_json(STATUS / "normalize_failure.json", {**state, "end": timestamp(), "exit_code": result.returncode})
            return result.returncode
        with (LOGS / "checkpoint.log").open("ab") as log:
            checkpoint = subprocess.run([str(ROOT / "scripts/external_v8/checkpoint_v8.sh")], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        if checkpoint.returncode != 0:
            atomic_json(STATUS / "checkpoint_failure.json", {"state": "CHECKPOINT_FAILURE", "timestamp": timestamp(), "exit_code": checkpoint.returncode})
            return checkpoint.returncode
    atomic_json(STATUS / "master_state.json", {"state": "V8_DEADLINE_REACHED", "timestamp": timestamp(), "deadline": timestamp(deadline)})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        LOGS.mkdir(parents=True, exist_ok=True)
        failure = {
            "state": "MASTER_UNHANDLED_EXCEPTION",
            "timestamp": timestamp(),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback_log": str(LOGS / "master_exception.log"),
        }
        atomic_json(STATUS / "master_state.json", failure)
        with (LOGS / "master_exception.log").open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp()}] {type(error).__name__}: {error}\n")
            traceback.print_exc(file=handle)
            handle.flush()
            os.fsync(handle.fileno())
        raise
