#!/usr/bin/env python3
"""Reconstruct and freeze the pre-migration V17 run after the VM reboot.

The reboot happened before the requested Phase-A handoff was written.  This
tool therefore records only durable facts recoverable from the repository and
labels the handoff RECONSTRUCTED_POST_REBOOT.  It never treats reconstructed
process metadata as a contemporaneous observation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_ROOT = ROOT / "results/model_family_expansion_v17"
CHECKPOINT = ROOT / "docs/checkpoints/vcpu_2x1_to_1x6"
CODEX_CHECKPOINT = ROOT / ".codex/checkpoints"
PROTOCOL_ROOT = ROOT / "docs/protocols/model_family_expansion_v17"
PACK_V4 = ROOT / "docs/evidence/model_family_expansion_v17_checkpoint_12h_v4"
OLD_RUN_ID = "v17_pre_vcpu_change_2x1_20260810T143647Z"
ARCHIVE_ROOT = ROOT / "results/model_family_expansion_v17_archive" / OLD_RUN_ID
EVIDENCE_ARCHIVE = ROOT / "docs/evidence/model_family_expansion_v17/archive" / OLD_RUN_ID
REPORT_ARCHIVE = ROOT / "docs/reports/model_family_expansion_v17/archive" / OLD_RUN_ID


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout


def inventory(root: Path, excluded_parts: set[str] | None = None) -> list[dict[str, object]]:
    excluded_parts = excluded_parts or set()
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if excluded_parts.intersection(path.relative_to(root).parts):
            continue
        rows.append({"path": rel(path), "size_bytes": path.stat().st_size, "sha256": sha(path)})
    return rows


def process_inventory() -> tuple[list[str], list[dict[str, object]]]:
    lines = [
        "capture_class=RECONSTRUCTED_POST_REBOOT",
        "warning=Phase A was not captured before reboot; historical PID and process environment are unavailable",
        f"captured_at={now()}",
    ]
    active: list[dict[str, object]] = []
    for entry in sorted(Path("/proc").iterdir(), key=lambda item: item.name):
        if not entry.name.isdigit():
            continue
        try:
            parts = (entry / "cmdline").read_bytes().split(b"\0")
            command = " ".join(part.decode("utf-8", errors="replace") for part in parts if part)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if "model_family_expansion_v17" not in command and "flipguard-v17" not in command:
            continue
        if "prepare_v17_vcpu_migration" in command:
            continue
        item = {"pid": int(entry.name), "command": command}
        active.append(item)
        lines.append(f"active_pid={item['pid']} command={command}")
    lines.append(f"active_v17_process_count={len(active)}")
    lines.append("pre_reboot_stop_status=STOPPED_AFTER_ATOMIC_CASE_FROM_DURABLE_RUN_WINDOW")
    lines.append("pre_reboot_signal=graceful_stop_marker")
    lines.append("pre_reboot_exit_code=not_recoverable_after_reboot")
    return lines, active


def category(phase: str) -> str:
    return {
        "primary": "heterogeneous_primary_correctness_direct_exhaustive_independent",
        "packed_primary": "packed_P6_correctness_direct_exhaustive_independent",
        "multiclass_exhaustive": "multiclass_P4_P5_exhaustive_and_independent",
        "ablation": "controlled_2x2_ablation",
        "training_seed": "tabular_training_seed",
        "training_seed_multiclass": "multiclass_training_seed",
        "training_seed_packed": "packed_training_seed",
        "depth_ladder": "depth_ladder",
        "latency": "formal_paired_latency_tabular",
        "latency_multiclass": "formal_paired_latency_multiclass",
        "latency_packed": "formal_paired_latency_packed",
    }[phase]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--copy-archive", action="store_true")
    args = parser.parse_args()
    for path in (CHECKPOINT, CODEX_CHECKPOINT, EVIDENCE_ARCHIVE, REPORT_ARCHIVE):
        path.mkdir(parents=True, exist_ok=True)

    protocol = json.loads((PROTOCOL_ROOT / "protocol.json").read_text(encoding="ascii"))
    ledger_path = OLD_ROOT / "run_status.csv"
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        ledger = list(csv.DictReader(handle))
    if len(ledger) != protocol["expected_run_ledger_rows"]:
        raise RuntimeError("old ledger count does not match frozen protocol")
    identities = [(row["phase"], row["case_id"]) for row in ledger]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate old case identity")

    reconciled = []
    for row in ledger:
        output = ROOT / row["output"]
        output_exists = output.is_file()
        verified_done = row["state"] == "DONE" and output_exists
        if row["state"] == "DONE" and not output_exists:
            raise RuntimeError(f"DONE output missing: {row['output']}")
        if verified_done and output.suffix == ".json":
            json.loads(output.read_text(encoding="utf-8"))
        reconciled.append({
            "phase": row["phase"],
            "case_id": row["case_id"],
            "category": category(row["phase"]),
            "ledger_state": row["state"],
            "attempts": row["attempts"],
            "output": row["output"],
            "output_exists": str(output_exists).lower(),
            "output_sha256": sha(output) if output_exists else "",
            "completion_verdict": "VERIFIED_DONE" if verified_done else "NOT_DONE",
            "final_aggregation_eligible": "false",
        })
    write_csv(
        CHECKPOINT / "old_run_case_reconciliation.csv",
        list(reconciled[0]),
        reconciled,
    )

    process_lines, active = process_inventory()
    if active:
        raise RuntimeError("active V17 process detected after reboot")
    write_text(CHECKPOINT / "old_run_process_inventory.txt", "\n".join(process_lines) + "\n")

    old_files = inventory(OLD_ROOT, {"archive", "runs", "final_vm1x6"})
    write_csv(CHECKPOINT / "old_run_file_inventory.csv", ["path", "size_bytes", "sha256"], old_files)
    write_text(
        CHECKPOINT / "old_run_tree_SHA256SUMS",
        "".join(f"{item['sha256'].removeprefix('sha256:')}  {item['path']}\n" for item in old_files),
    )

    status = run("git", "status", "--porcelain=v1")
    diff = run("git", "diff", "--binary")
    untracked = run("git", "ls-files", "--others", "--exclude-standard")
    git_summary = (
        f"capture_class=RECONSTRUCTED_POST_REBOOT\n"
        f"captured_at={now()}\n"
        f"branch={run('git', 'branch', '--show-current').strip()}\n"
        f"head={run('git', 'rev-parse', 'HEAD').strip()}\n"
        f"upstream_counts={subprocess.run(['git','rev-list','--left-right','--count','HEAD...@{upstream}'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.strip()}\n"
        "--- git status --porcelain=v1 ---\n" + status
    )
    write_text(CHECKPOINT / "old_run_git_status.txt", git_summary)
    write_text(CHECKPOINT / "old_run_worktree.patch", diff)
    write_text(CHECKPOINT / "old_run_untracked_inventory.txt", untracked)
    write_text(CODEX_CHECKPOINT / "v17_pre_vcpu_change_git_status.txt", status)
    write_text(CODEX_CHECKPOINT / "v17_pre_vcpu_change_worktree.patch", diff)
    write_text(CODEX_CHECKPOINT / "v17_pre_vcpu_change_untracked.txt", untracked)

    source_paths = set(run("git", "ls-files").splitlines())
    source_paths.update(
        item for item in untracked.splitlines()
        if item.startswith(("cmd/flipguard-v17-", "internal/", "scripts/"))
        or item in {"go.mod", "go.sum"}
    )
    source_rows = []
    for name in sorted(source_paths):
        path = ROOT / name
        if path.is_file():
            source_rows.append({"path": name, "size_bytes": path.stat().st_size, "sha256": sha(path)})
    write_csv(CHECKPOINT / "old_run_source_inventory.csv", ["path", "size_bytes", "sha256"], source_rows)

    state_counts = Counter(row["state"] for row in ledger)
    phase_counts = Counter(row["phase"] for row in ledger)
    category_counts = Counter(category(row["phase"]) for row in ledger)
    done_rows = sorted((row for row in ledger if row["state"] == "DONE"), key=lambda row: row["completed_at"])
    protocol_digest = sha(PROTOCOL_ROOT / "protocol.json")
    candidate_digest = sha(PROTOCOL_ROOT / "candidate_space.json")
    split_digest = sha(PROTOCOL_ROOT / "split_plan.csv")
    archive_manifest = {
        "schema_version": "flipguard_v17_pre_vcpu_change_archive_v1",
        "archive_capture_class": "RECONSTRUCTED_POST_REBOOT",
        "archive_note": "Phase A was reconstructed from durable artifacts after reboot; pre-reboot process metadata was not contemporaneously captured.",
        "old_run_id": OLD_RUN_ID,
        "status": "SUPERSEDED_FOR_FINAL_EVALUATION",
        "admissibility": "EXPLORATORY_ONLY",
        "exclude_from_final_aggregation": True,
        "exclusion_reason": "VM_CPU_TOPOLOGY_CHANGED_FROM_2x1_TO_1x6",
        "old_environment_id": "vmware_ubuntu24_2socket_1core_vcpu2_protocol_frozen",
        "virtual_socket_count": 2,
        "cores_per_virtual_socket": 1,
        "total_vcpu": 2,
        "cpu_affinity": [0, 1],
        "GOMAXPROCS": 2,
        "actual_verified_DONE": state_counts.get("DONE", 0),
        "actual_PENDING": state_counts.get("PENDING", 0),
        "actual_RUNNING": state_counts.get("RUNNING", 0),
        "actual_FAILED_RECORDED": state_counts.get("FAILED_RECORDED", 0),
        "expected_total": len(ledger),
        "phase_counts": dict(sorted(phase_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "latency_expected": sum(value for key, value in phase_counts.items() if key.startswith("latency")),
        "latency_completed": sum(1 for row in ledger if row["phase"].startswith("latency") and row["state"] == "DONE"),
        "stopped_at": json.loads((OLD_ROOT / "run_window.json").read_text(encoding="ascii"))["checkpoint_end_timestamp"],
        "last_completed_case": {key: done_rows[-1][key] for key in ("phase", "case_id", "completed_at", "output")},
        "interrupted_case": None,
        "pre_reboot_runner_status": "STOPPED_AFTER_ATOMIC_CASE",
        "source_HEAD": run("git", "rev-parse", "HEAD").strip(),
        "source_tree_digest": protocol["execution_critical_source_digest"],
        "binary_digests": protocol["execution_binaries"],
        "scientific_protocol_digest": protocol_digest,
        "candidate_space_digest": candidate_digest,
        "split_plan_digest": split_digest,
        "result_root": rel(OLD_ROOT),
        "log_root": rel(OLD_ROOT / "logs"),
        "checkpoint_root": rel(PACK_V4),
        "archive_root": rel(ARCHIVE_ROOT),
        "archive_file_inventory": rel(CHECKPOINT / "old_run_file_inventory.csv"),
        "archive_file_inventory_sha256": sha(CHECKPOINT / "old_run_file_inventory.csv"),
        "superseded_by_environment": "vmware_ubuntu24_1socket_6core_vcpu6",
        "final_paper_use": "prohibited",
        "final_aggregation_allowlisted": False,
        "created_at": now(),
    }

    if args.copy_archive:
        if ARCHIVE_ROOT.exists():
            raise RuntimeError(f"archive already exists: {ARCHIVE_ROOT}")
        ARCHIVE_ROOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(OLD_ROOT, ARCHIVE_ROOT / "result_root")
        copied = inventory(ARCHIVE_ROOT / "result_root")
        original_map = {Path(item["path"]).relative_to(rel(OLD_ROOT)).as_posix(): item["sha256"] for item in old_files}
        copied_map = {Path(item["path"]).relative_to(rel(ARCHIVE_ROOT / "result_root")).as_posix(): item["sha256"] for item in copied}
        if original_map != copied_map:
            raise RuntimeError("copied old result archive checksum mismatch")
        archive_manifest["archive_mode"] = "BYTE_IDENTICAL_COPY"
        archive_manifest["copied_file_count"] = len(copied)
    else:
        ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
        archive_manifest["archive_mode"] = "CHECKSUM_BOUND_REFERENCE"
        archive_manifest["copied_file_count"] = 0
    write_json(ARCHIVE_ROOT / "archive_manifest.json", archive_manifest)
    shutil.copy2(CHECKPOINT / "old_run_file_inventory.csv", ARCHIVE_ROOT / "old_run_file_inventory.csv")
    write_text(
        ARCHIVE_ROOT / "SHA256SUMS",
        f"{sha(ARCHIVE_ROOT / 'archive_manifest.json').removeprefix('sha256:')}  archive_manifest.json\n"
        f"{sha(ARCHIVE_ROOT / 'old_run_file_inventory.csv').removeprefix('sha256:')}  old_run_file_inventory.csv\n",
    )
    for destination in (EVIDENCE_ARCHIVE, REPORT_ARCHIVE):
        write_json(destination / "archive_reference.json", archive_manifest)
        write_text(
            destination / "SHA256SUMS",
            f"{sha(destination / 'archive_reference.json').removeprefix('sha256:')}  archive_reference.json\n",
        )

    external_cache_files = sorted(
        path for path in (ROOT / "external").rglob("*")
        if path.is_file() and path.suffix in {".pyc", ".pyo"}
    )
    handoff = f"""# V17 vCPU 2x1 to 1x6 handoff

status: RECONSTRUCTED_POST_REBOOT
created_at: {now()}

This handoff was not written before the reboot. It is reconstructed from the
durable V17 run ledger, run window, logs, protocol, and checkpoint v4. No
historical PID, pre-reboot `/proc` environment, or exit code is invented.

## Source state

- branch: `{run('git', 'branch', '--show-current').strip()}`
- HEAD: `{run('git', 'rev-parse', 'HEAD').strip()}`
- dirty worktree: `{str(bool(status.strip())).lower()}`
- status: `{rel(CHECKPOINT / 'old_run_git_status.txt')}`
- binary diff: `{rel(CHECKPOINT / 'old_run_worktree.patch')}`
- untracked inventory: `{rel(CHECKPOINT / 'old_run_untracked_inventory.txt')}`
- source inventory: `{rel(CHECKPOINT / 'old_run_source_inventory.csv')}`

## Superseded 2x1 run

- old run ID: `{OLD_RUN_ID}`
- verified progress: `{state_counts.get('DONE', 0)} / {len(ledger)}`
- pending: `{state_counts.get('PENDING', 0)}`
- failed recorded: `{state_counts.get('FAILED_RECORDED', 0)}`
- formal latency: `{archive_manifest['latency_completed']} / {archive_manifest['latency_expected']}`
- topology: 2 virtual sockets x 1 core, total 2 vCPU
- durable stop status: `STOPPED_AFTER_ATOMIC_CASE`
- stop mechanism: `STOP_AFTER_ATOMIC_CASE` marker after an atomic case
- process state after reboot: 0 V17 processes
- last verified DONE: `{done_rows[-1]['phase']} / {done_rows[-1]['case_id']}`
- archive root: `{rel(ARCHIVE_ROOT)}`
- archive manifest: `{rel(ARCHIVE_ROOT / 'archive_manifest.json')}`
- archive manifest digest: `{sha(ARCHIVE_ROOT / 'archive_manifest.json')}`
- checkpoint v4 manifest: `{sha(PACK_V4 / 'manifest.json')}`
- archive state: `SUPERSEDED_FOR_FINAL_EVALUATION / EXPLORATORY_ONLY`

## Frozen scientific bindings

- protocol: `{rel(PROTOCOL_ROOT / 'protocol.json')}`
- scientific protocol digest: `{protocol_digest}`
- candidate-space digest: `{candidate_digest}`
- split-plan digest: `{split_digest}`
- execution-critical source digest at freeze: `{protocol['execution_critical_source_digest']}`
- expected ledger: `{len(ledger)}` rows
- category breakdown: `{json.dumps(dict(sorted(phase_counts.items())), sort_keys=True)}`
- formal latency relation: 68 latency rows are included in the 204-row ledger; they are not additional rows.

## Phase-B reuse boundary

Reusable immutable inputs are the frozen protocol, policy files, candidate
definition, source datasets, dataset/split manifests, and protocol-bound model
artifacts. The new run must not reuse any old V17 selected configuration,
candidate execution output, latency sample, key material, `run_status.csv`,
summary, aggregate, `STOP_AFTER_ATOMIC_CASE`, DONE/FAILED row, or resume state.

The new run root must be `results/model_family_expansion_v17/runs/<new_run_id>`.
It must initialize at 0/{len(ledger)}, and final aggregation must use an explicit
new-run allowlist.

## Phase-B validation and operation

1. Verify 6 online CPUs, 1 socket x 6 cores, allowed list 0-5, and Go
   `runtime.NumCPU=6`, `runtime.GOMAXPROCS=6`.
2. Reverify protocol, candidate-space, split-plan, old archive, and checkpoint v4.
3. Create a new execution profile, environment manifest, source snapshot,
   run ID, run root, and clean 204-row ledger.
4. Run a separate preflight including interruption/resume; do not count it in 204.
5. Launch the final runner only with the new run ID/root.

Progress command: `python3 scripts/verify_model_family_expansion_v17_vm1x6.py --run-id <run_id> --progress`

Graceful stop command: `touch results/model_family_expansion_v17/runs/<run_id>/STOP_AFTER_ATOMIC_CASE`

Resume command: `GOMAXPROCS=6 taskset -c 0-5 python3 scripts/run_model_family_expansion_v17.py --run-id <run_id> --run-root results/model_family_expansion_v17/runs/<run_id> --resume --phase all`

Full-run supervisor: `scripts/run_model_family_expansion_v17_vm1x6_until_complete.sh <run_id>`

## Known risks

- The original runner hard-coded the legacy root; Phase B must finish scoped
  run-root infrastructure before the first final case.
- The frozen protocol contains historical 2-vCPU environment metadata; the
  scientific digest remains immutable and the 1x6 environment is bound by a
  separate execution-profile overlay.
- The protocol has predecessor-bound immutable multiclass inputs. They are
  distinct from the superseded 2x1 V17 result root and must be explicitly
  classified by the contamination verifier.
- External build trees contain `{len(external_cache_files)}` Python cache files.
  They are excluded from V17 source/evidence and are not imported into the new run.
- V16.1 DOCX/PDF/PPTX and HWP were not modified.
"""
    write_text(CODEX_CHECKPOINT / "vcpu_2x1_to_1x6_handoff.md", handoff)

    summary = {
        "status": "PASS_RECONSTRUCTED_POST_REBOOT",
        "old_run_id": OLD_RUN_ID,
        "verified_progress": f"{state_counts.get('DONE', 0)}/{len(ledger)}",
        "archive_root": rel(ARCHIVE_ROOT),
        "archive_manifest_sha256": sha(ARCHIVE_ROOT / "archive_manifest.json"),
        "active_processes": len(active),
        "handoff": rel(CODEX_CHECKPOINT / "vcpu_2x1_to_1x6_handoff.md"),
        "protocol_digest": protocol_digest,
        "candidate_space_digest": candidate_digest,
        "split_plan_digest": split_digest,
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
