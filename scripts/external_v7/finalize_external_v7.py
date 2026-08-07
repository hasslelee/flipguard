#!/usr/bin/env python3
"""Prepare and freeze the V7 checkpoint at its declared wall-clock boundary."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from build_external_v7_evidence import build as build_normalized
from build_publication_inputs_v7 import build as build_publication_inputs


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"
RESULTS = ROOT / "results/thesis_grade_protocol/external_end_to_end_code_v7"
PREPARED = RESULTS / "prepared-final-v4"
VERIFIER = EVIDENCE / "verify_external_end_to_end_code_v7.py"
FINAL_WINDOW = dt.timedelta(minutes=30)
SECURITY_POLICY_PATH = Path(
    "docs/evidence/security_v2_static_attestation_formal_v2/security_policy_v2.json"
)
DIRECT_POLICY_PATH = Path(
    "docs/evidence/security_v2_static_attestation_formal_v2/direct_synthesis_policy_v2.json"
)


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_once_or_verify(path: Path, content: str) -> None:
    if path.exists():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"refusing to overwrite nonidentical evidence: {path}")
        return
    write_text_atomic(path, content)


def write_json_once_or_verify(path: Path, payload: Any) -> None:
    write_text_once_or_verify(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


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
    raw_files = []
    for path in sorted(item for item in (ROOT / "external/v7/outputs").rglob("*") if item.is_file()):
        raw_files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    stage_manifest_paths = sorted((ROOT / "external/v7/status").glob("*/*/run_manifest.json"))
    stage_manifests = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in stage_manifest_paths
    ]
    return {
        "schema_version": "flipguard_external_v7_raw_result_index_v1",
        "source_commit": source_commit,
        "raw_output_root": "external/v7/outputs",
        "output_manifest_count": len(manifests),
        "output_manifests": manifests,
        "raw_file_count": len(raw_files),
        "raw_files": raw_files,
        "stage_manifest_count": len(stage_manifests),
        "stage_manifests": stage_manifests,
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
        report = json.loads(marker.read_text(encoding="utf-8"))
        current_commit = git_output("rev-parse", "HEAD")
        if report["source_commit"] != current_commit:
            raise RuntimeError("prepared V7 evidence source commit drift")
        current_index = raw_result_index(current_commit)
        prepared_index = load_json(destination / "raw_result_index.json")
        if prepared_index != current_index:
            raise RuntimeError("prepared V7 raw result index drift")
        return report
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
    destination.parent.mkdir(parents=True, exist_ok=True)
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
    disk = shutil.disk_usage(ROOT)
    filesystem = os.statvfs(ROOT)
    meminfo = {
        line.split(":", 1)[0]: int(line.split()[1])
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        if line.startswith(("MemAvailable:", "SwapTotal:", "SwapFree:"))
    }
    free_gib = disk.free / (1024 ** 3)
    inode_free_percent = filesystem.f_favail / filesystem.f_files * 100 if filesystem.f_files else 0
    if free_gib < 25 or inode_free_percent < 10:
        resource_gate = "HARD_RESOURCE_STOP"
    elif free_gib < 45:
        resource_gate = "RED"
    elif free_gib < 65:
        resource_gate = "YELLOW"
    else:
        resource_gate = "GREEN"
    try:
        docker_system_df = subprocess.check_output(
            ["docker", "system", "df", "--format", "{{json .}}"],
            cwd=ROOT,
            text=True,
            timeout=30,
        ).splitlines()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        docker_system_df = ["NOT_SEPARATELY_RECORDED"]
    pids = []
    for row in resources:
        if row["pid"] not in pids:
            pids.append(row["pid"])
    return {
        "schema_version": "flipguard_external_v7_environment_end_v1",
        "finalization_timestamp": finalization_timestamp,
        "declared_hard_pause_timestamp": (STATUS / "hard_pause_timestamp.txt").read_text().strip(),
        "source_commit": source_commit,
        "origin_commit": git_output("rev-parse", "origin/experiments/external-e2e-code-v7"),
        "branch": git_output("branch", "--show-current"),
        "pre_freeze_working_tree_porcelain": git_output("status", "--short"),
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_free_bytes": disk.free,
        "inode_free": filesystem.f_favail,
        "inode_total": filesystem.f_files,
        "memory_available_kib": meminfo.get("MemAvailable", 0),
        "swap_used_kib": meminfo.get("SwapTotal", 0) - meminfo.get("SwapFree", 0),
        "resource_gate": resource_gate,
        "docker_system_df": docker_system_df,
        "last_periodic_resource_sample_timestamp": last["timestamp"],
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
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(downtime_rows())
    write_text_once_or_verify(path, handle.getvalue())


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
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_text_once_or_verify(path, handle.getvalue())


def checkpoint_report(claims: dict[str, Any], environment: dict[str, Any]) -> str:
    def rows(name: str) -> list[dict[str, str]]:
        with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def compact(values: list[str]) -> str:
        return "; ".join(values) if values else "NONE"

    def numeric_sum(records: list[dict[str, str]], field: str) -> int:
        return sum(int(row[field]) for row in records if row[field].isdigit())

    start_environment = load_json(EVIDENCE / "environment_start.json")
    levels = {row["system"]: row for row in rows("artifact_execution_levels.csv")}
    source_rows = rows("source_checkout_manifest.csv")
    build_rows = rows("clean_build_matrix.csv")
    pipeline_rows = rows("official_pipeline_matrix.csv")
    native_rows = rows("native_execution_records.csv")
    accounting = rows("execution_accounting.csv")
    latency = rows("latency_summary.csv")
    numerical = rows("numerical_error_summary.csv")
    gate_rows = rows("provider_gate_records.csv")
    audit_rows = rows("audit_records.csv")
    security = rows("security_summary.csv")
    portability = rows("portability_summary.csv")
    failures = rows("failure_summary.csv")
    predecessor = rows("predecessor_comparison.csv")
    workload_contracts = load_json(EVIDENCE / "workload_contracts/manifest.json")["contracts"]
    per_sample = load_json(EVIDENCE / "per_sample_outputs/manifest.json")
    start = dt.datetime.fromisoformat(start_environment["autonomous_start_timestamp"])
    end = dt.datetime.fromisoformat(environment["finalization_timestamp"])
    encrypted = [row["system"] for row in levels.values() if int(row["evidence_level"]) >= 3]
    multi_sample = sorted({row["system"] for row in native_rows if int(row["evidence_level"]) >= 4})
    workloads = [
        f"{row['system']}={row['workload']}" for row in accounting
        if row["workload"] not in {"NOT_EVALUATED", "NOT_REPORTED"}
    ]
    selected = [
        f"{row['provider']}:{row['candidate_id']} ({row['final_flipguard_state']})"
        for row in gate_rows if row["audit_status"] == "SAFE"
    ]
    latency_lines = [
        f"{row['provider']}/{row['workload']}: mean_total_ms={row['mean_total_ms']}, "
        f"mean_eval_ms={row['mean_evaluation_ms']}, boundary={row['timing_boundary']}"
        for row in latency
    ]
    numerical_lines = [
        f"{row['provider']}/{row['arm']}: rms={row['rms_error']}, "
        f"max_abs={row['max_absolute_error']}, gate={row['gate_state']}"
        for row in numerical
    ]
    admitted = [key for key, value in claims["claims"].items() if value["paper_admitted"]]
    blocked = [key for key, value in claims["claims"].items() if not value["paper_admitted"]]
    tables = len(list((EVIDENCE / "tables").glob("*.csv"))) if (EVIDENCE / "tables").is_dir() else 0
    figures = len(list((EVIDENCE / "figures").glob("*.svg"))) if (EVIDENCE / "figures").is_dir() else 0
    total_rows = per_sample["total_rows"]
    return f"""# External End-to-End Code V7 Checkpoint

1. **Start/end/elapsed**: {start.isoformat()} / {end.isoformat()} / {(end - start).total_seconds():.3f} seconds.
2. **VM, Code/Codex, service continuity**: VM downtime `{environment['vm_downtime']}`; Code/Codex downtime `{environment['code_codex_downtime']}`; service restarts {environment['service_restart_count']} across {environment['service_instance_count']} instances.
3. **Branch/source/origin/tree**: `{environment['branch']}`; source `{environment['source_commit']}`; origin `{environment['origin_commit']}`; pre-freeze porcelain `{environment['pre_freeze_working_tree_porcelain'] or 'CLEAN'}`.
4. **Commits**: execution and orchestration history is preserved on the branch; the final evidence commit is created after this report is checksummed.
5. **Resources**: disk free {start_environment['disk_free_bytes']} -> {environment['disk_free_bytes']} bytes; inodes {start_environment['inode_free']} -> {environment['inode_free']}; memory available {start_environment['memory_available_kib']} -> {environment['memory_available_kib']} KiB; swap used {start_environment['swap_used_kib']} -> {environment['swap_used_kib']} KiB; final gate `{environment['resource_gate']}`.
6. **Official artifacts attempted/available**: {len(levels)} systems classified; source checkout PASS rows {sum(row['state'] == 'PASS' for row in source_rows)}.
7. **Clean builds passed**: {sum(row['state'] == 'PASS' for row in build_rows)} of {len(build_rows)} clean-build stage rows.
8. **Official pipelines passed**: {sum(row['state'] == 'PASS' for row in pipeline_rows)} of {len(pipeline_rows)} encrypted/official pipeline stage rows.
9. **Encrypted E2E systems**: {len(encrypted)}: {compact(encrypted)}.
10. **Multi-sample E2E systems**: {len(multi_sample)}: {compact(multi_sample)}.
11. **Decision-bearing providers**: {claims['decision_bearing_provider_count']}.
12. **Locked-audit providers**: {claims['locked_audit_provider_count']}.
13. **Provider-specific workloads**: {compact(workloads)}.
14. **Unique inputs by system**: {compact([f"{row['system']}={row['unique_inputs']}" for row in accounting])}.
15. **Validation/audit counts**: {compact([f"{row['provider']}={row['validation_samples']}/{row['audit_samples']}" for row in accounting])}.
16. **Context/keyset counts**: {compact([f"{row['system']}={row['contexts_keysets']}" for row in accounting])}.
17. **Measurement pass counts**: {compact([f"{row['system']}={row['measurement_passes']}" for row in accounting])}.
18. **Raw output rows**: normalized per-sample/plan rows {total_rows}; by source {json.dumps(per_sample['row_counts'], sort_keys=True)}.
19. **Graph identity states**: {compact([f"{row['provider']}:{row['workload_id']}={row['graph_identity']}" for row in workload_contracts])}.
20. **Selected configurations**: {compact(selected)}.
21. **Plans generated/executed**: {numeric_sum(accounting, 'plans_generated')}/{numeric_sum(accounting, 'plans_executed')}.
22. **Build/compile/tuning wall-clock**: {compact([f"{row['system']}={row['build_wall_clock_seconds']}/{row['compile_wall_clock_seconds']}/{row['tuning_wall_clock_seconds']} s" for row in accounting])}.
23. **Native evaluation and total latency**: {compact(latency_lines)}. No cross-runtime algorithm-only ratio is admitted.
24. **Numerical errors**: {compact(numerical_lines)}.
25. **Validation flips**: {compact([f"{row['candidate_id']}={row['validation_flips']}" for row in gate_rows])}.
26. **Audit flips**: {compact([f"{row['candidate_id']}={row['audit_flips']}" for row in audit_rows])}.
27. **Provider plus FlipGuard states**: {compact([f"{row['candidate_id']}={row['final_flipguard_state']}" for row in gate_rows])}.
28. **Security states**: {compact(sorted({row['security_state'] for row in security}))}; security-headline eligible rows {sum(row['headline_eligible'] == 'True' for row in security)}.
29. **PORTABLE_EXACT count**: {claims['portable_exact_count']}.
30. **GRAPH_EQUIVALENT_COMMON_EXECUTOR count**: {sum(row['graph_equivalent_common_executor'] == 'True' for row in portability)}.
31. **Common-executor paired results**: none; the common-executor record table is header-only.
32. **Fastest stable candidate per exact shared workload**: {compact(selected)}; no cross-runtime shared-workload winner is asserted.
33. **Predecessor vs V7**: {compact([f"{row['predecessor']}: {row['difference']}" for row in predecessor])}.
34. **Blockers**: {compact([f"{row['provider']}/{row['run_id']}={row['reason_code']}" for row in failures])}.
35. **Actual accounting totals**: encrypted candidate runs {numeric_sum(accounting, 'encrypted_candidate_runs')}; raw normalized rows {total_rows}; missing quantities remain explicit states.
36. **Generated tables/figures**: {tables}/{figures}; generation is restricted to the final 30-minute window and actual V7 records.
37. **Evidence manifest SHA-256**: bound by `manifest.json`, `content_tree_sha256`, and `SHA256SUMS` after this report is written.
38. **Admitted scoped claims**: {compact(admitted)}.
39. **Blocked/not-evaluated claims**: {compact(blocked)}.
40. **Final classification**: `{claims['final_classification']}`; paper claim gate remains `false`.
41. **Tests/verifiers**: normalized evidence verifier PASS before freeze; final SHA, policy, repository, Python, shell, and Go gates run in persistent final QA after freeze.
42. **Manuscript impact**: external evidence is scoped and auxiliary; unlike native timing boundaries are not promoted to a speedup claim.
43. **Exact remaining work**: manuscript integration remains paused; no additional experiment is auto-started.
44. **RUN DISPOSITION**: `PAUSE_AT_24H_CHECKPOINT`.
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
    environment_path = EVIDENCE / "environment_end.json"
    if environment_path.is_file():
        environment = load_json(environment_path)
        if environment["source_commit"] != source_commit:
            raise RuntimeError("existing V7 environment-end source commit drift")
    else:
        environment = environment_end(source_commit, now().isoformat(timespec="seconds"))

    generated_files = [
        path for path in sorted(PREPARED.rglob("*"))
        if path.is_file() and path.relative_to(PREPARED).as_posix() != "prepare_report.json"
    ]
    for source in generated_files:
        copy_or_verify(source, EVIDENCE / source.relative_to(PREPARED))
    copy_or_verify(STATUS / "resource_samples.csv", EVIDENCE / "resource_samples_raw.csv")

    write_json_once_or_verify(EVIDENCE / "environment_end.json", environment)
    write_downtime(EVIDENCE / "downtime_and_restart_log.csv")
    write_predecessor_comparison(EVIDENCE / "predecessor_comparison.csv")
    claims = json.loads((EVIDENCE / "claim_admission.json").read_text(encoding="utf-8"))
    write_text_once_or_verify(EVIDENCE / "CHECKPOINT_REPORT.md", checkpoint_report(claims, environment))

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
        "policy_bindings": {
            "security_policy": {
                "path": SECURITY_POLICY_PATH.as_posix(),
                "artifact_sha256": sha256(ROOT / SECURITY_POLICY_PATH),
                "policy_sha256": load_json(ROOT / SECURITY_POLICY_PATH)["policy_sha256"],
            },
            "direct_policy": {
                "path": DIRECT_POLICY_PATH.as_posix(),
                "artifact_sha256": sha256(ROOT / DIRECT_POLICY_PATH),
                "policy_sha256": load_json(ROOT / DIRECT_POLICY_PATH)["policy_sha256"],
            },
        },
    }
    write_json_once_or_verify(EVIDENCE / "manifest.json", manifest)
    sums = checksum_lines(EVIDENCE, {"SHA256SUMS"})
    write_text_once_or_verify(EVIDENCE / "SHA256SUMS", "\n".join(sums) + "\n")
    verification = run_verifier(EVIDENCE)
    return {"manifest": manifest, "verification": verification}


def prepare_finalization() -> dict[str, Any]:
    pause = read_time("hard_pause_timestamp.txt")
    if now() < pause - FINAL_WINDOW:
        raise RuntimeError(f"V7 final preparation is blocked until {(pause - FINAL_WINDOW).isoformat()}")
    if now() >= pause:
        return freeze()
    report = prepare(PREPARED)
    publication = build_publication_inputs(PREPARED)
    run_verifier(PREPARED)
    return {**report, "publication_inputs": publication}


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
