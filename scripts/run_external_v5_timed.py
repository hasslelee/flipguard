#!/usr/bin/env python3
"""Run one external V5 stage with a serialized host timing boundary."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = Path("/tmp/flipguard-external-v5-host.lock")


def write_json_atomic(path: Path, record: dict[str, object]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class Heartbeat:
    def __init__(self, path: Path, base: dict[str, object]) -> None:
        self.path = path
        self.base = base
        self.started = time.time()
        self.child_pid: int | None = None
        self.status = "STARTING"
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="external-v5-heartbeat", daemon=True)

    def start(self) -> None:
        self._write()
        self.thread.start()

    def update(self, status: str, child_pid: int | None = None) -> None:
        self.status = status
        if child_pid is not None:
            self.child_pid = child_pid
        self._write()

    def stop(self, status: str) -> None:
        self.status = status
        self.stop_event.set()
        self.thread.join(timeout=6)
        self._write()

    def _write(self) -> None:
        write_json_atomic(
            self.path,
            {
                **self.base,
                "status": self.status,
                "supervisor_pid": os.getpid(),
                "child_pid": self.child_pid,
                "heartbeat_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "elapsed_seconds": time.time() - self.started,
            },
        )

    def _run(self) -> None:
        while not self.stop_event.wait(5):
            self._write()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def parse_time(path: Path) -> dict[str, object]:
    fields: dict[str, object] = {}
    mapping = {
        "User time (seconds)": "user_seconds",
        "System time (seconds)": "system_seconds",
        "Maximum resident set size (kbytes)": "max_rss_kib",
        "Exit status": "time_exit_status",
    }
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for source, target in mapping.items():
            if line.strip().startswith(source + ":"):
                raw = line.split(":", 1)[1].strip()
                fields[target] = int(raw) if raw.isdigit() else float(raw)
    return fields


def relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return "EXTERNAL_PATH_REDACTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--mode", choices=["download", "build", "pipeline", "measurement"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    output = args.output_dir.resolve()
    cwd = args.cwd.resolve()
    output.mkdir(parents=True, exist_ok=False)
    stdout_path = output / "stdout.log"
    stderr_path = output / "stderr.log"
    time_path = output / "gnu_time.txt"
    env = os.environ.copy()
    env.update({
        "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2",
        "GOMAXPROCS": "2", "TOKENIZERS_PARALLELISM": "false",
        "LC_ALL": "C.UTF-8", "TZ": "Asia/Seoul",
    })
    wrapped = ["/usr/bin/time", "-v", "-o", str(time_path), "taskset", "-c", "0,1", *command]
    state_base = {
        "schema_version": "flipguard_external_host_timing_state_v5",
        "provider": args.provider,
        "workload": args.workload,
        "stage": args.stage,
        "mode": args.mode,
        "command": command,
        "working_directory": relative(cwd),
    }
    state_path = output / "run_state.json"
    heartbeat = Heartbeat(output / "heartbeat.json", state_base)
    heartbeat.start()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen[bytes] | None = None
    received_signal: int | None = None

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal received_signal
        received_signal = signum
        heartbeat.update(f"INTERRUPTING_SIGNAL_{signum}", process.pid if process else None)
        write_json_atomic(
            state_path,
            {
                **state_base,
                "status": "INTERRUPTING",
                "signal": signum,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        )
        if process is not None and process.poll() is None:
            process.send_signal(signum)

    previous_handlers = {
        signum: signal.signal(signum, handle_signal)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    with LOCK.open("w") as lock_handle:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            heartbeat.stop("HOST_LOCK_BUSY")
            write_json_atomic(state_path, {**state_base, "status": "HOST_LOCK_BUSY"})
            print("external_v5_timed=FAIL reason=host_lock_busy", file=sys.stderr)
            return 75
        start_wall = time.time()
        start_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        write_json_atomic(
            state_path,
            {**state_base, "status": "RUNNING", "start_timestamp": start_iso},
        )
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                wrapped,
                cwd=cwd,
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            heartbeat.update("RUNNING", process.pid)
            returncode = process.wait()
        end_wall = time.time()
        end_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    for signum, previous in previous_handlers.items():
        signal.signal(signum, previous)

    record = {
        "schema_version": "flipguard_external_host_timing_v5",
        "provider": args.provider,
        "workload": args.workload,
        "stage": args.stage,
        "mode": args.mode,
        "command": command,
        "working_directory": relative(cwd),
        "start_timestamp": start_iso,
        "end_timestamp": end_iso,
        "wall_seconds": end_wall - start_wall,
        "exit_status": returncode,
        "stdout_sha256": digest(stdout_path),
        "stderr_sha256": digest(stderr_path),
        "gnu_time_sha256": digest(time_path),
        "thread_environment": {key: env[key] for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "GOMAXPROCS"]},
        "cpu_affinity": "0,1",
        "process_priority": "inherited_nice_0",
        "outlier_removal": False,
    }
    if received_signal is not None:
        record["supervisor_received_signal"] = received_signal
    record.update(parse_time(time_path))
    write_json_atomic(output / "run_manifest.json", record)
    terminal_status = "PASS" if returncode == 0 else "FAIL"
    heartbeat.stop(terminal_status)
    write_json_atomic(
        state_path,
        {
            **state_base,
            "status": terminal_status,
            "start_timestamp": start_iso,
            "end_timestamp": end_iso,
            "exit_status": returncode,
            "run_manifest_sha256": digest(output / "run_manifest.json"),
        },
    )
    print(f"external_v5_timed={terminal_status} provider={args.provider} stage={args.stage} exit={returncode} wall_seconds={record['wall_seconds']:.6f}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
