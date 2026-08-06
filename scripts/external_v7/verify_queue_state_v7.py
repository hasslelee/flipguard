#!/usr/bin/env python3
"""Fail-closed structural verification of V7 service state."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-only", action="store_true")
    args = parser.parse_args()
    usage = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    if usage.free < 25 * 1024 ** 3 or stat.f_favail / stat.f_files < 0.10:
        print("HARD_RESOURCE_STOP")
        return 3
    if args.resource_only:
        print(json.dumps({"disk_free_bytes": usage.free, "inode_free": stat.f_favail}, sort_keys=True))
        return 0
    start = dt.datetime.fromisoformat((STATUS / "autonomous_start_timestamp.txt").read_text().strip())
    pause = dt.datetime.fromisoformat((STATUS / "hard_pause_timestamp.txt").read_text().strip())
    if pause - start != dt.timedelta(hours=24):
        raise SystemExit("invalid V7 deadline")
    master = json.loads((STATUS / "master_state.json").read_text())
    if master["hard_pause_timestamp"] != pause.isoformat(timespec="seconds"):
        raise SystemExit("master/deadline mismatch")
    print("V7 queue state: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
