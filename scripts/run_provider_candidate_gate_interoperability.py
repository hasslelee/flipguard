#!/usr/bin/env python3
"""Run the predeclared provider-candidate gate development matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/provider_candidate_gate_v1/contract.json"
)
DEFAULT_OUTPUT_PARENT = Path(
    "results/thesis_grade_protocol/provider_candidate_gate_v1"
)
SCHEMA_VERSION = "flipguard_provider_candidate_gate_run_v1"

VERIFIER_PATH = (
    REPO_ROOT / "scripts/verify_provider_candidate_gate_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_provider_candidate_gate_contract_for_runner",
    VERIFIER_PATH,
)
VERIFIER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VERIFIER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def save_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command(
    arguments: list[str],
    *,
    check: bool = True,
    stdout_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if stdout_path is None:
        return subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="ascii") as handle:
        return subprocess.run(
            arguments,
            cwd=REPO_ROOT,
            check=check,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )


def git(*arguments: str) -> str:
    return command(["git", *arguments]).stdout.strip()


def require_clean_origin() -> tuple[str, str]:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "INTEGRITY_BLOCK: provider matrix requires a clean tree:\n" +
            status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if not branch:
        raise ValueError("INTEGRITY_BLOCK: detached HEAD")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(
            f"INTEGRITY_BLOCK: HEAD {head} != origin/{branch} {origin}"
        )
    return head, origin


def local_dependency_directories(packages: list[str]) -> list[Path]:
    output = command(
        [
            "go",
            "list",
            "-deps",
            "-f",
            "{{if not .Standard}}{{.Dir}}{{end}}",
            *packages,
        ]
    ).stdout
    directories: set[Path] = set()
    for line in output.splitlines():
        if not line:
            continue
        path = Path(line).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        directories.add(path)
    return sorted(directories)


def execution_source_closure() -> tuple[dict[str, str], str]:
    packages = [
        "./cmd/flipguard-certify-candidate",
        "./cmd/flipguard-audit-candidate",
    ]
    directories = local_dependency_directories(packages)
    paths = {"go.mod", "go.sum"}
    for directory in directories:
        for path in directory.glob("*.go"):
            paths.add(path.relative_to(REPO_ROOT).as_posix())
    closure = {
        relative: sha256_path(REPO_ROOT / relative)
        for relative in sorted(paths)
    }
    return closure, canonical_digest(closure)


def build_binary(package: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command(
        [
            "go",
            "build",
            "-buildvcs=false",
            "-trimpath",
            "-o",
            str(output),
            package,
        ]
    )


def host_metadata() -> dict[str, Any]:
    cpu_model = ""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(
            encoding="ascii",
            errors="replace",
        ).splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    memory_kib = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(
            encoding="ascii",
            errors="replace",
        ).splitlines():
            if line.startswith("MemTotal:"):
                memory_kib = int(line.split()[1])
                break
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_model": cpu_model,
        "memory_total_kib": memory_kib,
        "python_version": platform.python_version(),
        "go_version": command(["go", "version"]).stdout.strip(),
    }


def default_output_root(head: str) -> Path:
    return DEFAULT_OUTPUT_PARENT / f"run_{head[:7]}"


def initialize(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite provider matrix run: {output_root}"
        )
    (output_root / "bin").mkdir(parents=True)
    (output_root / "logs").mkdir()
    (output_root / "selection").mkdir()
    (output_root / "audit").mkdir()
    contract_snapshot = output_root / "contract_snapshot.json"
    shutil.copyfile(contract_path, contract_snapshot)

    certify_binary = output_root / "bin/flipguard-certify-candidate"
    audit_binary = output_root / "bin/flipguard-audit-candidate"
    build_binary("./cmd/flipguard-certify-candidate", certify_binary)
    build_binary("./cmd/flipguard-audit-candidate", audit_binary)
    source_files, source_digest = execution_source_closure()
    contract = VERIFIER.load_json(contract_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "PREFLIGHT_PASS",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": head,
        "origin_commit": origin,
        "working_tree_clean": True,
        "contract_path": str(contract_path.relative_to(REPO_ROOT)),
        "contract_snapshot_path": str(
            contract_snapshot.relative_to(REPO_ROOT)
        ),
        "contract_sha256": sha256_path(contract_path),
        "security_policy_digest":
            contract["policy"]["security_policy_digest"],
        "direct_policy_digest":
            contract["policy"]["direct_policy_digest"],
        "execution_critical_source_files": source_files,
        "execution_critical_source_digest": source_digest,
        "host": host_metadata(),
        "binaries": {
            "certify_candidate": {
                "path": str(certify_binary.relative_to(REPO_ROOT)),
                "sha256": sha256_path(certify_binary),
            },
            "audit_candidate": {
                "path": str(audit_binary.relative_to(REPO_ROOT)),
                "sha256": sha256_path(audit_binary),
            },
        },
        "arm_order": contract["execution_rules"]["arm_order"],
        "no_retuning_declaration": True,
        "paper_claim_allowed": False,
    }
    save_atomic(output_root / "run_manifest.json", manifest)
    state = {
        "schema_version": SCHEMA_VERSION,
        "stage": "RUNNING",
        "run_manifest_sha256": sha256_path(
            output_root / "run_manifest.json"
        ),
        "arms": {
            arm["arm_id"]: {
                "selection": "PENDING",
                "audit": "PENDING",
                "selection_attempts": 0,
                "audit_attempts": 0,
            }
            for arm in contract["arms"]
        },
        "recoveries": [],
        "paper_claim_allowed": False,
    }
    save_atomic(output_root / "state.json", state)
    return state


def verify_resume(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
) -> dict[str, Any]:
    manifest = VERIFIER.load_json(output_root / "run_manifest.json")
    state = VERIFIER.load_json(output_root / "state.json")
    source_files, source_digest = execution_source_closure()
    if (
        manifest["source_commit"] != head
        or manifest["origin_commit"] != origin
        or manifest["contract_sha256"] != sha256_path(contract_path)
        or manifest["contract_sha256"] != sha256_path(
            REPO_ROOT / manifest["contract_snapshot_path"]
        )
        or manifest["execution_critical_source_files"] != source_files
        or manifest["execution_critical_source_digest"] != source_digest
        or state["run_manifest_sha256"] !=
        sha256_path(output_root / "run_manifest.json")
    ):
        raise ValueError(
            "INTEGRITY_BLOCK: provider matrix resume provenance changed"
        )
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError(
                "INTEGRITY_BLOCK: provider matrix binary changed"
            )
    return state


def append_ledger(
    output_root: Path,
    stage: str,
    arm_id: str,
    status: str,
    reason: str,
    result_path: Path | None,
) -> None:
    path = output_root / "stage_ledger.json"
    ledger: list[dict[str, Any]] = []
    if path.is_file():
        value = json.loads(path.read_text(encoding="ascii"))
        if isinstance(value, list):
            ledger = value
    ledger.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "arm_id": arm_id,
        "status": status,
        "reason": reason,
        "result_path": (
            str(result_path.relative_to(REPO_ROOT))
            if result_path is not None and result_path.is_file()
            else None
        ),
        "result_sha256": (
            sha256_path(result_path)
            if result_path is not None and result_path.is_file()
            else None
        ),
    })
    save_atomic(path, ledger)


def run_arm(
    contract: dict[str, Any],
    arm: dict[str, Any],
    output_root: Path,
    state: dict[str, Any],
) -> None:
    arm_id = arm["arm_id"]
    arm_state = state["arms"][arm_id]
    workload = contract["workload"]
    policy = contract["policy"]
    selection_path = output_root / "selection" / f"{arm_id}.json"
    selection_log = output_root / "logs" / f"{arm_id}_selection.log"
    audit_path = output_root / "audit" / f"{arm_id}.json"
    audit_log = output_root / "logs" / f"{arm_id}_audit.log"
    certify_binary = output_root / "bin/flipguard-certify-candidate"
    audit_binary = output_root / "bin/flipguard-audit-candidate"

    if arm_state["selection"] == "PENDING":
        arm_state["selection_attempts"] += 1
        save_atomic(output_root / "state.json", state)
        completed = command(
            [
                str(certify_binary),
                "--model",
                workload["model_path"],
                "--validation",
                workload["validation_path"],
                "--split-id",
                workload["split_id"],
                "--candidate",
                arm["candidate_path"],
                "--margin-floor",
                str(policy["margin_floor"]),
                "--safety-factor",
                str(policy["safety_factor"]),
                "--key-repeats",
                str(policy["validation_key_repeats"]),
                "--out",
                str(selection_path),
            ],
            check=False,
            stdout_path=selection_log,
        )
        if completed.returncode != 0 or not selection_path.is_file():
            arm_state["selection"] = "IMPLEMENTATION_FAILURE"
            arm_state["audit"] = "NOT_APPLICABLE"
            append_ledger(
                output_root,
                "selection",
                arm_id,
                "RECOVERABLE_IMPLEMENTATION_FAILURE",
                f"exit_code={completed.returncode}",
                selection_path,
            )
            save_atomic(output_root / "state.json", state)
            return
        selection = VERIFIER.load_json(selection_path)
        outcome = selection["outcome"]
        arm_state["selection"] = outcome
        append_ledger(
            output_root,
            "selection",
            arm_id,
            (
                "PASS"
                if outcome == "SELECTED"
                else "PARTIAL_SCIENTIFIC_RESULT"
            ),
            f"outcome={outcome} status={selection['trial']['status']}",
            selection_path,
        )
        if outcome != "SELECTED":
            arm_state["audit"] = "NOT_APPLICABLE"
            save_atomic(output_root / "state.json", state)
            return
        save_atomic(output_root / "state.json", state)

    if arm_state["selection"] != "SELECTED" or \
            arm_state["audit"] != "PENDING":
        return
    arm_state["audit_attempts"] += 1
    save_atomic(output_root / "state.json", state)
    completed = command(
        [
            str(audit_binary),
            "--selection",
            str(selection_path),
            "--audit",
            workload["audit_path"],
            "--manifest",
            workload["split_manifest_path"],
            "--key-repeats",
            str(policy["audit_key_repeats"]),
            "--out",
            str(audit_path),
        ],
        check=False,
        stdout_path=audit_log,
    )
    if completed.returncode != 0 or not audit_path.is_file():
        arm_state["audit"] = "IMPLEMENTATION_FAILURE"
        append_ledger(
            output_root,
            "locked_audit",
            arm_id,
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
            f"exit_code={completed.returncode}",
            audit_path,
        )
        save_atomic(output_root / "state.json", state)
        return
    audit = VERIFIER.load_json(audit_path)
    arm_state["audit"] = audit["outcome"]
    append_ledger(
        output_root,
        "locked_audit",
        arm_id,
        (
            "PASS"
            if audit["outcome"] == "LOCKED_AUDIT_PASS"
            else "PARTIAL_SCIENTIFIC_RESULT"
        ),
        (
            f"outcome={audit['outcome']} "
            f"status={audit['audit_trial']['status']} "
            f"retuning={audit['retuning_performed']}"
        ),
        audit_path,
    )
    save_atomic(output_root / "state.json", state)


def build_summary(
    contract: dict[str, Any],
    output_root: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for arm in contract["arms"]:
        arm_id = arm["arm_id"]
        selection_path = output_root / "selection" / f"{arm_id}.json"
        audit_path = output_root / "audit" / f"{arm_id}.json"
        row: dict[str, Any] = {
            "arm_id": arm_id,
            "provider_kind": arm["provider_kind"],
            "selection_state": state["arms"][arm_id]["selection"],
            "audit_state": state["arms"][arm_id]["audit"],
            "candidate_trials": 0,
            "selection_key_runs": 0,
            "audit_key_runs": 0,
            "retuning": 0,
        }
        if selection_path.is_file():
            selection = VERIFIER.load_json(selection_path)
            row.update({
                "candidate_id":
                    selection["bound_candidate"]["candidate"]["id"],
                "candidate_trials": selection["trials_used"],
                "selection_key_runs": selection["encrypted_key_runs"],
                "selection_status": selection["trial"]["status"],
                "selection_flips":
                    selection["trial"]["decision_flips"],
                "selection_violations":
                    selection["trial"]["error_violations"],
            })
        if audit_path.is_file():
            audit = VERIFIER.load_json(audit_path)
            row.update({
                "audit_status": audit["audit_trial"]["status"],
                "audit_key_runs":
                    audit["audit_trial"]["key_repeats_completed"],
                "audit_flips":
                    audit["audit_trial"]["decision_flips"],
                "audit_violations":
                    audit["audit_trial"]["error_violations"],
                "retuning": int(audit["retuning_performed"]),
                "selection_audit_candidate_identical":
                    audit["selected_candidate"]["id"] ==
                    row.get("candidate_id"),
            })
        rows.append(row)

    implementation_failures = sum(
        row["selection_state"] == "IMPLEMENTATION_FAILURE" or
        row["audit_state"] == "IMPLEMENTATION_FAILURE"
        for row in rows
    )
    scientific_negatives = sum(
        row["selection_state"] != "SELECTED" or
        row["audit_state"] not in (
            "LOCKED_AUDIT_PASS",
            "NOT_APPLICABLE",
        )
        for row in rows
        if row["selection_state"] != "IMPLEMENTATION_FAILURE" and
        row["audit_state"] != "IMPLEMENTATION_FAILURE"
    )
    claim_state = (
        "BLOCKED"
        if implementation_failures
        else "PARTIALLY_SUPPORTED"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "PASS"
            if implementation_failures == 0
            else "PARTIAL_IMPLEMENTATION_FAILURE"
        ),
        "evaluation_role": "development_interoperability_control",
        "arms": rows,
        "counts": {
            "arms": len(rows),
            "selected": sum(
                row["selection_state"] == "SELECTED" for row in rows
            ),
            "no_safe": sum(
                row["selection_state"] == "NO_SAFE" for row in rows
            ),
            "locked_audit_pass": sum(
                row["audit_state"] == "LOCKED_AUDIT_PASS" for row in rows
            ),
            "locked_audit_fail": sum(
                row["audit_state"] == "LOCKED_AUDIT_FAIL" for row in rows
            ),
            "candidate_trials": sum(
                row["candidate_trials"] for row in rows
            ),
            "selection_key_runs": sum(
                row["selection_key_runs"] for row in rows
            ),
            "audit_key_runs": sum(
                row["audit_key_runs"] for row in rows
            ),
            "retuning": sum(row["retuning"] for row in rows),
            "scientific_negatives": scientific_negatives,
            "implementation_failures": implementation_failures,
        },
        "claim_states": {
            "provider_class_interoperability": claim_state,
            "provider_locked_literal_replay": claim_state,
            "third_party_autotuner_integration": "NOT_EVALUATED",
            "third_party_autotuner_quality": "NOT_EVALUATED",
        },
        "paper_claim_allowed": False,
        "block_reason": (
            "single development workload and synthetic external-format "
            "fixture do not support a paper-level external-autotuner claim"
        ),
    }


def write_sha256sums(output_root: Path) -> None:
    path = output_root / "SHA256SUMS"
    files = sorted(
        item for item in output_root.rglob("*")
        if item.is_file() and item != path
    )
    lines = [
        f"{sha256_path(item).removeprefix('sha256:')}  "
        f"{item.relative_to(output_root).as_posix()}"
        for item in files
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def verify_output(
    contract_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    VERIFIER.validate_contract(contract_path)
    manifest = VERIFIER.load_json(output_root / "run_manifest.json")
    state = VERIFIER.load_json(output_root / "state.json")
    summary = VERIFIER.load_json(output_root / "summary.json")
    if (
        manifest["schema_version"] != SCHEMA_VERSION
        or manifest["contract_sha256"] != sha256_path(contract_path)
        or state["stage"] != summary["status"]
        or state["stage"] not in (
            "PASS",
            "PARTIAL_IMPLEMENTATION_FAILURE",
        )
        or state["paper_claim_allowed"]
        or summary["paper_claim_allowed"]
        or summary["counts"]["arms"] != 4
        or summary["counts"]["retuning"] != 0
    ):
        raise ValueError(
            "provider candidate gate output invariant changed"
        )
    for line in (
        output_root / "SHA256SUMS"
    ).read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        path = output_root / relative
        if sha256_path(path) != "sha256:" + digest:
            raise ValueError(
                f"provider candidate gate output changed: {relative}"
            )
    for arm in summary["arms"]:
        selection_path = (
            output_root / "selection" / f"{arm['arm_id']}.json"
        )
        if selection_path.is_file():
            selection = VERIFIER.load_json(selection_path)
            if (
                selection["schema_version"] != 1
                or selection["trials_used"] != 1
                or selection["bound_candidate"]["policy_retuning"] != 0
                or selection["bound_candidate"][
                    "security_policy_digest"
                ] != manifest["security_policy_digest"]
            ):
                raise ValueError(
                    f"{arm['arm_id']}: selection invariant changed"
                )
        audit_path = output_root / "audit" / f"{arm['arm_id']}.json"
        if audit_path.is_file():
            audit = VERIFIER.load_json(audit_path)
            if (
                audit["retuning_performed"]
                or audit["selected_candidate"]["id"] !=
                arm["candidate_id"]
            ):
                raise ValueError(
                    f"{arm['arm_id']}: locked audit identity changed"
                )
    return summary


def preflight(contract_path: Path) -> dict[str, str]:
    head, origin = require_clean_origin()
    contract = VERIFIER.validate_contract(contract_path)
    command([
        "go",
        "test",
        "./internal/providergate",
        "./internal/ckksplanner",
        "./cmd/flipguard-certify-candidate",
        "./cmd/flipguard-audit-candidate",
    ])
    with tempfile.TemporaryDirectory(
        prefix="flipguard-provider-gate-preflight-",
        dir="/tmp",
    ) as temporary:
        root = Path(temporary)
        certify = root / "flipguard-certify-candidate"
        audit = root / "flipguard-audit-candidate"
        build_binary("./cmd/flipguard-certify-candidate", certify)
        build_binary("./cmd/flipguard-audit-candidate", audit)
        binaries = {
            "certify": sha256_path(certify),
            "audit": sha256_path(audit),
        }
    _, source_digest = execution_source_closure()
    return {
        "head": head,
        "origin": origin,
        "contract_sha256": contract["contract_sha256"],
        "execution_critical_source_digest": source_digest,
        "certify_binary_sha256": binaries["certify"],
        "audit_binary_sha256": binaries["audit"],
    }


def main() -> int:
    args = parse_args()
    contract_path = args.contract
    if not contract_path.is_absolute():
        contract_path = REPO_ROOT / contract_path
    head = git("rev-parse", "HEAD")
    output_root = args.output_root or default_output_root(head)
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root

    if args.verify:
        summary = verify_output(contract_path, output_root)
        print(
            "provider_candidate_gate_run=VERIFIED "
            f"arms={summary['counts']['arms']} "
            f"selected={summary['counts']['selected']} "
            f"audit_pass={summary['counts']['locked_audit_pass']} "
            f"claim={summary['claim_states']['provider_class_interoperability']} "
            "paper_claim_allowed=false"
        )
        return 0

    preflight_summary = preflight(contract_path)
    print(
        "provider_candidate_gate_preflight=PASS "
        f"head={preflight_summary['head']} "
        f"source_digest={preflight_summary['execution_critical_source_digest']} "
        f"contract_digest={preflight_summary['contract_sha256']}"
    )
    if args.preflight_only:
        return 0

    head, origin = require_clean_origin()
    contract = VERIFIER.load_json(contract_path)
    if args.resume:
        state = verify_resume(
            contract_path,
            output_root,
            head,
            origin,
        )
    else:
        state = initialize(
            contract_path,
            output_root,
            head,
            origin,
        )
    for arm in contract["arms"]:
        run_arm(contract, arm, output_root, state)

    summary = build_summary(contract, output_root, state)
    state["stage"] = summary["status"]
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    save_atomic(output_root / "state.json", state)
    save_atomic(output_root / "summary.json", summary)
    write_sha256sums(output_root)
    verify_output(contract_path, output_root)
    print(
        f"provider_candidate_gate_run={summary['status']} "
        f"arms={summary['counts']['arms']} "
        f"selected={summary['counts']['selected']} "
        f"audit_pass={summary['counts']['locked_audit_pass']} "
        f"scientific_negatives={summary['counts']['scientific_negatives']} "
        f"implementation_failures={summary['counts']['implementation_failures']} "
        "paper_claim_allowed=false"
    )
    return 0 if summary["counts"]["implementation_failures"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
