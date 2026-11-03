#!/usr/bin/env python3
"""Sequential, logged, resumable V17 encrypted tabular/depth execution."""

import argparse
import csv
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_RESULTS = ROOT / "results/model_family_expansion_v17"
RESULTS = LEGACY_RESULTS
INPUTS = LEGACY_RESULTS
PROTOCOL = ROOT / "docs/protocols/model_family_expansion_v17/protocol.json"
STATUS = RESULTS / "run_status.csv"
STOP_REQUEST = RESULTS / "STOP_AFTER_ATOMIC_CASE"
RUN_MANIFEST = RESULTS / "run_manifest.json"
RUN_ID = "legacy_unscoped"
ENVIRONMENT_ID = "legacy_protocol_environment"
FIELDS = ["phase", "case_id", "state", "started_at", "completed_at", "attempts", "command_sha256", "output", "reason"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_suffix(path.suffix + ".tmp")
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    target.replace(path)


def write_eta_checkpoint(rows: dict[tuple[str, str], dict[str, str]]) -> None:
    terminal = [row for row in rows.values() if row.get("state") in {"DONE", "FAILED_RECORDED", "UNSUPPORTED_RECORDED"}]
    completed = len(terminal)
    if completed not in {5, 10}:
        return
    destination = ROOT / f"docs/checkpoints/model_family_expansion_v17_vcpu6/ETA_AFTER_{completed}_CASES.md"
    if destination.is_file():
        return
    manifest = json.loads(RUN_MANIFEST.read_text(encoding="ascii"))
    started_text = manifest.get("full_run_started_at") or manifest["created_at"]
    started = datetime.fromisoformat(started_text.replace("Z", "+00:00"))
    elapsed_seconds = max(1.0, (datetime.now(timezone.utc) - started).total_seconds())
    durations: dict[str, list[float]] = {}
    for row in terminal:
        if not row.get("started_at") or not row.get("completed_at"):
            continue
        left = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
        right = datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00"))
        durations.setdefault(row["phase"], []).append((right - left).total_seconds())
    telemetry_path = RESULTS / "telemetry/telemetry.csv"
    telemetry_rows = []
    if telemetry_path.is_file():
        import csv
        with telemetry_path.open(newline="", encoding="ascii") as handle:
            telemetry_rows = list(csv.DictReader(handle))
    def average(field: str) -> float | None:
        values = [float(row[field]) for row in telemetry_rows if row.get(field) not in {None, ""}]
        return sum(values) / len(values) if values else None
    throughput = completed / (elapsed_seconds / 3600)
    remaining = 204 - completed
    predicted_correctness_hours = remaining / throughput if throughput else None
    old_throughput = 14 / 12.545555555555556
    document = f"""# ETA after {completed} terminal cases

- run ID: `{RUN_ID}`
- environment ID: `{ENVIRONMENT_ID}`
- elapsed wall-clock hours: `{elapsed_seconds / 3600:.6f}`
- terminal case throughput per hour: `{throughput:.6f}`
- worker count: `1`
- case-level concurrency: `0`
- old 2x1 engineering throughput per hour: `{old_throughput:.6f}`
- observed 1x6 / old 2x1 engineering throughput ratio: `{throughput / old_throughput:.6f}`
- mean iowait ticks per telemetry interval: `{average('cpu_iowait_delta')}`
- mean steal ticks per telemetry interval: `{average('cpu_steal_delta')}`
- predicted remaining total-ledger hours at observed throughput: `{predicted_correctness_hours}`
- predicted formal latency time: `not separately extrapolated until correctness timing is terminal`
- uncertainty: `high; family costs are heterogeneous and no 3x CPU-speed assumption is used`
- per-phase observed seconds: `{json.dumps({key: values for key, values in sorted(durations.items())}, sort_keys=True)}`

This comparison is operational ETA evidence only and is not a paper performance result.
"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")


def command_inputs(command: list[str]) -> list[dict[str, str | int]]:
    inputs = []
    for value in command:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            continue
        inputs.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest_file(path),
        })
    return inputs


def result_binding(phase: str, case_id: str, command: list[str], output: Path, started_at: str, completed_at: str) -> None:
    manifest = json.loads(RUN_MANIFEST.read_text(encoding="ascii"))
    binaries = []
    for item in command_inputs(command):
        if "/bin/flipguard-v17-" in item["path"]:
            binaries.append(item)
    binding = {
        "schema_version": "flipguard_v17_vm1x6_case_binding_v1",
        "run_id": RUN_ID,
        "environment_id": ENVIRONMENT_ID,
        "guest_virtual_sockets": 1,
        "guest_cores_per_socket": 6,
        "total_vcpu": 6,
        "phase": phase,
        "case_id": case_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "scientific_protocol_digest": manifest["scientific_protocol_digest"],
        "execution_profile_digest": manifest["execution_profile_digest"],
        "source_tree_digest": manifest["source_tree_digest"],
        "candidate_space_digest": manifest["candidate_space_digest"],
        "split_plan_digest": manifest["split_plan_digest"],
        "command_sha256": digest_text(" ".join(command)),
        "execution_binaries": binaries,
        "input_bindings": command_inputs(command),
        "output": output.relative_to(ROOT).as_posix(),
        "output_sha256": digest_file(output),
        "telemetry_reference": (RESULTS / "telemetry/telemetry.csv").relative_to(ROOT).as_posix(),
        "old_v17_result_import_count": 0,
        "old_v17_latency_import_count": 0,
        "old_v17_completion_marker_import_count": 0,
    }
    write_json_atomic(output.parent / "result_binding.json", binding)


def active_flipguard_binaries() -> list[dict[str, str | int]]:
    active = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid(): continue
        try:
            parts = (entry / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if not parts or not parts[0]: continue
        executable = Path(parts[0].decode("utf-8", errors="replace")).name
        if executable.startswith("flipguard-") or executable == "flipguard":
            active.append({"pid": int(entry.name), "executable": executable, "command_sha256": digest_text(" ".join(part.decode("utf-8", errors="replace") for part in parts if part))})
    return sorted(active, key=lambda item: int(item["pid"]))


def load_status() -> dict[tuple[str, str], dict[str, str]]:
    if not STATUS.is_file(): return {}
    with STATUS.open(newline="", encoding="utf-8") as handle:
        return {(row["phase"], row["case_id"]): row for row in csv.DictReader(handle)}


def save_status(rows: dict[tuple[str, str], dict[str, str]]) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    target = STATUS.with_suffix(".csv.tmp")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows[key] for key in sorted(rows))
    target.replace(STATUS)


def update(rows, phase, case_id, **values) -> None:
    key = (phase, case_id)
    current = rows.get(key, {field: "" for field in FIELDS})
    current.update({"phase": phase, "case_id": case_id}, **{name: str(value) for name, value in values.items()})
    rows[key] = current; save_status(rows)


def recover_stale_running(rows: dict[tuple[str, str], dict[str, str]]) -> None:
    if active_flipguard_binaries():
        return
    for (phase, case_id), row in rows.items():
        if row.get("state") != "RUNNING":
            continue
        row["state"] = "PENDING"
        row["completed_at"] = now()
        row["reason"] = "stale_running_recovered_without_active_binary"
    save_status(rows)


def stop_requested() -> bool:
    return STOP_REQUEST.is_file()


def run_atomic(rows, phase: str, case_id: str, command: list[str], expected: Path) -> None:
    key = (phase, case_id)
    existing_state = rows.get(key, {}).get("state")
    if existing_state in {"FAILED_RECORDED", "UNSUPPORTED_RECORDED"}:
        return
    if expected.is_file():
        binding = expected.parent / "result_binding.json"
        if RUN_ID != "legacy_unscoped" and not binding.is_file():
            raise RuntimeError(f"scoped result is missing its binding: {expected}")
        update(rows, phase, case_id, state="DONE", completed_at=rows.get(key, {}).get("completed_at") or now(), output=expected.relative_to(ROOT).as_posix(), reason="verified_existing_checkpoint")
        return
    attempts = int(rows.get(key, {}).get("attempts") or 0) + 1
    command_text = " ".join(command)
    started = now()
    update(rows, phase, case_id, state="RUNNING", started_at=started, completed_at="", attempts=attempts, command_sha256=digest_text(command_text), output=expected.relative_to(ROOT).as_posix(), reason="")
    write_json_atomic(RESULTS / "current_case.json", {"phase": phase, "case_id": case_id, "state": "RUNNING", "started_at": started})
    log = RESULTS / "logs" / phase / f"{case_id.replace('/', '__')}.attempt{attempts}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("x", encoding="utf-8") as handle:
        handle.write(f"started_at={started}\ncommand_sha256={digest_text(command_text)}\ncommand={command_text}\n")
        handle.flush()
        completed = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True)
        handle.write(f"completed_at={now()}\nexit_code={completed.returncode}\n")
    if completed.returncode == 0 and expected.is_file():
        completed_at = now()
        result_binding(phase, case_id, command, expected, started, completed_at)
        update(rows, phase, case_id, state="DONE", completed_at=completed_at, reason="", output=expected.relative_to(ROOT).as_posix())
    elif completed.returncode == 75:
        update(rows, phase, case_id, state="PENDING", completed_at=now(), reason=f"durable_key_run_checkpoint;log={log.relative_to(ROOT)}")
    else:
        update(rows, phase, case_id, state="FAILED_RECORDED", completed_at=now(), reason=f"exit_code={completed.returncode};log={log.relative_to(ROOT)}")
    write_json_atomic(RESULTS / "current_case.json", {"phase": phase, "case_id": case_id, "state": rows[key]["state"], "completed_at": rows[key]["completed_at"]})
    write_eta_checkpoint(rows)


def tabular_cases(phase: str) -> list[tuple[str, Path]]:
    summary = json.loads((INPUTS / "plaintext/summary.json").read_text(encoding="ascii"))
    result = []
    for relative in summary["manifests"]:
        manifest_path = ROOT / relative
        item = json.loads(manifest_path.read_text(encoding="ascii"))
        if phase == "primary" and item["role"] != "primary": continue
        if phase == "ablation" and item["role"] != "ablation": continue
        if phase == "training_seed" and item["role"] != "training_seed": continue
        result.append((relative, manifest_path))
    return result


def initialize_status(rows: dict[tuple[str, str], dict[str, str]]) -> None:
    expected: list[tuple[str, str, Path]] = []
    for phase in ("primary", "training_seed", "ablation"):
        for _, manifest_path in tabular_cases(phase):
            item = json.loads(manifest_path.read_text(encoding="ascii"))
            case_id = f"{item['dataset_id']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item.get('training_seed', 0)}"
            expected.append((phase, case_id, RESULTS / phase / case_id / "case_summary.json"))
            if phase == "primary":
                expected.append(("latency", case_id, RESULTS / "latency" / case_id / "paired_latency.json"))
    expected.append(("packed_primary", "packed_cnn_lite_binary01_v17", RESULTS / "primary/packed_cnn_lite_binary01_v17/case_summary.json"))
    for model_id in ("mnist_mlp_square_784_100_10_v1", "mnist_lenet5_small_square_v1"):
        expected.append(("latency_multiclass", model_id, RESULTS / f"latency/multiclass/{model_id}/paired_latency.json"))
    expected.append(("latency_packed", "packed_cnn_lite_binary01_v17", RESULTS / "latency/packed_cnn_lite_binary01_v17/paired_latency.json"))
    for model_id in ("mnist_mlp_square_784_100_10_v1", "mnist_lenet5_small_square_v1"):
        expected.append(("multiclass_exhaustive", model_id, RESULTS / f"exhaustive/{model_id}/exhaustive.json"))
    for depth in (1, 2, 4, 6, 8):
        expected.append(("depth_ladder", f"D{depth}", RESULTS / f"depth_ladder/results/D{depth}/result.json"))
    for model in ("mlp100", "lenet5_small"):
        for seed in (0, 1, 2):
            expected.append(("training_seed_multiclass", f"{model}/seed_{seed}", RESULTS / f"training_seed_multiclass/{model}/seed_{seed}/case_summary.json"))
    for seed in (0, 1, 2):
        expected.append(("training_seed_packed", f"seed_{seed}", RESULTS / f"training_seed_packed/seed_{seed}/case_summary.json"))
    for phase, case_id, output in expected:
        key = (phase, case_id)
        if key not in rows:
            rows[key] = {
                "phase": phase, "case_id": case_id, "state": "PENDING",
                "started_at": "", "completed_at": "", "attempts": "0",
                "command_sha256": "", "output": output.relative_to(ROOT).as_posix(),
                "reason": "not_started",
            }
    save_status(rows)


def is_primary_representative(item: dict) -> bool:
    return (
        item.get("dataset_id") == "banknote"
        and int(item.get("outer_fold", -1)) == 0
        and int(item.get("training_seed", 0)) == 0
        and item.get("model_id") in {
            "linear_poly3", "mlp_square_linear_score", "mlp_square2_linear_score",
        }
    )


def run_tabular(rows, phase: str, binary: Path, subset: str = "all") -> None:
    for relative, manifest_path in tabular_cases(phase):
        if stop_requested(): return
        item = json.loads(manifest_path.read_text(encoding="ascii"))
        representative = phase == "primary" and is_primary_representative(item)
        if subset == "representatives" and not representative: continue
        if subset == "remaining" and representative: continue
        case_id = f"{item['dataset_id']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item.get('training_seed', 0)}"
        source = manifest_path.parent
        output = RESULTS / phase / case_id
        command = [str(binary), "--model", str(source / "model.json"), "--selection", str(source / "configuration_selection.csv"), "--independent", str(source / "independent_evaluation.csv"), "--dataset", item["dataset_id"], "--model-id", item["model_id"], "--split-id", f"outer_fold_{item['outer_fold']}_training_seed_{item.get('training_seed', 0)}", "--out-root", str(output)]
        run_atomic(rows, phase, case_id, command, output / "case_summary.json")


def run_depth(rows, binary: Path) -> None:
    for depth in (1, 2, 4, 6, 8):
        if stop_requested(): return
        source = INPUTS / f"depth_ladder/inputs/D{depth}"
        output = RESULTS / f"depth_ladder/results/D{depth}/result.json"
        command = [str(binary), "--depth", str(depth), "--model", str(source / "model.json"), "--data", str(source / "configuration_selection.csv"), "--out", str(output)]
        run_atomic(rows, "depth_ladder", f"D{depth}", command, output)


def run_packed(rows, binary: Path) -> None:
    if stop_requested(): return
    source = ROOT / "datasets/vision_suite/mnist/cnn_lite_square_binary01"
    output = RESULTS / "primary/packed_cnn_lite_binary01_v17"
    command = [str(binary), "--model", str(source / "model.json"), "--selection", str(source / "configuration_validation.csv"), "--audit", str(source / "locked_audit_test.csv"), "--source", str(ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"), "--manifest", str(source / "extraction_manifest.json"), "--out-root", str(output), "--stop-request", str(STOP_REQUEST)]
    run_atomic(rows, "packed_primary", "packed_cnn_lite_binary01_v17", command, output / "case_summary.json")


def run_multiclass(rows, binary: Path, requested: str = "all") -> None:
    source_root = ROOT / "datasets/journal_multiclass_extension_v1/mnist"
    validation = source_root / "configuration_validation.csv"
    audit = source_root / "locked_audit.csv"
    source = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"
    for model_id, model_name in (("mnist_mlp_square_784_100_10_v1", "mnist_mlp_square_784_100_10_v1.json"), ("mnist_lenet5_small_square_v1", "mnist_lenet5_small_square_v1.json")):
        if requested != "all" and model_id != requested:
            continue
        if stop_requested(): return
        output = RESULTS / f"exhaustive/{model_id}"
        command = [str(binary), "--model", str(source_root / model_name), "--validation", str(validation), "--audit", str(audit), "--source", str(source), "--out-root", str(output), "--stop-request", str(STOP_REQUEST)]
        run_atomic(rows, "multiclass_exhaustive", model_id, command, output / "exhaustive.json")


def run_multiclass_training_seeds(rows, binary: Path) -> None:
    source_root = ROOT / "datasets/journal_multiclass_extension_v1/mnist"
    source = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"
    for model in ("mlp100", "lenet5_small"):
        for seed in (0, 1, 2):
            if stop_requested(): return
            model_path = INPUTS / f"plaintext/multiclass_training_seed/{model}/seed_{seed}/model.json"
            output = RESULTS / f"training_seed_multiclass/{model}/seed_{seed}"
            command = [str(binary), "--model", str(model_path), "--validation", str(source_root / "configuration_validation.csv"), "--audit", str(source_root / "locked_audit.csv"), "--source", str(source), "--training-seed", str(seed), "--out-root", str(output)]
            run_atomic(rows, "training_seed_multiclass", f"{model}/seed_{seed}", command, output / "case_summary.json")


def run_packed_training_seeds(rows, binary: Path) -> None:
    source = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"
    for seed in (0, 1, 2):
        if stop_requested(): return
        inputs = INPUTS / f"plaintext/packed_cnn_training_seed/seed_{seed}"
        output = RESULTS / f"training_seed_packed/seed_{seed}"
        command = [str(binary), "--model", str(inputs / "model.json"), "--selection", str(inputs / "configuration_validation.csv"), "--audit", str(inputs / "locked_audit_test.csv"), "--source", str(source), "--manifest", str(inputs / "extraction_manifest.json"), "--out-root", str(output)]
        run_atomic(rows, "training_seed_packed", f"seed_{seed}", command, output / "case_summary.json")


def run_tabular_latency(rows, binary: Path) -> None:
    affinity = ",".join(str(item) for item in sorted(os.sched_getaffinity(0)))
    for _, manifest_path in tabular_cases("primary"):
        item = json.loads(manifest_path.read_text(encoding="ascii"))
        case_id = f"{item['dataset_id']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item.get('training_seed', 0)}"
        case_root = RESULTS / "primary" / case_id
        output = RESULTS / "latency" / case_id / "paired_latency.json"
        if not (case_root / "case_summary.json").is_file():
            update(rows, "latency", case_id, state="PENDING_DEPENDENCY", output=output.relative_to(ROOT).as_posix(), reason="primary case incomplete")
            continue
        command = ["taskset", "-c", affinity, str(binary), "--case-root", str(case_root), "--out", str(output)]
        run_atomic(rows, "latency", case_id, command, output)


def run_primary_paired_latency(rows, binary: Path, requested: str) -> None:
    affinity = ",".join(str(item) for item in sorted(os.sched_getaffinity(0)))
    subset = ROOT / "docs/protocols/model_family_expansion_v17/latency_subsets.json"
    stop = str(STOP_REQUEST)
    if requested == "packed":
        case_root = RESULTS / "primary/packed_cnn_lite_binary01_v17"
        output = RESULTS / "latency/packed_cnn_lite_binary01_v17/paired_latency.json"
        if not (case_root / "case_summary.json").is_file():
            update(rows, "latency_packed", "packed_cnn_lite_binary01_v17", state="PENDING_DEPENDENCY", output=output.relative_to(ROOT).as_posix(), reason="packed primary case incomplete")
            return
        command = [
            "taskset", "-c", affinity, str(binary),
            "--kind", "packed_cnn_lite_binary01",
            "--model", "datasets/vision_suite/mnist/cnn_lite_square_binary01/model.json",
            "--data", "datasets/vision_suite/mnist/cnn_lite_square_binary01/locked_audit_test.csv",
            "--direct-source", str(case_root / "selection.json"),
            "--finite-source", str(case_root / "exhaustive.json"),
            "--direct-audit-source", str(case_root / "direct_independent_evaluation.json"),
            "--finite-audit-source", str(case_root / "fastest_safe_independent_evaluation.json"),
            "--subset-manifest", str(subset), "--subset-id", "p6_packed_cnn_locked_audit_20_v1",
            "--out-root", str(output.parent), "--stop-request", stop,
        ]
        run_atomic(rows, "latency_packed", "packed_cnn_lite_binary01_v17", command, output)
        return
    if requested in {"mlp100", "lenet"}:
        model_id = "mnist_mlp_square_784_100_10_v1" if requested == "mlp100" else "mnist_lenet5_small_square_v1"
        model_name = "mnist_mlp_square_784_100_10_v1.json" if requested == "mlp100" else "mnist_lenet5_small_square_v1.json"
        subset_id = "p4_mlp100_locked_audit_20_v1" if requested == "mlp100" else "p5_lenet_locked_audit_20_v1"
        finite_root = RESULTS / f"exhaustive/{model_id}"
        output = RESULTS / f"latency/multiclass/{model_id}/paired_latency.json"
        if not (finite_root / "exhaustive.json").is_file():
            update(rows, "latency_multiclass", model_id, state="PENDING_DEPENDENCY", output=output.relative_to(ROOT).as_posix(), reason=f"{model_id} V17 B3 exhaustive case incomplete")
            return
        command = [
            "taskset", "-c", affinity, str(binary),
            "--kind", "journal_mnist_multiclass",
            "--model", f"datasets/journal_multiclass_extension_v1/mnist/{model_name}",
            "--data", "datasets/journal_multiclass_extension_v1/mnist/locked_audit.csv",
            "--direct-source", f"results/journal_multiclass_extension_v1/encrypted/{model_id}/selection_result.json",
            "--finite-source", str(finite_root / "exhaustive.json"),
            "--direct-audit-source", f"results/journal_multiclass_extension_v1/encrypted/{model_id}/locked_audit_result.json",
            "--finite-audit-source", str(finite_root / "exhaustive.json"),
            "--subset-manifest", str(subset), "--subset-id", subset_id,
            "--out-root", str(output.parent), "--stop-request", stop,
        ]
        run_atomic(rows, "latency_multiclass", model_id, command, output)
        return
    raise RuntimeError(f"unknown primary paired latency request: {requested}")


def main() -> None:
    global RESULTS, INPUTS, STATUS, STOP_REQUEST, RUN_MANIFEST, RUN_ID, ENVIRONMENT_ID
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--input-root", type=Path, default=LEGACY_RESULTS)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--clear-stop-request", action="store_true")
    parser.add_argument("--phase", choices=["primary", "training_seed", "multiclass_training_seed", "packed_training_seed", "latency", "latency_packed", "latency_multiclass", "depth_ladder", "ablation", "packed", "multiclass", "all"], default="all")
    args = parser.parse_args()
    if args.run_root or args.run_id:
        if not args.run_root or not args.run_id:
            raise SystemExit("--run-id and --run-root are required together")
        RESULTS = args.run_root.resolve()
        try:
            RESULTS.relative_to(ROOT)
        except ValueError as exc:
            raise SystemExit("run root must be inside the repository") from exc
        expected_root = (ROOT / "results/model_family_expansion_v17/runs" / args.run_id).resolve()
        if RESULTS != expected_root:
            raise SystemExit(f"run root must equal {expected_root}")
        RUN_ID = args.run_id
        INPUTS = args.input_root.resolve()
        if INPUTS != LEGACY_RESULTS.resolve():
            raise SystemExit("scoped V17 input root must be the immutable protocol-bound legacy input root")
        STATUS = RESULTS / "run_status.csv"
        STOP_REQUEST = RESULTS / "STOP_AFTER_ATOMIC_CASE"
        RUN_MANIFEST = RESULTS / "run_manifest.json"
        if not RUN_MANIFEST.is_file():
            raise SystemExit("missing scoped run manifest")
        run_manifest = json.loads(RUN_MANIFEST.read_text(encoding="ascii"))
        if run_manifest.get("run_id") != RUN_ID or run_manifest.get("result_root") != RESULTS.relative_to(ROOT).as_posix():
            raise SystemExit("scoped run manifest identity mismatch")
        ENVIRONMENT_ID = run_manifest["environment_id"]
        if os.environ.get("GOMAXPROCS") != "6" or sorted(os.sched_getaffinity(0)) != list(range(6)):
            raise SystemExit("vm1x6 runner requires GOMAXPROCS=6 and affinity CPUs 0-5")
        if args.clear_stop_request and STOP_REQUEST.is_file():
            STOP_REQUEST.unlink()
    elif args.run_root is None:
        INPUTS = LEGACY_RESULTS
    if not PROTOCOL.is_file(): raise SystemExit("PROTOCOL_FROZEN gate missing")
    subprocess.run([sys.executable, "scripts/verify_model_family_expansion_v17_protocol.py"], cwd=ROOT, check=True)
    if RUN_ID == "legacy_unscoped":
        subprocess.run([sys.executable, "scripts/build_v17_multiclass_predecessor_reuse.py"], cwd=ROOT, check=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="ascii"))
    active = active_flipguard_binaries()
    if active:
        raise SystemExit("concurrent FlipGuard binary detected: " + json.dumps(active, sort_keys=True))
    lock_path = RESULTS / ".ckks_execution.lock"; lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit("another V17 CKKS process owns the execution lock")
        binaries = {"tabular": RESULTS / "bin/flipguard-v17-tabular-case", "depth": RESULTS / "bin/flipguard-v17-depth-ladder", "packed": RESULTS / "bin/flipguard-v17-packed-cnn-case", "multiclass": RESULTS / "bin/flipguard-v17-multiclass-exhaustive", "multiclass_seed": RESULTS / "bin/flipguard-v17-multiclass-seed-case", "tabular_latency": RESULTS / "bin/flipguard-v17-tabular-paired-latency", "primary_latency": RESULTS / "bin/flipguard-v17-primary-paired-latency"}
        for binary in binaries.values():
            if not binary.is_file(): raise SystemExit(f"missing frozen binary {binary}")
        bound = {Path(item["path"]).name: item["sha256"] for item in protocol["execution_binaries"]}
        for binary in binaries.values():
            actual = "sha256:" + hashlib.sha256(binary.read_bytes()).hexdigest()
            if bound.get(binary.name) != actual:
                raise SystemExit(f"execution binary digest mismatch: {binary.relative_to(ROOT)}")
        rows = load_status()
        initialize_status(rows)
        if args.resume:
            recover_stale_running(rows)
        if args.initialize_only:
            counts = {}
            for row in rows.values(): counts[row["state"]] = counts.get(row["state"], 0) + 1
            print(json.dumps({"status": "INITIALIZED", "counts": counts, "ledger": STATUS.relative_to(ROOT).as_posix()}, sort_keys=True))
            return
        run_manifest = json.loads(RUN_MANIFEST.read_text(encoding="ascii"))
        if "full_run_started_at" not in run_manifest:
            run_manifest["full_run_started_at"] = now()
            run_manifest["status"] = "RUNNING"
            write_json_atomic(RUN_MANIFEST, run_manifest)
        legacy_phases = [
            "primary_representatives", "packed", "multiclass_mlp100",
            "depth_ladder", "primary_remaining", "multiclass_lenet",
            "latency_mlp100", "latency_packed", "latency",
            "training_seed", "ablation", "packed_training_seed",
            "multiclass_training_seed", "latency_lenet",
        ]
        vm1x6_phases = [
            "primary_representatives", "packed", "multiclass_mlp100",
            "depth_ladder", "primary_remaining", "multiclass_lenet",
            "training_seed", "ablation", "packed_training_seed",
            "multiclass_training_seed", "latency_mlp100",
            "latency_packed", "latency", "latency_lenet",
        ]
        phases = (vm1x6_phases if RUN_ID != "legacy_unscoped" else legacy_phases) if args.phase == "all" else [args.phase]
        for phase in phases:
            if stop_requested(): break
            if phase == "depth_ladder": run_depth(rows, binaries["depth"])
            elif phase == "packed": run_packed(rows, binaries["packed"])
            elif phase == "multiclass": run_multiclass(rows, binaries["multiclass"])
            elif phase == "multiclass_mlp100": run_multiclass(rows, binaries["multiclass"], "mnist_mlp_square_784_100_10_v1")
            elif phase == "multiclass_lenet": run_multiclass(rows, binaries["multiclass"], "mnist_lenet5_small_square_v1")
            elif phase == "multiclass_training_seed": run_multiclass_training_seeds(rows, binaries["multiclass_seed"])
            elif phase == "packed_training_seed": run_packed_training_seeds(rows, binaries["packed"])
            elif phase == "latency": run_tabular_latency(rows, binaries["tabular_latency"])
            elif phase == "latency_packed": run_primary_paired_latency(rows, binaries["primary_latency"], "packed")
            elif phase == "latency_mlp100": run_primary_paired_latency(rows, binaries["primary_latency"], "mlp100")
            elif phase == "latency_lenet": run_primary_paired_latency(rows, binaries["primary_latency"], "lenet")
            elif phase == "latency_multiclass":
                run_primary_paired_latency(rows, binaries["primary_latency"], "mlp100")
                if not stop_requested(): run_primary_paired_latency(rows, binaries["primary_latency"], "lenet")
            elif phase == "primary_representatives": run_tabular(rows, "primary", binaries["tabular"], "representatives")
            elif phase == "primary_remaining": run_tabular(rows, "primary", binaries["tabular"], "remaining")
            else: run_tabular(rows, phase, binaries["tabular"])
        counts = {}
        for row in rows.values(): counts[row["state"]] = counts.get(row["state"], 0) + 1
        state = "STOPPED_AFTER_ATOMIC_CASE" if stop_requested() else "CHECKPOINT"
        print(json.dumps({"status": state, "counts": counts, "ledger": STATUS.relative_to(ROOT).as_posix()}, sort_keys=True))


if __name__ == "__main__":
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    main()
