#!/usr/bin/env python3
"""Step-0 re-measurement: constant encoding at the ciphertext scale.

Re-runs configuration selection and the separate-input evaluation for the 65
primary tabular cases with the output constants encoded at the exact
ciphertext scale, plus a default-scale control on the first fold of each
dataset-model combination. One CKKS case runs at a time. Outputs go to a new
run directory; the frozen V17 evidence is only read.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "results/model_family_expansion_v17"
INPUTS = FROZEN / "plaintext/primary"
MODEL_ORDER = ["linear_poly3", "mlp_square_linear_score", "mlp_square2_linear_score"]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def cases() -> list[dict]:
    items = []
    for manifest in sorted(INPUTS.glob("*/*/fold_*/training_seed_*/manifest.json")):
        item = json.loads(manifest.read_text(encoding="utf-8"))
        if item.get("role") != "primary":
            continue
        item["source"] = manifest.parent
        items.append(item)
    items.sort(key=lambda i: (MODEL_ORDER.index(i["model_id"]), i["dataset_id"], int(i["outer_fold"])))
    return items


def run_case(binary: Path, out_root: Path, item: dict, mode: str, status_rows: list, status_path: Path) -> None:
    case_id = f"{item['dataset_id']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item.get('training_seed', 0)}"
    output = out_root / mode / case_id
    done = output / "case_summary.json"
    if done.is_file():
        return
    source = item["source"]
    command = [
        "taskset", "-c", "0-5", str(binary),
        "--model", str(source / "model.json"),
        "--selection", str(source / "configuration_selection.csv"),
        "--independent", str(source / "independent_evaluation.csv"),
        "--dataset", item["dataset_id"], "--model-id", item["model_id"],
        "--split-id", f"outer_fold_{item['outer_fold']}_training_seed_{item.get('training_seed', 0)}",
        "--constant-encoding", mode, "--out-root", str(output),
    ]
    started = now()
    env = dict(os.environ, GOMAXPROCS="6")
    proc = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    state = "DONE" if proc.returncode == 0 and done.is_file() else "FAILED"
    status_rows.append({"mode": mode, "case_id": case_id, "state": state, "started_at": started,
                        "completed_at": now(), "message": (proc.stdout.strip() or proc.stderr.strip())[-400:]})
    with status_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mode", "case_id", "state", "started_at", "completed_at", "message"])
        writer.writeheader()
        writer.writerows(status_rows)
    print(f"[{now()}] {mode} {case_id} {state}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    out_root = ROOT / "runs" / args.run_id
    binary = out_root / "bin/flipguard-scale-exact-tabular-case"
    if not binary.is_file():
        raise SystemExit(f"missing binary {binary}")
    if FROZEN in out_root.parents:
        raise SystemExit("output must not be inside frozen evidence")
    status_path = out_root / "run_status.csv"
    status_rows: list = []
    if status_path.is_file():
        with status_path.open(encoding="utf-8") as handle:
            status_rows = list(csv.DictReader(handle))
    with (out_root / "run.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another step-0 process owns the execution lock")
        items = cases()
        if len(items) != 65:
            raise SystemExit(f"expected 65 primary tabular cases, found {len(items)}")
        for item in items:
            run_case(binary, out_root, item, "ciphertext_scale", status_rows, status_path)
        for item in items:
            if int(item["outer_fold"]) == 0:
                run_case(binary, out_root, item, "default_scale", status_rows, status_path)
    (out_root / "RUN_COMPLETE").write_text(now() + "\n", encoding="utf-8")
    print("complete", flush=True)


if __name__ == "__main__":
    sys.exit(main())
