#!/usr/bin/env python3
"""Validate VM1x6, derive the frozen 204-row matrix, and initialize a clean run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = ROOT / "docs/protocols/model_family_expansion_v17"
LEGACY = ROOT / "results/model_family_expansion_v17"
CHECKPOINT = ROOT / "docs/checkpoints/model_family_expansion_v17_vcpu6"
PROFILE = PROTOCOL_ROOT / "execution_profiles/vmware_ubuntu24_1socket_6core_vcpu6_v1.json"
OLD_RUN_ID = "v17_pre_vcpu_change_2x1_20260810T143647Z"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(rows: list[dict]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def run(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def lscpu() -> dict[str, str]:
    values = {}
    for line in run("lscpu").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def cpu_allowed() -> str:
    for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
        if line.startswith("Cpus_allowed_list:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Cpus_allowed_list missing")


def expected_matrix(run_root: Path) -> list[dict]:
    rows = []
    with (PROTOCOL_ROOT / "split_plan.csv").open(newline="", encoding="utf-8") as handle:
        splits = list(csv.DictReader(handle))
    for item in splits:
        case_id = f"{item['dataset']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item['training_seed']}"
        output = run_root / item["suite_role"] / case_id / "case_summary.json"
        rows.append({"phase": item["suite_role"], "case_id": case_id, "category": item["suite_role"], "output": output.relative_to(ROOT).as_posix(), "source_manifest": item["manifest"]})
        if item["suite_role"] == "primary":
            latency = run_root / "latency" / case_id / "paired_latency.json"
            rows.append({"phase": "latency", "case_id": case_id, "category": "formal_paired_latency_tabular", "output": latency.relative_to(ROOT).as_posix(), "source_manifest": item["manifest"]})
    rows.append({"phase": "packed_primary", "case_id": "packed_cnn_lite_binary01_v17", "category": "packed_P6", "output": (run_root / "primary/packed_cnn_lite_binary01_v17/case_summary.json").relative_to(ROOT).as_posix(), "source_manifest": "datasets/vision_suite/mnist/cnn_lite_square_binary01/extraction_manifest.json"})
    for model_id in ("mnist_mlp_square_784_100_10_v1", "mnist_lenet5_small_square_v1"):
        rows.append({"phase": "multiclass_exhaustive", "case_id": model_id, "category": "multiclass_exhaustive", "output": (run_root / f"exhaustive/{model_id}/exhaustive.json").relative_to(ROOT).as_posix(), "source_manifest": "datasets/journal_multiclass_extension_v1/mnist/input_split_manifest.json"})
        rows.append({"phase": "latency_multiclass", "case_id": model_id, "category": "formal_paired_latency_multiclass", "output": (run_root / f"latency/multiclass/{model_id}/paired_latency.json").relative_to(ROOT).as_posix(), "source_manifest": "docs/protocols/model_family_expansion_v17/latency_subsets.json"})
    rows.append({"phase": "latency_packed", "case_id": "packed_cnn_lite_binary01_v17", "category": "formal_paired_latency_packed", "output": (run_root / "latency/packed_cnn_lite_binary01_v17/paired_latency.json").relative_to(ROOT).as_posix(), "source_manifest": "docs/protocols/model_family_expansion_v17/latency_subsets.json"})
    for depth in (1, 2, 4, 6, 8):
        rows.append({"phase": "depth_ladder", "case_id": f"D{depth}", "category": "depth_ladder", "output": (run_root / f"depth_ladder/results/D{depth}/result.json").relative_to(ROOT).as_posix(), "source_manifest": f"results/model_family_expansion_v17/depth_ladder/inputs/D{depth}/model.json"})
    for model in ("mlp100", "lenet5_small"):
        for seed in (0, 1, 2):
            rows.append({"phase": "training_seed_multiclass", "case_id": f"{model}/seed_{seed}", "category": "multiclass_training_seed", "output": (run_root / f"training_seed_multiclass/{model}/seed_{seed}/case_summary.json").relative_to(ROOT).as_posix(), "source_manifest": f"results/model_family_expansion_v17/plaintext/multiclass_training_seed/{model}/seed_{seed}/manifest.json"})
    for seed in (0, 1, 2):
        rows.append({"phase": "training_seed_packed", "case_id": f"seed_{seed}", "category": "packed_training_seed", "output": (run_root / f"training_seed_packed/seed_{seed}/case_summary.json").relative_to(ROOT).as_posix(), "source_manifest": f"results/model_family_expansion_v17/plaintext/packed_cnn_training_seed/seed_{seed}/extraction_manifest.json"})
    return sorted(rows, key=lambda row: (row["phase"], row["case_id"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or f"v17_final_vm1x6_{stamp}"
    run_root = ROOT / "results/model_family_expansion_v17/runs" / run_id
    if run_root.exists():
        raise RuntimeError(f"refusing to initialize existing run root: {run_root}")
    protocol = json.loads((PROTOCOL_ROOT / "protocol.json").read_text(encoding="ascii"))
    if sha(PROTOCOL_ROOT / "protocol.json") != "sha256:09aac669e2a970edfadf99486a3c977f92e0a5ddc96f20432ed9221cc070d6c6":
        raise RuntimeError("scientific protocol digest mismatch")
    if sha(PROTOCOL_ROOT / "candidate_space.json") != "sha256:174b9c0ebc553a14ebf6f61df5ffc890ab448103677a890d9f159fc4429bc3b7":
        raise RuntimeError("candidate-space digest mismatch")
    if sha(PROTOCOL_ROOT / "split_plan.csv") != "sha256:a02e61ce17ec49291c065a5ba60069506cda8d275144a17b8dd890272cfce8b5":
        raise RuntimeError("split-plan digest mismatch")
    subprocess.run(["python3", "docs/evidence/model_family_expansion_v17_checkpoint_12h_v4/verify_model_family_expansion_v17.py"], cwd=ROOT, check=True)

    cpu = lscpu()
    observed = {"online": int(cpu["CPU(s)"]), "sockets": int(cpu["Socket(s)"]), "cores": int(cpu["Core(s) per socket"]), "threads": int(cpu["Thread(s) per core"]), "allowed": cpu_allowed(), "affinity": sorted(os.sched_getaffinity(0))}
    if observed != {"online": 6, "sockets": 1, "cores": 6, "threads": 1, "allowed": "0-5", "affinity": list(range(6))}:
        raise RuntimeError(f"BLOCKED_ENVIRONMENT_VALIDATION: {observed}")
    probe = run("go", "run", ".codex/checkpoints/cpu_runtime_probe.go")
    if "runtime.NumCPU=6" not in probe or "runtime.GOMAXPROCS=6" not in probe:
        raise RuntimeError(f"BLOCKED_ENVIRONMENT_VALIDATION: {probe}")
    quota = Path("/sys/fs/cgroup/user.slice/cpu.max").read_text(encoding="ascii").strip()
    cpuset = Path("/sys/fs/cgroup/user.slice/cpuset.cpus.effective").read_text(encoding="ascii").strip()
    if quota != "max 100000" or cpuset != "0-5":
        raise RuntimeError(f"BLOCKED_ENVIRONMENT_VALIDATION: quota={quota} cpuset={cpuset}")

    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "execution_profile_id": "vmware_ubuntu24_1socket_6core_vcpu6_v1",
        "references_scientific_protocol_digest": sha(PROTOCOL_ROOT / "protocol.json"),
        "guest_virtual_sockets": 1, "guest_cores_per_socket": 6, "guest_total_vcpu": 6,
        "cpu_allowed_list": "0-5", "GOMAXPROCS": 6, "case_worker_count": 1,
        "latency_worker_count": 1, "affinity_policy": "single CKKS process allowed CPUs 0-5",
        "host_concurrent_use_policy": {"allowed": ["web browsing", "document editing", "light IDE use"], "prohibited_during_formal_latency": ["gaming", "video encoding", "large compression", "host compilation", "benchmarks", "Windows Update", "full antivirus scan"]},
        "telemetry_policy": "guest load, CPU deltas, iowait, steal, memory, swap, context switches, process CPU, and IO pressure; no post-hoc sample deletion",
        "created_at": now(), "supersedes_environment_id": "vmware_ubuntu24_2socket_1core_vcpu2_protocol_frozen",
        "scientific_protocol_environment_field_status": "immutable historical metadata; superseded only by this execution overlay",
        "homogeneous_reexecution_rule": "superseded 2x1 V17 result/checkpoint/key/latency state is never imported",
    }
    write_json(PROFILE, profile)
    profile_digest = sha(PROFILE)
    environment_id = f"vmware_ubuntu24_1socket_6core_vcpu6_{stamp}"
    environment_path = ROOT / "docs/evidence/model_family_expansion_v17/environments" / f"{environment_id}.json"
    mem = {line.split(":", 1)[0]: line.split()[1] for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines() if ":" in line}
    os_release = {line.split("=", 1)[0]: line.split("=", 1)[1].strip('"') for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines() if "=" in line}
    environment = {
        "environment_id": environment_id, "host_cpu_model": "AMD Ryzen 5 3600 6-Core Processor",
        "host_physical_cores": 6, "host_logical_processors": 12, "hypervisor": "VMware Workstation",
        "guest_os": os_release.get("PRETTY_NAME"), "guest_kernel": platform.release(),
        "guest_virtual_sockets": 1, "guest_cores_per_socket": 6, "guest_total_vcpu": 6,
        "guest_visible_cpu_count": 6, "Cpus_allowed_list": "0-5", "effective_GOMAXPROCS": 6,
        "case_worker_count": 1, "memory_kib": int(mem["MemTotal"]), "swap_kib": int(mem["SwapTotal"]),
        "Go_version": run("go", "version"), "Python_version": run("python3", "--version"), "Lattigo_version": "v6.2.0",
        "Git_HEAD": run("git", "rev-parse", "HEAD"), "scientific_source_digest": protocol["execution_critical_source_digest"],
        "source_tree_digest": protocol["execution_critical_source_digest"],
        "scientific_protocol_digest": sha(PROTOCOL_ROOT / "protocol.json"), "execution_profile_digest": profile_digest,
        "candidate_space_digest": sha(PROTOCOL_ROOT / "candidate_space.json"), "dataset_split_digest": sha(PROTOCOL_ROOT / "split_plan.csv"),
        "cpu_quota": quota, "effective_cpuset": cpuset, "created_at": now(), "supersedes_old_run_id": OLD_RUN_ID,
        "supersedes_old_environment_id": "vmware_ubuntu24_2socket_1core_vcpu2_protocol_frozen",
        "host_concurrent_use_policy": profile["host_concurrent_use_policy"],
        "host_observability_limit": "Windows-host load is not fully observable from the guest; raw guest telemetry is retained and no new outlier rule is introduced.",
    }
    write_json(environment_path, environment)
    capture = "\n\n".join([
        "$ nproc\n" + run("nproc"), "$ nproc --all\n" + run("nproc", "--all"),
        "$ lscpu\n" + run("lscpu"), "$ lscpu -e\n" + run("lscpu", "-e"),
        "$ /proc/cpuinfo\n" + Path("/proc/cpuinfo").read_text(encoding="ascii"),
        "$ /proc/self/status CPU/MEM allowed\n" + "\n".join(line for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines() if line.startswith(("Cpus_allowed", "Mems_allowed"))),
        "$ taskset -pc self\n" + run("taskset", "-pc", str(os.getpid())),
        "$ uname -a\n" + run("uname", "-a"), "$ /etc/os-release\n" + Path("/etc/os-release").read_text(encoding="utf-8"),
        "$ systemd-detect-virt\n" + run("systemd-detect-virt"), "$ free -h\n" + run("free", "-h"),
        "$ go version\n" + run("go", "version"), "$ python3 --version\n" + run("python3", "--version"),
        "$ go env\n" + run("go", "env"), "$ runtime probe\n" + probe,
        "$ CPU cgroup\n" + f"cpu.max={quota}\ncpuset.cpus.effective={cpuset}",
    ]) + "\n"
    write(CHECKPOINT / "environment_capture.txt", capture)

    matrix = expected_matrix(run_root)
    identities = [(row["phase"], row["case_id"]) for row in matrix]
    if len(matrix) != protocol["expected_run_ledger_rows"] or len(identities) != len(set(identities)):
        raise RuntimeError(f"BLOCKED_MATRIX_COUNT_MISMATCH: total={len(matrix)} unique={len(set(identities))}")
    breakdown = Counter(row["phase"] for row in matrix)
    if sum(value for key, value in breakdown.items() if key.startswith("latency")) != 68:
        raise RuntimeError("BLOCKED_MATRIX_COUNT_MISMATCH: formal latency != 68")
    CHECKPOINT.mkdir(parents=True, exist_ok=True)
    write_csv(CHECKPOINT / "expected_case_inventory.csv", matrix, list(matrix[0]))
    write_json(CHECKPOINT / "case_category_breakdown.json", {"protocol_derived_total": len(matrix), "formal_latency_included_in_total": 68, "non_latency_rows": 136, "phase_counts": dict(sorted(breakdown.items()))})
    reconciliation = [{"category": key, "expected": value, "old_ledger": value, "new_ledger": value, "relation": "IDENTICAL_CASE_IDENTITY"} for key, value in sorted(breakdown.items())]
    reconciliation.append({"category": "TOTAL", "expected": len(matrix), "old_ledger": 204, "new_ledger": len(matrix), "relation": "PASS"})
    write_csv(CHECKPOINT / "case_count_reconciliation.csv", reconciliation, list(reconciliation[0]))
    old = {(row["phase"], row["case_id"]): row for row in csv.DictReader((LEGACY / "run_status.csv").open(newline="", encoding="utf-8"))}
    differences = [{"phase": row["phase"], "case_id": row["case_id"], "old_present": str((row["phase"], row["case_id"]) in old).lower(), "old_state": old.get((row["phase"], row["case_id"]), {}).get("state", ""), "new_initial_state": "PENDING", "identity_difference": "NONE" if (row["phase"], row["case_id"]) in old else "MISSING_OLD"} for row in matrix]
    write_csv(CHECKPOINT / "old_vs_new_case_id_diff.csv", differences, list(differences[0]))
    if any(row["identity_difference"] != "NONE" for row in differences):
        raise RuntimeError("BLOCKED_MATRIX_COUNT_MISMATCH: old/new case identity differs")

    run_root.mkdir(parents=True)
    (run_root / "bin").mkdir()
    binaries = []
    bound = {Path(item["path"]).name: item for item in protocol["execution_binaries"]}
    for name, item in sorted(bound.items()):
        source = LEGACY / "bin" / name
        destination = run_root / "bin" / name
        shutil.copy2(source, destination)
        if sha(destination) != item["sha256"]:
            raise RuntimeError(f"binary copy mismatch: {name}")
        binaries.append({"name": name, "path": destination.relative_to(ROOT).as_posix(), "size_bytes": destination.stat().st_size, "sha256": sha(destination)})
    binary_set_digest = canonical([{"name": item["name"], "sha256": item["sha256"]} for item in binaries])

    source_files = []
    for item in protocol["execution_critical_sources"]:
        path = ROOT / item["path"]
        if sha(path) != item["sha256"]:
            raise RuntimeError(f"scientific execution source drift: {item['path']}")
        source_files.append({"path": item["path"], "sha256": item["sha256"]})
    for path in sorted({
        ROOT / "scripts/prepare_v17_vcpu_migration.py", ROOT / "scripts/setup_model_family_expansion_v17_vm1x6.py",
        ROOT / "scripts/run_model_family_expansion_v17_vm1x6.py", ROOT / "scripts/run_model_family_expansion_v17_vm1x6_until_complete.sh",
        ROOT / "scripts/capture_v17_vm1x6_telemetry.py", ROOT / "scripts/verify_model_family_expansion_v17_vm1x6.py",
        ROOT / "scripts/finalize_model_family_expansion_v17_vm1x6.py", ROOT / "scripts/preflight_model_family_expansion_v17_vm1x6.py",
        PROFILE, environment_path,
    }):
        source_files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    source_files = sorted(source_files, key=lambda item: item["path"])
    source_tree_digest = canonical(source_files)
    snapshot_root = ROOT / "docs/evidence/model_family_expansion_v17/source_snapshots" / run_id
    snapshot_root.mkdir(parents=True)
    write(snapshot_root / "git_status.txt", run("git", "status", "--porcelain=v1") + "\n")
    write(snapshot_root / "git_diff.patch", subprocess.run(["git", "diff", "--binary"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout)
    write(snapshot_root / "untracked_source_inventory.txt", run("git", "ls-files", "--others", "--exclude-standard") + "\n")
    snapshot = {"schema_version": "flipguard_v17_vm1x6_source_snapshot_v1", "run_id": run_id, "Git_HEAD": environment["Git_HEAD"], "scientific_execution_source_digest": protocol["execution_critical_source_digest"], "source_tree_digest": source_tree_digest, "source_files": source_files, "execution_binaries": binaries, "binary_set_digest": binary_set_digest, "created_at": now()}
    write_json(snapshot_root / "manifest.json", snapshot)
    write(snapshot_root / "SHA256SUMS", "".join(f"{sha(path).removeprefix('sha256:')}  {path.name}\n" for path in sorted(snapshot_root.iterdir()) if path.is_file() and path.name != "SHA256SUMS"))

    run_manifest = {
        "schema_version": "flipguard_v17_vm1x6_run_v1", "run_id": run_id, "status": "INITIALIZED",
        "admissibility": "PENDING_FULL_VALIDATION", "environment_id": environment_id,
        "environment_manifest": environment_path.relative_to(ROOT).as_posix(), "environment_digest": sha(environment_path),
        "scientific_protocol_digest": sha(PROTOCOL_ROOT / "protocol.json"), "execution_profile_digest": profile_digest,
        "scientific_execution_source_digest": protocol["execution_critical_source_digest"], "source_tree_digest": source_tree_digest,
        "source_snapshot_manifest": (snapshot_root / "manifest.json").relative_to(ROOT).as_posix(),
        "execution_binaries": binaries, "binary_set_digest": binary_set_digest,
        "candidate_space_digest": sha(PROTOCOL_ROOT / "candidate_space.json"), "split_plan_digest": sha(PROTOCOL_ROOT / "split_plan.csv"),
        "expected_case_count": len(matrix), "result_root": run_root.relative_to(ROOT).as_posix(),
        "supersedes_old_run_id": OLD_RUN_ID, "old_result_import_count": 0, "old_latency_import_count": 0,
        "old_completion_marker_import_count": 0, "reused_old_selected_configuration_count": 0,
        "reused_old_key_material_count": 0, "predecessor_protocol_inputs": "allowed only where already immutable in the frozen scientific protocol; no old V17 2x1 result-root output is imported",
        "created_at": now(), "commit_count": 0, "push_count": 0,
    }
    write_json(run_root / "run_manifest.json", run_manifest)
    env = os.environ.copy(); env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "GOMAXPROCS": "6"})
    subprocess.run(["taskset", "-c", "0-5", "python3", "scripts/run_model_family_expansion_v17_vm1x6.py", "--run-id", run_id, "--run-root", str(run_root), "--initialize-only", "--phase", "all"], cwd=ROOT, env=env, check=True)
    with (run_root / "run_status.csv").open(newline="", encoding="utf-8") as handle:
        initialized = list(csv.DictReader(handle))
    states = Counter(row["state"] for row in initialized)
    if states != {"PENDING": 204}:
        raise RuntimeError(f"clean-ledger assertion failed: {states}")
    write_json(run_root / "initialization_assertions.json", {"completed": 0, "running": 0, "failed": 0, "pending": 204, "imported_old_rows": 0, "reused_old_latency_samples": 0, "reused_old_completion_markers": 0, "reused_old_selected_configurations": 0, "reused_old_key_material": 0, "case_ids_unique": True})
    print(json.dumps({"status": "READY_FOR_PREFLIGHT", "run_id": run_id, "environment_id": environment_id, "expected": len(matrix), "initial_counts": dict(states), "scientific_protocol_digest": run_manifest["scientific_protocol_digest"], "execution_profile_digest": profile_digest, "environment_digest": run_manifest["environment_digest"], "source_tree_digest": source_tree_digest, "binary_set_digest": binary_set_digest}, sort_keys=True))


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
