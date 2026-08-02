#!/usr/bin/env python3
"""Run three serial, append-only fresh-key blocks for the focused MLP amendment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from verify_journal_mlp_paired_latency_protocol_v1 import verify


PROTOCOL = Path("docs/evidence/journal_mlp_paired_latency_protocol_v1_2")
DEFAULT_OUTPUT = Path("results/journal_mlp_paired_latency_v1/execution")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def complete_attempt(path: Path, expected_records: int) -> bool:
    required = [path / "run_manifest.json", path / "records.jsonl", path / "result.json", path / "completed.json"]
    if not all(item.is_file() for item in required):
        return False
    completion = load(path / "completed.json")
    if completion.get("records") != expected_records:
        return False
    if completion.get("ledger_sha256") != sha(path / "records.jsonl"):
        return False
    if completion.get("result_sha256") != sha(path / "result.json"):
        return False
    with (path / "records.jsonl").open(encoding="utf-8") as handle:
        if sum(1 for line in handle if line.strip()) != expected_records:
            return False
    result = load(path / "result.json")
    return len(result.get("records", [])) == expected_records


def existing_ckks_processes(binary: Path) -> list[str]:
    current_pid = os.getpid()
    result = subprocess.run(["ps", "-eo", "pid=,args="], check=True, capture_output=True, text=True)
    matches = []
    binary_name = binary.name
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split(maxsplit=1)
        if len(fields) != 2 or int(fields[0]) == current_pid:
            continue
        if binary_name in fields[1]:
            matches.append(stripped)
    return matches


def next_attempt(root: Path) -> int:
    attempts = []
    if root.exists():
        for path in root.glob("attempt_*"):
            try:
                attempts.append(int(path.name.split("_", 1)[1]))
            except ValueError:
                continue
    for log_path in root.parent.glob(f"{root.name}_attempt_*.log"):
        try:
            attempts.append(int(log_path.stem.rsplit("_", 1)[1]))
        except ValueError:
            continue
    return max(attempts, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--maximum-attempts", type=int, default=3)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = (repo / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    protocol_pack = repo / PROTOCOL
    protocol = verify(protocol_pack, repo)
    binary = repo / load(protocol_pack / "manifest.json")["frozen_binary"]["path"]
    if existing := existing_ckks_processes(binary):
        raise RuntimeError("concurrent focused MLP CKKS process detected: " + " | ".join(existing))
    if subprocess.run(["git", "diff", "--quiet"], cwd=repo).returncode != 0 or subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo
    ).returncode != 0:
        raise RuntimeError("execution requires a clean tracked working tree")

    output.mkdir(parents=True, exist_ok=True)
    expected_per_keyset = len(protocol["selected_rows"]) * len(protocol["arms"]) * protocol["measurement_runs"]
    status = {
        "schema_version": "flipguard_journal_mlp_paired_latency_orchestration_v1",
        "protocol_sha256": sha(protocol_pack / "execution_protocol.json"),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "keysets": [],
    }
    for keyset in range(1, protocol["fresh_keysets"] + 1):
        keyset_root = output / f"keyset_{keyset:02d}"
        completed = [
            path for path in sorted(keyset_root.glob("attempt_*"))
            if complete_attempt(path, expected_per_keyset)
        ] if keyset_root.exists() else []
        if completed:
            status["keysets"].append({"keyset": keyset, "status": "PRESERVED_COMPLETE", "path": str(completed[-1].relative_to(repo))})
            continue
        for _ in range(args.maximum_attempts):
            attempt = next_attempt(keyset_root)
            attempt_root = keyset_root / f"attempt_{attempt:02d}"
            command = [
                str(binary),
                "--protocol", str(protocol_pack / "execution_protocol.json"),
                "--output", str(attempt_root),
                "--keyset", str(keyset),
                "--attempt", str(attempt),
            ]
            log_path = output / f"keyset_{keyset:02d}_attempt_{attempt:02d}.log"
            with log_path.open("x", encoding="utf-8") as log:
                process = subprocess.run(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, text=True)
            if process.returncode == 0 and complete_attempt(attempt_root, expected_per_keyset):
                status["keysets"].append({
                    "keyset": keyset, "status": "PASS", "attempt": attempt,
                    "path": str(attempt_root.relative_to(repo)), "log": str(log_path.relative_to(repo)),
                })
                break
            status["keysets"].append({
                "keyset": keyset, "status": "RECOVERABLE_PROCESS_FAILURE",
                "attempt": attempt, "path": str(attempt_root.relative_to(repo)),
                "log": str(log_path.relative_to(repo)), "return_code": process.returncode,
            })
        else:
            raise RuntimeError(f"keyset {keyset} exhausted {args.maximum_attempts} preserved attempts")
    status["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    status["expected_measurement_records"] = protocol["expected_measurement_records"]
    status["completed_measurement_records"] = protocol["expected_measurement_records"]
    status_path = output / "orchestration_complete.json"
    if status_path.exists():
        existing = load(status_path)
        if existing["protocol_sha256"] != status["protocol_sha256"]:
            raise RuntimeError("existing orchestration completion binds another protocol")
    else:
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"journal_mlp_paired_latency=COMPLETE records={protocol['expected_measurement_records']} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
