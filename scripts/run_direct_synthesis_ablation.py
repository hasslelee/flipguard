#!/usr/bin/env python3
"""Run and summarize the predeclared seed-0 direct-synthesis ablation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("configs/direct_synthesis_ablation_v1.json")
DIRECT_PACK = Path(
    "docs/evidence/direct_locked_audit_seed0_development_v1"
)
CATALOG_PACK = Path("docs/evidence/security_v2_bounded_oracle_v1")
RESULT_BASE = Path(
    "results/thesis_grade_protocol/direct_synthesis_ablation_v1"
)
SCHEMA_VERSION = "flipguard_direct_synthesis_ablation_run_v1"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXPECTED_DATASETS = (
    "banknote",
    "digits_binary",
    "iris_binary",
    "mnist_pool16",
    "wdbc",
)
EXPECTED_MODELS = ("linear_poly3", "mlp_square_linear_score")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight-only", action="store_true")
    action.add_argument("--resume", action="store_true")
    parser.add_argument("--run-root", type=Path)
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().isoformat()


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


def write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run_checked(
    command: Sequence[str],
    *,
    stdout_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if stdout_path is None:
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="ascii") as handle:
        return subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )


def git_text(*arguments: str) -> str:
    return run_checked(["git", *arguments]).stdout.strip()


def require_clean_provenance() -> tuple[str, str]:
    head = git_text("rev-parse", "HEAD")
    origin = git_text(
        "rev-parse",
        "origin/feature/flipguard-auto-tuner",
    )
    status = git_text("status", "--short")
    if status:
        raise ValueError(
            "INTEGRITY_BLOCK: working tree is not clean:\n" + status
        )
    if head != origin:
        raise ValueError(
            f"INTEGRITY_BLOCK: HEAD {head} != origin {origin}"
        )
    return head, origin


def execution_source_closure() -> tuple[dict[str, str], str]:
    output = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--",
            "cmd",
            "internal",
            "go.mod",
            "go.sum",
        ],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    paths = [
        Path(value.decode("utf-8"))
        for value in output.split(b"\0")
        if value
    ]
    closure = {
        path.as_posix(): sha256_path(REPO_ROOT / path)
        for path in sorted(paths)
    }
    return closure, canonical_digest(closure)


def load_contract() -> dict[str, Any]:
    contract = json.loads(
        (REPO_ROOT / CONTRACT_PATH).read_text(encoding="ascii")
    )
    if contract["schema_version"] != \
            "flipguard_direct_synthesis_ablation_contract_v1" or \
            contract["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            contract["security_policy_digest"] != \
                SECURITY_POLICY_DIGEST or \
            contract["split_seed"] != 0 or \
            contract["datasets"] != list(EXPECTED_DATASETS) or \
            contract["model_ids"] != list(EXPECTED_MODELS) or \
            contract["fixed_output_error_budget"] != 0.001 or \
            contract["safety_factor"] != 0.5 or \
            contract["margin_floor"] != 0.001 or \
            contract["max_encrypted_trials"] != 4 or \
            contract["key_repeats"] != 3 or \
            contract["paper_claim_allowed"]:
        raise ValueError("INTEGRITY_BLOCK: ablation contract changed")
    expected_arms = {
        "graph_only_fixed_tolerance",
        "one_shot_direct",
        "full_flipguard",
        "latency_only_no_certification",
    }
    if {arm["id"] for arm in contract["arms"]} != expected_arms:
        raise ValueError("INTEGRITY_BLOCK: ablation arms changed")
    return contract


def verify_sha256sums(pack: Path) -> None:
    checksum_path = pack / "SHA256SUMS"
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        path = pack / relative
        if sha256_path(path) != "sha256:" + digest:
            raise ValueError(
                f"INTEGRITY_BLOCK: frozen pack changed: {path}"
            )


def validate_security(candidate: dict[str, Any]) -> None:
    security = candidate["security"]
    if security["envelope_id"] != \
            "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError("INTEGRITY_BLOCK: security policy ID changed")
    for field in (
        "admission_status",
        "ciphertext_q_admission",
        "evaluation_key_qp_admission",
        "final_admission",
    ):
        if security[field] != "PASS":
            raise ValueError(
                "INTEGRITY_BLOCK: inadmissible ablation candidate "
                f"{candidate['id']}"
            )


def load_direct_workloads() -> list[dict[str, Any]]:
    pack = REPO_ROOT / DIRECT_PACK
    verify_sha256sums(pack)
    manifest = json.loads(
        (pack / "manifest.json").read_text(encoding="ascii")
    )
    workloads = manifest["workloads"]
    expected = {
        (dataset, model)
        for dataset in EXPECTED_DATASETS
        for model in EXPECTED_MODELS
    }
    observed = {
        (row["dataset_id"], row["model_id"])
        for row in workloads
        if int(row["split_seed"]) == 0
    }
    if observed != expected or len(workloads) != 10:
        raise ValueError("INTEGRITY_BLOCK: direct seed-0 matrix changed")
    for row in workloads:
        selection_path = pack / row["selection_snapshot"]
        audit_path = pack / row["audit_result_snapshot"]
        selection = json.loads(
            selection_path.read_text(encoding="ascii")
        )
        audit = json.loads(audit_path.read_text(encoding="ascii"))
        if selection["plan"]["direct_policy_digest"] != \
                DIRECT_POLICY_DIGEST or \
                selection["plan"]["security_policy_digest"] != \
                    SECURITY_POLICY_DIGEST or \
                selection["outcome"] != "SELECTED" or \
                audit["selected_candidate"] != selection["selected"] or \
                audit["retuning_performed"]:
            raise ValueError(
                "INTEGRITY_BLOCK: frozen direct identity changed"
            )
        validate_security(selection["selected"])
    return sorted(
        workloads,
        key=lambda row: (row["dataset_id"], row["model_id"]),
    )


def verify_catalog_pack() -> dict[str, Any]:
    pack = REPO_ROOT / CATALOG_PACK
    manifest = json.loads(
        (pack / "manifest.json").read_text(encoding="ascii")
    )
    for relative, record in manifest["files"].items():
        if sha256_path(pack / relative) != record["sha256"]:
            raise ValueError(
                f"INTEGRITY_BLOCK: catalog pack changed: {relative}"
            )
    summary = json.loads(
        (pack / "oracle/summary.json").read_text(encoding="ascii")
    )
    if summary["security_policy_digest"] != SECURITY_POLICY_DIGEST or \
            summary["development_catalog_candidates"] != 140 or \
            summary["candidate_identities_per_workload_after"] != 14 or \
            summary["allow_incomplete"]:
        raise ValueError("INTEGRITY_BLOCK: catalog accounting changed")
    return manifest


def build_binaries(run_root: Path) -> dict[str, dict[str, str]]:
    targets = {
        "materialize": "./cmd/flipguard-materialize-tabular",
        "synthesize": "./cmd/flipguard-synthesize",
        "autotune": "./cmd/flipguard-autotune",
        "audit": "./cmd/flipguard-audit",
    }
    binaries = {}
    for name, target in targets.items():
        path = run_root / "bin" / f"flipguard-{name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        run_checked(["go", "build", "-o", str(path), target])
        binaries[name] = {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": sha256_path(path),
            "target": target,
        }
    return binaries


def workload_paths(row: dict[str, Any]) -> dict[str, Path]:
    pack = REPO_ROOT / DIRECT_PACK
    return {
        "model": pack / row["model_artifact_snapshot"],
        "validation_source": pack / row["source_data_snapshot"],
        "prepared_validation": pack
        / row["prepared_validation_snapshot"],
        "audit_source": pack / row["audit_source_snapshot"],
        "split_manifest": pack / row["split_manifest_snapshot"],
        "full_selection": pack / row["selection_snapshot"],
        "full_audit": pack / row["audit_result_snapshot"],
    }


def validate_graph_plan(
    plan: dict[str, Any],
    row: dict[str, Any],
) -> None:
    policy = plan["policy"]
    contract = plan["contract"]
    if plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST or \
            policy["synthesis_budget_mode"] != \
                "graph_fixed_tolerance" or \
            policy["fixed_output_error_budget"] != 0.001 or \
            policy["repair_scale_step_bits"] != 4 or \
            policy["max_repair_levels"] != 2 or \
            contract["decision"]["margin_floor"] != 0.001 or \
            contract["decision"]["safety_factor"] != 0.5 or \
            contract["deployment"]["max_encrypted_trials"] != 4 or \
            contract["deployment"]["validation_key_repeats"] != 3 or \
            contract["dataset_id"] != row["dataset_id"] or \
            contract["model_id"] != row["model_id"]:
        raise ValueError(
            "INTEGRITY_BLOCK: graph-only plan contract changed"
        )
    if len(plan["initial_candidates"]) != 1:
        raise ValueError(
            "INTEGRITY_BLOCK: graph-only initial candidate count changed"
        )
    validate_security(plan["initial_candidates"][0])


def preflight(run_root: Path) -> dict[str, Any]:
    if run_root.exists():
        raise ValueError(
            f"refusing to overwrite existing run root: {run_root}"
        )
    head, origin = require_clean_provenance()
    contract = load_contract()
    workloads = load_direct_workloads()
    catalog_manifest = verify_catalog_pack()
    run_root.mkdir(parents=True)
    binaries = build_binaries(run_root)
    source_files, source_digest = execution_source_closure()
    plans = []
    for row in workloads:
        paths = workload_paths(row)
        tag = f"seed0__{row['dataset_id']}__{row['model_id']}"
        prepared = run_root / "preflight/prepared" / f"{tag}.csv"
        materialization = (
            run_root / "preflight/materialization" / f"{tag}.json"
        )
        plan_path = run_root / "preflight/plans" / f"{tag}.json"
        prepared.parent.mkdir(parents=True, exist_ok=True)
        materialization.parent.mkdir(parents=True, exist_ok=True)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        run_checked(
            [
                str(run_root / "bin/flipguard-materialize"),
                "--model",
                str(paths["model"].relative_to(REPO_ROOT)),
                "--data",
                str(
                    paths["validation_source"].relative_to(REPO_ROOT)
                ),
                "--data-space",
                "model",
                "--out",
                str(prepared.relative_to(REPO_ROOT)),
                "--manifest-out",
                str(materialization.relative_to(REPO_ROOT)),
            ]
        )
        if sha256_path(prepared) != \
                sha256_path(paths["prepared_validation"]):
            raise ValueError(
                "INTEGRITY_BLOCK: prepared validation replay changed "
                f"for {tag}"
            )
        run_checked(
            [
                str(run_root / "bin/flipguard-synthesize"),
                "--model",
                str(paths["model"].relative_to(REPO_ROOT)),
                "--validation",
                str(prepared.relative_to(REPO_ROOT)),
                "--split-id",
                "split_seed_0",
                "--margin-floor",
                "0.001",
                "--safety-factor",
                "0.5",
                "--key-repeats",
                "3",
                "--max-encrypted-trials",
                "4",
                "--synthesis-budget-mode",
                "graph_fixed_tolerance",
                "--fixed-output-error-budget",
                "0.001",
                "--out",
                str(plan_path.relative_to(REPO_ROOT)),
            ]
        )
        plan = json.loads(plan_path.read_text(encoding="ascii"))
        validate_graph_plan(plan, row)
        plans.append(
            {
                "tag": tag,
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "model_sha256": sha256_path(paths["model"]),
                "validation_source_sha256":
                    sha256_path(paths["validation_source"]),
                "prepared_validation_sha256": sha256_path(prepared),
                "audit_source_sha256":
                    sha256_path(paths["audit_source"]),
                "split_manifest_sha256":
                    sha256_path(paths["split_manifest"]),
                "full_selection_sha256":
                    sha256_path(paths["full_selection"]),
                "full_audit_sha256":
                    sha256_path(paths["full_audit"]),
                "plan_path": str(plan_path.relative_to(REPO_ROOT)),
                "plan_sha256": sha256_path(plan_path),
                "initial_candidate":
                    plan["initial_candidates"][0],
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "PREFLIGHT_PASS",
        "source_commit": head,
        "origin_commit": origin,
        "working_tree_clean": True,
        "execution_critical_source_files": source_files,
        "execution_critical_source_digest": source_digest,
        "orchestrator_path":
            "scripts/run_direct_synthesis_ablation.py",
        "orchestrator_sha256": sha256_path(
            REPO_ROOT / "scripts/run_direct_synthesis_ablation.py"
        ),
        "protocol_path":
            "docs/research/step_7e1_direct_synthesis_ablation_protocol.md",
        "protocol_sha256": sha256_path(
            REPO_ROOT
            / "docs/research/step_7e1_direct_synthesis_ablation_protocol.md"
        ),
        "ablation_contract_path": str(CONTRACT_PATH),
        "ablation_contract_sha256": sha256_path(
            REPO_ROOT / CONTRACT_PATH
        ),
        "ablation_contract_digest": canonical_digest(contract),
        "direct_pack_manifest_sha256": sha256_path(
            REPO_ROOT / DIRECT_PACK / "manifest.json"
        ),
        "catalog_pack_manifest_sha256": sha256_path(
            REPO_ROOT / CATALOG_PACK / "manifest.json"
        ),
        "catalog_file_binding": catalog_manifest["files"],
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "binaries": binaries,
        "plans": plans,
        "versions": {
            "go": run_checked(["go", "version"]).stdout.strip(),
            "python": sys.version.split()[0],
        },
        "host": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "preflight_started_at": now(),
        "paper_claim_allowed": False,
    }
    write_atomic(run_root / "run_manifest.json", manifest)
    state = {
        "schema_version": SCHEMA_VERSION,
        "run_manifest_sha256": sha256_path(
            run_root / "run_manifest.json"
        ),
        "stage": "PREFLIGHT_PASS",
        "workloads": {
            plan["tag"]: {
                "dataset_id": plan["dataset_id"],
                "model_id": plan["model_id"],
                "graph_selection": {"status": "PENDING"},
                "graph_audit": {"status": "PENDING"},
            }
            for plan in plans
        },
        "recoveries": [],
        "paper_claim_allowed": False,
    }
    write_atomic(run_root / "state.json", state)
    return manifest


def verify_resume_gate(
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    head, origin = require_clean_provenance()
    load_contract()
    load_direct_workloads()
    verify_catalog_pack()
    manifest_path = run_root / "run_manifest.json"
    state_path = run_root / "state.json"
    manifest = json.loads(manifest_path.read_text(encoding="ascii"))
    state = json.loads(state_path.read_text(encoding="ascii"))
    if manifest["source_commit"] != manifest["origin_commit"] or \
            manifest["status"] != "PREFLIGHT_PASS" or \
            manifest["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            manifest["security_policy_digest"] != \
                SECURITY_POLICY_DIGEST or \
            state["run_manifest_sha256"] != sha256_path(manifest_path):
        raise ValueError("INTEGRITY_BLOCK: resume provenance changed")
    if manifest["execution_critical_source_digest"] != \
            execution_source_closure()[1]:
        raise ValueError(
            "INTEGRITY_BLOCK: execution source closure changed"
        )
    if manifest["ablation_contract_sha256"] != \
            sha256_path(REPO_ROOT / CONTRACT_PATH):
        raise ValueError(
            "INTEGRITY_BLOCK: ablation contract bytes changed"
        )
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError("INTEGRITY_BLOCK: execution binary changed")
    for plan_record in manifest["plans"]:
        plan_path = REPO_ROOT / plan_record["plan_path"]
        if sha256_path(plan_path) != plan_record["plan_sha256"]:
            raise ValueError("INTEGRITY_BLOCK: static plan changed")
        row = {
            "dataset_id": plan_record["dataset_id"],
            "model_id": plan_record["model_id"],
        }
        validate_graph_plan(
            json.loads(plan_path.read_text(encoding="ascii")),
            row,
        )
    state.setdefault("resume_records", []).append(
        {
            "timestamp": now(),
            "current_commit": head,
            "current_origin_commit": origin,
            "execution_commit": manifest["source_commit"],
            "execution_critical_source_digest":
                manifest["execution_critical_source_digest"],
        }
    )
    write_atomic(state_path, state)
    return manifest, state


def write_command(path: Path, command: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(" ".join(command) + "\n", encoding="ascii")


def execute_with_retries(
    command: Sequence[str],
    log_base: Path,
) -> tuple[bool, int, str]:
    last_detail = ""
    for attempt in range(1, 4):
        log_path = log_base.with_name(
            f"{log_base.stem}.attempt{attempt}{log_base.suffix}"
        )
        if log_path.exists():
            raise ValueError(
                f"refusing to overwrite attempt log: {log_path}"
            )
        write_command(log_path.with_suffix(".command.txt"), command)
        try:
            run_checked(command, stdout_path=log_path)
            return True, attempt, sha256_path(log_path)
        except subprocess.CalledProcessError as exc:
            last_detail = (
                f"exit={exc.returncode} log={log_path} "
                f"log_sha256={sha256_path(log_path)}"
            )
    return False, 3, last_detail


def selection_evaluations(result: dict[str, Any]) -> int:
    samples = int(
        result["plan"]["contract"]["decision"]["validation_samples"]
    )
    return sum(
        samples * int(trial["key_repeats_completed"])
        for trial in result["trials"]
    )


def validate_graph_selection(
    result: dict[str, Any],
    row: dict[str, Any],
) -> str:
    validate_graph_plan(result["plan"], row)
    if result["trials_used"] != len(result["trials"]) or \
            result["trials_used"] > 4:
        raise ValueError(
            "INTEGRITY_BLOCK: graph-only trial accounting changed"
        )
    for trial in result["trials"]:
        validate_security(trial["candidate"])
    outcome = result["outcome"]
    if outcome == "SELECTED":
        if result["selected"] != result["trials"][-1]["candidate"] or \
                result["trials"][-1]["status"] != "SAFE":
            raise ValueError(
                "INTEGRITY_BLOCK: graph-only first-SAFE changed"
            )
    elif outcome != "NO_SAFE":
        raise ValueError(
            f"INTEGRITY_BLOCK: unknown graph outcome {outcome}"
        )
    return outcome


def validate_graph_audit(
    audit: dict[str, Any],
    selection: dict[str, Any],
) -> str:
    if audit["retuning_performed"] or \
            audit["selected_candidate"] != selection["selected"] or \
            audit["selection_contract_digest"] != \
                selection["plan"]["contract_digest"]:
        raise ValueError(
            "INTEGRITY_BLOCK: graph-only audit identity changed"
        )
    validate_security(audit["selected_candidate"])
    outcome = audit["outcome"]
    if outcome not in ("LOCKED_AUDIT_PASS", "LOCKED_AUDIT_FAIL"):
        raise ValueError(
            f"INTEGRITY_BLOCK: unknown graph audit outcome {outcome}"
        )
    return outcome


def build_path_binding_manifest(
    source_path: Path,
    validation_source: Path,
    audit_source: Path,
    output_path: Path,
) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="ascii"))
    replay = json.loads(source_path.read_text(encoding="ascii"))
    expected = {
        "configuration_validation": validation_source,
        "locked_audit_test": audit_source,
    }
    original_paths = {}
    for partition, artifact in expected.items():
        if source[partition]["csv_digest"] != sha256_path(artifact):
            raise ValueError(
                "INTEGRITY_BLOCK: split manifest digest does not "
                f"match {artifact}"
            )
        original_paths[partition] = source[partition]["path"]
        replay[partition]["path"] = str(
            artifact.relative_to(REPO_ROOT)
        )
    replay["representation_recovery"] = {
        "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
        "reason_code": "FROZEN_EQUIVALENT_PATH_BINDING_MISMATCH",
        "source_manifest_path": str(
            source_path.relative_to(REPO_ROOT)
        ),
        "source_manifest_sha256": sha256_path(source_path),
        "original_paths": original_paths,
        "bound_paths": {
            partition: replay[partition]["path"]
            for partition in expected
        },
        "row_membership_changed": False,
        "csv_digest_changed": False,
        "encrypted_execution_before_recovery": False,
    }
    write_atomic(output_path, replay)
    observed = json.loads(output_path.read_text(encoding="ascii"))
    for partition in expected:
        if observed[partition]["row_ids"] != \
                source[partition]["row_ids"] or \
                observed[partition]["csv_digest"] != \
                source[partition]["csv_digest"] or \
                observed[partition]["path"] != \
                replay[partition]["path"]:
            raise ValueError(
                "INTEGRITY_BLOCK: path-binding manifest changed "
                f"{partition} semantics"
            )
    return replay["representation_recovery"]


def execute_graph_arm(
    run_root: Path,
    manifest: dict[str, Any],
    state: dict[str, Any],
) -> None:
    direct_rows = {
        (row["dataset_id"], row["model_id"]): row
        for row in load_direct_workloads()
    }
    autotune = str(
        REPO_ROOT / manifest["binaries"]["autotune"]["path"]
    )
    audit_binary = str(
        REPO_ROOT / manifest["binaries"]["audit"]["path"]
    )
    resume_epoch = len(state.get("resume_records", []))
    for plan_record in manifest["plans"]:
        tag = plan_record["tag"]
        row = direct_rows[
            (plan_record["dataset_id"], plan_record["model_id"])
        ]
        paths = workload_paths(row)
        workload = state["workloads"][tag]
        selection_path = (
            run_root / "graph_only/selection/results" / f"{tag}.json"
        )
        prepared_validation = (
            run_root
            / "graph_only/selection/prepared"
            / f"{tag}.csv"
        )
        if workload["graph_selection"]["status"] == "PENDING":
            selection_path.parent.mkdir(parents=True, exist_ok=True)
            prepared_validation.parent.mkdir(parents=True, exist_ok=True)
            command = [
                autotune,
                "--model",
                str(paths["model"].relative_to(REPO_ROOT)),
                "--data",
                str(
                    paths["validation_source"].relative_to(REPO_ROOT)
                ),
                "--data-space",
                "model",
                "--prepared-validation-out",
                str(prepared_validation.relative_to(REPO_ROOT)),
                "--split-id",
                "split_seed_0",
                "--margin-floor",
                "0.001",
                "--safety-factor",
                "0.5",
                "--key-repeats",
                "3",
                "--max-encrypted-trials",
                "4",
                "--synthesis-budget-mode",
                "graph_fixed_tolerance",
                "--fixed-output-error-budget",
                "0.001",
                "--out",
                str(selection_path.relative_to(REPO_ROOT)),
            ]
            success, attempts, detail = execute_with_retries(
                command,
                run_root
                / "graph_only/selection/logs"
                / f"{tag}.resume{resume_epoch}.log",
            )
            if not success:
                workload["graph_selection"] = {
                    "status": "RECOVERABLE_IMPLEMENTATION_FAILURE",
                    "attempts": attempts,
                    "detail": detail,
                }
                workload["graph_audit"] = {
                    "status": "SKIPPED_SELECTION_EXECUTION_FAILURE"
                }
                write_atomic(run_root / "state.json", state)
                continue
            if sha256_path(prepared_validation) != \
                    sha256_path(paths["prepared_validation"]):
                raise ValueError(
                    "INTEGRITY_BLOCK: execution materialization changed"
                )
            result = json.loads(
                selection_path.read_text(encoding="ascii")
            )
            outcome = validate_graph_selection(result, row)
            workload["graph_selection"] = {
                "status": (
                    "PASS"
                    if outcome == "SELECTED"
                    else "PARTIAL_SCIENTIFIC_RESULT"
                ),
                "outcome": outcome,
                "attempts": attempts,
                "result_path": str(
                    selection_path.relative_to(REPO_ROOT)
                ),
                "result_sha256": sha256_path(selection_path),
                "prepared_validation_sha256":
                    sha256_path(prepared_validation),
                "trials": result["trials_used"],
                "key_runs": result["encrypted_key_runs"],
                "encrypted_sample_evaluations":
                    selection_evaluations(result),
            }
            if outcome == "NO_SAFE":
                workload["graph_audit"] = {
                    "status": "NOT_APPLICABLE_NO_SAFE"
                }
            write_atomic(run_root / "state.json", state)
        if workload["graph_selection"].get("outcome") != "SELECTED":
            continue
        audit_path = (
            run_root / "graph_only/audit/results" / f"{tag}.json"
        )
        if workload["graph_audit"]["status"] == \
                "RECOVERABLE_IMPLEMENTATION_FAILURE" and \
                not audit_path.exists():
            workload["graph_audit"] = {"status": "PENDING"}
        if workload["graph_audit"]["status"] != "PENDING":
            continue
        selection = json.loads(
            selection_path.read_text(encoding="ascii")
        )
        prepared_audit = (
            run_root / "graph_only/audit/prepared" / f"{tag}.csv"
        )
        compatibility_manifest = (
            run_root / "graph_only/audit/manifests" / f"{tag}.json"
        )
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        prepared_audit.parent.mkdir(parents=True, exist_ok=True)
        compatibility_manifest.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        representation_recovery = build_path_binding_manifest(
            paths["split_manifest"],
            paths["validation_source"],
            paths["audit_source"],
            compatibility_manifest,
        )
        if not any(
            record.get("reason_code")
            == "FROZEN_EQUIVALENT_PATH_BINDING_MISMATCH"
            and record.get("tag") == tag
            for record in state["recoveries"]
        ):
            state["recoveries"].append(
                {
                    "timestamp": now(),
                    "tag": tag,
                    **representation_recovery,
                    "compatibility_manifest_path": str(
                        compatibility_manifest.relative_to(REPO_ROOT)
                    ),
                    "compatibility_manifest_sha256":
                        sha256_path(compatibility_manifest),
                    "selection_rerun": False,
                    "prior_audit_reached_ckks_execution": False,
                }
            )
            write_atomic(run_root / "state.json", state)
        command = [
            audit_binary,
            "--selection",
            str(selection_path.relative_to(REPO_ROOT)),
            "--audit",
            str(paths["audit_source"].relative_to(REPO_ROOT)),
            "--prepared-audit-out",
            str(prepared_audit.relative_to(REPO_ROOT)),
            "--audit-data-space",
            "model",
            "--manifest",
            str(compatibility_manifest.relative_to(REPO_ROOT)),
            "--key-repeats",
            "3",
            "--out",
            str(audit_path.relative_to(REPO_ROOT)),
        ]
        success, attempts, detail = execute_with_retries(
            command,
            run_root
            / "graph_only/audit/logs"
            / f"{tag}.resume{resume_epoch}.log",
        )
        if not success:
            workload["graph_audit"] = {
                "status": "RECOVERABLE_IMPLEMENTATION_FAILURE",
                "attempts": attempts,
                "detail": detail,
            }
            write_atomic(run_root / "state.json", state)
            continue
        audit = json.loads(audit_path.read_text(encoding="ascii"))
        outcome = validate_graph_audit(audit, selection)
        trial = audit["audit_trial"]
        workload["graph_audit"] = {
            "status": (
                "PASS"
                if outcome == "LOCKED_AUDIT_PASS"
                else "PARTIAL_SCIENTIFIC_RESULT"
            ),
            "outcome": outcome,
            "attempts": attempts,
            "result_path": str(audit_path.relative_to(REPO_ROOT)),
            "result_sha256": sha256_path(audit_path),
            "prepared_audit_sha256": sha256_path(prepared_audit),
            "source_split_manifest_sha256":
                sha256_path(paths["split_manifest"]),
            "compatibility_manifest_sha256":
                sha256_path(compatibility_manifest),
            "retuning": 0,
            "key_runs": trial["key_repeats_completed"],
            "encrypted_sample_evaluations": (
                int(
                    audit["audit_contract"]["decision"][
                        "validation_samples"
                    ]
                )
                * int(trial["key_repeats_completed"])
            ),
            "flips": trial["decision_flips"],
            "violations": trial["error_violations"],
        }
        write_atomic(run_root / "state.json", state)


def load_catalog_views() -> tuple[dict[tuple[str, str], dict], dict]:
    pack = REPO_ROOT / CATALOG_PACK
    with (
        pack / "oracle/oracle_selection_security_v2.csv"
    ).open(newline="", encoding="ascii") as handle:
        selection_rows = list(csv.DictReader(handle))
    with (
        pack / "oracle/candidate_certificates_security_v2.csv"
    ).open(newline="", encoding="ascii") as handle:
        certificate_rows = list(csv.DictReader(handle))
    primary = {
        (row["dataset_id"], row["model_id"]): row
        for row in selection_rows
        if row["split_seed"] == "0" and row["alpha"] == "0.5"
    }
    certificates: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in certificate_rows:
        if row["split_seed"] == "0" and row["alpha"] == "0.5":
            certificates.setdefault(
                (row["dataset_id"], row["model_id"]),
                [],
            ).append(row)
    if len(primary) != 10 or \
            any(len(rows) != 14 for rows in certificates.values()):
        raise ValueError("INTEGRITY_BLOCK: catalog seed-0 view changed")
    return primary, certificates


def trial_metrics(
    trial: dict[str, Any],
    samples: int,
) -> dict[str, Any]:
    return {
        "validation_status": trial["status"],
        "validation_flips": trial["decision_flips"],
        "validation_violations": trial["error_violations"],
        "validation_max_error": trial["max_observed_error"],
        "validation_max_budget_usage":
            trial["max_error_budget_usage"],
        "key_runs": trial["key_repeats_completed"],
        "encrypted_sample_evaluations":
            samples * trial["key_repeats_completed"],
        "mean_total_ms": trial["mean_total_ms"],
    }


def selection_accounting(
    selection: dict[str, Any],
) -> dict[str, int]:
    samples = int(
        selection["plan"]["contract"]["decision"][
            "validation_samples"
        ]
    )
    key_runs = sum(
        int(trial["key_repeats_completed"])
        for trial in selection["trials"]
    )
    return {
        "key_runs": key_runs,
        "encrypted_sample_evaluations": samples * key_runs,
    }


def audit_metrics(audit: dict[str, Any]) -> dict[str, Any]:
    trial = audit["audit_trial"]
    samples = int(
        audit["audit_contract"]["decision"]["validation_samples"]
    )
    return {
        "audit_status": audit["outcome"],
        "audit_flips": trial["decision_flips"],
        "audit_violations": trial["error_violations"],
        "audit_key_runs": trial["key_repeats_completed"],
        "audit_encrypted_sample_evaluations":
            samples * trial["key_repeats_completed"],
        "audit_retuning": int(audit["retuning_performed"]),
    }


def summarize(
    run_root: Path,
    manifest: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    direct_rows = load_direct_workloads()
    catalog_selection, catalog_certificates = load_catalog_views()
    rows = []
    for direct_row in direct_rows:
        dataset = direct_row["dataset_id"]
        model = direct_row["model_id"]
        tag = f"seed0__{dataset}__{model}"
        paths = workload_paths(direct_row)
        full = json.loads(
            paths["full_selection"].read_text(encoding="ascii")
        )
        full_audit = json.loads(
            paths["full_audit"].read_text(encoding="ascii")
        )
        samples = int(
            full["plan"]["contract"]["decision"][
                "validation_samples"
            ]
        )
        first = full["trials"][0]
        first_safe = first["status"] == "SAFE"
        one_shot = {
            "arm": "one_shot_direct",
            "dataset_id": dataset,
            "model_id": model,
            "outcome": "SELECTED" if first_safe else "NO_SAFE",
            "candidate_id": (
                first["candidate"]["id"] if first_safe else ""
            ),
            "trials": 1,
            "repairs": 0,
            "repair_causes": "",
            "security_admission": "PASS",
            **trial_metrics(first, samples),
        }
        if first_safe:
            if first["candidate"] != full["selected"]:
                raise ValueError(
                    "INTEGRITY_BLOCK: one-shot/full identity changed"
                )
            one_shot.update(audit_metrics(full_audit))
        else:
            one_shot.update(
                {
                    "audit_status": "NOT_APPLICABLE_NO_SAFE",
                    "audit_flips": "",
                    "audit_violations": "",
                    "audit_key_runs": "",
                    "audit_encrypted_sample_evaluations": "",
                    "audit_retuning": "",
                }
            )
        rows.append(one_shot)

        full_trial = full["trials"][-1]
        full_causes = [
            trial["candidate"]["generation_kind"]
            for trial in full["trials"][1:]
        ]
        rows.append(
            {
                "arm": "full_flipguard",
                "dataset_id": dataset,
                "model_id": model,
                "outcome": full["outcome"],
                "candidate_id": full["selected"]["id"],
                "trials": full["trials_used"],
                "repairs": full["trials_used"] - 1,
                "repair_causes": ";".join(full_causes),
                "security_admission": "PASS",
                **trial_metrics(full_trial, samples),
                **selection_accounting(full),
                **audit_metrics(full_audit),
            }
        )

        graph_state = state["workloads"][tag]["graph_selection"]
        graph_audit_state = state["workloads"][tag]["graph_audit"]
        if graph_state["status"] in (
            "PENDING",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
        ):
            continue
        graph_path = REPO_ROOT / graph_state["result_path"]
        graph = json.loads(graph_path.read_text(encoding="ascii"))
        graph_trial = graph["trials"][-1]
        graph_row = {
            "arm": "graph_only_fixed_tolerance",
            "dataset_id": dataset,
            "model_id": model,
            "outcome": graph["outcome"],
            "candidate_id": (
                graph["selected"]["id"]
                if graph["outcome"] == "SELECTED"
                else ""
            ),
            "trials": graph["trials_used"],
            "repairs": graph["trials_used"] - 1,
            "repair_causes": ";".join(
                trial["candidate"]["generation_kind"]
                for trial in graph["trials"][1:]
            ),
            "security_admission": "PASS",
            **trial_metrics(
                graph_trial,
                int(
                    graph["plan"]["contract"]["decision"][
                        "validation_samples"
                    ]
                ),
            ),
            **selection_accounting(graph),
        }
        if graph["outcome"] == "SELECTED" and \
                graph_audit_state["status"] not in (
                    "PENDING",
                    "RECOVERABLE_IMPLEMENTATION_FAILURE",
                ):
            graph_audit = json.loads(
                (
                    REPO_ROOT / graph_audit_state["result_path"]
                ).read_text(encoding="ascii")
            )
            graph_row.update(audit_metrics(graph_audit))
        else:
            graph_row.update(
                {
                    "audit_status": (
                        "NOT_APPLICABLE_NO_SAFE"
                        if graph["outcome"] == "NO_SAFE"
                        else "NOT_EVALUATED"
                    ),
                    "audit_flips": "",
                    "audit_violations": "",
                    "audit_key_runs": "",
                    "audit_encrypted_sample_evaluations": "",
                    "audit_retuning": "",
                }
            )
        rows.append(graph_row)

        oracle = catalog_selection[(dataset, model)]
        certificates = catalog_certificates[(dataset, model)]
        latency_id = oracle["latency_only_candidate"]
        selected_certificates = [
            row
            for row in certificates
            if row["candidate_id"] == latency_id
        ]
        if len(selected_certificates) != 1:
            raise ValueError(
                "INTEGRITY_BLOCK: latency-only candidate identity "
                f"ambiguous for {tag}"
            )
        latency = selected_certificates[0]
        executable = [
            row for row in certificates if row["run_status"] == "ok"
        ]
        fastest = min(
            executable,
            key=lambda row: (
                float(row["mean_total_ms"]),
                row["candidate_id"],
            ),
        )
        if fastest["candidate_id"] != latency_id:
            raise ValueError(
                "INTEGRITY_BLOCK: latency-only rule changed"
            )
        rows.append(
            {
                "arm": "latency_only_no_certification",
                "dataset_id": dataset,
                "model_id": model,
                "outcome": "SELECTED_WITHOUT_CERTIFICATION",
                "candidate_id": latency_id,
                "trials": 14,
                "repairs": 0,
                "repair_causes": "",
                "security_admission": "PASS",
                "validation_status": latency["certificate_status"],
                "validation_flips":
                    int(latency["decision_flips_v_cert"]),
                "validation_violations":
                    int(latency["error_violations_v_cert"]),
                "validation_max_error":
                    float(latency["max_y_error_v_cert"]),
                "validation_max_budget_usage": "",
                "key_runs": 14,
                "encrypted_sample_evaluations": sum(
                    int(row["sample_count"]) for row in certificates
                ),
                "mean_total_ms": float(latency["mean_total_ms"]),
                "audit_status": "NOT_EVALUATED",
                "audit_flips": "",
                "audit_violations": "",
                "audit_key_runs": "",
                "audit_encrypted_sample_evaluations": "",
                "audit_retuning": "",
            }
        )
    incomplete = [
        workload
        for workload in state["workloads"].values()
        if workload["graph_selection"]["status"] in (
            "PENDING",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
        ) or workload["graph_audit"]["status"] in (
            "PENDING",
            "RECOVERABLE_IMPLEMENTATION_FAILURE",
        )
    ]
    arm_rows = {
        arm: [row for row in rows if row["arm"] == arm]
        for arm in (
            "graph_only_fixed_tolerance",
            "one_shot_direct",
            "full_flipguard",
            "latency_only_no_certification",
        )
    }
    full_results = {
        (row["dataset_id"], row["model_id"]): json.loads(
            workload_paths(row)["full_selection"].read_text(
                encoding="ascii"
            )
        )
        for row in direct_rows
    }
    graph_results = {
        (
            plan["dataset_id"],
            plan["model_id"],
        ): json.loads(
            (
                run_root
                / "graph_only/selection/results"
                / f"{plan['tag']}.json"
            ).read_text(encoding="ascii")
        )
        for plan in manifest["plans"]
        if (
            run_root
            / "graph_only/selection/results"
            / f"{plan['tag']}.json"
        ).is_file()
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "RECOVERABLE_IMPLEMENTATION_FAILURE"
            if incomplete
            else "PASS"
        ),
        "population": "10 seed-0 development dataset-model workloads",
        "ablation_contract_digest":
            manifest["ablation_contract_digest"],
        "arms": {
            arm: {
                "workloads": len(values),
                "selected": sum(
                    row["outcome"]
                    in ("SELECTED", "SELECTED_WITHOUT_CERTIFICATION")
                    for row in values
                ),
                "no_safe": sum(
                    row["outcome"] == "NO_SAFE" for row in values
                ),
                "trials": sum(int(row["trials"]) for row in values),
                "repairs": sum(int(row["repairs"]) for row in values),
                "key_runs": sum(int(row["key_runs"]) for row in values),
                "encrypted_sample_evaluations": sum(
                    int(row["encrypted_sample_evaluations"])
                    for row in values
                ),
                "validation_safe": sum(
                    row["validation_status"] == "SAFE"
                    for row in values
                ),
                "validation_rejected": sum(
                    row["validation_status"] == "REJECTED"
                    for row in values
                ),
                "validation_failed": sum(
                    row["validation_status"] == "FAILED"
                    for row in values
                ),
                "validation_flips": sum(
                    int(row["validation_flips"]) for row in values
                ),
                "validation_violations": sum(
                    int(row["validation_violations"])
                    for row in values
                ),
                "audit_pass": sum(
                    row["audit_status"] == "LOCKED_AUDIT_PASS"
                    for row in values
                ),
                "audit_rejected": sum(
                    row["audit_status"] == "LOCKED_AUDIT_FAIL"
                    for row in values
                ),
                "audit_flips": sum(
                    int(row["audit_flips"])
                    for row in values
                    if row["audit_flips"] != ""
                ),
                "audit_violations": sum(
                    int(row["audit_violations"])
                    for row in values
                    if row["audit_violations"] != ""
                ),
                "audit_key_runs": sum(
                    int(row["audit_key_runs"])
                    for row in values
                    if row["audit_key_runs"] != ""
                ),
                "audit_encrypted_sample_evaluations": sum(
                    int(row["audit_encrypted_sample_evaluations"])
                    for row in values
                    if row[
                        "audit_encrypted_sample_evaluations"
                    ] != ""
                ),
                "audit_retuning": sum(
                    int(row["audit_retuning"])
                    for row in values
                    if row["audit_retuning"] != ""
                ),
                "audit_not_applicable": sum(
                    str(row["audit_status"]).startswith(
                        "NOT_APPLICABLE"
                    )
                    for row in values
                ),
                "audit_not_evaluated": sum(
                    row["audit_status"] == "NOT_EVALUATED"
                    for row in values
                ),
            }
            for arm, values in arm_rows.items()
        },
        "adaptive_repair_effect_count": sum(
            row["outcome"] == "NO_SAFE"
            for row in arm_rows["one_shot_direct"]
        ),
        "graph_only_initial_literal_differs_from_full": sum(
            (
                graph_results[key]["trials"][0]["candidate"]["path"],
                graph_results[key]["trials"][0]["candidate"][
                    "parameters"
                ],
            )
            != (
                full_results[key]["trials"][0]["candidate"]["path"],
                full_results[key]["trials"][0]["candidate"][
                    "parameters"
                ],
            )
            for key in graph_results
        ),
        "graph_only_selected_literal_differs_from_full": sum(
            (
                graph_results[key]["selected"]["path"],
                graph_results[key]["selected"]["parameters"],
            )
            != (
                full_results[key]["selected"]["path"],
                full_results[key]["selected"]["parameters"],
            )
            for key in graph_results
            if graph_results[key]["outcome"] == "SELECTED"
        ),
        "graph_only_candidate_id_representation_differs": sum(
            graph_results[key]["selected"]["id"]
            != full_results[key]["selected"]["id"]
            for key in graph_results
            if graph_results[key]["outcome"] == "SELECTED"
        ),
        "decision_contract_effect_count": sum(
            (
                graph_results[key]["trials"][0]["candidate"]["path"],
                graph_results[key]["trials"][0]["candidate"][
                    "parameters"
                ],
                graph_results[key]["trials_used"],
                graph_results[key]["outcome"],
            )
            != (
                full_results[key]["trials"][0]["candidate"]["path"],
                full_results[key]["trials"][0]["candidate"][
                    "parameters"
                ],
                full_results[key]["trials_used"],
                full_results[key]["outcome"],
            )
            for key in graph_results
        ),
        "candidate_id_difference_reason": (
            "candidate IDs bind policy/contract identity; literal "
            "identity is path plus CKKS parameters"
        ),
        "latency_only_non_safe_selected": sum(
            row["validation_status"] != "SAFE"
            for row in arm_rows["latency_only_no_certification"]
        ),
        "paper_claim_allowed": False,
    }
    write_atomic(run_root / "summary.json", summary)
    if rows:
        csv_path = run_root / "workload_arm_results.csv"
        with csv_path.open("w", newline="", encoding="ascii") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(rows[0]),
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
    state["stage"] = summary["status"]
    write_atomic(run_root / "state.json", state)
    return summary


def main() -> None:
    args = parse_args()
    head = git_text("rev-parse", "HEAD")
    run_root = args.run_root or RESULT_BASE / f"run_{head[:7]}"
    if not run_root.is_absolute():
        run_root = REPO_ROOT / run_root
    if args.preflight_only:
        manifest = preflight(run_root)
        print(
            "direct_synthesis_ablation_preflight=PASS "
            f"commit={manifest['source_commit']} "
            f"source_digest={manifest['execution_critical_source_digest']} "
            f"contract={manifest['ablation_contract_digest']} "
            f"run_root={run_root.relative_to(REPO_ROOT)}"
        )
        return
    manifest, state = verify_resume_gate(run_root)
    execute_graph_arm(run_root, manifest, state)
    summary = summarize(run_root, manifest, state)
    print(
        "direct_synthesis_ablation="
        f"{summary['status']} "
        f"graph_workloads="
        f"{summary['arms']['graph_only_fixed_tolerance']['workloads']}/10 "
        f"adaptive_rescues={summary['adaptive_repair_effect_count']} "
        f"latency_only_non_safe="
        f"{summary['latency_only_non_safe_selected']} "
        f"run_root={run_root.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
