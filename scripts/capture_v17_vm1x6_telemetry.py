#!/usr/bin/env python3
"""Capture guest-visible telemetry without applying post-hoc exclusions."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


FIELDS = [
    "timestamp", "load1", "load5", "load15", "cpu_user_delta",
    "cpu_system_delta", "cpu_idle_delta", "cpu_iowait_delta", "cpu_steal_delta",
    "mem_available_kib", "swap_free_kib", "context_switches_delta",
    "process_cpu_ticks", "io_pressure_some_avg10", "current_phase", "current_case_id",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cpu() -> tuple[int, int, int, int, int, int]:
    parts = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()
    values = [int(value) for value in parts[1:]]
    context = next(int(line.split()[1]) for line in Path("/proc/stat").read_text(encoding="ascii").splitlines() if line.startswith("ctxt "))
    return values[0], values[2], values[3], values[4], values[7], context


def memory() -> tuple[int, int]:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
        key, value, *_ = line.replace(":", "").split()
        values[key] = int(value)
    return values["MemAvailable"], values["SwapFree"]


def process_ticks(run_root: Path) -> int:
    total = 0
    needle = str(run_root)
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
            if needle not in command and "flipguard-v17" not in command:
                continue
            stat = (entry / "stat").read_text(encoding="ascii").split()
            total += int(stat[13]) + int(stat[14])
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return total


def io_pressure() -> str:
    path = Path("/proc/pressure/io")
    if not path.is_file():
        return ""
    first = path.read_text(encoding="ascii").splitlines()[0].split()
    value = next((item.split("=", 1)[1] for item in first if item.startswith("avg10=")), "")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    output = run_root / "telemetry/telemetry.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = cpu()
    new = not output.is_file()
    with output.open("a", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        if new:
            writer.writeheader()
        while not (run_root / "TELEMETRY_STOP").is_file():
            current = cpu()
            loads = os.getloadavg()
            available, swap = memory()
            state = {}
            current_path = run_root / "current_case.json"
            if current_path.is_file():
                try:
                    state = json.loads(current_path.read_text(encoding="ascii"))
                except (json.JSONDecodeError, OSError):
                    state = {"phase": "UNREADABLE", "case_id": "UNREADABLE"}
            writer.writerow({
                "timestamp": now(), "load1": loads[0], "load5": loads[1], "load15": loads[2],
                "cpu_user_delta": current[0] - previous[0], "cpu_system_delta": current[1] - previous[1],
                "cpu_idle_delta": current[2] - previous[2], "cpu_iowait_delta": current[3] - previous[3],
                "cpu_steal_delta": current[4] - previous[4], "context_switches_delta": current[5] - previous[5],
                "mem_available_kib": available, "swap_free_kib": swap,
                "process_cpu_ticks": process_ticks(run_root), "io_pressure_some_avg10": io_pressure(),
                "current_phase": state.get("phase", "IDLE"), "current_case_id": state.get("case_id", "IDLE"),
            })
            handle.flush()
            previous = current
            time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
