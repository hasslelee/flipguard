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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/model_family_expansion_v17"
PROTOCOL = ROOT / "docs/protocols/model_family_expansion_v17/protocol.json"
STATUS = RESULTS / "run_status.csv"
STOP_REQUEST = RESULTS / "STOP_AFTER_ATOMIC_CASE"
FIELDS = ["phase", "case_id", "state", "started_at", "completed_at", "attempts", "command_sha256", "output", "reason"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def stop_requested() -> bool:
    return STOP_REQUEST.is_file()


def run_atomic(rows, phase: str, case_id: str, command: list[str], expected: Path) -> None:
    key = (phase, case_id)
    if expected.is_file():
        update(rows, phase, case_id, state="DONE", completed_at=rows.get(key, {}).get("completed_at") or now(), output=expected.relative_to(ROOT).as_posix(), reason="verified_existing_checkpoint")
        return
    attempts = int(rows.get(key, {}).get("attempts") or 0) + 1
    command_text = " ".join(command)
    started = now()
    update(rows, phase, case_id, state="RUNNING", started_at=started, completed_at="", attempts=attempts, command_sha256=digest_text(command_text), output=expected.relative_to(ROOT).as_posix(), reason="")
    log = RESULTS / "logs" / phase / f"{case_id.replace('/', '__')}.attempt{attempts}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("x", encoding="utf-8") as handle:
        handle.write(f"started_at={started}\ncommand_sha256={digest_text(command_text)}\ncommand={command_text}\n")
        handle.flush()
        completed = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True)
        handle.write(f"completed_at={now()}\nexit_code={completed.returncode}\n")
    if completed.returncode == 0 and expected.is_file():
        update(rows, phase, case_id, state="DONE", completed_at=now(), reason="", output=expected.relative_to(ROOT).as_posix())
    elif completed.returncode == 75:
        update(rows, phase, case_id, state="PENDING", completed_at=now(), reason=f"durable_key_run_checkpoint;log={log.relative_to(ROOT)}")
    else:
        update(rows, phase, case_id, state="FAILED_RECORDED", completed_at=now(), reason=f"exit_code={completed.returncode};log={log.relative_to(ROOT)}")


def tabular_cases(phase: str) -> list[tuple[str, Path]]:
    summary = json.loads((RESULTS / "plaintext/summary.json").read_text(encoding="ascii"))
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
        source = RESULTS / f"depth_ladder/inputs/D{depth}"
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
            model_path = RESULTS / f"plaintext/multiclass_training_seed/{model}/seed_{seed}/model.json"
            output = RESULTS / f"training_seed_multiclass/{model}/seed_{seed}"
            command = [str(binary), "--model", str(model_path), "--validation", str(source_root / "configuration_validation.csv"), "--audit", str(source_root / "locked_audit.csv"), "--source", str(source), "--training-seed", str(seed), "--out-root", str(output)]
            run_atomic(rows, "training_seed_multiclass", f"{model}/seed_{seed}", command, output / "case_summary.json")


def run_packed_training_seeds(rows, binary: Path) -> None:
    source = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"
    for seed in (0, 1, 2):
        if stop_requested(): return
        inputs = RESULTS / f"plaintext/packed_cnn_training_seed/seed_{seed}"
        output = RESULTS / f"training_seed_packed/seed_{seed}"
        command = [str(binary), "--model", str(inputs / "model.json"), "--selection", str(inputs / "configuration_validation.csv"), "--audit", str(inputs / "locked_audit_test.csv"), "--source", str(source), "--manifest", str(inputs / "extraction_manifest.json"), "--out-root", str(output)]
        run_atomic(rows, "training_seed_packed", f"seed_{seed}", command, output / "case_summary.json")


def run_tabular_latency(rows, binary: Path) -> None:
    affinity = min(os.sched_getaffinity(0))
    for _, manifest_path in tabular_cases("primary"):
        item = json.loads(manifest_path.read_text(encoding="ascii"))
        case_id = f"{item['dataset_id']}/{item['model_id']}/fold_{item['outer_fold']}/training_seed_{item.get('training_seed', 0)}"
        case_root = RESULTS / "primary" / case_id
        output = RESULTS / "latency" / case_id / "paired_latency.json"
        if not (case_root / "case_summary.json").is_file():
            update(rows, "latency", case_id, state="PENDING_DEPENDENCY", output=output.relative_to(ROOT).as_posix(), reason="primary case incomplete")
            continue
        command = ["taskset", "-c", str(affinity), str(binary), "--case-root", str(case_root), "--out", str(output)]
        run_atomic(rows, "latency", case_id, command, output)


def run_primary_paired_latency(rows, binary: Path, requested: str) -> None:
    affinity = min(os.sched_getaffinity(0))
    subset = ROOT / "docs/protocols/model_family_expansion_v17/latency_subsets.json"
    stop = str(STOP_REQUEST)
    if requested == "packed":
        case_root = RESULTS / "primary/packed_cnn_lite_binary01_v17"
        output = RESULTS / "latency/packed_cnn_lite_binary01_v17/paired_latency.json"
        if not (case_root / "case_summary.json").is_file():
            update(rows, "latency_packed", "packed_cnn_lite_binary01_v17", state="PENDING_DEPENDENCY", output=output.relative_to(ROOT).as_posix(), reason="packed primary case incomplete")
            return
        command = [
            "taskset", "-c", str(affinity), str(binary),
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
            "taskset", "-c", str(affinity), str(binary),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--phase", choices=["primary", "training_seed", "multiclass_training_seed", "packed_training_seed", "latency", "latency_packed", "latency_multiclass", "depth_ladder", "ablation", "packed", "multiclass", "all"], default="all")
    args = parser.parse_args()
    if not PROTOCOL.is_file(): raise SystemExit("PROTOCOL_FROZEN gate missing")
    subprocess.run([sys.executable, "scripts/verify_model_family_expansion_v17_protocol.py"], cwd=ROOT, check=True)
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
        bound = {item["path"]: item["sha256"] for item in protocol["execution_binaries"]}
        for binary in binaries.values():
            relative = binary.relative_to(ROOT).as_posix()
            actual = "sha256:" + hashlib.sha256(binary.read_bytes()).hexdigest()
            if bound.get(relative) != actual:
                raise SystemExit(f"execution binary digest mismatch: {relative}")
        rows = load_status()
        initialize_status(rows)
        phases = [
            "primary_representatives", "packed", "multiclass_mlp100",
            "depth_ladder", "primary_remaining", "multiclass_lenet",
            "latency_mlp100", "latency_packed", "latency",
            "training_seed", "ablation", "packed_training_seed",
            "multiclass_training_seed", "latency_lenet",
        ] if args.phase == "all" else [args.phase]
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
