#!/usr/bin/env python3
"""Launch a V5 timed stage independently of the current Codex tool session."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_json_atomic(path: Path, record: dict[str, object]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--ledger-dir", type=Path, default=ROOT / "external/v5/supervisors")
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    ledger = args.ledger_dir.resolve()
    ledger.mkdir(parents=True, exist_ok=True)
    record_path = ledger / f"{args.label}.json"
    log_path = ledger / f"{args.label}.log"
    if record_path.exists() or log_path.exists():
        parser.error(f"detached ledger already exists for {args.label}")

    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            command,
            cwd=args.cwd.resolve(),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )

    time.sleep(0.5)
    record = {
        "schema_version": "flipguard_external_detached_launcher_v1",
        "label": args.label,
        "command": command,
        "working_directory": str(args.cwd.resolve()),
        "launcher_pid": os.getpid(),
        "child_pid": process.pid,
        "process_group_id": os.getpgid(process.pid) if process.poll() is None else None,
        "launch_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "alive_after_launch": process.poll() is None,
        "early_exit_status": process.poll(),
        "log_path": str(log_path),
    }
    write_json_atomic(record_path, record)
    print(
        f"external_v5_detached={'RUNNING' if record['alive_after_launch'] else 'EARLY_EXIT'} "
        f"label={args.label} pid={process.pid} ledger={record_path}"
    )
    return 0 if record["alive_after_launch"] else int(record["early_exit_status"] or 1)


if __name__ == "__main__":
    raise SystemExit(main())
