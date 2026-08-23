#!/usr/bin/env python3
"""Run a non-claim-bearing VM1x6 interruption/resume preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    run_root = ROOT / "results/model_family_expansion_v17/runs" / args.run_id
    run_manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="ascii"))
    preflight = run_root / "preflight/tabular_interruption_resume"
    result = preflight / "case_summary.json"
    if result.is_file() and (preflight / "preflight_manifest.json").is_file():
        print(json.dumps({"status": "PASS_EXISTING", "manifest_sha256": sha(preflight / "preflight_manifest.json")}, sort_keys=True))
        return
    if os.environ.get("GOMAXPROCS") != "6" or sorted(os.sched_getaffinity(0)) != list(range(6)):
        raise RuntimeError("preflight requires GOMAXPROCS=6 and affinity 0-5")
    source = ROOT / "results/model_family_expansion_v17/smoke/inputs/tabular_p3_banknote_fold0"
    model = ROOT / "results/model_family_expansion_v17/plaintext/primary/banknote/mlp_square2_linear_score/fold_0/training_seed_0/model.json"
    binary = run_root / "bin/flipguard-v17-tabular-case"
    command = [
        str(binary), "--model", str(model), "--selection", str(source / "configuration_selection.csv"),
        "--independent", str(source / "independent_evaluation.csv"), "--dataset", "banknote",
        "--model-id", "mlp_square2_linear_score", "--split-id", "vm1x6_preflight_not_in_final_matrix",
        "--out-root", str(preflight),
    ]
    preflight.mkdir(parents=True, exist_ok=True)
    interrupted_log = (preflight / "interrupted_attempt.log").open("w", encoding="utf-8")
    started = now()
    process = subprocess.Popen(command, cwd=ROOT, stdout=interrupted_log, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 10800
    selection = preflight / "selection.json"
    while not selection.is_file() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if not selection.is_file():
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=60)
        interrupted_log.close()
        raise RuntimeError("preflight did not produce a durable selection checkpoint")
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=60)
    interrupted_exit = process.returncode
    interrupted_log.close()
    if result.is_file():
        raise RuntimeError("preflight completed before controlled interruption")

    resumed_log_path = preflight / "resumed_attempt.log"
    with resumed_log_path.open("w", encoding="utf-8") as resumed_log:
        completed = subprocess.run(command, cwd=ROOT, stdout=resumed_log, stderr=subprocess.STDOUT, text=True)
    if completed.returncode != 0 or not result.is_file():
        raise RuntimeError(f"preflight resume failed with exit {completed.returncode}")
    spec = importlib.util.spec_from_file_location("v17_result_verifier", ROOT / "scripts/verify_model_family_expansion_v17_results.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load result verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.verify_case(result)
    manifest = {
        "schema_version": "flipguard_v17_vm1x6_preflight_v1", "status": "PASS",
        "claim_bearing": False, "included_in_final_204": False, "run_id": args.run_id,
        "environment_id": run_manifest["environment_id"], "guest_total_vcpu": 6,
        "GOMAXPROCS": 6, "affinity": "0-5", "worker_count": 1,
        "started_at": started, "completed_at": now(), "controlled_interrupt_signal": "SIGTERM",
        "interrupted_exit_code": interrupted_exit, "durable_checkpoint": selection.relative_to(ROOT).as_posix(),
        "resume_command_sha256": "sha256:" + hashlib.sha256(" ".join(command).encode("utf-8")).hexdigest(),
        "result": result.relative_to(ROOT).as_posix(), "result_sha256": sha(result),
        "scientific_protocol_digest": run_manifest["scientific_protocol_digest"],
        "execution_profile_digest": run_manifest["execution_profile_digest"],
        "source_tree_digest": run_manifest["source_tree_digest"], "binary_sha256": sha(binary),
        "old_v17_result_import_count": 0, "old_v17_latency_import_count": 0,
        "old_v17_completion_marker_import_count": 0,
    }
    write_json(preflight / "preflight_manifest.json", manifest)
    (preflight / "SHA256SUMS").write_text(
        "".join(f"{sha(path).removeprefix('sha256:')}  {path.name}\n" for path in sorted(preflight.iterdir()) if path.is_file() and path.name != "SHA256SUMS"),
        encoding="ascii",
    )
    print(json.dumps({"status": "PASS", "manifest_sha256": sha(preflight / "preflight_manifest.json"), "interrupted_exit_code": interrupted_exit}, sort_keys=True))


if __name__ == "__main__":
    main()
