#!/usr/bin/env python3
"""Capture a privacy-conscious, reproducible V6 host environment manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
THREAD_KEYS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "GOMAXPROCS",
    "RAYON_NUM_THREADS",
    "CUDA_VISIBLE_DEVICES",
    "LANG",
    "LC_ALL",
)


def run(command: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command, check=False, text=True, capture_output=True, timeout=timeout
        )
        output = completed.stdout.strip() or completed.stderr.strip()
        return {"exit_code": completed.returncode, "output": output[:8000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exit_code": None, "output": type(error).__name__}


def parse_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--hard-pause", required=True)
    parser.add_argument("--phase", choices=("start", "end"), required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise ValueError(f"refusing to overwrite environment manifest: {output}")

    disk = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    git_status = run(["git", "status", "--short"])
    relevant_processes = run(
        [
            "ps",
            "-eo",
            "pid=,comm=",
        ]
    )
    relevant_names = {
        "python",
        "python3",
        "docker",
        "ninja",
        "cmake",
        "bazel",
        "go",
        "hevm",
    }
    process_rows = []
    for line in relevant_processes["output"].splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2 and fields[1] in relevant_names:
            process_rows.append({"pid": int(fields[0]), "command_name": fields[1]})

    manifest = {
        "schema_version": "flipguard_external_end_to_end_clean_v6_environment_v1",
        "phase": args.phase,
        "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "autonomous_start_timestamp": args.start,
        "hard_pause_timestamp": args.hard_pause,
        "repository": ".",
        "branch": run(["git", "branch", "--show-current"])["output"],
        "commit": run(["git", "rev-parse", "HEAD"])["output"],
        "working_tree_clean": git_status["output"] == "",
        "kernel": platform.release(),
        "platform": platform.platform(),
        "os_release": parse_os_release(),
        "virtualization": {
            "product_name": Path("/sys/class/dmi/id/product_name").read_text().strip(),
            "sys_vendor": Path("/sys/class/dmi/id/sys_vendor").read_text().strip(),
        },
        "cpu": run(["lscpu", "-J"]),
        "logical_cpus": os.cpu_count(),
        "memory": run(["free", "-b"]),
        "swap": run(["swapon", "--show", "--bytes"]),
        "root_disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "inode_total": stat.f_files,
            "inode_free": stat.f_favail,
        },
        "docker": {
            "version": run(["docker", "version", "--format", "{{json .}}"]),
            "info": run(["docker", "info", "--format", "{{json .}}"]),
        },
        "compilers": {
            "go": run(["go", "version"]),
            "python": run(["python3", "--version"]),
            "gcc": run(["gcc", "--version"]),
            "clang": run(["clang", "--version"]),
            "cmake": run(["cmake", "--version"]),
            "ninja": run(["ninja", "--version"]),
        },
        "gpu": {
            "nvidia": run(["nvidia-smi", "-L"]),
            "rocm": run(["rocminfo"]),
            "display_controllers": run(["lspci"]),
        },
        "environment_variables": {key: os.environ.get(key) for key in THREAD_KEYS},
        "running_research_processes": process_rows,
        "systemd_user_manager": run(["systemctl", "--user", "is-system-running"]),
        "network_github": run(["curl", "-fsSI", "--max-time", "10", "https://github.com"]),
        "previous_verifiers": {
            "comprehensive_ckks_comparison_v3": "PASS",
            "paper_artifacts_v3": "PASS",
            "research_completion_checkpoint_v10": "PASS_AFTER_UNTRACKED_PYC_CACHE_REMOVAL",
            "security_v2_static_artifact": "PASS",
            "final_confirmatory_evidence": "PASS",
            "external_provider_research_boundary_v2": "PASS",
            "historical_suite_current_source_closure": "NOT_APPLICABLE_SOURCE_EVOLVED",
        },
        "privacy_note": "Only research-affecting environment variables and process basenames are recorded.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
