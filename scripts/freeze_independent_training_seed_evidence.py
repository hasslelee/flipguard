#!/usr/bin/env python3
"""Freeze and verify independent-training-seed extension evidence."""

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
    "independent_training_seed_extension_v1/run_f3cfd7f"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/independent_training_seed_extension_v1"
)
INPUT_ROOT = Path("datasets/independent_training_seed_suite_v1")
SCHEMA_VERSION = "flipguard_independent_training_seed_evidence_v1"
EXECUTION_COMMIT = "f3cfd7f4527cc9ceb66c1b36d9926512102e7435"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
INPUT_POLICY_DIGEST = (
    "sha256:"
    "e9353654e5ec899fc91ce70e8dd501905b95973bcb8493cc1d27f3ffc77af1cb"
)

INPUT_VERIFIER_PATH = (
    REPO_ROOT / "scripts/verify_independent_training_seed_extension.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_independent_training_seed_extension",
    INPUT_VERIFIER_PATH,
)
INPUT_VERIFIER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(INPUT_VERIFIER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--python-with-science-deps",
        default=".venv/bin/python",
    )
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


def validate_candidate(candidate: dict[str, Any]) -> None:
    security = candidate["security"]
    if security["envelope_id"] != \
            "security_guidelines_cic2025_table5_2_ternary_128_v2":
        raise ValueError("independent-seed security policy changed")
    for field in (
        "admission_status",
        "ciphertext_q_admission",
        "evaluation_key_qp_admission",
        "final_admission",
    ):
        if security[field] != "PASS":
            raise ValueError(
                f"independent-seed {field}={security[field]}"
            )
    if security["headroom_bits"] < 0:
        raise ValueError("independent-seed security headroom changed")


def string_ids(values: list[Any]) -> list[str]:
    result = [str(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError("independent-seed row IDs are not unique")
    return result


def validate_run(run_root: Path) -> tuple[dict, dict, dict]:
    input_summary = INPUT_VERIFIER.validate_tree(
        REPO_ROOT / INPUT_ROOT
    )
    run_manifest = json.loads(
        (run_root / "run_manifest.json").read_text(encoding="ascii")
    )
    state = json.loads(
        (run_root / "state.json").read_text(encoding="ascii")
    )
    runner_summary = json.loads(
        (run_root / "summary.json").read_text(encoding="ascii")
    )
    if run_manifest["source_commit"] != EXECUTION_COMMIT or \
            run_manifest["origin_commit"] != EXECUTION_COMMIT or \
            not run_manifest["working_tree_clean"] or \
            run_manifest["status"] != "PREFLIGHT_PASS" or \
            run_manifest["direct_policy_digest"] != \
                DIRECT_POLICY_DIGEST or \
            run_manifest["security_policy_digest"] != \
                SECURITY_POLICY_DIGEST or \
            run_manifest["input_policy_digest"] != \
                INPUT_POLICY_DIGEST:
        raise ValueError("independent-seed run provenance changed")
    if run_manifest["execution_critical_source_digest"] != \
            canonical_digest(
                run_manifest["execution_critical_source_files"]
            ):
        raise ValueError("independent-seed source closure changed")
    for relative, expected in \
            run_manifest["execution_critical_source_files"].items():
        if sha256_path(REPO_ROOT / relative) != expected:
            raise ValueError(
                f"independent-seed execution source changed: {relative}"
            )
    for binary in run_manifest["binaries"].values():
        if sha256_path(REPO_ROOT / binary["path"]) != binary["sha256"]:
            raise ValueError("independent-seed binary changed")
    if run_manifest["input_summary_sha256"] != \
            sha256_path(REPO_ROOT / INPUT_ROOT / "summary.json") or \
            input_summary["policy_digest"] != INPUT_POLICY_DIGEST:
        raise ValueError("independent-seed input binding changed")
    if state["stage"] != "PASS" or \
            runner_summary["status"] != "PASS" or \
            runner_summary["instances"] != 9 or \
            runner_summary["selection_selected"] != 9 or \
            runner_summary["selection_no_safe"] != 0 or \
            runner_summary["audit_pass"] != 9 or \
            runner_summary["audit_rejected"] != 0 or \
            runner_summary["retuning"] != 0 or \
            runner_summary["paper_claim_allowed"]:
        raise ValueError("independent-seed terminal summary changed")

    instances = {
        (
            int(instance["training_seed"]),
            instance["dataset_id"],
        ): instance
        for instance in input_summary["instances"]
    }
    preflight = {
        (
            int(record["training_seed"]),
            record["dataset_id"],
        ): record
        for record in run_manifest["plans"]
    }
    rows = []
    static_id_changes = 0
    for tag, workload in sorted(state["workloads"].items()):
        seed = int(workload["training_seed"])
        dataset = workload["dataset_id"]
        instance = instances[(seed, dataset)]
        source_model = REPO_ROOT / instance["model_path"]
        source_root = source_model.parent
        source_validation = source_root / "configuration_validation.csv"
        source_audit = source_root / "locked_audit_test.csv"
        source_manifest = source_root / "split_manifest.json"
        selection_path = (
            run_root / "selection/results" / f"{tag}.json"
        )
        audit_path = run_root / "audit/results" / f"{tag}.json"
        compatibility_path = (
            run_root / "audit/manifests" / f"{tag}.json"
        )
        selection = json.loads(
            selection_path.read_text(encoding="ascii")
        )
        audit = json.loads(audit_path.read_text(encoding="ascii"))
        original = json.loads(
            source_manifest.read_text(encoding="ascii")
        )
        compatibility = json.loads(
            compatibility_path.read_text(encoding="ascii")
        )
        selection_state = workload["selection"]
        audit_state = workload["locked_audit"]
        if selection_state["result_sha256"] != \
                sha256_path(selection_path) or \
                audit_state["result_sha256"] != sha256_path(audit_path):
            raise ValueError(f"{tag}: state result digest changed")

        plan = selection["plan"]
        contract = plan["contract"]
        selected = selection["selected"]
        trial = selection["trials"][0]
        if plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
                plan["security_policy_digest"] != \
                    SECURITY_POLICY_DIGEST or \
                contract["workload_id"] != \
                    f"split_seed_{seed}/{dataset}/mlp_square_linear_score" or \
                contract["decision"]["margin_floor"] != 0.001 or \
                contract["decision"]["safety_factor"] != 0.5 or \
                contract["deployment"]["max_encrypted_trials"] != 4 or \
                contract["deployment"]["validation_key_repeats"] != 3 or \
                selection["outcome"] != "SELECTED" or \
                selection["trials_used"] != 1 or \
                len(selection["trials"]) != 1 or \
                selected != trial["candidate"] or \
                trial["status"] != "SAFE":
            raise ValueError(f"{tag}: first-SAFE selection changed")
        validate_candidate(selected)
        if contract["model_artifact"]["sha256"] != \
                sha256_path(source_model) or \
                contract["source_data"]["path"] != \
                    str(source_validation.relative_to(REPO_ROOT)) or \
                contract["source_data"]["sha256"] != \
                    sha256_path(source_validation) or \
                not contract["input_materialization"][
                    "source_replay_verified"
                ]:
            raise ValueError(f"{tag}: selection source replay changed")
        validation_samples = int(
            contract["decision"]["validation_samples"]
        )
        selection_evaluations = (
            validation_samples
            * int(trial["key_repeats_completed"])
        )
        if trial["v_cert"] + trial["v_amb"] != validation_samples or \
                selection_evaluations != \
                    selection_state[
                        "encrypted_sample_evaluations"
                    ] or \
                trial["decision_flips"] != 0 or \
                trial["error_violations"] != 0:
            raise ValueError(f"{tag}: selection accounting changed")

        if audit["outcome"] != "LOCKED_AUDIT_PASS" or \
                audit["retuning_performed"] or \
                audit["selected_candidate"] != selected or \
                audit["selection_contract_digest"] != \
                    plan["contract_digest"] or \
                audit["audit_trial"]["candidate"] != selected or \
                audit["audit_trial"]["status"] != "SAFE":
            raise ValueError(f"{tag}: locked audit identity changed")
        audit_contract = audit["audit_contract"]
        audit_trial = audit["audit_trial"]
        if audit_contract["model_artifact"] != \
                contract["model_artifact"] or \
                audit_contract["source_data"]["path"] != \
                    str(source_audit.relative_to(REPO_ROOT)) or \
                audit_contract["source_data"]["sha256"] != \
                    sha256_path(source_audit) or \
                audit_contract["deployment"][
                    "max_encrypted_trials"
                ] != 1 or \
                not audit_contract["input_materialization"][
                    "source_replay_verified"
                ]:
            raise ValueError(f"{tag}: audit source replay changed")
        audit_samples = int(
            audit_contract["decision"]["validation_samples"]
        )
        audit_evaluations = (
            audit_samples
            * int(audit_trial["key_repeats_completed"])
        )
        if audit_trial["v_cert"] + audit_trial["v_amb"] != \
                audit_samples or \
                audit_evaluations != \
                    audit_state["encrypted_sample_evaluations"] or \
                audit_trial["decision_flips"] != 0 or \
                audit_trial["error_violations"] != 0 or \
                audit_state["retuning"] != 0:
            raise ValueError(f"{tag}: audit accounting changed")

        if compatibility["representation_recovery"][
                "source_manifest_sha256"
            ] != sha256_path(source_manifest) or \
                compatibility["representation_recovery"][
                    "semantic_assignment_changed"
                ] or \
                audit["split_manifest"]["sha256"] != \
                    sha256_path(compatibility_path):
            raise ValueError(f"{tag}: manifest recovery changed")
        for partition in (
            "configuration_validation",
            "locked_audit_test",
        ):
            if string_ids(original[partition]["row_ids"]) != \
                    compatibility[partition]["row_ids"] or \
                    original[partition]["path"] != \
                    compatibility[partition]["path"] or \
                    original[partition]["csv_digest"] != \
                    compatibility[partition]["csv_digest"]:
                raise ValueError(
                    f"{tag}: {partition} semantics changed"
                )
        if set(
            string_ids(
                original["configuration_validation"]["row_ids"]
            )
        ) & set(
            string_ids(original["locked_audit_test"]["row_ids"])
        ):
            raise ValueError(f"{tag}: validation/audit overlap")

        static = preflight[(seed, dataset)]["initial_candidate"]
        if static["parameters"] != selected["parameters"] or \
                static["security"] != selected["security"]:
            raise ValueError(
                f"{tag}: preflight literal parameters changed"
            )
        static_id_identical = static["id"] == selected["id"]
        static_id_changes += int(not static_id_identical)
        rows.append(
            {
                "tag": tag,
                "training_seed": seed,
                "dataset_id": dataset,
                "model_sha256": sha256_path(source_model),
                "candidate_id": selected["id"],
                "static_plan_candidate_id":
                    static["id"],
                "static_candidate_id_identical":
                    static_id_identical,
                "literal_parameters_identical": True,
                "security_headroom_bits":
                    selected["security"]["headroom_bits"],
                "selection_outcome": selection["outcome"],
                "selection_trials": selection["trials_used"],
                "repairs": selection["trials_used"] - 1,
                "selection_key_runs":
                    trial["key_repeats_completed"],
                "selection_encrypted_evaluations":
                    selection_evaluations,
                "selection_v_cert": trial["v_cert"],
                "selection_v_amb": trial["v_amb"],
                "selection_flips": trial["decision_flips"],
                "selection_violations":
                    trial["error_violations"],
                "selection_max_error":
                    trial["max_observed_error"],
                "selection_max_budget_usage":
                    trial["max_error_budget_usage"],
                "audit_outcome": audit["outcome"],
                "audit_key_runs":
                    audit_trial["key_repeats_completed"],
                "audit_encrypted_evaluations":
                    audit_evaluations,
                "audit_v_cert": audit_trial["v_cert"],
                "audit_v_amb": audit_trial["v_amb"],
                "audit_flips": audit_trial["decision_flips"],
                "audit_violations":
                    audit_trial["error_violations"],
                "audit_max_error":
                    audit_trial["max_observed_error"],
                "audit_max_budget_usage":
                    audit_trial["max_error_budget_usage"],
                "retuning": 0,
            }
        )

    recovery_logs = sorted(
        run_root.glob("audit/logs/*.attempt*.log")
    )
    parser_failures = [
        path
        for path in recovery_logs
        if "cannot unmarshal number" in path.read_text(
            encoding="ascii"
        )
    ]
    successful_attempt_logs = [
        path
        for path in recovery_logs
        if "locked_audit=LOCKED_AUDIT_PASS" in path.read_text(
            encoding="ascii"
        )
    ]
    if len(recovery_logs) != 27 or \
            len(parser_failures) != 18 or \
            len(successful_attempt_logs) != 9:
        raise ValueError(
            "independent-seed parser failure ledger changed"
        )
    manifest_recoveries = [
        record
        for record in state["recoveries"]
        if record["reason_code"]
        == "NUMERIC_ROW_IDS_IN_STRING_SCHEMA"
    ]
    accounting_recoveries = [
        record
        for record in state["recoveries"]
        if record["reason_code"]
        == "POST_RESULT_ACCOUNTING_FIELD_MISMATCH"
    ]
    if len(manifest_recoveries) != 9 or \
            len(accounting_recoveries) != 1 or \
            any(
                record["semantic_assignment_changed"]
                or record["encrypted_selection_rerun"]
                or record["prior_audit_reached_ckks_execution"]
                for record in manifest_recoveries
            ):
        raise ValueError("independent-seed recovery ledger changed")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": (
            "three datasets x three independent training/data-split "
            "seeds for mlp_square_linear_score"
        ),
        "status": "SUPPORTED",
        "training_seed_generalization": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "paper_claim_block_reason": (
            "three datasets and three declared seeds do not establish "
            "universal training-seed or model generalization"
        ),
        "instances": len(rows),
        "trained_model_digests": len(
            {row["model_sha256"] for row in rows}
        ),
        "selection": {
            "selected": sum(
                row["selection_outcome"] == "SELECTED"
                for row in rows
            ),
            "no_safe": 0,
            "trials": sum(
                row["selection_trials"] for row in rows
            ),
            "repairs": sum(row["repairs"] for row in rows),
            "key_runs": sum(
                row["selection_key_runs"] for row in rows
            ),
            "encrypted_sample_evaluations": sum(
                row["selection_encrypted_evaluations"]
                for row in rows
            ),
            "v_cert": sum(row["selection_v_cert"] for row in rows),
            "v_amb": sum(row["selection_v_amb"] for row in rows),
            "flips": sum(row["selection_flips"] for row in rows),
            "violations": sum(
                row["selection_violations"] for row in rows
            ),
            "maximum_error": max(
                row["selection_max_error"] for row in rows
            ),
            "maximum_budget_usage": max(
                row["selection_max_budget_usage"]
                for row in rows
            ),
        },
        "locked_audit": {
            "pass": sum(
                row["audit_outcome"] == "LOCKED_AUDIT_PASS"
                for row in rows
            ),
            "rejected": 0,
            "failed": 0,
            "key_runs": sum(row["audit_key_runs"] for row in rows),
            "encrypted_sample_evaluations": sum(
                row["audit_encrypted_evaluations"] for row in rows
            ),
            "v_cert": sum(row["audit_v_cert"] for row in rows),
            "v_amb": sum(row["audit_v_amb"] for row in rows),
            "flips": sum(row["audit_flips"] for row in rows),
            "violations": sum(
                row["audit_violations"] for row in rows
            ),
            "retuning": sum(row["retuning"] for row in rows),
            "maximum_error": max(
                row["audit_max_error"] for row in rows
            ),
            "maximum_budget_usage": max(
                row["audit_max_budget_usage"] for row in rows
            ),
        },
        "security": {
            "admitted": len(rows),
            "inadmissible": 0,
            "minimum_headroom_bits": min(
                row["security_headroom_bits"] for row in rows
            ),
        },
        "static_preflight": {
            "literal_parameters_identical": len(rows),
            "candidate_id_identical": len(rows) - static_id_changes,
            "candidate_id_representation_changes":
                static_id_changes,
            "reason": (
                "candidate IDs bind the prepared-contract path; "
                "selection literals retain identical CKKS parameters "
                "and Security V2 facts"
            ),
        },
        "recoveries": {
            "post_result_accounting": len(accounting_recoveries),
            "numeric_to_string_manifest_views":
                len(manifest_recoveries),
            "preserved_pre_ckks_parser_failure_logs":
                len(parser_failures),
            "successful_logs_reusing_attempt1_paths":
                len(successful_attempt_logs),
            "overwritten_attempt1_parser_failure_logs": 9,
            "encrypted_selection_reruns": 0,
            "semantic_split_changes": 0,
        },
        "claim_limits": [
            "no universal training-seed robustness claim",
            "no independent-dataset inference from nine rows",
            "no bounded-catalog or global-optimum claim",
            "no packed inference claim",
            "no model-accuracy improvement claim",
        ],
    }
    if summary["trained_model_digests"] != 9 or \
            summary["selection"]["selected"] != 9 or \
            summary["selection"]["trials"] != 9 or \
            summary["selection"]["repairs"] != 0 or \
            summary["selection"]["flips"] != 0 or \
            summary["selection"]["violations"] != 0 or \
            summary["locked_audit"]["pass"] != 9 or \
            summary["locked_audit"]["flips"] != 0 or \
            summary["locked_audit"]["violations"] != 0 or \
            summary["locked_audit"]["retuning"] != 0 or \
            summary["security"]["admitted"] != 9:
        raise ValueError("independent-seed evidence invariant changed")
    return run_manifest, state, {"summary": summary, "rows": rows}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def copy_tree_contents(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def build_pack(run_root: Path, output_root: Path) -> None:
    run_manifest, state, derived = validate_run(run_root)
    output_root.mkdir(parents=True)
    raw = output_root / "raw"
    raw.mkdir()
    for name in (
        "run_manifest.json",
        "run_manifest.sha256",
        "state.json",
        "summary.json",
        "summary.csv",
    ):
        shutil.copy2(run_root / name, raw / name)
    for name in ("preflight", "selection", "audit"):
        source = run_root / name
        destination = raw / name
        destination.mkdir()
        for path in sorted(source.rglob("*")):
            if path.is_dir() or "/bin/" in path.as_posix():
                continue
            relative = path.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    inputs = output_root / "inputs"
    inputs.mkdir()
    copy_tree_contents(REPO_ROOT / INPUT_ROOT, inputs)
    (output_root / "summary.json").write_bytes(
        canonical_json(derived["summary"])
    )
    write_csv(output_root / "workload_summary.csv", derived["rows"])
    recovery = {
        "schema_version": SCHEMA_VERSION,
        "recoveries": state["recoveries"],
        "resume_records": state["resume_records"],
        "additional_disclosed_recoveries": [
            {
                "classification":
                    "RECOVERABLE_IMPLEMENTATION_FAILURE",
                "reason_code":
                    "DEFAULT_RUN_ROOT_CHANGED_AFTER_ORCHESTRATOR_COMMIT",
                "encrypted_execution_started": False,
                "resolution": (
                    "resume used the explicit immutable run_f3cfd7f root"
                ),
            },
            {
                "classification":
                    "RECOVERABLE_IMPLEMENTATION_FAILURE",
                "reason_code":
                    "RECOVERY_ATTEMPT1_LOG_PATH_REUSED",
                "encrypted_result_overwritten": False,
                "frozen_evidence_overwritten": False,
                "preserved_parser_failure_logs": 18,
                "overwritten_parser_failure_logs": 9,
                "impact": (
                    "the successful resume reused each attempt1 log "
                    "path; attempt2 and attempt3 failure logs remain"
                ),
            },
        ],
    }
    (output_root / "recovery_records.json").write_bytes(
        canonical_json(recovery)
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "execution_commit": EXECUTION_COMMIT,
        "execution_critical_source_digest":
            run_manifest["execution_critical_source_digest"],
        "orchestrator_resume_commits": [
            record["current_commit"]
            for record in state["resume_records"]
        ],
        "binary_sha256": {
            name: value["sha256"]
            for name, value in run_manifest["binaries"].items()
        },
        "input_policy_digest": INPUT_POLICY_DIGEST,
        "input_summary_sha256":
            run_manifest["input_summary_sha256"],
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "run_manifest_sha256": sha256_path(
            run_root / "run_manifest.json"
        ),
        "runner_state_sha256": sha256_path(
            run_root / "state.json"
        ),
        "summary_sha256": sha256_path(
            output_root / "summary.json"
        ),
        "workload_summary_sha256": sha256_path(
            output_root / "workload_summary.csv"
        ),
        "instances": 9,
        "claim_status": "SUPPORTED",
        "training_seed_generalization": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
    }
    (output_root / "manifest.json").write_bytes(
        canonical_json(manifest)
    )
    readme = """# Independent Training-Seed Extension Evidence V1

This pack freezes three datasets x three independently trained
`mlp_square_linear_score` models. All nine direct selections chose their first
Security-V2-admitted literal and all nine byte-identical locked audits passed
without retuning.

The pack preserves 18 numeric-row-ID parser failure logs and the run-local
string-typed manifest views. The successful resume reused nine `attempt1` log
paths, so those nine first-failure logs were overwritten before this pack was
frozen; this artifact-assurance limitation is disclosed in
`recovery_records.json`. The views change representation only:
ordered row values, source paths, CSV digests, split membership, candidates,
and policies remain unchanged. The failed attempts did not reach CKKS audit
execution, and no encrypted selection was rerun.

The result supports only the declared three-dataset, three-seed scope.
Training-seed generalization remains `PARTIALLY_SUPPORTED`, and
`paper_claim_allowed=false`.
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
        prefix="flipguard_independent_seed_evidence_"
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
            raise ValueError(
                "independent-seed evidence file set changed"
            )
        for relative in sorted(expected):
            if (output_root / relative).read_bytes() != \
                    (replay / relative).read_bytes():
                raise ValueError(
                    f"independent-seed evidence changed: {relative}"
                )


def verify_source_replay(
    python_with_science_deps: str,
) -> None:
    subprocess.run(
        [
            python_with_science_deps,
            "scripts/verify_independent_training_seed_extension.py",
        ],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
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
    verify_source_replay(args.python_with_science_deps)
    if args.verify:
        verify_pack(run_root, output_root)
        print(
            "independent_training_seed_evidence=PASS "
            f"manifest={sha256_path(output_root / 'manifest.json')}"
        )
        return
    if output_root.exists():
        raise SystemExit(
            f"refusing to overwrite evidence pack: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="flipguard_independent_seed_freeze_",
        dir=str(output_root.parent),
    ) as temporary:
        staging = Path(temporary) / "pack"
        build_pack(run_root, staging)
        staging.rename(output_root)
    print(
        "independent_training_seed_evidence=FROZEN "
        f"manifest={sha256_path(output_root / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
