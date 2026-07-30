#!/usr/bin/env python3
"""Maintain append-only autonomous-suite timing, stage, and recovery records."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(
    "results/thesis_grade_protocol/autonomous_execution_v1"
)
STAGE_STATUSES = {
    "PASS",
    "PARTIAL_SCIENTIFIC_RESULT",
    "RECOVERABLE_IMPLEMENTATION_FAILURE",
    "INTEGRITY_BLOCK",
    "INFRASTRUCTURE_BLOCK",
}
DEPENDENCY_GRAPH = {
    "preflight": [],
    "direct_selection": ["preflight"],
    "locked_audit": ["direct_selection"],
    "no_safe_controls": ["preflight"],
    "structural_holdout": ["preflight"],
    "paired_latency": ["direct_selection", "locked_audit"],
    "final_evidence_freeze": [
        "no_safe_controls",
        "structural_holdout",
        "paired_latency",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    subparsers = parser.add_subparsers(dest="action", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--window-hours", type=float, required=True)
    init.add_argument("--initial-head")

    stage = subparsers.add_parser("record-stage")
    stage.add_argument("--stage", required=True)
    stage.add_argument("--status", choices=sorted(STAGE_STATUSES), required=True)
    stage.add_argument("--reason-code", required=True)
    stage.add_argument("--command", default="")
    stage.add_argument("--artifact", action="append", default=[])
    stage.add_argument("--retry-count", type=int, default=0)

    recovery = subparsers.add_parser("record-recovery")
    recovery.add_argument("--stage", required=True)
    recovery.add_argument("--attempt", type=int, required=True)
    recovery.add_argument("--reason-code", required=True)
    recovery.add_argument("--action-taken", required=True)
    recovery.add_argument("--outcome", required=True)

    subparsers.add_parser("status")
    return parser.parse_args()


def now() -> datetime:
    return datetime.now().astimezone()


def parse_timestamp(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def init(root: Path, hours: float, initial_head: str | None) -> None:
    if hours <= 0:
        raise ValueError("autonomous window hours must be positive")
    window_path = root / "window.json"
    if window_path.exists():
        window = read_json(window_path)
        start = parse_timestamp(window["autonomous_start_timestamp"])
        earliest = parse_timestamp(window["earliest_normal_pause_timestamp"])
        actual_hours = (earliest - start).total_seconds() / 3600
        if abs(actual_hours - hours) > 1e-9:
            raise ValueError(
                f"existing autonomous window is {actual_hours}h, not {hours}h"
            )
    else:
        start = now()
        earliest = start + timedelta(hours=hours)
        write_new_json(
            window_path,
            {
                "schema_version": 1,
                "mode": f"AUTONOMOUS_{hours:g}H_CONTINUE",
                "pipeline_policy": (
                    "CLAIM_LEVEL_FAIL_CLOSED_PIPELINE_LEVEL_CONTINUE"
                ),
                "autonomous_start_timestamp": start.isoformat(),
                "earliest_normal_pause_timestamp": earliest.isoformat(),
                "initial_head": initial_head or git_head(),
                "normal_pause_allowed": False,
                "status": "ACTIVE",
            },
        )
    graph_path = root / "stage_dependency_graph.json"
    expected_graph = {
        "schema_version": 1,
        "policy": "CLAIM_LEVEL_FAIL_CLOSED_PIPELINE_LEVEL_CONTINUE",
        "statuses": sorted(STAGE_STATUSES),
        "dependencies": DEPENDENCY_GRAPH,
        "normal_pause_rule": (
            "normal pause is forbidden before earliest_normal_pause_timestamp"
        ),
        "hard_stop_rule": (
            "immediate stop is reserved for integrity, security, destructive, "
            "or unrecoverable infrastructure failures"
        ),
    }
    if graph_path.exists():
        if read_json(graph_path) != expected_graph:
            raise ValueError("autonomous stage dependency graph changed")
    else:
        write_new_json(graph_path, expected_graph)
    print(
        f"autonomous_window=start={start.isoformat()} "
        f"earliest_pause={earliest.isoformat()}"
    )


def record_stage(args: argparse.Namespace) -> None:
    if args.stage not in DEPENDENCY_GRAPH:
        raise ValueError(f"unknown stage {args.stage}")
    append_jsonl(
        args.root / "stage_ledger.jsonl",
        {
            "schema_version": 1,
            "timestamp": now().isoformat(),
            "head": git_head(),
            "stage": args.stage,
            "status": args.status,
            "reason_code": args.reason_code,
            "command": args.command,
            "artifacts": args.artifact,
            "retry_count": args.retry_count,
        },
    )
    print(f"stage={args.stage} status={args.status}")


def record_recovery(args: argparse.Namespace) -> None:
    append_jsonl(
        args.root / "recovery_log.jsonl",
        {
            "schema_version": 1,
            "timestamp": now().isoformat(),
            "head": git_head(),
            "stage": args.stage,
            "attempt": args.attempt,
            "reason_code": args.reason_code,
            "action_taken": args.action_taken,
            "outcome": args.outcome,
        },
    )
    print(
        f"recovery_stage={args.stage} attempt={args.attempt} "
        f"outcome={args.outcome}"
    )


def status(root: Path) -> None:
    window = read_json(root / "window.json")
    current = now()
    earliest = parse_timestamp(window["earliest_normal_pause_timestamp"])
    elapsed = current - parse_timestamp(window["autonomous_start_timestamp"])
    remaining = earliest - current
    print(
        json.dumps(
            {
                "autonomous_start_timestamp": window[
                    "autonomous_start_timestamp"
                ],
                "earliest_normal_pause_timestamp": window[
                    "earliest_normal_pause_timestamp"
                ],
                "current_timestamp": current.isoformat(),
                "elapsed_seconds": elapsed.total_seconds(),
                "remaining_seconds": max(0.0, remaining.total_seconds()),
                "normal_pause_allowed": current >= earliest,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> int:
    args = parse_args()
    if args.action == "init":
        init(args.root, args.window_hours, args.initial_head)
    elif args.action == "record-stage":
        record_stage(args)
    elif args.action == "record-recovery":
        record_recovery(args)
    elif args.action == "status":
        status(args.root)
    else:
        raise ValueError(f"unsupported action {args.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
