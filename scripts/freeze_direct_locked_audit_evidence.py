#!/usr/bin/env python3
"""Freeze or verify a compact direct locked-audit evidence snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "seed0_floor18_keys3/locked_audit/"
    "seed0_floor18_keys3_locked_audit_keys3"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/direct_locked_audit_seed0_v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--evidence-id",
        default="direct_locked_audit_seed0_v1",
    )
    parser.add_argument(
        "--evidence-stage",
        choices=("preliminary", "confirmatory"),
        default="preliminary",
        help="claim stage recorded in the frozen evidence manifest",
    )
    parser.add_argument(
        "--selection-run-id",
        default="seed0_floor18_keys3",
    )
    parser.add_argument(
        "--audit-run-id",
        default="seed0_floor18_keys3_locked_audit_keys3",
    )
    parser.add_argument(
        "--split-seeds",
        default="0",
        help="comma-separated split seeds represented by the checkpoint",
    )
    parser.add_argument(
        "--key-repeats",
        type=int,
        default=3,
        help="exact fresh-key repetitions required per locked audit",
    )
    parser.add_argument(
        "--execution-command",
        default=(
            "scripts/run_direct_tabular_locked_audit_matrix.sh "
            "--seed0 --force"
        ),
    )
    parser.add_argument(
        "--expected-model-ids",
        default="",
        help=(
            "optional comma-separated exact model IDs required in the pack"
        ),
    )
    parser.add_argument(
        "--require-max-budget-usage-below",
        type=float,
        default=None,
        help=(
            "require every locked-audit normalized error-budget usage "
            "to be finite and strictly below this value"
        ),
    )
    parser.add_argument(
        "--require-source-replay",
        action="store_true",
        help=(
            "require and snapshot model-input source materialization "
            "with source replay verified for every selection"
        ),
    )
    parser.add_argument(
        "--extra-artifact",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help=(
            "checksum and snapshot an additional protocol or analysis "
            "artifact; may be repeated"
        ),
    )
    parser.add_argument(
        "--source-protocol-manifest",
        type=Path,
        default=None,
        help=(
            "clean-run protocol whose source commit/files must match "
            "--source-commit; it is snapshotted as source_protocol"
        ),
    )
    parser.add_argument("--allow-checkpoint", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return require_dict(
        json.loads(path.read_text(encoding="utf-8")),
        str(path),
    )


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source artifact {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def parse_extra_artifacts(
    values: list[str],
) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    names: set[str] = set()
    for value in values:
        name, separator, raw_path = value.partition("=")
        if (
            not separator
            or not name
            or not raw_path
            or not all(
                character.isalnum() or character in {"_", "-"}
                for character in name
            )
            or name in names
        ):
            raise ValueError(
                "--extra-artifact must use unique NAME=PATH values "
                "with alphanumeric, underscore, or hyphen names"
            )
        names.add(name)
        parsed.append((name, Path(raw_path)))
    return parsed


def validate_source_protocol(
    path: Path,
    source_commit: str,
) -> None:
    protocol = load_json(path)
    source = require_dict(
        protocol.get("source"),
        f"{path}: source",
    )
    files = require_dict(
        source.get("files"),
        f"{path}: source files",
    )
    if (
        protocol.get("status") != "COMPLETE"
        or source.get("commit") != source_commit
        or not files
    ):
        raise ValueError(
            f"{path}: source protocol is not COMPLETE at {source_commit}"
        )
    digest = hashlib.sha256()
    for relative, raw_binding in sorted(files.items()):
        item = require_dict(
            raw_binding,
            f"{path}: source binding {relative}",
        )
        source_path = Path(relative)
        if source_path.is_absolute() or ".." in source_path.parts:
            raise ValueError(
                f"{path}: unsafe source path {source_path}"
            )
        repository_path = Path.cwd() / source_path
        actual = "sha256:" + sha256_file(repository_path)
        if (
            repository_path.stat().st_size != item.get("bytes")
            or actual != item.get("sha256")
        ):
            raise ValueError(
                f"{path}: source binding changed for {source_path}"
            )
        digest.update(str(source_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(actual.encode("ascii"))
        digest.update(b"\n")
    if "sha256:" + digest.hexdigest() != source.get("digest"):
        raise ValueError(f"{path}: composite source digest changed")


def freeze(args: argparse.Namespace) -> None:
    if not args.source_commit:
        raise ValueError("--source-commit is required when freezing")
    source_commit = git_text("rev-parse", args.source_commit)
    git_text("cat-file", "-e", source_commit + "^{commit}")
    if args.key_repeats <= 0:
        raise ValueError("--key-repeats must be positive")
    if args.evidence_stage == "confirmatory" and (
        args.allow_checkpoint or not args.require_source_replay
    ):
        raise ValueError(
            "confirmatory evidence requires a complete "
            "source-replay-gated pack"
        )

    source = args.source_root
    output = args.output_root
    status_path = source / "locked_audit_status.csv"
    summary_path = source / "summary" / "summary.json"
    results_csv_path = (
        source / "summary" / "locked_audit_results.csv"
    )
    summary = load_json(summary_path)
    if not summary.get("complete") and not args.allow_checkpoint:
        raise ValueError("source locked-audit matrix is incomplete")
    if summary.get("locked_audit_fails") != 0:
        raise ValueError("source contains locked-audit failures")
    if summary.get("failed_executions") != 0:
        raise ValueError("source contains execution failures")

    with status_path.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        status_rows = list(csv.DictReader(handle))
    if len(status_rows) != int(summary["expected_runs"]):
        if not args.allow_checkpoint:
            raise ValueError(
                "source status row count does not match expected runs"
            )
        if len(status_rows) != int(summary["recorded_runs"]):
            raise ValueError(
                "checkpoint status row count does not match recorded runs"
            )
    if any(row["status"] != "ok" for row in status_rows):
        raise ValueError("source status contains failed rows")

    split_seeds = [
        int(value.strip())
        for value in args.split_seeds.split(",")
        if value.strip()
    ]
    if not split_seeds:
        raise ValueError("--split-seeds contains no seeds")
    selected_status_rows = [
        row
        for row in status_rows
        if int(row["split_seed"]) in set(split_seeds)
    ]
    if not selected_status_rows:
        raise ValueError("requested split scope contains no workloads")
    status_rows = selected_status_rows

    expected_model_ids = {
        value.strip()
        for value in args.expected_model_ids.split(",")
        if value.strip()
    }
    observed_model_ids = {
        row["model_id"] for row in status_rows
    }
    if (
        expected_model_ids
        and observed_model_ids != expected_model_ids
    ):
        raise ValueError(
            "source model IDs changed: "
            f"got {sorted(observed_model_ids)}, "
            f"expected {sorted(expected_model_ids)}"
        )
    budget_limit = args.require_max_budget_usage_below
    if budget_limit is not None and (
        not math.isfinite(budget_limit) or budget_limit <= 0
    ):
        raise ValueError(
            "--require-max-budget-usage-below must be finite and positive"
        )
    extra_values = list(args.extra_artifact)
    if args.source_protocol_manifest is not None:
        validate_source_protocol(
            args.source_protocol_manifest,
            source_commit,
        )
        extra_values.append(
            "source_protocol="
            + str(args.source_protocol_manifest)
        )
    extras = parse_extra_artifacts(extra_values)

    if output.exists():
        if not args.force:
            raise ValueError(
                f"{output} already exists; use --force to replace it"
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)

    def snapshot(source_path: Path, relative: Path) -> Path:
        target = output / relative
        if target.is_file():
            if sha256_file(target) != sha256_file(source_path):
                raise ValueError(
                    f"conflicting deduplicated snapshot {target}"
                )
            return target
        copy_file(source_path, target)
        return target

    scoped_status_path = output / "source_locked_audit_status.csv"
    with scoped_status_path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(status_rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(status_rows)
    with results_csv_path.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        source_result_rows = list(csv.DictReader(handle))
    scoped_result_rows = [
        row
        for row in source_result_rows
        if int(row["split_seed"]) in set(split_seeds)
    ]
    scoped_results_path = output / "outputs/locked_audit_results.csv"
    scoped_results_path.parent.mkdir(parents=True, exist_ok=True)
    with scoped_results_path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(scoped_result_rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(scoped_result_rows)

    external_inputs: list[dict[str, Any]] = []
    workload_records: list[dict[str, Any]] = []
    for row in sorted(
        status_rows,
        key=lambda value: (
            int(value["split_seed"]),
            value["dataset_id"],
            value["model_id"],
        ),
    ):
        identity = (
            f"seed{row['split_seed']}__"
            f"{row['dataset_id']}__{row['model_id']}"
        )
        result_source = Path(row["result_path"])
        selection_source = Path(row["selection_path"])
        manifest_source = Path(row["manifest_path"])
        audit_source = Path(row["audit_path"])

        result_target = snapshot(
            result_source,
            Path("outputs/audit_results") / f"{identity}.json",
        )
        selection_target = snapshot(
            selection_source,
            Path("inputs/selections") / f"{identity}.json",
        )
        manifest_target = snapshot(
            manifest_source,
            Path("inputs/split_manifests") / f"{identity}.json",
        )

        result = load_json(result_source)
        selection = load_json(selection_source)
        split_manifest = load_json(manifest_source)
        selection_contract = require_dict(
            require_dict(
                selection.get("plan"),
                f"{selection_source}: plan",
            ).get("contract"),
            f"{selection_source}: contract",
        )
        model_binding = require_dict(
            selection_contract.get("model_artifact"),
            f"{selection_source}: model artifact",
        )
        validation_binding = require_dict(
            selection_contract.get("validation_data"),
            f"{selection_source}: validation artifact",
        )
        source_binding_value = selection_contract.get("source_data")
        materialization_value = selection_contract.get(
            "input_materialization"
        )
        source_binding: dict[str, Any] | None = None
        materialization: dict[str, Any] | None = None
        if (
            source_binding_value is not None
            or materialization_value is not None
            or args.require_source_replay
        ):
            source_binding = require_dict(
                source_binding_value,
                f"{selection_source}: source data",
            )
            materialization = require_dict(
                materialization_value,
                f"{selection_source}: input materialization",
            )
            if (
                materialization.get("schema_version")
                != "flipguard_tabular_validation_v2"
                or materialization.get("source_feature_space")
                != "model_input"
                or materialization.get("preprocessing_method")
                != "identity_model_input_v1"
                or materialization.get("source_replay_verified")
                is not True
            ):
                raise ValueError(
                    f"{identity}: model-input source replay "
                    "contract is invalid"
                )
        source_test_path = Path(
            str(split_manifest["source_test_csv"])
        )
        model_snapshot = snapshot(
            Path(str(model_binding["path"])),
            Path("inputs/model_artifacts")
            / f"{row['dataset_id']}__{row['model_id']}.json",
        )
        source_test_snapshot = snapshot(
            source_test_path,
            Path("inputs/source_test_csv")
            / f"{row['dataset_id']}__{row['model_id']}.csv",
        )
        split_validation = require_dict(
            split_manifest.get("configuration_validation"),
            f"{identity}: split configuration validation",
        )
        split_audit = require_dict(
            split_manifest.get("locked_audit_test"),
            f"{identity}: split locked audit",
        )
        source_snapshot: Path | None = None
        prepared_snapshot: Path | None = None
        if source_binding is not None:
            source_data_path = Path(str(source_binding["path"]))
            if (
                source_data_path != Path(str(split_validation["path"]))
                or str(source_binding["sha256"])
                != str(split_validation["csv_digest"])
            ):
                raise ValueError(
                    f"{identity}: source data is not the declared "
                    "configuration-validation partition"
                )
            source_snapshot = snapshot(
                source_data_path,
                Path("inputs/source_data") / f"{identity}.csv",
            )
            prepared_snapshot = snapshot(
                Path(str(validation_binding["path"])),
                Path("inputs/prepared_validation")
                / f"{identity}.csv",
            )
        audit_contract = require_dict(
            result.get("audit_contract"),
            f"{result_source}: audit contract",
        )
        audit_validation_binding = require_dict(
            audit_contract.get("validation_data"),
            f"{result_source}: audit validation artifact",
        )
        audit_source_binding_value = audit_contract.get("source_data")
        audit_materialization_value = audit_contract.get(
            "input_materialization"
        )
        audit_source_binding: dict[str, Any] | None = None
        audit_materialization: dict[str, Any] | None = None
        audit_source_snapshot: Path | None = None
        prepared_audit_snapshot: Path | None = None
        if (
            audit_source_binding_value is not None
            or audit_materialization_value is not None
            or args.require_source_replay
        ):
            audit_source_binding = require_dict(
                audit_source_binding_value,
                f"{result_source}: audit source data",
            )
            audit_materialization = require_dict(
                audit_materialization_value,
                f"{result_source}: audit input materialization",
            )
            if (
                audit_materialization.get("schema_version")
                != "flipguard_tabular_validation_v2"
                or audit_materialization.get("source_feature_space")
                != "model_input"
                or audit_materialization.get("preprocessing_method")
                != "identity_model_input_v1"
                or audit_materialization.get(
                    "source_replay_verified"
                )
                is not True
                or Path(str(audit_source_binding["path"]))
                != audit_source
                or str(audit_source_binding["sha256"])
                != str(split_audit["csv_digest"])
            ):
                raise ValueError(
                    f"{identity}: locked-audit source replay "
                    "contract is invalid"
                )
            audit_source_snapshot = snapshot(
                audit_source,
                Path("inputs/audit_source_data")
                / f"{identity}.csv",
            )
            prepared_audit_snapshot = snapshot(
                Path(str(audit_validation_binding["path"])),
                Path("inputs/prepared_audit")
                / f"{identity}.csv",
            )

        bindings = [
            (
                "model_artifact",
                Path(str(model_binding["path"])),
                str(model_binding["sha256"]),
            ),
            (
                (
                    "prepared_validation"
                    if source_binding is not None
                    else "configuration_validation"
                ),
                Path(str(validation_binding["path"])),
                str(validation_binding["sha256"]),
            ),
            (
                "locked_audit_test",
                audit_source,
                str(split_audit["csv_digest"]),
            ),
            (
                "source_test_csv",
                source_test_path,
                str(split_manifest["source_test_csv_digest"]),
            ),
        ]
        if source_binding is not None:
            bindings.append(
                (
                    "source_data",
                    Path(str(source_binding["path"])),
                    str(source_binding["sha256"]),
                )
            )
        if audit_source_binding is not None:
            bindings.append(
                (
                    "prepared_audit",
                    Path(str(audit_validation_binding["path"])),
                    str(audit_validation_binding["sha256"]),
                )
            )
        for kind, path, expected_digest in bindings:
            actual = "sha256:" + sha256_file(path)
            if actual != expected_digest:
                raise ValueError(
                    f"{identity}: {kind} digest {actual} "
                    f"!= {expected_digest}"
                )
            external_inputs.append(
                {
                    "workload": identity,
                    "kind": kind,
                    "path": str(path),
                    "sha256": actual,
                    "size_bytes": path.stat().st_size,
                }
            )

        trial = require_dict(
            result.get("audit_trial"),
            f"{result_source}: audit trial",
        )
        candidate = require_dict(
            result.get("selected_candidate"),
            f"{result_source}: selected candidate",
        )
        parameters = require_dict(
            candidate.get("parameters"),
            f"{result_source}: parameters",
        )
        max_budget_usage = trial.get("max_error_budget_usage")
        if budget_limit is not None and (
            not isinstance(max_budget_usage, (int, float))
            or not math.isfinite(float(max_budget_usage))
            or float(max_budget_usage) >= budget_limit
        ):
            raise ValueError(
                f"{identity}: normalized error-budget usage "
                f"{max_budget_usage!r} is not below {budget_limit}"
            )
        if trial.get("key_repeats_completed") != args.key_repeats:
            raise ValueError(
                f"{identity}: completed key repeats "
                f"{trial.get('key_repeats_completed')!r} != "
                f"{args.key_repeats}"
            )
        workload_records.append(
            {
                "workload": identity,
                "split_seed": int(row["split_seed"]),
                "dataset_id": row["dataset_id"],
                "model_id": row["model_id"],
                "outcome": result["outcome"],
                "candidate_id": candidate["id"],
                "log_n": parameters["log_n"],
                "q_prime_count": len(parameters["log_q"]),
                "log_default_scale": parameters[
                    "log_default_scale"
                ],
                "key_repeats_completed": trial[
                    "key_repeats_completed"
                ],
                "configuration_trials": int(
                    selection["trials_used"]
                ),
                "selection_key_runs": int(
                    selection["encrypted_key_runs"]
                ),
                "decision_flips": trial["decision_flips"],
                "error_violations": trial["error_violations"],
                "max_error_budget_usage": (
                    max_budget_usage
                    if max_budget_usage is not None
                    else ""
                ),
                "v_cert": trial["v_cert"],
                "v_amb": trial["v_amb"],
                "audit_result_snapshot": str(
                    result_target.relative_to(output)
                ),
                "selection_snapshot": str(
                    selection_target.relative_to(output)
                ),
                "split_manifest_snapshot": str(
                    manifest_target.relative_to(output)
                ),
                "model_artifact_sha256": model_binding["sha256"],
                "model_artifact_snapshot": str(
                    model_snapshot.relative_to(output)
                ),
                "source_test_sha256": split_manifest[
                    "source_test_csv_digest"
                ],
                "source_test_snapshot": str(
                    source_test_snapshot.relative_to(output)
                ),
                "source_replay_verified": (
                    materialization is not None
                    and materialization.get(
                        "source_replay_verified"
                    )
                    is True
                ),
                "source_feature_space": (
                    materialization.get("source_feature_space", "")
                    if materialization is not None
                    else ""
                ),
                "preprocessing_method": (
                    materialization.get("preprocessing_method", "")
                    if materialization is not None
                    else ""
                ),
                "source_data_sha256": (
                    source_binding.get("sha256", "")
                    if source_binding is not None
                    else ""
                ),
                "prepared_validation_sha256": validation_binding[
                    "sha256"
                ],
                "source_data_snapshot": (
                    str(source_snapshot.relative_to(output))
                    if source_snapshot is not None
                    else ""
                ),
                "prepared_validation_snapshot": (
                    str(prepared_snapshot.relative_to(output))
                    if prepared_snapshot is not None
                    else ""
                ),
                "audit_source_replay_verified": (
                    audit_materialization is not None
                    and audit_materialization.get(
                        "source_replay_verified"
                    )
                    is True
                ),
                "audit_source_feature_space": (
                    audit_materialization.get(
                        "source_feature_space",
                        "",
                    )
                    if audit_materialization is not None
                    else ""
                ),
                "audit_preprocessing_method": (
                    audit_materialization.get(
                        "preprocessing_method",
                        "",
                    )
                    if audit_materialization is not None
                    else ""
                ),
                "audit_source_sha256": (
                    audit_source_binding.get("sha256", "")
                    if audit_source_binding is not None
                    else ""
                ),
                "prepared_audit_sha256": audit_validation_binding[
                    "sha256"
                ],
                "audit_source_snapshot": (
                    str(audit_source_snapshot.relative_to(output))
                    if audit_source_snapshot is not None
                    else ""
                ),
                "prepared_audit_snapshot": (
                    str(
                        prepared_audit_snapshot.relative_to(output)
                    )
                    if prepared_audit_snapshot is not None
                    else ""
                ),
            }
        )

    summary = dict(summary)
    summary.update(
        {
            "complete": True,
            "expected_runs": len(workload_records),
            "recorded_runs": len(workload_records),
            "successful_executions": len(workload_records),
            "failed_executions": 0,
            "failed_tags": [],
            "locked_audit_passes": len(workload_records),
            "locked_audit_fails": 0,
            "retuned_runs": 0,
            "zero_flip_passes": sum(
                row["decision_flips"] == 0
                for row in workload_records
            ),
            "zero_violation_passes": sum(
                row["error_violations"] == 0
                for row in workload_records
            ),
            "total_configuration_trials": sum(
                row["configuration_trials"]
                for row in workload_records
            ),
            "total_fresh_key_runs": sum(
                row["key_repeats_completed"]
                for row in workload_records
            ),
            "total_selection_key_runs": sum(
                row["selection_key_runs"]
                for row in workload_records
            ),
            "total_v_cert": sum(
                row["v_cert"] for row in workload_records
            ),
            "total_v_amb": sum(
                row["v_amb"] for row in workload_records
            ),
            "split_seeds": split_seeds,
            "source_expected_runs": int(
                load_json(summary_path)["expected_runs"]
            ),
        }
    )
    (output / "outputs/summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    extra_records = []
    for name, source_path in extras:
        suffix = "".join(source_path.suffixes)
        target = snapshot(
            source_path,
            Path("extras") / f"{name}{suffix}",
        )
        extra_records.append(
            {
                "name": name,
                "source_path": str(source_path),
                "snapshot": str(target.relative_to(output)),
                "sha256": "sha256:" + sha256_file(target),
                "size_bytes": target.stat().st_size,
            }
        )

    manifest = {
        "schema_version": 1,
        "evidence_id": args.evidence_id,
        "evidence_stage": args.evidence_stage,
        "evidence_type": (
            "observed_no_retuning_locked_audit_"
            + args.evidence_stage
        ),
        "source_code": {
            "git_commit": source_commit,
            "commit_time": git_text(
                "show", "-s", "--format=%cI", source_commit
            ),
            "subject": git_text(
                "show", "-s", "--format=%s", source_commit
            ),
        },
        "execution": {
            "selection_run_id": args.selection_run_id,
            "audit_run_id": args.audit_run_id,
            "command": args.execution_command,
            "split_seeds": split_seeds,
            "key_repeats": args.key_repeats,
            "retuning_allowed": False,
            "checkpoint": not bool(summary.get("complete")),
        },
        "scope_policy": {
            "expected_model_ids": sorted(expected_model_ids),
            "require_max_budget_usage_below": budget_limit,
            "require_source_replay": args.require_source_replay,
            "require_self_contained_inputs": True,
            "source_protocol_required":
                args.source_protocol_manifest is not None,
        },
        "structural_summary": summary,
        "workloads": workload_records,
        "external_inputs": external_inputs,
        "extra_artifacts": extra_records,
        "claim_boundary": (
            "All frozen candidates in the recorded split checkpoint "
            "remained SAFE with "
            "zero flips and zero protected error-budget violations "
            "on the disjoint locked-audit V_cert rows across three "
            "fresh keypairs. This is limited observed evidence, "
            "not a distribution-wide, split-independent, "
            "key-independent, or analytical safety guarantee."
        ),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.require_source_replay:
        input_storage_note = (
            "The exact model artifact, upstream source test CSV, and "
            "source/materialized CSVs for both selection and locked "
            "audit are included and bound by SHA-256."
        )
    else:
        input_storage_note = (
            "The exact model artifact and upstream source test CSV are "
            "included and bound by SHA-256. The large partition CSVs are "
            "not duplicated for this legacy non-replay pack."
        )

    readme = f"""# Direct Locked Audit Evidence: {args.evidence_id}

## Result

- Split seeds in this pack: `{",".join(map(str, split_seeds))}`
- Frozen configurations audited: `{len(workload_records)}`
- Locked-audit PASS: `{summary["locked_audit_passes"]}/{len(workload_records)}`
- Configuration trials: `{summary["total_configuration_trials"]}`
- Fresh-key runs: `{summary["total_fresh_key_runs"]}`
- Retuning during audit: `{summary["retuned_runs"]}`
- Total audit V_cert: `{summary["total_v_cert"]}`
- Total audit V_amb: `{summary["total_v_amb"]}`
- Matrix complete: `{str(bool(summary.get("complete"))).lower()}`
- Expected model IDs: `{",".join(sorted(expected_model_ids)) or "not constrained"}`
- Normalized error-budget usage limit: `{budget_limit if budget_limit is not None else "not constrained"}`
- Source replay required: `{str(args.require_source_replay).lower()}`
- Extra protocol/analysis artifacts: `{len(extra_records)}`

The audit command evaluated each validation-selected CKKS literal exactly
once on the disjoint `locked_audit_test.csv` partition with
{args.key_repeats} fresh keypair(s). It did not call synthesis or candidate
repair.

## Reproduce

Regenerate the deterministic split artifacts, regenerate the selection run,
and execute:

```bash
{args.execution_command}
```

Verify this compact snapshot:

```bash
python3 scripts/freeze_direct_locked_audit_evidence.py \\
  --output-root docs/evidence/{args.evidence_id} \\
  --verify
```

{input_storage_note} The snapshot includes
{len(workload_records)} selection results and the matching split manifests,
locked-audit results, execution ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen {args.evidence_stage} evidence for the recorded split set and
{args.key_repeats} fresh keypair(s). It supports no-retuning held-out decision
stability for the recorded workloads. It does not establish split
independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
"""
    readme_path = output / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    checksum_paths = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_text = "".join(
        f"{sha256_file(path)}  {path.relative_to(output)}\n"
        for path in checksum_paths
    )
    (output / "SHA256SUMS").write_text(
        checksum_text,
        encoding="utf-8",
    )

    print(
        "direct_locked_audit_evidence="
        f"FROZEN_{args.evidence_stage.upper()} "
        f"workloads={len(workload_records)} "
        f"files={len(checksum_paths)} output={output}"
    )


def verify_self_contained_input(
    root: Path,
    row: dict[str, Any],
) -> None:
    selection_snapshot = root / str(
        row.get("selection_snapshot", "")
    )
    audit_result_snapshot = root / str(
        row.get("audit_result_snapshot", "")
    )
    model_snapshot = root / str(
        row.get("model_artifact_snapshot", "")
    )
    source_test_snapshot = root / str(
        row.get("source_test_snapshot", "")
    )
    split_manifest_snapshot = root / str(
        row.get("split_manifest_snapshot", "")
    )
    if (
        not selection_snapshot.is_file()
        or not audit_result_snapshot.is_file()
        or not model_snapshot.is_file()
        or not source_test_snapshot.is_file()
        or not split_manifest_snapshot.is_file()
        or "sha256:" + sha256_file(model_snapshot)
        != row.get("model_artifact_sha256")
        or "sha256:" + sha256_file(source_test_snapshot)
        != row.get("source_test_sha256")
    ):
        raise ValueError(
            "snapshot self-contained upstream input changed"
        )
    selection = load_json(selection_snapshot)
    contract = require_dict(
        require_dict(
            selection.get("plan"),
            f"{selection_snapshot}: plan",
        ).get("contract"),
        f"{selection_snapshot}: contract",
    )
    audit_result = load_json(audit_result_snapshot)
    audit_contract = require_dict(
        audit_result.get("audit_contract"),
        f"{audit_result_snapshot}: audit contract",
    )
    split_manifest = load_json(split_manifest_snapshot)
    if (
        require_dict(
            contract.get("model_artifact"),
            f"{selection_snapshot}: model artifact",
        ).get("sha256")
        != row["model_artifact_sha256"]
        or require_dict(
            audit_contract.get("model_artifact"),
            f"{audit_result_snapshot}: model artifact",
        ).get("sha256")
        != row["model_artifact_sha256"]
        or split_manifest.get("source_test_csv_digest")
        != row["source_test_sha256"]
        or split_manifest.get("model_artifact_digest")
        != row["model_artifact_sha256"]
    ):
        raise ValueError("snapshot upstream input binding changed")


def verify(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{checksum_path}: checksum list is empty")
    declared: set[Path] = set()
    for line_number, line in enumerate(lines, start=1):
        digest, separator, relative_text = line.partition("  ")
        if (
            len(digest) != 64
            or not separator
            or not relative_text
        ):
            raise ValueError(
                f"{checksum_path}: invalid line {line_number}"
            )
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"{checksum_path}: unsafe path {relative}"
            )
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing snapshot file {path}")
        actual = sha256_file(path)
        if actual != digest:
            raise ValueError(
                f"{path}: digest {actual} != {digest}"
            )
        declared.add(relative)

    actual_files = {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual_files != declared:
        raise ValueError(
            "snapshot file set does not match SHA256SUMS"
        )

    manifest = load_json(root / "manifest.json")
    evidence_stage = manifest.get("evidence_stage", "preliminary")
    if (
        evidence_stage not in {"preliminary", "confirmatory"}
        or manifest.get("evidence_type")
        != "observed_no_retuning_locked_audit_"
        + evidence_stage
    ):
        raise ValueError("snapshot evidence stage/type is invalid")
    summary = require_dict(
        manifest.get("structural_summary"),
        f"{root}/manifest.json: structural_summary",
    )
    workloads = manifest.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("snapshot contains no workloads")
    if (
        not manifest.get("evidence_id")
        or summary.get("locked_audit_passes") != len(workloads)
        or summary.get("locked_audit_fails") != 0
        or summary.get("retuned_runs") != 0
        or summary.get("total_fresh_key_runs")
        != sum(
            int(row.get("key_repeats_completed", -1))
            for row in workloads
        )
    ):
        raise ValueError("snapshot structural summary is invalid")
    if any(
        row.get("outcome") != "LOCKED_AUDIT_PASS"
        or row.get("decision_flips") != 0
        or row.get("error_violations") != 0
        for row in workloads
    ):
        raise ValueError("snapshot contains a failed audit workload")
    scope_policy = require_dict(
        manifest.get("scope_policy", {}),
        "snapshot scope_policy",
    )
    expected_model_ids = set(
        scope_policy.get("expected_model_ids", [])
    )
    if expected_model_ids and {
        row.get("model_id") for row in workloads
    } != expected_model_ids:
        raise ValueError("snapshot model scope is inconsistent")
    budget_limit = scope_policy.get(
        "require_max_budget_usage_below"
    )
    if budget_limit is not None and (
        not isinstance(budget_limit, (int, float))
        or not math.isfinite(float(budget_limit))
        or float(budget_limit) <= 0
        or any(
            not isinstance(
                row.get("max_error_budget_usage"),
                (int, float),
            )
            or not math.isfinite(
                float(row["max_error_budget_usage"])
            )
            or float(row["max_error_budget_usage"])
            >= float(budget_limit)
            for row in workloads
        )
    ):
        raise ValueError(
            "snapshot normalized error-budget policy is invalid"
        )
    require_source_replay = scope_policy.get(
        "require_source_replay",
        False,
    )
    if not isinstance(require_source_replay, bool):
        raise ValueError(
            "snapshot source-replay policy must be boolean"
        )
    require_self_contained_inputs = scope_policy.get(
        "require_self_contained_inputs",
        False,
    )
    if not isinstance(require_self_contained_inputs, bool):
        raise ValueError(
            "snapshot self-contained-input policy must be boolean"
        )
    if evidence_stage == "confirmatory" and (
        require_source_replay is not True
        or require_self_contained_inputs is not True
        or manifest.get("execution", {}).get("checkpoint") is not False
    ):
        raise ValueError(
            "confirmatory snapshot lacks complete self-contained "
            "source replay"
        )
    if require_self_contained_inputs:
        for row_value in workloads:
            row = require_dict(
                row_value,
                "snapshot self-contained-input workload",
            )
            verify_self_contained_input(root, row)
    if require_source_replay:
        for row_value in workloads:
            row = require_dict(
                row_value,
                "snapshot source-replay workload",
            )
            if (
                row.get("source_replay_verified") is not True
                or row.get("source_feature_space") != "model_input"
                or row.get("preprocessing_method")
                != "identity_model_input_v1"
                or row.get("audit_source_replay_verified") is not True
                or row.get("audit_source_feature_space")
                != "model_input"
                or row.get("audit_preprocessing_method")
                != "identity_model_input_v1"
            ):
                raise ValueError(
                    "snapshot contains an invalid source replay"
                )
            source_snapshot = root / str(
                row.get("source_data_snapshot", "")
            )
            prepared_snapshot = root / str(
                row.get("prepared_validation_snapshot", "")
            )
            selection_snapshot = root / str(
                row.get("selection_snapshot", "")
            )
            audit_source_snapshot = root / str(
                row.get("audit_source_snapshot", "")
            )
            prepared_audit_snapshot = root / str(
                row.get("prepared_audit_snapshot", "")
            )
            audit_result_snapshot = root / str(
                row.get("audit_result_snapshot", "")
            )
            if (
                not source_snapshot.is_file()
                or not prepared_snapshot.is_file()
                or not selection_snapshot.is_file()
                or not audit_source_snapshot.is_file()
                or not prepared_audit_snapshot.is_file()
                or not audit_result_snapshot.is_file()
                or "sha256:" + sha256_file(source_snapshot)
                != row.get("source_data_sha256")
                or "sha256:" + sha256_file(prepared_snapshot)
                != row.get("prepared_validation_sha256")
                or "sha256:" + sha256_file(audit_source_snapshot)
                != row.get("audit_source_sha256")
                or "sha256:" + sha256_file(prepared_audit_snapshot)
                != row.get("prepared_audit_sha256")
            ):
                raise ValueError(
                    "snapshot source/prepared materialization changed"
                )
            selection = load_json(selection_snapshot)
            contract = require_dict(
                require_dict(
                    selection.get("plan"),
                    f"{selection_snapshot}: plan",
                ).get("contract"),
                f"{selection_snapshot}: contract",
            )
            materialization = require_dict(
                contract.get("input_materialization"),
                f"{selection_snapshot}: input materialization",
            )
            if (
                require_dict(
                    contract.get("source_data"),
                    f"{selection_snapshot}: source data",
                ).get("sha256")
                != row["source_data_sha256"]
                or require_dict(
                    contract.get("model_artifact"),
                    f"{selection_snapshot}: model artifact",
                ).get("sha256")
                != row["model_artifact_sha256"]
                or require_dict(
                    contract.get("validation_data"),
                    f"{selection_snapshot}: validation data",
                ).get("sha256")
                != row["prepared_validation_sha256"]
                or materialization.get("source_replay_verified")
                is not True
                or materialization.get("source_feature_space")
                != "model_input"
                or materialization.get("preprocessing_method")
                != "identity_model_input_v1"
            ):
                raise ValueError(
                    "snapshot selection/source replay binding changed"
                )
            audit_result = load_json(audit_result_snapshot)
            audit_contract = require_dict(
                audit_result.get("audit_contract"),
                f"{audit_result_snapshot}: audit contract",
            )
            audit_materialization = require_dict(
                audit_contract.get("input_materialization"),
                f"{audit_result_snapshot}: input materialization",
            )
            if (
                require_dict(
                    audit_contract.get("source_data"),
                    f"{audit_result_snapshot}: source data",
                ).get("sha256")
                != row["audit_source_sha256"]
                or require_dict(
                    audit_contract.get("model_artifact"),
                    f"{audit_result_snapshot}: model artifact",
                ).get("sha256")
                != row["model_artifact_sha256"]
                or require_dict(
                    audit_contract.get("validation_data"),
                    f"{audit_result_snapshot}: validation data",
                ).get("sha256")
                != row["prepared_audit_sha256"]
                or audit_materialization.get(
                    "source_replay_verified"
                )
                is not True
                or audit_materialization.get(
                    "source_feature_space"
                )
                != "model_input"
                or audit_materialization.get(
                    "preprocessing_method"
                )
                != "identity_model_input_v1"
            ):
                raise ValueError(
                    "snapshot audit/source replay binding changed"
                )
    extras = manifest.get("extra_artifacts", [])
    if not isinstance(extras, list):
        raise ValueError("snapshot extra_artifacts must be a list")
    for item in extras:
        record = require_dict(item, "snapshot extra artifact")
        path = root / str(record["snapshot"])
        if (
            not path.is_file()
            or path.stat().st_size != record["size_bytes"]
            or "sha256:" + sha256_file(path)
            != record["sha256"]
        ):
            raise ValueError(
                f"snapshot extra artifact changed: {path}"
            )
    if scope_policy.get("source_protocol_required"):
        protocol_items = [
            require_dict(item, "snapshot source protocol")
            for item in extras
            if require_dict(
                item,
                "snapshot extra artifact",
            ).get("name") == "source_protocol"
        ]
        if len(protocol_items) != 1:
            raise ValueError("snapshot source protocol is missing")
        protocol_path = root / str(
            protocol_items[0]["snapshot"]
        )
        protocol = load_json(protocol_path)
        if (
            protocol.get("status") != "COMPLETE"
            or protocol.get("source", {}).get("commit")
            != manifest["source_code"]["git_commit"]
        ):
            raise ValueError(
                "snapshot source protocol/commit binding changed"
            )

    print(
        "direct_locked_audit_evidence=VERIFIED "
        f"files={len(declared)} workloads={len(workloads)}"
    )


def main() -> int:
    args = parse_args()
    if args.verify:
        verify(args.output_root)
    else:
        freeze(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
