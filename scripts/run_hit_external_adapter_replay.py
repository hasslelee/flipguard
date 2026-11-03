#!/usr/bin/env python3
"""Replay one source-pinned AWS HIT candidate through the provider gate."""

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
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/hit_external_adapter_v1/contract.json"
)
DEFAULT_OUTPUT_PARENT = Path(
    "results/thesis_grade_protocol/hit_external_adapter_v1"
)
MATERIALIZER = Path("tools/lattigo-cross-version-materializer")
RUN_SCHEMA = "flipguard_hit_external_adapter_run_v1"
PROVIDER_ID = "aws_hit_902e87e_source_replay_v1"

VERIFIER_PATH = REPO_ROOT / (
    "scripts/verify_hit_external_adapter_contract.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_hit_contract_for_runner",
    VERIFIER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def command(
    arguments: list[str],
    *,
    cwd: Path = REPO_ROOT,
    check: bool = True,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if log_path is None:
        return subprocess.run(
            arguments,
            cwd=cwd,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="ascii") as handle:
        return subprocess.run(
            arguments,
            cwd=cwd,
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
            "INTEGRITY_BLOCK: HIT replay requires a clean tree:\n" + status
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


def source_url(
    contract: dict[str, Any],
    source: dict[str, Any],
) -> str:
    repositories = {
        "hit": (
            "awslabs/homomorphic-implementors-toolkit",
            contract["upstream"]["hit_commit"],
        ),
        "wrapper": (
            "awslabs/aws-cppwrapper-lattigo",
            contract["upstream"]["wrapper_commit"],
        ),
        "lattigo_v2": (
            "ldsec/lattigo",
            contract["upstream"]["lattigo_v2_commit"],
        ),
        "lattigo_v6": (
            "tuneinsight/lattigo",
            contract["upstream"]["lattigo_v6_commit"],
        ),
    }
    repository = source["repository"]
    if repository not in repositories:
        raise ValueError(f"unsupported source repository: {repository}")
    owner_repo, commit = repositories[repository]
    return (
        f"https://raw.githubusercontent.com/{owner_repo}/"
        f"{commit}/{source['path']}"
    )


def fetch_bytes(url: str, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "FlipGuard-HIT-Replay/1"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(
        f"failed to fetch {url} after {attempts} attempts: {last_error}"
    )


def execution_source_closure() -> tuple[dict[str, str], str]:
    packages = [
        "./cmd/flipguard-certify-candidate",
        "./cmd/flipguard-audit-candidate",
    ]
    listed = command([
        "go",
        "list",
        "-deps",
        "-f",
        "{{if not .Standard}}{{.Dir}}{{end}}",
        *packages,
    ]).stdout
    directories: set[Path] = set()
    for line in listed.splitlines():
        if not line:
            continue
        path = Path(line).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        directories.add(path)
    relative_paths = {"go.mod", "go.sum"}
    for directory in directories:
        for path in directory.glob("*.go"):
            relative_paths.add(path.relative_to(REPO_ROOT).as_posix())
    materializer = REPO_ROOT / MATERIALIZER
    for name in ("go.mod", "go.sum", "main.go"):
        relative_paths.add((MATERIALIZER / name).as_posix())
    closure = {
        relative: sha256_path(REPO_ROOT / relative)
        for relative in sorted(relative_paths)
    }
    return closure, canonical_digest(closure)


def build_binary(package: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command([
        "go",
        "build",
        "-buildvcs=false",
        "-trimpath",
        "-o",
        str(output),
        package,
    ])


def validate_materialization(
    contract: dict[str, Any],
    materialization: dict[str, Any],
) -> None:
    expected_input = contract["candidate_input"]
    expected_literal = contract["expected_literal"]
    if materialization["input"] != expected_input:
        raise ValueError("materializer input changed")
    derived = materialization["derived"]
    if (
        derived["log_n"] != expected_literal["log_n"]
        or derived["log_q"] != expected_literal["log_q"]
        or derived["log_p"] != expected_literal["log_p"]
    ):
        raise ValueError("HIT formula replay changed")
    for field in (
        "concrete_import_q_identical",
        "concrete_import_p_identical",
        "scale_identical",
        "ring_identical",
        "xs_identical",
        "xe_identical",
        "exact_concrete_translation",
    ):
        if materialization[field] is not True:
            raise ValueError(f"exact translation failed: {field}")
    if not materialization.get("lattigo_v6_2_0_native_log_literal_error"):
        raise ValueError("native-v6 diagnostic unexpectedly changed")
    v2 = materialization["lattigo_v2_2_0"]
    imported = materialization["lattigo_v6_2_0_concrete_import"]
    if (
        v2["module"] != "github.com/ldsec/lattigo/v2"
        or v2["version"] != "v2.2.0"
        or imported["module"] != "github.com/tuneinsight/lattigo/v6"
        or imported["version"] != "v6.2.0"
        or v2["q"] != imported["q"]
        or v2["p"] != imported["p"]
        or imported["log_n"] != expected_literal["log_n"]
        or imported["log_default_scale"] !=
        expected_literal["log_default_scale"]
        or imported["ring_type"] != "standard"
        or imported["xs"] != "uniform_ternary_[1/3,1/3,1/3]"
        or imported["xe"] !=
        "discrete_gaussian_sigma_3.2_bound_19.2"
    ):
        raise ValueError("concrete runtime semantics changed")
    q_product = 1
    for value in imported["q"]:
        q_product *= value
    p_product = 1
    for value in imported["p"]:
        p_product *= value
    if (
        q_product.bit_length() != 181
        or p_product.bit_length() != 61
        or (q_product * p_product).bit_length() !=
        expected_literal["concrete_product_log_qp"]
    ):
        raise ValueError("concrete modulus-product measurement changed")


def candidate_request(
    materialization: dict[str, Any],
) -> dict[str, Any]:
    imported = materialization["lattigo_v6_2_0_concrete_import"]
    return {
        "schema_version": 2,
        "provider_kind": "external_autotuner",
        "provider_id": PROVIDER_ID,
        "path": "rescale",
        "parameters": {
            "log_n": imported["log_n"],
            "q": imported["q"],
            "p": imported["p"],
            "log_default_scale": imported["log_default_scale"],
        },
    }


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
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_model": cpu_model,
        "python_version": platform.python_version(),
        "go_version": command(["go", "version"]).stdout.strip(),
    }


def initialize(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
) -> None:
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite HIT replay: {output_root}"
        )
    for directory in ("raw_sources", "bin", "logs"):
        (output_root / directory).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(contract_path, output_root / "contract_snapshot.json")
    contract = load_json(contract_path)

    source_rows = []
    for source in contract["sources"]:
        url = source_url(contract, source)
        data = fetch_bytes(url)
        actual = "sha256:" + hashlib.sha256(data).hexdigest()
        if actual != source["sha256"]:
            raise ValueError(
                f"INTEGRITY_BLOCK: {source['source_id']} digest "
                f"{actual} != {source['sha256']}"
            )
        local = (
            output_root / "raw_sources" / source["source_id"] /
            Path(source["path"]).name
        )
        local.parent.mkdir()
        local.write_bytes(data)
        source_rows.append({
            **source,
            "url": url,
            "local_path": local.relative_to(output_root).as_posix(),
        })
    save_atomic(output_root / "source_manifest.json", {
        "schema_version": "flipguard_hit_source_manifest_v1",
        "sources": source_rows,
    })

    candidate_input = contract["candidate_input"]
    completed = command(
        [
            "go",
            "run",
            ".",
            "--num-slots",
            str(candidate_input["num_slots"]),
            "--max-ct-level",
            str(candidate_input["max_ct_level"]),
            "--log-scale",
            str(candidate_input["log_scale"]),
            "--num-ks-primes",
            str(candidate_input["num_ks_primes"]),
        ],
        cwd=REPO_ROOT / MATERIALIZER,
    )
    materialization = json.loads(completed.stdout)
    validate_materialization(contract, materialization)
    save_atomic(output_root / "materialization.json", materialization)
    request = candidate_request(materialization)
    save_atomic(output_root / "candidate_request.json", request)

    certify = output_root / "bin/flipguard-certify-candidate"
    audit = output_root / "bin/flipguard-audit-candidate"
    build_binary("./cmd/flipguard-certify-candidate", certify)
    build_binary("./cmd/flipguard-audit-candidate", audit)
    closure, closure_digest = execution_source_closure()
    manifest = {
        "schema_version": RUN_SCHEMA,
        "status": "PREFLIGHT_PASS",
        "source_commit": head,
        "origin_commit": origin,
        "working_tree_clean": True,
        "contract_sha256": sha256_path(contract_path),
        "contract_snapshot_sha256": sha256_path(
            output_root / "contract_snapshot.json"
        ),
        "source_manifest_sha256": sha256_path(
            output_root / "source_manifest.json"
        ),
        "materialization_sha256": sha256_path(
            output_root / "materialization.json"
        ),
        "candidate_request_sha256": sha256_path(
            output_root / "candidate_request.json"
        ),
        "execution_critical_source_files": closure,
        "execution_critical_source_digest": closure_digest,
        "binaries": {
            "certify_candidate": {
                "path": certify.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_path(certify),
            },
            "audit_candidate": {
                "path": audit.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_path(audit),
            },
        },
        "security_policy_digest":
            contract["policy"]["security_policy_digest"],
        "direct_policy_digest":
            contract["policy"]["direct_policy_digest"],
        "candidate_trials": 1,
        "synthesis_calls": 0,
        "repair_calls": 0,
        "retuning": 0,
        "host": host_metadata(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "paper_claim_allowed": False,
    }
    save_atomic(output_root / "run_manifest.json", manifest)
    save_atomic(output_root / "state.json", {
        "schema_version": RUN_SCHEMA,
        "stage": "PREFLIGHT_PASS",
        "selection": "PENDING",
        "audit": "PENDING",
        "candidate_trials_started": 0,
        "audit_trials_started": 0,
        "paper_claim_allowed": False,
    })


def verify_preflight(
    contract_path: Path,
    output_root: Path,
    head: str,
    origin: str,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    manifest = load_json(output_root / "run_manifest.json")
    state = load_json(output_root / "state.json")
    closure, closure_digest = execution_source_closure()
    if (
        manifest["source_commit"] != head
        or manifest["origin_commit"] != origin
        or manifest["contract_sha256"] != sha256_path(contract_path)
        or manifest["contract_snapshot_sha256"] != sha256_path(
            output_root / "contract_snapshot.json"
        )
        or manifest["execution_critical_source_files"] != closure
        or manifest["execution_critical_source_digest"] != closure_digest
    ):
        raise ValueError("INTEGRITY_BLOCK: HIT preflight provenance changed")
    if state["stage"] != "PREFLIGHT_PASS":
        raise ValueError(
            f"INTEGRITY_BLOCK: HIT replay is not resumable: {state['stage']}"
        )
    source_manifest = load_json(output_root / "source_manifest.json")
    expected_sources = {
        source["source_id"]: source for source in contract["sources"]
    }
    for source in source_manifest["sources"]:
        expected = expected_sources.pop(source["source_id"])
        local = output_root / source["local_path"]
        if (
            source["sha256"] != expected["sha256"]
            or sha256_path(local) != expected["sha256"]
        ):
            raise ValueError("INTEGRITY_BLOCK: HIT source replay changed")
    if expected_sources:
        raise ValueError("INTEGRITY_BLOCK: HIT source replay is incomplete")
    materialization = load_json(output_root / "materialization.json")
    validate_materialization(contract, materialization)
    if load_json(output_root / "candidate_request.json") != \
            candidate_request(materialization):
        raise ValueError("INTEGRITY_BLOCK: provider candidate changed")
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError("INTEGRITY_BLOCK: HIT replay binary changed")
    return state


def append_ledger(
    output_root: Path,
    stage: str,
    status: str,
    reason: str,
    command_line: list[str] | None = None,
    artifact: Path | None = None,
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
        "status": status,
        "reason": reason,
        "command": command_line,
        "artifact": (
            artifact.relative_to(output_root).as_posix()
            if artifact is not None and artifact.is_file()
            else None
        ),
        "artifact_sha256": (
            sha256_path(artifact)
            if artifact is not None and artifact.is_file()
            else None
        ),
    })
    save_atomic(path, ledger)


def build_summary(
    output_root: Path,
    selection: dict[str, Any] | None,
    audit: dict[str, Any] | None,
    implementation_failure: str | None = None,
) -> dict[str, Any]:
    selection_status = (
        None if selection is None else selection["trial"]["status"]
    )
    selection_outcome = (
        "IMPLEMENTATION_FAILURE"
        if implementation_failure
        else None if selection is None else selection["outcome"]
    )
    audit_status = (
        None if audit is None else audit["audit_trial"]["status"]
    )
    audit_outcome = None if audit is None else audit["outcome"]
    selected = selection_outcome == "SELECTED"
    audit_pass = audit_outcome == "LOCKED_AUDIT_PASS"
    return {
        "schema_version": RUN_SCHEMA,
        "status": (
            "RECOVERABLE_IMPLEMENTATION_FAILURE"
            if implementation_failure
            else "PASS"
        ),
        "classification": "SOURCE_REPLAYED_PUBLIC_PARAMETER_SELECTOR",
        "evaluation_role": "seed0_development_interoperability_control",
        "selection": {
            "outcome": selection_outcome,
            "status": selection_status,
            "candidate_trials": (
                0 if selection is None else selection["trials_used"]
            ),
            "key_runs": (
                0 if selection is None else selection["encrypted_key_runs"]
            ),
            "flips": (
                None
                if selection is None
                else selection["trial"]["decision_flips"]
            ),
            "violations": (
                None
                if selection is None
                else selection["trial"]["error_violations"]
            ),
        },
        "locked_audit": {
            "outcome": audit_outcome,
            "status": audit_status,
            "key_runs": (
                0
                if audit is None
                else audit["audit_trial"]["key_repeats_completed"]
            ),
            "flips": (
                None
                if audit is None
                else audit["audit_trial"]["decision_flips"]
            ),
            "violations": (
                None
                if audit is None
                else audit["audit_trial"]["error_violations"]
            ),
            "retuning": (
                0 if audit is None else int(audit["retuning_performed"])
            ),
        },
        "candidate_identity": (
            None
            if selection is None
            else selection["bound_candidate"]["candidate"]["id"]
        ),
        "selection_audit_candidate_identical": (
            None
            if audit is None or selection is None
            else audit["selected_candidate"] ==
            selection["bound_candidate"]["candidate"]
        ),
        "security": (
            None
            if selection is None
            else selection["bound_candidate"]["candidate"]["security"]
        ),
        "implementation_failure": implementation_failure,
        "claim_states": {
            "source_replayed_public_parameter_selector":
                "PARTIALLY_SUPPORTED",
            "lossless_cross_version_literal_import": "SUPPORTED",
            "encrypted_external_candidate_certification": (
                "PARTIALLY_SUPPORTED"
                if selected
                else "BLOCKED"
            ),
            "no_retuning_locked_audit": (
                "PARTIALLY_SUPPORTED"
                if audit_pass
                else "NOT_EVALUATED" if not selected else "BLOCKED"
            ),
            "general_external_autotuner_integration": "NOT_EVALUATED",
            "hit_candidate_quality": "NOT_EVALUATED",
        },
        "paper_claim_allowed": False,
    }


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_checksums(root: Path) -> None:
    indexed: set[str] = set()
    for line in (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
        digest, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file() or sha256_path(target) != f"sha256:{digest}":
            raise ValueError(f"HIT replay artifact changed: {relative}")
        indexed.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if indexed != actual:
        raise ValueError("HIT replay artifact file set changed")


def run_replay(
    contract_path: Path,
    output_root: Path,
    state: dict[str, Any],
) -> None:
    contract = load_json(contract_path)
    workload = contract["workload"]
    policy = contract["policy"]
    selection_path = output_root / "selection.json"
    audit_path = output_root / "locked_audit.json"
    candidate_path = output_root / "candidate_request.json"
    certify = output_root / "bin/flipguard-certify-candidate"
    audit_binary = output_root / "bin/flipguard-audit-candidate"

    state["stage"] = "SELECTION_RUNNING"
    state["selection"] = "RUNNING"
    state["candidate_trials_started"] = 1
    save_atomic(output_root / "state.json", state)
    selection_command = [
        str(certify),
        "--model",
        workload["model_path"],
        "--validation",
        workload["validation_path"],
        "--split-id",
        workload["split_id"],
        "--candidate",
        str(candidate_path),
        "--margin-floor",
        str(policy["margin_floor"]),
        "--safety-factor",
        str(policy["safety_factor"]),
        "--key-repeats",
        str(policy["validation_key_repeats"]),
        "--out",
        str(selection_path),
    ]
    append_ledger(
        output_root,
        "selection",
        "RUNNING",
        "single predeclared candidate started",
        selection_command,
    )
    completed = command(
        selection_command,
        check=False,
        log_path=output_root / "logs/selection.log",
    )
    if completed.returncode != 0 or not selection_path.is_file():
        reason = f"selection_exit_code={completed.returncode}"
        state["stage"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["selection"] = "IMPLEMENTATION_FAILURE"
        state["audit"] = "NOT_APPLICABLE"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "selection",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
            reason,
            selection_command,
            selection_path,
        )
        save_atomic(
            output_root / "summary.json",
            build_summary(output_root, None, None, reason),
        )
        finalize(output_root, state["stage"])
        return

    selection = load_json(selection_path)
    state["selection"] = selection["outcome"]
    append_ledger(
        output_root,
        "selection",
        (
            "PASS"
            if selection["outcome"] == "SELECTED"
            else "PARTIAL_SCIENTIFIC_RESULT"
        ),
        (
            f"outcome={selection['outcome']} "
            f"status={selection['trial']['status']}"
        ),
        selection_command,
        selection_path,
    )
    if selection["outcome"] != "SELECTED":
        state["stage"] = "COMPLETE_PARTIAL_SCIENTIFIC_RESULT"
        state["audit"] = "NOT_APPLICABLE"
        save_atomic(output_root / "state.json", state)
        save_atomic(
            output_root / "summary.json",
            build_summary(output_root, selection, None),
        )
        finalize(output_root, state["stage"])
        return

    state["stage"] = "AUDIT_RUNNING"
    state["audit"] = "RUNNING"
    state["audit_trials_started"] = 1
    save_atomic(output_root / "state.json", state)
    audit_command = [
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
    ]
    append_ledger(
        output_root,
        "locked_audit",
        "RUNNING",
        "byte-identical selected literal replay started",
        audit_command,
    )
    completed = command(
        audit_command,
        check=False,
        log_path=output_root / "logs/locked_audit.log",
    )
    if completed.returncode != 0 or not audit_path.is_file():
        reason = f"audit_exit_code={completed.returncode}"
        state["stage"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        state["audit"] = "IMPLEMENTATION_FAILURE"
        save_atomic(output_root / "state.json", state)
        append_ledger(
            output_root,
            "locked_audit",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
            reason,
            audit_command,
            audit_path,
        )
        save_atomic(
            output_root / "summary.json",
            build_summary(output_root, selection, None, reason),
        )
        finalize(output_root, state["stage"])
        return
    audit = load_json(audit_path)
    state["audit"] = audit["outcome"]
    state["stage"] = (
        "COMPLETE"
        if audit["outcome"] == "LOCKED_AUDIT_PASS"
        else "COMPLETE_PARTIAL_SCIENTIFIC_RESULT"
    )
    save_atomic(output_root / "state.json", state)
    append_ledger(
        output_root,
        "locked_audit",
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
        audit_command,
        audit_path,
    )
    save_atomic(
        output_root / "summary.json",
        build_summary(output_root, selection, audit),
    )
    finalize(output_root, state["stage"])


def finalize(output_root: Path, status: str) -> None:
    manifest = load_json(output_root / "run_manifest.json")
    save_atomic(output_root / "completion_manifest.json", {
        "schema_version": RUN_SCHEMA,
        "status": status,
        "run_manifest_sha256": sha256_path(
            output_root / "run_manifest.json"
        ),
        "summary_sha256": sha256_path(output_root / "summary.json"),
        "source_commit": manifest["source_commit"],
        "candidate_trials_started": load_json(
            output_root / "state.json"
        )["candidate_trials_started"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "paper_claim_allowed": False,
    })
    write_checksums(output_root)


def verify_output(
    contract_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    contract_path = (
        contract_path
        if contract_path.is_absolute()
        else REPO_ROOT / contract_path
    )
    output_root = (
        output_root
        if output_root.is_absolute()
        else REPO_ROOT / output_root
    )
    VERIFIER.validate_contract(contract_path)
    verify_checksums(output_root)
    contract = load_json(contract_path)
    if sha256_path(output_root / "contract_snapshot.json") != \
            sha256_path(contract_path):
        raise ValueError("HIT contract snapshot changed")
    materialization = load_json(output_root / "materialization.json")
    validate_materialization(contract, materialization)
    if load_json(output_root / "candidate_request.json") != \
            candidate_request(materialization):
        raise ValueError("HIT provider request changed")
    summary = load_json(output_root / "summary.json")
    state = load_json(output_root / "state.json")
    completion = load_json(output_root / "completion_manifest.json")
    if (
        summary["paper_claim_allowed"] is not False
        or completion["paper_claim_allowed"] is not False
        or completion["status"] != state["stage"]
        or completion["run_manifest_sha256"] != sha256_path(
            output_root / "run_manifest.json"
        )
        or completion["summary_sha256"] != sha256_path(
            output_root / "summary.json"
        )
        or state["candidate_trials_started"] != 1
    ):
        raise ValueError("HIT completion gate changed")
    selection_path = output_root / "selection.json"
    selection = (
        load_json(selection_path) if selection_path.is_file() else None
    )
    audit_path = output_root / "locked_audit.json"
    audit = load_json(audit_path) if audit_path.is_file() else None
    if selection is not None:
        candidate = selection["bound_candidate"]["candidate"]
        expected = candidate_request(materialization)["parameters"]
        if (
            selection["trials_used"] != 1
            or candidate["parameters"] != expected
            or candidate["security"]["final_admission"] != "PASS"
            or candidate["security"]["measurement"] !=
            "ceil_log2_concrete_modulus_product"
            or candidate["security"]["log_qp"] != 242
        ):
            raise ValueError("HIT selection literal or ledger changed")
        if selection["outcome"] == "SELECTED" and audit is None:
            raise ValueError("selected HIT candidate has no locked audit")
    if audit is not None and (
        selection is None
        or audit["retuning_performed"] is not False
        or audit["selected_candidate"] !=
        selection["bound_candidate"]["candidate"]
    ):
        raise ValueError("HIT locked-audit identity changed")
    expected_summary = build_summary(
        output_root,
        selection,
        audit,
        summary["implementation_failure"],
    )
    if summary != expected_summary:
        raise ValueError("HIT summary changed")
    return summary


def main() -> int:
    args = parse_args()
    contract_path = (
        args.contract
        if args.contract.is_absolute()
        else REPO_ROOT / args.contract
    )
    if args.verify:
        if args.output_root is None:
            raise ValueError("--output-root is required with --verify")
        summary = verify_output(contract_path, args.output_root)
        print(
            "hit_external_adapter_replay=VERIFIED "
            f"selection={summary['selection']['status']} "
            f"audit={summary['locked_audit']['status']} "
            "paper_claim_allowed=false"
        )
        return 0
    VERIFIER.validate_contract(contract_path)
    head, origin = require_clean_origin()
    output_root = (
        REPO_ROOT / DEFAULT_OUTPUT_PARENT / f"run_{head[:7]}"
        if args.output_root is None
        else args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if args.resume:
        state = verify_preflight(
            contract_path,
            output_root,
            head,
            origin,
        )
        run_replay(contract_path, output_root, state)
        summary = verify_output(contract_path, output_root)
        print(
            "hit_external_adapter_replay=COMPLETE "
            f"selection={summary['selection']['status']} "
            f"audit={summary['locked_audit']['status']} "
            f"output={output_root}"
        )
        return 0
    initialize(contract_path, output_root, head, origin)
    print(
        "hit_external_adapter_preflight=PASS "
        f"source_commit={head} output={output_root}"
    )
    if not args.preflight_only:
        print("encrypted_execution=NOT_STARTED use --resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
