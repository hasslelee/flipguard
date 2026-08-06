#!/usr/bin/env python3
"""Persistent, deadline-bound, serial external-provider queue for V7."""

from __future__ import annotations

import csv
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"
QUEUE_PATH = EVIDENCE / "execution_queue.json"
UTC = dt.timezone.utc
SURVIVAL_SECONDS = 300
NO_NEW_JOB_SECONDS = 1800
RESOURCE_INTERVAL_SECONDS = 900
HEARTBEAT_INTERVAL_SECONDS = 60


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def stamp(value: dt.datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def parse_time(path: Path) -> dt.datetime:
    return dt.datetime.fromisoformat(path.read_text(encoding="utf-8").strip())


def read_or_create_deadline() -> tuple[dt.datetime, dt.datetime]:
    start_path = STATUS / "autonomous_start_timestamp.txt"
    pause_path = STATUS / "hard_pause_timestamp.txt"
    if start_path.exists() != pause_path.exists():
        raise RuntimeError("integrity block: only one V7 deadline file exists")
    if start_path.exists():
        start, pause = parse_time(start_path), parse_time(pause_path)
        if pause - start != dt.timedelta(hours=24):
            raise RuntimeError("integrity block: V7 deadline is not exactly 24 hours")
        return start, pause
    start = now()
    pause = start + dt.timedelta(hours=24)
    atomic_text(start_path, stamp(start) + "\n")
    atomic_text(pause_path, stamp(pause) + "\n")
    atomic_text(STATUS / "autonomous_start_timestamp_utc.txt", start.astimezone(UTC).isoformat(timespec="seconds") + "\n")
    atomic_text(STATUS / "hard_pause_timestamp_utc.txt", pause.astimezone(UTC).isoformat(timespec="seconds") + "\n")
    return start, pause


def disk_state() -> dict[str, int | str]:
    usage = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    free_gib = usage.free / (1024 ** 3)
    inode_free_pct = stat.f_favail / stat.f_files * 100 if stat.f_files else 0
    if free_gib < 25 or inode_free_pct < 10:
        gate = "HARD_RESOURCE_STOP"
    elif free_gib < 45:
        gate = "RED"
    elif free_gib < 65:
        gate = "YELLOW"
    else:
        gate = "GREEN"
    return {
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
        "inode_free": stat.f_favail,
        "inode_total": stat.f_files,
        "resource_gate": gate,
    }


class Master:
    def __init__(self) -> None:
        self.stop_requested = threading.Event()
        self.active_provider = "NONE"
        self.active_stage = "MASTER_PREFLIGHT"
        self.service_restarts = 0
        self.start, self.pause = read_or_create_deadline()
        self.instance_start = now()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.resource_thread = threading.Thread(target=self._resource_loop, daemon=True)

    def state(self, state: str, **extra: Any) -> None:
        payload = {
            "schema_version": "flipguard_external_v7_master_state_v1",
            "state": state,
            "timestamp": stamp(),
            "autonomous_start_timestamp": stamp(self.start),
            "hard_pause_timestamp": stamp(self.pause),
            "active_provider": self.active_provider,
            "active_stage": self.active_stage,
            "pid": os.getpid(),
            "systemd_invocation_id": os.environ.get("INVOCATION_ID", "NOT_SYSTEMD"),
            **extra,
        }
        atomic_json(STATUS / "master_state.json", payload)

    def _heartbeat_loop(self) -> None:
        while not self.stop_requested.wait(HEARTBEAT_INTERVAL_SECONDS):
            atomic_text(STATUS / "heartbeat.txt", stamp() + "\n")
            self.state("RUNNING")

    def _resource_loop(self) -> None:
        output = STATUS / "resource_samples.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        while not self.stop_requested.is_set():
            sample = disk_state()
            meminfo = {
                line.split(":", 1)[0]: int(line.split()[1])
                for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
                if line.startswith(("MemAvailable:", "SwapTotal:", "SwapFree:"))
            }
            row = {
                "timestamp": stamp(),
                **sample,
                "memory_available_kib": meminfo.get("MemAvailable", 0),
                "swap_used_kib": meminfo.get("SwapTotal", 0) - meminfo.get("SwapFree", 0),
                "active_provider": self.active_provider,
                "active_stage": self.active_stage,
                "pid": os.getpid(),
            }
            is_new = not output.exists()
            with output.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
                handle.flush()
                os.fsync(handle.fileno())
            atomic_json(STATUS / "resource_state.json", row)
            if sample["resource_gate"] == "HARD_RESOURCE_STOP":
                self.state("HARD_RESOURCE_STOP", resource=row)
                self.stop_requested.set()
                return
            if self.stop_requested.wait(RESOURCE_INTERVAL_SECONDS):
                return

    def survival_test(self) -> None:
        path = STATUS / "service_survival_test.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("state") == "PASS":
            return
        test_start_path = STATUS / "service_survival_test_start.txt"
        if not test_start_path.exists():
            atomic_text(test_start_path, stamp() + "\n")
        test_start = parse_time(test_start_path)
        self.active_stage = "SERVICE_SURVIVAL_TEST"
        checkpoints: list[int] = []
        while not self.stop_requested.is_set():
            elapsed = int((now() - test_start).total_seconds())
            checkpoints = [point for point in (60, 180, 300) if elapsed >= point]
            atomic_json(path, {
                "schema_version": "flipguard_external_v7_service_survival_v1",
                "state": "PASS" if elapsed >= SURVIVAL_SECONDS else "RUNNING",
                "start_timestamp": stamp(test_start),
                "last_observed_timestamp": stamp(),
                "elapsed_seconds": elapsed,
                "observed_checkpoints_seconds": checkpoints,
                "systemd_invocation_id": os.environ.get("INVOCATION_ID", "NOT_SYSTEMD"),
            })
            if elapsed >= SURVIVAL_SECONDS:
                append_jsonl(STATUS / "checkpoints.jsonl", {
                    "timestamp": stamp(), "stage": "SERVICE_SURVIVAL_TEST", "state": "PASS"
                })
                return
            time.sleep(min(5, SURVIVAL_SECONDS - elapsed))

    def run(self) -> int:
        atomic_text(STATUS / "heartbeat.txt", stamp() + "\n")
        self.heartbeat_thread.start()
        self.resource_thread.start()
        self.state("STARTING")
        self.survival_test()
        if self.stop_requested.is_set():
            return 3
        release_path = STATUS / "queue_release.json"
        self.active_stage = "WAITING_FOR_FROZEN_QUEUE_RELEASE"
        while not self.stop_requested.is_set():
            if release_path.exists():
                release = json.loads(release_path.read_text(encoding="utf-8"))
                if release.get("state") != "PASS":
                    raise RuntimeError("integrity block: queue release exists without PASS")
                break
            if now() >= self.pause - dt.timedelta(minutes=30):
                break
            self.state("WAITING_FOR_FROZEN_QUEUE_RELEASE")
            time.sleep(10)
        if not release_path.exists():
            self.state("QUEUE_NOT_RELEASED_BEFORE_FINALIZATION")
            return 4
        queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))["providers"]
        atomic_json(STATUS / "provider_queue.json", {
            "schema_version": "flipguard_external_v7_runtime_queue_v1",
            "frozen_queue_sha256": subprocess.check_output(["sha256sum", str(QUEUE_PATH)], text=True).split()[0],
            "providers": queue,
        })
        completed = {
            json.loads(line)["provider"]
            for line in (STATUS / "completed_jobs.jsonl").read_text(encoding="utf-8").splitlines()
        } if (STATUS / "completed_jobs.jsonl").exists() else set()
        for provider in queue:
            if self.stop_requested.is_set() or provider["id"] in completed:
                continue
            remaining = (self.pause - now()).total_seconds()
            if remaining <= NO_NEW_JOB_SECONDS:
                break
            resource = disk_state()
            if resource["resource_gate"] in {"RED", "HARD_RESOURCE_STOP"}:
                self.state("RESOURCE_GATE_BLOCK", resource=resource)
                break
            self.active_provider = provider["id"]
            self.active_stage = "PROVIDER_JOB"
            self.state("RUNNING_PROVIDER")
            started = stamp()
            command = [str(ROOT / "scripts/external_v7/run_provider_job_v7.sh"), provider["id"]]
            result = subprocess.run(command, cwd=ROOT, check=False)
            record = {
                "provider": provider["id"],
                "start_timestamp": started,
                "end_timestamp": stamp(),
                "return_code": result.returncode,
                "state": "COMPLETED" if result.returncode == 0 else "PROVIDER_FAILED_CONTINUE",
            }
            destination = "completed_jobs.jsonl" if result.returncode == 0 else "failed_jobs.jsonl"
            append_jsonl(STATUS / destination, record)
        self.active_provider = "NONE"
        self.active_stage = "FINALIZATION" if now() >= self.pause - dt.timedelta(minutes=30) else "QUEUE_EXHAUSTED_QA"
        while not self.stop_requested.is_set() and now() < self.pause - dt.timedelta(minutes=30):
            self.state("QUEUE_EXHAUSTED_QA_WAIT")
            time.sleep(min(300, max(1, (self.pause - dt.timedelta(minutes=30) - now()).total_seconds())))
        if not self.stop_requested.is_set():
            subprocess.run(["python3", "scripts/external_v7/finalize_external_v7.py"], cwd=ROOT, check=False)
            while now() < self.pause and not self.stop_requested.wait(1):
                pass
            self.state("PAUSED_AT_24H")
        return 0

    def stop(self, signum: int, _frame: object) -> None:
        append_jsonl(STATUS / "checkpoints.jsonl", {
            "timestamp": stamp(), "stage": self.active_stage, "provider": self.active_provider,
            "state": f"SIGNAL_{signum}_CHECKPOINT"
        })
        self.state("STOP_REQUESTED", signal=signum)
        self.stop_requested.set()

    def close(self) -> None:
        self.stop_requested.set()
        self.heartbeat_thread.join(timeout=5)
        self.resource_thread.join(timeout=5)


def main() -> int:
    STATUS.mkdir(parents=True, exist_ok=True)
    lock = Path("/tmp/flipguard-external-v7-master.lock").open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 73
    master = Master()
    signal.signal(signal.SIGTERM, master.stop)
    signal.signal(signal.SIGINT, master.stop)
    try:
        return master.run()
    finally:
        master.close()


if __name__ == "__main__":
    raise SystemExit(main())
