#!/usr/bin/env python3
"""Record host-resource state for the full V6 autonomous window."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]


def parse_timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def command(command: list[str]) -> str:
    try:
        return subprocess.run(
            command, check=False, text=True, capture_output=True, timeout=30
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", required=True, type=parse_timestamp)
    parser.add_argument("--interval-seconds", type=int, default=900)
    args = parser.parse_args()
    output = ROOT / "external/v6/status/resource_samples.csv"
    heartbeat = ROOT / "external/v6/status/resource_monitor_heartbeat.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    is_new = not output.exists()
    with output.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(
                [
                    "timestamp",
                    "disk_free_bytes",
                    "inode_free",
                    "memory_available_kib",
                    "swap_used_kib",
                    "docker_disk_usage",
                    "active_provider_units",
                    "result_bytes",
                ]
            )
        while True:
            now = dt.datetime.now().astimezone()
            usage = shutil.disk_usage(ROOT)
            stat = os.statvfs(ROOT)
            memory = Path("/proc/meminfo").read_text()
            values = {
                line.split(":", 1)[0]: int(line.split()[1])
                for line in memory.splitlines()
                if line.startswith(("MemAvailable:", "SwapTotal:", "SwapFree:"))
            }
            units = command(
                [
                    "systemctl",
                    "--user",
                    "list-units",
                    "flipguard-v6-*",
                    "--state=running",
                    "--no-legend",
                    "--plain",
                ]
            )
            docker = command(["docker", "system", "df", "--format", "{{json .}}"])
            result_root = ROOT / "results/thesis_grade_protocol/external_end_to_end_clean_v6"
            result_bytes = sum(
                item.stat().st_size for item in result_root.rglob("*") if item.is_file()
            ) if result_root.exists() else 0
            writer.writerow(
                [
                    now.isoformat(timespec="seconds"),
                    usage.free,
                    stat.f_favail,
                    values.get("MemAvailable", 0),
                    values.get("SwapTotal", 0) - values.get("SwapFree", 0),
                    docker.replace("\n", " | "),
                    units.replace("\n", " | "),
                    result_bytes,
                ]
            )
            handle.flush()
            os.fsync(handle.fileno())
            heartbeat.write_text(now.isoformat(timespec="seconds") + "\n", encoding="utf-8")
            if now >= args.until:
                break
            time.sleep(min(args.interval_seconds, max(1, (args.until - now).total_seconds())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
