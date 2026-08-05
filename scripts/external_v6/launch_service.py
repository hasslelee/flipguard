#!/usr/bin/env python3
"""Launch a V6 stage as a transient systemd user service."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
UNIT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--source-path")
    parser.add_argument("--binary-path")
    parser.add_argument("--input-path")
    parser.add_argument("--output-path")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a command is required after --")
    if not UNIT_RE.fullmatch(args.unit) or not args.unit.startswith("flipguard-v6-"):
        parser.error("unit must match flipguard-v6-[a-z0-9-]+")
    return args


def main() -> int:
    args = parse_args()
    active = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", args.unit], check=False
    )
    if active.returncode == 0:
        raise RuntimeError(f"service is already active: {args.unit}")

    runner = [
        sys.executable,
        str(ROOT / "scripts/external_v6/run_stage.py"),
        "--provider",
        args.provider,
        "--run-id",
        args.run_id,
        "--stage",
        args.stage,
        "--workload",
        args.workload,
        "--cwd",
        args.cwd,
    ]
    for flag, value in (
        ("--source-path", args.source_path),
        ("--binary-path", args.binary_path),
        ("--input-path", args.input_path),
        ("--output-path", args.output_path),
    ):
        if value is not None:
            runner.extend([flag, value])
    runner.extend(["--", *args.command])

    launch = [
        "systemd-run",
        "--user",
        f"--unit={args.unit}",
        "--collect",
        "--same-dir",
        "--property=KillMode=control-group",
        "--property=TimeoutStopSec=120",
        "--property=OOMPolicy=stop",
        f"--setenv=FLIPGUARD_V6_SERVICE_UNIT={args.unit}",
        *runner,
    ]
    completed = subprocess.run(launch, cwd=ROOT, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    print(f"service={args.unit} state=LAUNCHED provider={args.provider} run_id={args.run_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        print(f"V6 service launch error: {error}", file=sys.stderr)
        raise SystemExit(2)
