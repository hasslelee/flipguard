#!/usr/bin/env python3
"""Prepare and freeze the V7 checkpoint at its declared wall-clock boundary."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from build_external_v7_evidence import build as build_normalized


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"
RESULTS = ROOT / "results/thesis_grade_protocol/external_end_to_end_code_v7"
PREPARED = RESULTS / "prepared-final-v1"
VERIFIER = EVIDENCE / "verify_external_end_to_end_code_v7.py"
FINAL_WINDOW = dt.timedelta(minutes=30)


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def read_time(name: str) -> dt.datetime:
    return dt.datetime.fromisoformat((STATUS / name).read_text(encoding="utf-8").strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def raw_result_index(source_commit: str) -> dict[str, Any]:
    manifests = []
    for path in sorted((ROOT / "external/v7/outputs").glob("**/manifest.json")):
        manifests.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    stage_manifests = sorted((ROOT / "external/v7/status").glob("*/*/run_manifest.json"))
    return {
        "schema_version": "flipguard_external_v7_raw_result_index_v1",
        "source_commit": source_commit,
        "raw_output_root": "external/v7/outputs",
        "output_manifest_count": len(manifests),
        "output_manifests": manifests,
        "stage_manifest_count": len(stage_manifests),
        "large_raw_outputs_tracked_in_git": False,
    }


def run_verifier(root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["python3", str(VERIFIER), "--root", str(root)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def prepare(destination: Path) -> dict[str, Any]:
    if destination.exists():
        marker = destination / "prepare_report.json"
        if not marker.is_file():
            raise RuntimeError(f"refusing partial prepared-result overwrite: {destination}")
        run_verifier(destination)
        return json.loads(marker.read_text(encoding="utf-8"))
    destination.mkdir(parents=True)
    source_commit = git_output("rev-parse", "HEAD")
    summary = build_normalized(destination, source_commit)
    write_json_atomic(destination / "raw_result_index.json", raw_result_index(source_commit))
    verification = run_verifier(destination)
    report = {
        "schema_version": "flipguard_external_v7_prepare_report_v1",
        "state": "PASS",
        "source_commit": source_commit,
        "hard_pause_timestamp": (STATUS / "hard_pause_timestamp.txt").read_text().strip(),
        "summary": summary,
        "verification": verification,
    }
    write_json_atomic(destination / "prepare_report.json", report)
    return report


def preflight() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="flipguard-v7-finalizer-") as temporary:
        return prepare(Path(temporary) / "prepared")


def copy_or_verify(source: Path, destination: Path) -> None:
    if destination.exists():
        if not destination.is_file() or sha256(source) != sha256(destination):
            raise RuntimeError(f"refusing to overwrite nonidentical evidence: {destination}")
        return
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def read_resource_rows() -> list[dict[str, str]]:
    path = STATUS / "resource_samples.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def environment_end(source_commit: str, finalization_timestamp: str) -> dict[str, Any]:
    resources = read_resource_rows()
    last = resources[-1]
    pids = []
    for row in resources:
        if row["pid"] not in pids:
            pids.append(row["pid"])
    return {
        "schema_version": "flipguard_external_v7_environment_end_v1",
        "finalization_timestamp": finalization_timestamp,
        "source_commit": source_commit,
        "origin_commit": git_output("rev-parse", "origin/experiments/external-e2e-code-v7"),
        "branch": git_output("branch", "--show-current"),
        "pre_freeze_working_tree_porcelain": git_output("status", "--short"),
        "disk_total_bytes": int(last["disk_total_bytes"]),
        "disk_used_bytes": int(last["disk_used_bytes"]),
        "disk_free_bytes": int(last["disk_free_bytes"]),
        "inode_free": int(last["inode_free"]),
        "inode_total": int(last["inode_total"]),
        "memory_available_kib": int(last["memory_available_kib"]),
        "swap_used_kib": int(last["swap_used_kib"]),
        "resource_gate": last["resource_gate"],
        "service_instance_count": len(pids),
        "service_restart_count": max(0, len(pids) - 1),
        "service_pids": pids,
        "vm_downtime": "NOT_OBSERVED_IN_RESOURCE_LEDGER",
        "code_codex_downtime": "NOT_SEPARATELY_RECORDED",
        "policy_retuning": 0,
        "frozen_core_evidence_modifications": 0,
    }


def downtime_rows() -> list[dict[str, Any]]:
    rows = []
    resource_rows = read_resource_rows()
    previous = None
    for row in resource_rows:
        if previous is not None and row["pid"] != previous["pid"]:
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "event": "MASTER_SERVICE_INSTANCE_CHANGED",
                    "previous_pid": previous["pid"],
                    "new_pid": row["pid"],
                    "provider": row["active_provider"],
                    "stage": row["active_stage"],
                    "reason": "See checkpoints.jsonl and systemd journal",
                }
            )
        previous = row
    checkpoint_path = STATUS / "checkpoints.jsonl"
    if checkpoint_path.exists():
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if not str(item.get("state", "")).startswith("SIGNAL_"):
                continue
            rows.append(
                {
                    "timestamp": item["timestamp"],
                    "event": item["state"],
                    "previous_pid": "NOT_REPORTED",
                    "new_pid": "NOT_REPORTED",
                    "provider": item.get("provider", "NOT_REPORTED"),
                    "stage": item.get("stage", "NOT_REPORTED"),
                    "reason": "Graceful on-disk checkpoint",
                }
            )
    return sorted(rows, key=lambda row: row["timestamp"])


def write_downtime(path: Path) -> None:
    fields = ["timestamp", "event", "previous_pid", "new_pid", "provider", "stage", "reason"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(downtime_rows())


def write_predecessor_comparison(path: Path) -> None:
    rows = [
        {
            "predecessor": "external_end_to_end_clean_v6",
            "commit": "9d8775aa3adc9029b369b812e4a9760420bac892",
            "v7_relation": "implementation predecessor only",
            "result_reused": False,
            "difference": "V7 regenerated builds, keys, ciphertexts, outputs, and timings",
        },
        {
            "predecessor": "comprehensive_ckks_comparison_v3",
            "commit": "5592b5d2c415eb08c040e7e2b04dd9b6346eb6b8",
            "v7_relation": "protocol and landscape predecessor",
            "result_reused": False,
            "difference": "V7 records only newly executed provider artifacts",
        },
        {
            "predecessor": "external_v7_root_owned_attempt1",
            "commit": "NOT_APPLICABLE_RUNTIME_CHECKPOINT",
            "v7_relation": "historical interrupted output preserved",
            "result_reused": False,
            "difference": "Canonical V7 output root was regenerated or source-bound recovered",
        },
    ]
    fields = ["predecessor", "commit", "v7_relation", "result_reused", "difference"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def checkpoint_report(claims: dict[str, Any], environment: dict[str, Any]) -> str:
    levels = {
        row["system"]: row
        for row in csv.DictReader((EVIDENCE / "artifact_execution_levels.csv").open(newline=""))
    }
    return f"""# External End-to-End Code V7 Checkpoint

## Disposition

- RUN DISPOSITION: `PAUSE_AT_24H_CHECKPOINT`
- Classification: `{claims['final_classification']}`
- Paper claim gate: `false`
- Source commit: `{environment['source_commit']}`

## Actual Evidence

- Official systems classified: {len(levels)}
- Encrypted end-to-end systems: {claims['encrypted_e2e_system_count']}
- Decision-bearing external providers: {claims['decision_bearing_provider_count']}
- Locked-audit external providers: {claims['locked_audit_provider_count']}
- PORTABLE_EXACT arms: {claims['portable_exact_count']}
- ELASM/CoreLab frozen grid: 72 attempted, 70 encrypted E2E, 2 execution failures
- EVA shared-polynomial gate: one selected SAFE candidate, disjoint locked audit PASS, retuning 0

## Fail-Closed Boundaries

- Native absolute latency is not interpreted as a configuration-only cross-runtime speedup.
- Build and source checkout results are not counted as encrypted execution.
- HECO's official recovered benchmark uses BFV and is not a CKKS comparison arm.
- No global-optimality, universal-provider, or universal-security claim is admitted.
- HECATE clean build PASS and runtime preparation failure are both preserved.
- Provider blockers remain explicit states rather than numeric zeros.

## Environment End

- Disk free bytes: {environment['disk_free_bytes']}
- Resource gate: `{environment['resource_gate']}`
- Service instances: {environment['service_instance_count']}
- Service restarts: {environment['service_restart_count']}
"""


def checksum_lines(root: Path, exclude: set[str]) -> list[str]:
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in exclude:
            continue
        lines.append(f"{sha256(path).removeprefix('sha256:')}  {relative}")
    return lines


def freeze() -> dict[str, Any]:
    pause = read_time("hard_pause_timestamp.txt")
    if now() < pause:
        raise RuntimeError(f"V7 freeze is blocked until {pause.isoformat()}")
    prepared_report = prepare(PREPARED)
    source_commit = git_output("rev-parse", "HEAD")
    finalization_timestamp = pause.isoformat(timespec="seconds")
    environment = environment_end(source_commit, finalization_timestamp)

    generated_files = [
        path for path in sorted(PREPARED.iterdir())
        if path.is_file() and path.name not in {"prepare_report.json"}
    ]
    for source in generated_files:
        copy_or_verify(source, EVIDENCE / source.name)
    copy_or_verify(STATUS / "resource_samples.csv", EVIDENCE / "resource_samples.csv")

    write_json_atomic(EVIDENCE / "environment_end.json", environment)
    write_downtime(EVIDENCE / "downtime_and_restart_log.csv")
    write_predecessor_comparison(EVIDENCE / "predecessor_comparison.csv")
    claims = json.loads((EVIDENCE / "claim_admission.json").read_text(encoding="utf-8"))
    write_text_atomic(EVIDENCE / "CHECKPOINT_REPORT.md", checkpoint_report(claims, environment))

    content_lines = checksum_lines(EVIDENCE, {"manifest.json", "SHA256SUMS"})
    tree_material = "\n".join(content_lines) + "\n"
    tree_digest = f"sha256:{hashlib.sha256(tree_material.encode()).hexdigest()}"
    manifest = {
        "schema_version": "flipguard_external_end_to_end_code_v7_final_v1",
        "state": "FROZEN",
        "run_disposition": "PAUSE_AT_24H_CHECKPOINT",
        "autonomous_start_timestamp": (STATUS / "autonomous_start_timestamp.txt").read_text().strip(),
        "hard_pause_timestamp": (STATUS / "hard_pause_timestamp.txt").read_text().strip(),
        "source_commit": source_commit,
        "origin_commit": environment["origin_commit"],
        "paper_claim_allowed": False,
        "final_classification": claims["final_classification"],
        "content_tree_sha256": tree_digest,
        "prepared_report": prepared_report,
    }
    write_json_atomic(EVIDENCE / "manifest.json", manifest)
    sums = checksum_lines(EVIDENCE, {"SHA256SUMS"})
    write_text_atomic(EVIDENCE / "SHA256SUMS", "\n".join(sums) + "\n")
    verification = run_verifier(EVIDENCE)
    return {"manifest": manifest, "verification": verification}


def prepare_finalization() -> dict[str, Any]:
    pause = read_time("hard_pause_timestamp.txt")
    if now() < pause - FINAL_WINDOW:
        raise RuntimeError(f"V7 final preparation is blocked until {(pause - FINAL_WINDOW).isoformat()}")
    if now() >= pause:
        return freeze()
    return prepare(PREPARED)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--prepare-finalization", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight()
    elif args.freeze:
        result = freeze()
    else:
        result = prepare_finalization()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
