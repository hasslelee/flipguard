#!/usr/bin/env python3
"""Freeze and verify the direct-synthesis ablation evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = Path(
    "results/thesis_grade_protocol/"
    "direct_synthesis_ablation_v1/run_062e1a9"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/direct_synthesis_ablation_v1"
)
SCHEMA_VERSION = "flipguard_direct_synthesis_ablation_evidence_v1"
EXECUTION_COMMIT = "062e1a9e0305b57ae75d681eb35a4655c5f00c43"
CONTRACT_DIGEST = (
    "sha256:"
    "8521da562e477d2a2f5dc60e3524affe85a22067225764a5910fe78e3ac0d6bf"
)

RUNNER_PATH = REPO_ROOT / "scripts/run_direct_synthesis_ablation.py"
SPEC = importlib.util.spec_from_file_location(
    "run_direct_synthesis_ablation",
    RUNNER_PATH,
)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def git_blob(commit: str, relative: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def verify_historical_source_map(
    source_commit: str,
    source_files: dict[str, str],
) -> None:
    for relative, expected in source_files.items():
        if sha256_bytes(git_blob(source_commit, relative)) != expected:
            raise ValueError(
                f"ablation historical execution source changed: {relative}"
            )


def validate_summary(summary: dict[str, Any]) -> None:
    expected = {
        "graph_only_fixed_tolerance": {
            "workloads": 10,
            "selected": 10,
            "no_safe": 0,
            "trials": 14,
            "repairs": 4,
            "key_runs": 42,
            "encrypted_sample_evaluations": 7365,
            "validation_safe": 10,
            "validation_rejected": 0,
            "validation_failed": 0,
            "validation_flips": 0,
            "validation_violations": 0,
            "audit_pass": 10,
            "audit_rejected": 0,
            "audit_flips": 0,
            "audit_violations": 0,
            "audit_key_runs": 30,
            "audit_encrypted_sample_evaluations": 4980,
            "audit_retuning": 0,
            "audit_not_applicable": 0,
            "audit_not_evaluated": 0,
        },
        "one_shot_direct": {
            "workloads": 10,
            "selected": 6,
            "no_safe": 4,
            "trials": 10,
            "repairs": 0,
            "key_runs": 30,
            "encrypted_sample_evaluations": 4938,
            "validation_safe": 6,
            "validation_rejected": 4,
            "validation_failed": 0,
            "validation_flips": 194,
            "validation_violations": 850,
            "audit_pass": 6,
            "audit_rejected": 0,
            "audit_flips": 0,
            "audit_violations": 0,
            "audit_key_runs": 18,
            "audit_encrypted_sample_evaluations": 2538,
            "audit_retuning": 0,
            "audit_not_applicable": 4,
            "audit_not_evaluated": 0,
        },
        "full_flipguard": {
            "workloads": 10,
            "selected": 10,
            "no_safe": 0,
            "trials": 14,
            "repairs": 4,
            "key_runs": 42,
            "encrypted_sample_evaluations": 7365,
            "validation_safe": 10,
            "validation_rejected": 0,
            "validation_failed": 0,
            "validation_flips": 0,
            "validation_violations": 0,
            "audit_pass": 10,
            "audit_rejected": 0,
            "audit_flips": 0,
            "audit_violations": 0,
            "audit_key_runs": 30,
            "audit_encrypted_sample_evaluations": 4980,
            "audit_retuning": 0,
            "audit_not_applicable": 0,
            "audit_not_evaluated": 0,
        },
        "latency_only_no_certification": {
            "workloads": 10,
            "selected": 10,
            "no_safe": 0,
            "trials": 140,
            "repairs": 0,
            "key_runs": 140,
            "encrypted_sample_evaluations": 23044,
            "validation_safe": 0,
            "validation_rejected": 10,
            "validation_failed": 0,
            "validation_flips": 794,
            "validation_violations": 1610,
            "audit_pass": 0,
            "audit_rejected": 0,
            "audit_flips": None,
            "audit_violations": None,
            "audit_key_runs": None,
            "audit_encrypted_sample_evaluations": None,
            "audit_retuning": None,
            "audit_not_applicable": 0,
            "audit_not_evaluated": 10,
        },
    }
    if summary["schema_version"] != RUNNER.SCHEMA_VERSION or \
            summary["status"] != "PASS" or \
            summary["ablation_contract_digest"] != CONTRACT_DIGEST or \
            summary["paper_claim_allowed"] or \
            summary["adaptive_repair_effect_count"] != 4 or \
            summary["decision_contract_effect_count"] != 0 or \
            summary[
                "graph_only_initial_literal_differs_from_full"
            ] != 0 or \
            summary[
                "graph_only_selected_literal_differs_from_full"
            ] != 0 or \
            summary[
                "graph_only_candidate_id_representation_differs"
            ] != 10 or \
            summary["latency_only_non_safe_selected"] != 10:
        raise ValueError("ablation summary invariant changed")
    if summary["arms"] != expected:
        raise ValueError("ablation arm accounting changed")


def validate_run(
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    RUNNER.load_contract()
    direct_rows = RUNNER.load_direct_workloads()
    RUNNER.verify_catalog_pack()
    manifest = json.loads(
        (run_root / "run_manifest.json").read_text(encoding="ascii")
    )
    state = json.loads(
        (run_root / "state.json").read_text(encoding="ascii")
    )
    summary = json.loads(
        (run_root / "summary.json").read_text(encoding="ascii")
    )
    if manifest["source_commit"] != EXECUTION_COMMIT or \
            manifest["origin_commit"] != EXECUTION_COMMIT or \
            manifest["status"] != "PREFLIGHT_PASS" or \
            manifest["ablation_contract_digest"] != CONTRACT_DIGEST or \
            manifest["direct_policy_digest"] != \
                RUNNER.DIRECT_POLICY_DIGEST or \
            manifest["security_policy_digest"] != \
                RUNNER.SECURITY_POLICY_DIGEST or \
            state["run_manifest_sha256"] != \
                sha256_path(run_root / "run_manifest.json") or \
            state["stage"] != "PASS" or \
            state["paper_claim_allowed"]:
        raise ValueError("ablation provenance changed")
    if manifest["execution_critical_source_digest"] != \
            RUNNER.canonical_digest(
                manifest["execution_critical_source_files"]
            ):
        raise ValueError("ablation execution source closure changed")
    verify_historical_source_map(
        manifest["source_commit"],
        manifest["execution_critical_source_files"],
    )
    for binary in manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError("ablation execution binary changed")
    validate_summary(summary)

    source_by_key = {
        (row["dataset_id"], row["model_id"]): row
        for row in direct_rows
    }
    rows = []
    for plan in manifest["plans"]:
        tag = plan["tag"]
        source = source_by_key[
            (plan["dataset_id"], plan["model_id"])
        ]
        paths = RUNNER.workload_paths(source)
        workload = state["workloads"][tag]
        selection_path = (
            run_root / "graph_only/selection/results" / f"{tag}.json"
        )
        audit_path = (
            run_root / "graph_only/audit/results" / f"{tag}.json"
        )
        compatibility_path = (
            run_root / "graph_only/audit/manifests" / f"{tag}.json"
        )
        selection = json.loads(
            selection_path.read_text(encoding="ascii")
        )
        audit = json.loads(audit_path.read_text(encoding="ascii"))
        compatibility = json.loads(
            compatibility_path.read_text(encoding="ascii")
        )
        if workload["graph_selection"]["status"] != "PASS" or \
                workload["graph_audit"]["status"] != "PASS" or \
                workload["graph_selection"]["result_sha256"] != \
                    sha256_path(selection_path) or \
                workload["graph_audit"]["result_sha256"] != \
                    sha256_path(audit_path):
            raise ValueError(f"{tag}: state/result binding changed")
        if RUNNER.validate_graph_selection(
            selection,
            source,
        ) != "SELECTED" or RUNNER.validate_graph_audit(
            audit,
            selection,
        ) != "LOCKED_AUDIT_PASS":
            raise ValueError(f"{tag}: encrypted outcome changed")
        if audit["audit_trial"]["decision_flips"] != 0 or \
                audit["audit_trial"]["error_violations"] != 0 or \
                audit["retuning_performed"]:
            raise ValueError(f"{tag}: audit evidence changed")
        original = json.loads(
            paths["split_manifest"].read_text(encoding="ascii")
        )
        recovery = compatibility["representation_recovery"]
        if recovery["reason_code"] != \
                "FROZEN_EQUIVALENT_PATH_BINDING_MISMATCH" or \
                recovery["row_membership_changed"] or \
                recovery["csv_digest_changed"] or \
                recovery["encrypted_execution_before_recovery"]:
            raise ValueError(f"{tag}: recovery classification changed")
        for partition in (
            "configuration_validation",
            "locked_audit_test",
        ):
            if compatibility[partition]["row_ids"] != \
                    original[partition]["row_ids"] or \
                    compatibility[partition]["csv_digest"] != \
                    original[partition]["csv_digest"]:
                raise ValueError(
                    f"{tag}: path recovery changed split semantics"
                )
        full = json.loads(
            paths["full_selection"].read_text(encoding="ascii")
        )
        if selection["trials"][0]["candidate"]["parameters"] != \
                full["trials"][0]["candidate"]["parameters"] or \
                selection["selected"]["parameters"] != \
                    full["selected"]["parameters"]:
            raise ValueError(
                f"{tag}: graph/full literal equality changed"
            )
        rows.append(
            {
                "tag": tag,
                "dataset_id": plan["dataset_id"],
                "model_id": plan["model_id"],
                "selection_result_sha256":
                    sha256_path(selection_path),
                "audit_result_sha256": sha256_path(audit_path),
                "candidate_id": selection["selected"]["id"],
                "trials": selection["trials_used"],
                "repairs": selection["trials_used"] - 1,
                "selection_key_runs":
                    selection["encrypted_key_runs"],
                "selection_encrypted_sample_evaluations":
                    RUNNER.selection_evaluations(selection),
                "audit_outcome": audit["outcome"],
                "audit_flips":
                    audit["audit_trial"]["decision_flips"],
                "audit_violations":
                    audit["audit_trial"]["error_violations"],
                "audit_retuning":
                    int(audit["retuning_performed"]),
                "literal_parameters_equal_full": True,
                "candidate_id_equal_full":
                    selection["selected"]["id"]
                    == full["selected"]["id"],
            }
        )

    failure_logs = [
        path
        for path in sorted(
            run_root.glob(
                "graph_only/audit/logs/*.resume1.attempt*.log"
            )
        )
        if "does not match selection" in path.read_text(
            encoding="ascii"
        )
    ]
    success_logs = [
        path
        for path in sorted(
            run_root.glob(
                "graph_only/audit/logs/*.resume2.attempt1.log"
            )
        )
        if "locked_audit=LOCKED_AUDIT_PASS" in path.read_text(
            encoding="ascii"
        )
    ]
    recoveries = [
        record
        for record in state["recoveries"]
        if record["reason_code"]
        == "FROZEN_EQUIVALENT_PATH_BINDING_MISMATCH"
    ]
    if len(failure_logs) != 30 or \
            len(success_logs) != 10 or \
            len(recoveries) != 10:
        raise ValueError("ablation recovery ledger changed")
    derived = {
        "workloads": rows,
        "recovery": {
            "classification": "RECOVERABLE_IMPLEMENTATION_FAILURE",
            "reason_code":
                "FROZEN_EQUIVALENT_PATH_BINDING_MISMATCH",
            "affected_workloads": 10,
            "pre_ckks_failed_attempts": 30,
            "post_recovery_audit_passes": 10,
            "selection_reruns": 0,
            "row_membership_changes": 0,
            "csv_digest_changes": 0,
        },
    }
    return manifest, summary, derived


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def copy_run(run_root: Path, destination: Path) -> None:
    for path in sorted(run_root.rglob("*")):
        if path.is_dir() or "/bin/" in path.as_posix():
            continue
        relative = path.relative_to(run_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def build_pack(run_root: Path, output_root: Path) -> None:
    manifest, summary, derived = validate_run(run_root)
    output_root.mkdir(parents=True)
    raw = output_root / "raw"
    raw.mkdir()
    copy_run(run_root, raw)
    shutil.copy2(
        REPO_ROOT / RUNNER.CONTRACT_PATH,
        output_root / "ablation_contract.json",
    )
    shutil.copy2(
        REPO_ROOT
        / "docs/research/step_7e1_direct_synthesis_ablation_protocol.md",
        output_root / "protocol.md",
    )
    (output_root / "summary.json").write_bytes(
        canonical_json(summary)
    )
    (output_root / "recovery_summary.json").write_bytes(
        canonical_json(derived["recovery"])
    )
    write_csv(
        output_root / "graph_only_workloads.csv",
        derived["workloads"],
    )
    reference_bindings = {
        "direct_pack": {
            "path": str(RUNNER.DIRECT_PACK),
            "manifest_sha256": sha256_path(
                REPO_ROOT / RUNNER.DIRECT_PACK / "manifest.json"
            ),
            "sha256sums_sha256": sha256_path(
                REPO_ROOT / RUNNER.DIRECT_PACK / "SHA256SUMS"
            ),
        },
        "catalog_pack": {
            "path": str(RUNNER.CATALOG_PACK),
            "manifest_sha256": sha256_path(
                REPO_ROOT / RUNNER.CATALOG_PACK / "manifest.json"
            ),
        },
        "workloads": manifest["plans"],
    }
    (output_root / "reference_bindings.json").write_bytes(
        canonical_json(reference_bindings)
    )
    evidence_manifest = {
        "schema_version": SCHEMA_VERSION,
        "execution_commit": EXECUTION_COMMIT,
        "execution_critical_source_digest":
            manifest["execution_critical_source_digest"],
        "execution_binaries": {
            name: value["sha256"]
            for name, value in manifest["binaries"].items()
        },
        "resume_commits": [
            record["current_commit"]
            for record in json.loads(
                (run_root / "state.json").read_text(encoding="ascii")
            ).get("resume_records", [])
        ],
        "direct_policy_digest": RUNNER.DIRECT_POLICY_DIGEST,
        "security_policy_digest": RUNNER.SECURITY_POLICY_DIGEST,
        "ablation_contract_digest": CONTRACT_DIGEST,
        "run_manifest_sha256": sha256_path(
            run_root / "run_manifest.json"
        ),
        "runner_state_sha256": sha256_path(
            run_root / "state.json"
        ),
        "summary_sha256": sha256_path(
            output_root / "summary.json"
        ),
        "graph_only_workloads_sha256": sha256_path(
            output_root / "graph_only_workloads.csv"
        ),
        "recovery_summary_sha256": sha256_path(
            output_root / "recovery_summary.json"
        ),
        "reference_bindings_sha256": sha256_path(
            output_root / "reference_bindings.json"
        ),
        "claim_states": {
            "decision_contract_candidate_synthesis_effect":
                "BLOCKED",
            "adaptive_repair": "SUPPORTED",
            "latency_only_no_certification_comparator":
                "SUPPORTED",
            "development_locked_audit": "SUPPORTED",
        },
        "claim_details": {
            "decision_contract_candidate_synthesis_effect": (
                "not observed in the ten natural seed-0 development "
                "workloads; graph-only and full literal parameters, "
                "trials, repairs, and outcomes were identical"
            ),
            "adaptive_repair": (
                "four first-trial rejections became SAFE under the "
                "frozen bounded numerical repair"
            ),
            "latency_only_no_certification_comparator": (
                "selected a validation-REJECTED candidate in all ten "
                "development workloads"
            ),
        },
        "paper_claim_allowed": False,
    }
    (output_root / "manifest.json").write_bytes(
        canonical_json(evidence_manifest)
    )
    readme = """# Direct-Synthesis Ablation Evidence V1

This pack freezes the predeclared seed-0 development ablation. Graph-only
fixed-tolerance synthesis and full FlipGuard produced the same literal
parameters, trials, repairs, and outcomes on all ten natural workloads.
Candidate IDs differ because they bind policy/contract identity. Therefore,
the decision-contract candidate-synthesis effect was not observed in this
scope.

The one-shot view selected 6/10 and returned NO_SAFE for four first-trial
rejections. Frozen adaptive repair selected all four without validation or
audit violations. The Security-V2 latency-only arm selected a REJECTED
candidate in 10/10 workloads and has no locked-audit claim.

Thirty original audit attempts failed before CKKS execution because equivalent
frozen paths were represented differently. The recovery bound the evidence
pack paths while preserving row membership and CSV digests; all ten recovered
audits passed without selection rerun or retuning.

This is development evidence. It does not make the paper claim admissible.
"""
    (output_root / "README.md").write_text(
        readme,
        encoding="ascii",
    )
    checksum_lines = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            checksum_lines.append(
                f"{sha256_path(path).removeprefix('sha256:')}  "
                f"{path.relative_to(output_root).as_posix()}\n"
            )
    (output_root / "SHA256SUMS").write_text(
        "".join(checksum_lines),
        encoding="ascii",
    )


def verify_pack(run_root: Path, output_root: Path) -> None:
    validate_run(run_root)
    if not output_root.is_dir():
        raise ValueError(f"evidence pack missing: {output_root}")
    with tempfile.TemporaryDirectory(
        prefix="flipguard_direct_ablation_evidence_"
    ) as temporary:
        replay = Path(temporary) / "pack"
        build_pack(run_root, replay)
        expected = {
            path.relative_to(output_root)
            for path in output_root.rglob("*")
            if path.is_file()
        }
        observed = {
            path.relative_to(replay)
            for path in replay.rglob("*")
            if path.is_file()
        }
        if expected != observed:
            raise ValueError("ablation evidence file set changed")
        for relative in sorted(expected):
            if (output_root / relative).read_bytes() != \
                    (replay / relative).read_bytes():
                raise ValueError(
                    f"ablation evidence changed: {relative}"
                )


def main() -> None:
    args = parse_args()
    run_root = (
        args.run_root
        if args.run_root.is_absolute()
        else REPO_ROOT / args.run_root
    )
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else REPO_ROOT / args.output_root
    )
    if args.verify:
        verify_pack(run_root, output_root)
        print(
            "direct_synthesis_ablation_evidence=PASS "
            f"manifest={sha256_path(output_root / 'manifest.json')}"
        )
        return
    if output_root.exists():
        raise SystemExit(
            f"refusing to overwrite evidence pack: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_direct_ablation_freeze_",
        dir=str(output_root.parent),
    ) as temporary:
        staging = Path(temporary) / "pack"
        build_pack(run_root, staging)
        staging.rename(output_root)
    print(
        "direct_synthesis_ablation_evidence=FROZEN "
        f"manifest={sha256_path(output_root / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
