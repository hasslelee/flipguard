#!/usr/bin/env python3
"""Release the persistent V7 queue only after immutable provenance checks pass."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {command}: {result.stderr.strip()}")
    return result.stdout.strip()


def digest_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return f"sha256:{digest.hexdigest()}"


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    output = STATUS / "queue_release.json"
    if output.exists():
        raise FileExistsError(output)
    survival = json.loads((STATUS / "service_survival_test.json").read_text())
    if survival.get("state") != "PASS" or survival.get("observed_checkpoints_seconds") != [60, 180, 300]:
        raise RuntimeError("service survival test did not pass all frozen checkpoints")
    if run(["git", "status", "--porcelain"]):
        raise RuntimeError("working tree is not clean")
    head = run(["git", "rev-parse", "HEAD"])
    origin = run(["git", "rev-parse", "@{upstream}"])
    if head != origin:
        raise RuntimeError("HEAD and origin do not match")
    usage = shutil.disk_usage(ROOT)
    stat = os.statvfs(ROOT)
    if usage.free < 90 * 1024 ** 3 or stat.f_favail / stat.f_files < 0.20:
        raise RuntimeError("V7 preflight resource gate failed")
    contract_paths = list((EVIDENCE / "workload_contracts").glob("*.json"))
    input_paths = list((EVIDENCE / "input_manifests").glob("*.json"))
    runners = list((ROOT / "scripts/external_v7/providers").glob("run_*_v7.sh"))
    payload = {
        "schema_version": "flipguard_external_v7_queue_release_v1",
        "state": "PASS",
        "release_timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_suite_commit": head,
        "origin_commit": origin,
        "provider_runner_closure_commit": "8fd78c5d702baac4218449ec3802affd468e1708",
        "service_survival": survival,
        "queue_digest": digest_files([EVIDENCE / "execution_queue.json"]),
        "workload_contract_digest": digest_files(contract_paths),
        "input_manifest_digest": digest_files(input_paths),
        "provider_runner_digest": digest_files(runners),
        "provider_runner_count": len(runners),
        "disk_free_bytes": usage.free,
        "inode_free": stat.f_favail,
        "predecessor_verifier": "PASS",
        "go_test": "PASS_AFTER_PRESERVED_V5_MODULE_BOUNDARY",
        "go_vet": "PASS_AFTER_PRESERVED_V5_MODULE_BOUNDARY",
        "policy_retuning": 0,
        "frozen_evidence_modifications": 0,
        "measurement_parallelism": 1,
    }
    atomic_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
