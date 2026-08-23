#!/usr/bin/env python3
"""Fail-closed verifier for an isolated V17 VM1x6 run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/protocols/model_family_expansion_v17/protocol.json"
PROFILE = ROOT / "docs/protocols/model_family_expansion_v17/execution_profiles/vmware_ubuntu24_1socket_6core_vcpu6_v1.json"
ARCHIVE = ROOT / "results/model_family_expansion_v17_archive/v17_pre_vcpu_change_2x1_20260810T143647Z"
TERMINAL = {"DONE", "FAILED_RECORDED", "UNSUPPORTED_RECORDED"}


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def verify_archive() -> None:
    manifest = load(ARCHIVE / "archive_manifest.json")
    require(manifest["status"] == "SUPERSEDED_FOR_FINAL_EVALUATION", "old archive status drift")
    require(manifest["admissibility"] == "EXPLORATORY_ONLY", "old archive admissibility drift")
    require(manifest["exclude_from_final_aggregation"] is True, "old archive exclusion disabled")
    with (ARCHIVE / "old_run_file_inventory.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    copied = ARCHIVE / "result_root"
    require(len(rows) == manifest["copied_file_count"], "old archive copy population mismatch")
    for row in rows:
        source = ROOT / row["path"]
        relative = source.relative_to(ROOT / "results/model_family_expansion_v17")
        target = copied / relative
        require(target.is_file() and target.stat().st_size == int(row["size_bytes"]) and sha(target) == row["sha256"], f"old archive mismatch: {relative}")


def current_source_digest(snapshot: dict) -> str:
    values = []
    for item in snapshot["source_files"]:
        path = ROOT / item["path"]
        require(path.is_file(), f"source snapshot path missing: {item['path']}")
        actual = sha(path)
        require(actual == item["sha256"], f"source snapshot drift: {item['path']}")
        values.append({"path": item["path"], "sha256": actual})
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--skip-live-environment", action="store_true")
    args = parser.parse_args()
    run_root = ROOT / "results/model_family_expansion_v17/runs" / args.run_id
    require(run_root.is_dir(), "run root missing")
    manifest = load(run_root / "run_manifest.json")
    require(manifest["run_id"] == args.run_id, "run ID mismatch")
    require(manifest["result_root"] == run_root.relative_to(ROOT).as_posix(), "result root mismatch")
    require(manifest["scientific_protocol_digest"] == sha(PROTOCOL), "scientific protocol digest mismatch")
    require(manifest["candidate_space_digest"] == sha(PROTOCOL.parent / "candidate_space.json"), "candidate-space digest mismatch")
    require(manifest["split_plan_digest"] == sha(PROTOCOL.parent / "split_plan.csv"), "split-plan digest mismatch")
    require(manifest["execution_profile_digest"] == sha(PROFILE), "execution-profile digest mismatch")
    environment = ROOT / manifest["environment_manifest"]
    require(environment.is_file() and manifest["environment_digest"] == sha(environment), "environment digest mismatch")
    env = load(environment)
    require((env["guest_virtual_sockets"], env["guest_cores_per_socket"], env["guest_total_vcpu"]) == (1, 6, 6), "environment topology mismatch")
    require(env["Cpus_allowed_list"] == "0-5" and env["effective_GOMAXPROCS"] == 6, "environment CPU exposure mismatch")
    snapshot = load(ROOT / manifest["source_snapshot_manifest"])
    require(current_source_digest(snapshot) == manifest["source_tree_digest"], "source-tree digest mismatch")
    for item in manifest["execution_binaries"]:
        path = ROOT / item["path"]
        require(path.is_file() and sha(path) == item["sha256"], f"binary mismatch: {item['path']}")
    verify_archive()
    if not args.skip_live_environment:
        require(os.environ.get("GOMAXPROCS") in {None, "6"}, "live GOMAXPROCS conflicts with profile")
        require(os.cpu_count() == 6 and sorted(os.sched_getaffinity(0)) == list(range(6)), "live CPU exposure is not 0-5")

    with (run_root / "run_status.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 204, f"ledger population {len(rows)} != 204")
    identities = [(row["phase"], row["case_id"]) for row in rows]
    require(len(identities) == len(set(identities)), "duplicate ledger identity")
    allowed_states = TERMINAL | {"PENDING", "RUNNING", "PENDING_DEPENDENCY", "RETRYABLE"}
    require(all(row["state"] in allowed_states for row in rows), "unclassified ledger state")
    for row in rows:
        output = ROOT / row["output"]
        require(output.resolve().is_relative_to(run_root.resolve()), f"output escapes scoped run root: {row['output']}")
        if row["state"] == "DONE":
            require(output.is_file(), f"DONE output missing: {row['phase']}/{row['case_id']}")
            binding_path = output.parent / "result_binding.json"
            require(binding_path.is_file(), f"DONE binding missing: {row['phase']}/{row['case_id']}")
            binding = load(binding_path)
            require(binding["run_id"] == args.run_id and binding["environment_id"] == manifest["environment_id"], "result binding run/environment mismatch")
            require(binding["total_vcpu"] == 6 and binding["guest_virtual_sockets"] == 1 and binding["guest_cores_per_socket"] == 6, "result binding topology mismatch")
            require(binding["output_sha256"] == sha(output), "result output digest mismatch")
            require(binding["old_v17_result_import_count"] == binding["old_v17_latency_import_count"] == binding["old_v17_completion_marker_import_count"] == 0, "old V17 result contamination")
    counts = Counter(row["state"] for row in rows)
    latency = [row for row in rows if row["phase"].startswith("latency")]
    require(len(latency) == 68, f"formal latency ledger population {len(latency)} != 68")
    if args.require_complete:
        require(all(row["state"] in TERMINAL for row in rows), f"nonterminal rows remain: {dict(counts)}")
        require(all(row["state"] in TERMINAL for row in latency), "nonterminal formal latency rows remain")
    result = {
        "status": "PASS",
        "run_id": args.run_id,
        "counts": dict(sorted(counts.items())),
        "latency_terminal": sum(row["state"] in TERMINAL for row in latency),
        "latency_expected": 68,
        "source_tree_digest": manifest["source_tree_digest"],
        "environment_digest": manifest["environment_digest"],
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
