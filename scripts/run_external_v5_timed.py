#!/usr/bin/env python3
"""Run one external V5 stage with a serialized host timing boundary."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = Path("/tmp/flipguard-external-v5-host.lock")


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

    output = args.output_dir
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
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock_handle:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("external_v5_timed=FAIL reason=host_lock_busy", file=sys.stderr)
            return 75
        start_wall = time.time()
        start_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            completed = subprocess.run(wrapped, cwd=args.cwd, env=env, stdout=stdout, stderr=stderr, check=False)
        end_wall = time.time()
        end_iso = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    record = {
        "schema_version": "flipguard_external_host_timing_v5",
        "provider": args.provider,
        "workload": args.workload,
        "stage": args.stage,
        "mode": args.mode,
        "command": command,
        "working_directory": relative(args.cwd),
        "start_timestamp": start_iso,
        "end_timestamp": end_iso,
        "wall_seconds": end_wall - start_wall,
        "exit_status": completed.returncode,
        "stdout_sha256": digest(stdout_path),
        "stderr_sha256": digest(stderr_path),
        "gnu_time_sha256": digest(time_path),
        "thread_environment": {key: env[key] for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "GOMAXPROCS"]},
        "cpu_affinity": "0,1",
        "process_priority": "inherited_nice_0",
        "outlier_removal": False,
    }
    record.update(parse_time(time_path))
    (output / "run_manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"external_v5_timed={'PASS' if completed.returncode == 0 else 'FAIL'} provider={args.provider} stage={args.stage} exit={completed.returncode} wall_seconds={record['wall_seconds']:.6f}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
