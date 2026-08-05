#!/usr/bin/env python3
"""Run one V6 provider stage with durable logs, heartbeat, and host locking."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UTC = dt.timezone.utc
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
THREAD_ENV = {
    "OMP_NUM_THREADS": "2",
    "OPENBLAS_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2",
    "GOMAXPROCS": "2",
    "RAYON_NUM_THREADS": "2",
}


def timestamp() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def digest_path(path: Path | None, *, exclude_vcs: bool = False) -> str:
    if path is None or not path.exists():
        return "NOT_AVAILABLE"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative_path = item.relative_to(path)
        if exclude_vcs and any(part in {".git", "__pycache__"} for part in relative_path.parts):
            continue
        relative = relative_path.as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(item).removeprefix("sha256:")))
    return f"sha256:{digest.hexdigest()}"


def read_proc_rss_kib(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, PermissionError, ValueError):
        return None
    return None


def disk_snapshot() -> tuple[int, int]:
    usage = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    return usage.free, stat.f_favail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--source-path")
    parser.add_argument("--binary-path")
    parser.add_argument("--input-path")
    parser.add_argument("--output-path")
    parser.add_argument("--cpus", default="0,1")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    for value in (args.provider, args.run_id):
        if not ID_RE.fullmatch(value):
            parser.error(f"unsafe identifier: {value}")
    return args


def resolve_optional(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    status_root = ROOT / "external/v6/status" / args.provider
    run_status = status_root / args.run_id
    log_root = ROOT / "external/v6/logs" / args.provider / args.run_id
    if run_status.exists() or log_root.exists():
        raise ValueError(f"refusing to overwrite V6 run {args.provider}/{args.run_id}")
    run_status.mkdir(parents=True)
    log_root.mkdir(parents=True)

    working_directory = resolve_optional(args.cwd)
    if working_directory is None or not working_directory.is_dir():
        raise ValueError(f"working directory does not exist: {working_directory}")

    source_path = resolve_optional(args.source_path)
    binary_path = resolve_optional(args.binary_path)
    input_path = resolve_optional(args.input_path)
    output_path = resolve_optional(args.output_path)
    command = list(args.command)
    if shutil.which("taskset") and args.cpus:
        command = ["taskset", "--cpu-list", args.cpus, *command]

    environment = os.environ.copy()
    environment.update(THREAD_ENV)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment_record = {
        "schema_version": "flipguard_external_v6_stage_environment_v1",
        "provider": args.provider,
        "run_id": args.run_id,
        "thread_environment": THREAD_ENV,
        "cwd": str(Path(args.cwd)),
        "command": args.command,
        "taskset_cpus": args.cpus,
    }
    atomic_json(log_root / "environment.json", environment_record)

    unit = os.environ.get("INVOCATION_ID", "NOT_SYSTEMD")
    for relative, value in {
        "start_timestamp.txt": timestamp() + "\n",
        "current_stage.txt": args.stage + "\n",
        "current_workload.txt": args.workload + "\n",
        "completed_samples.txt": "0\n",
        "heartbeat.txt": timestamp() + "\n",
        "service_unit.txt": os.environ.get("FLIPGUARD_V6_SERVICE_UNIT", unit) + "\n",
        "pid.txt": str(os.getpid()) + "\n",
        "source_sha256.txt": digest_path(source_path, exclude_vcs=True) + "\n",
        "binary_sha256.txt": digest_path(binary_path) + "\n",
        "input_sha256.txt": digest_path(input_path) + "\n",
        "output_sha256.txt": "PENDING\n",
    }.items():
        atomic_text(run_status / relative, value)
    atomic_text(status_root / "latest_run_id.txt", args.run_id + "\n")

    lock_path = Path("/tmp/flipguard-v6-measurement.lock")
    lock_handle = lock_path.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        atomic_text(run_status / "exit_code.txt", "INTEGRITY_BLOCK_CONCURRENT_MEASUREMENT\n")
        atomic_text(run_status / "end_timestamp.txt", timestamp() + "\n")
        raise RuntimeError("another V6 build or measurement holds the host lock") from error

    stdout_handle = (log_root / "stdout.log").open("xb")
    stderr_handle = (log_root / "stderr.log").open("xb")
    time_path = log_root / "time.log"
    timed_command = ["/usr/bin/time", "-v", "-o", str(time_path), "--", *command]
    start_monotonic = time.monotonic()
    process = subprocess.Popen(
        timed_command,
        cwd=working_directory,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=stdout_handle,
        stderr=stderr_handle,
        start_new_session=False,
    )
    atomic_text(run_status / "pid.txt", f"{os.getpid()}\n{process.pid}\n")

    stop_monitor = threading.Event()
    process_csv = log_root / "process_samples.csv"
    resource_csv = log_root / "resource_samples.csv"
    with process_csv.open("x", newline="", encoding="utf-8") as proc_handle, resource_csv.open(
        "x", newline="", encoding="utf-8"
    ) as resource_handle:
        proc_writer = csv.writer(proc_handle)
        resource_writer = csv.writer(resource_handle)
        proc_writer.writerow(["timestamp", "elapsed_seconds", "pid", "rss_kib"])
        resource_writer.writerow(
            ["timestamp", "elapsed_seconds", "disk_free_bytes", "inode_free", "load1"]
        )
        proc_handle.flush()
        resource_handle.flush()

        def monitor() -> None:
            while not stop_monitor.wait(5):
                now = timestamp()
                elapsed = time.monotonic() - start_monotonic
                free_bytes, free_inodes = disk_snapshot()
                rss = read_proc_rss_kib(process.pid)
                proc_writer.writerow([now, f"{elapsed:.6f}", process.pid, rss if rss is not None else ""])
                resource_writer.writerow(
                    [now, f"{elapsed:.6f}", free_bytes, free_inodes, f"{os.getloadavg()[0]:.6f}"]
                )
                proc_handle.flush()
                resource_handle.flush()
                os.fsync(proc_handle.fileno())
                os.fsync(resource_handle.fileno())
                atomic_text(run_status / "heartbeat.txt", now + "\n")

        monitor_thread = threading.Thread(target=monitor, name="v6-heartbeat", daemon=True)
        monitor_thread.start()

        interrupted_signal: int | None = None

        def forward(signum: int, _frame: object) -> None:
            nonlocal interrupted_signal
            interrupted_signal = signum
            atomic_text(run_status / "current_stage.txt", f"INTERRUPTING_SIGNAL_{signum}\n")
            if process.poll() is None:
                process.send_signal(signum)

        signal.signal(signal.SIGTERM, forward)
        signal.signal(signal.SIGINT, forward)
        return_code = process.wait()
        stop_monitor.set()
        monitor_thread.join(timeout=10)

    stdout_handle.close()
    stderr_handle.close()
    end = timestamp()
    elapsed = time.monotonic() - start_monotonic
    atomic_text(run_status / "heartbeat.txt", end + "\n")
    atomic_text(run_status / "exit_code.txt", str(return_code) + "\n")
    atomic_text(run_status / "end_timestamp.txt", end + "\n")
    atomic_text(run_status / "output_sha256.txt", digest_path(output_path) + "\n")
    final_state = "PASS" if return_code == 0 else "FAILED"
    atomic_text(run_status / "current_stage.txt", final_state + "\n")
    manifest = {
        "schema_version": "flipguard_external_v6_stage_run_v1",
        "provider": args.provider,
        "run_id": args.run_id,
        "stage": args.stage,
        "workload": args.workload,
        "command": args.command,
        "return_code": return_code,
        "interrupted_signal": interrupted_signal,
        "elapsed_seconds": elapsed,
        "end_timestamp": end,
        "source_sha256": digest_path(source_path, exclude_vcs=True),
        "binary_sha256": digest_path(binary_path),
        "input_sha256": digest_path(input_path),
        "output_sha256": digest_path(output_path),
        "stdout_sha256": sha256_file(log_root / "stdout.log"),
        "stderr_sha256": sha256_file(log_root / "stderr.log"),
        "time_sha256": sha256_file(time_path),
        "state": final_state,
    }
    atomic_json(run_status / "run_manifest.json", manifest)
    return return_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"V6 stage runner error: {error}", file=sys.stderr)
        raise SystemExit(2)
