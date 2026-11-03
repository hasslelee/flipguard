#!/usr/bin/env python3
"""Capture the immutable V7 queue-release environment."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
OUTPUT = ROOT / "docs/evidence/external_end_to_end_code_v7/environment_start.json"


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else f"UNAVAILABLE_EXIT_{result.returncode}"


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    usage = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    mem = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        if line.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"))
    }
    payload = {
        "schema_version": "flipguard_external_v7_environment_start_v1",
        "captured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "autonomous_start_timestamp": (STATUS / "autonomous_start_timestamp.txt").read_text().strip(),
        "hard_pause_timestamp": (STATUS / "hard_pause_timestamp.txt").read_text().strip(),
        "branch": run(["git", "branch", "--show-current"]),
        "source_commit": run(["git", "rev-parse", "HEAD"]),
        "origin_commit": run(["git", "rev-parse", "@{upstream}"]),
        "working_tree_porcelain": run(["git", "status", "--porcelain"]),
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "UNKNOWN"),
        "logical_cpus": os.cpu_count(),
        "memory_total_kib": mem.get("MemTotal", 0),
        "memory_available_kib": mem.get("MemAvailable", 0),
        "swap_total_kib": mem.get("SwapTotal", 0),
        "swap_used_kib": mem.get("SwapTotal", 0) - mem.get("SwapFree", 0),
        "disk_total_bytes": usage.total,
        "disk_free_bytes": usage.free,
        "inode_total": stat.f_files,
        "inode_free": stat.f_favail,
        "docker_version": run(["docker", "version", "--format", "{{.Client.Version}}/{{.Server.Version}}"]),
        "gpu": run(["nvidia-smi", "-L"]) if shutil.which("nvidia-smi") else "NOT_VISIBLE_VMWARE_SVGA_ONLY",
        "rocm": "VISIBLE" if shutil.which("rocminfo") else "NOT_VISIBLE",
        "systemd_unit_active": run(["systemctl", "--user", "is-active", "flipguard-external-v7.service"]),
        "systemd_unit_enabled": run(["systemctl", "--user", "is-enabled", "flipguard-external-v7.service"]),
        "systemd_linger": run(["loginctl", "show-user", os.environ["USER"], "-p", "Linger"]),
        "service_survival_test": json.loads((STATUS / "service_survival_test.json").read_text()),
        "measurement_parallelism": 1,
        "thread_policy": "taskset CPUs 0,1; OMP/OpenBLAS/MKL/GOMAXPROCS=2",
        "linger_enable_attempt": "FAILED_SUDO_PASSWORD_REQUIRED",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
