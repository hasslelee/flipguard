#!/usr/bin/env python3
"""Run and verify the disjoint locked-audit finite-domain NO_SAFE control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = Path(
    "results/thesis_grade_protocol/tabular_splits_v1"
)
RETROSPECTIVE_ROOT = Path(
    "results/thesis_grade_protocol/"
    "finite_domain_no_safe_control_v1/full"
)
DATASETS = (
    "banknote",
    "digits_binary",
    "iris_binary",
    "mnist_pool16",
    "wdbc",
)
MODELS = (
    "linear_poly3",
    "mlp_square_linear_score",
)
DOMAIN = (
    (
        "short_chain_3",
        "baseline_non_rescale",
        "naive",
    ),
    (
        "short_chain_3",
        "rescale_aware",
        "rescale",
    ),
)
MARGIN_FLOOR = 0.001
SAFETY_FACTOR = 0.5
EXPECTED_PARAMETER_FAILURES = (
    "cannot rescale ciphertext at level",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Re-execute the two-candidate finite NO_SAFE domain on "
            "disjoint locked-audit partitions with fresh keys."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("smoke", "confirm"),
        default="smoke",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def bind(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "path": (
            str(resolved.relative_to(REPO_ROOT))
            if resolved.is_relative_to(REPO_ROOT)
            else str(resolved)
        ),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_path(resolved),
    }


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        return list(reader)


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise ValueError(f"{path}: cannot write an empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_finite(raw: str, label: str) -> float:
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{label}: expected finite number")
    return value


def parse_bool(raw: str, label: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError(f"{label}: invalid boolean {raw!r}")


def runtime_source_files() -> tuple[Path, ...]:
    files = [
        path.relative_to(REPO_ROOT)
        for root in (
            REPO_ROOT / "cmd/flipguard",
            REPO_ROOT / "internal",
        )
        for path in root.rglob("*.go")
        if not path.name.endswith("_test.go")
    ]
    files.extend(
        (
            Path(
                "scripts/"
                "run_finite_domain_no_safe_locked_audit.py"
            ),
            Path("go.mod"),
            Path("go.sum"),
        )
    )
    return tuple(sorted(set(files), key=str))


def source_state() -> tuple[str, str, bool, dict[str, Any]]:
    files = runtime_source_files()
    missing = [
        str(path)
        for path in files
        if not (REPO_ROOT / path).is_file()
    ]
    if missing:
        raise ValueError(f"runtime source files are missing: {missing}")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *[str(path) for path in files],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    bindings = {
        str(path): {
            "bytes": (REPO_ROOT / path).stat().st_size,
            "sha256": sha256_path(REPO_ROOT / path),
        }
        for path in files
    }
    digest = hashlib.sha256()
    for path, item in sorted(bindings.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return (
        commit,
        "sha256:" + digest.hexdigest(),
        bool(status),
        bindings,
    )


def workload_scope(mode: str) -> tuple[tuple[int, str, str], ...]:
    if mode == "smoke":
        return ((0, "banknote", "linear_poly3"),)
    return tuple(
        (seed, dataset, model)
        for seed in range(5)
        for dataset in DATASETS
        for model in MODELS
    )


def candidate_id(profile: str, path: str) -> str:
    return f"{profile}__{path}"


def artifact_paths(
    seed: int,
    dataset: str,
    model: str,
) -> tuple[Path, Path, Path, dict[str, Any]]:
    root = (
        SPLIT_ROOT
        / f"split_seed_{seed}"
        / dataset
        / model
    )
    manifest_path = root / "split_manifest.json"
    manifest = read_json(REPO_ROOT / manifest_path)
    model_path = Path(manifest["model_artifact"])
    audit_path = Path(manifest["locked_audit_test"]["path"])
    return model_path, audit_path, manifest_path, manifest


def validate_workload_inputs(
    seed: int,
    dataset: str,
    model: str,
) -> dict[str, Any]:
    (
        model_path,
        audit_path,
        manifest_path,
        manifest,
    ) = artifact_paths(seed, dataset, model)
    if (
        manifest.get("schema_version") != 1
        or manifest.get("split_seed") != seed
        or manifest.get("dataset_id") != dataset
        or manifest.get("model_id") != model
    ):
        raise ValueError(
            f"{manifest_path}: workload identity mismatch"
        )

    model_full = REPO_ROOT / model_path
    audit_full = REPO_ROOT / audit_path
    manifest_full = REPO_ROOT / manifest_path
    configuration = manifest["configuration_validation"]
    audit = manifest["locked_audit_test"]
    if (
        sha256_path(model_full)
        != manifest["model_artifact_digest"]
        or sha256_path(audit_full) != audit["csv_digest"]
    ):
        raise ValueError(
            f"{manifest_path}: artifact digest mismatch"
        )

    validation_ids = configuration["row_ids"]
    audit_ids = audit["row_ids"]
    if (
        len(validation_ids) != len(set(validation_ids))
        or len(audit_ids) != len(set(audit_ids))
        or set(validation_ids).intersection(audit_ids)
    ):
        raise ValueError(
            f"{manifest_path}: split partitions are not disjoint"
        )
    rows = read_csv(audit_full)
    actual_ids = [row["row_id"] for row in rows]
    if actual_ids != audit_ids:
        raise ValueError(
            f"{audit_path}: row IDs differ from split manifest"
        )

    model_payload = read_json(model_full)
    if (
        model_payload.get("dataset_id") != dataset
        or model_payload.get("model_id") != model
    ):
        raise ValueError(f"{model_path}: model identity mismatch")
    threshold = parse_finite(
        str(
            model_payload["polynomial_score"][
                "decision_threshold"
            ]
        ),
        f"{model_path} threshold",
    )
    score_by_id: dict[str, float] = {}
    for row in rows:
        row_id = row["row_id"]
        score_by_id[row_id] = parse_finite(
            row["polynomial_score"],
            f"{audit_path} row {row_id} polynomial_score",
        )

    margins = {
        row_id: abs(score - threshold)
        for row_id, score in score_by_id.items()
    }
    return {
        "model_path": model_path,
        "audit_path": audit_path,
        "manifest_path": manifest_path,
        "model": bind(model_full),
        "audit": bind(audit_full),
        "manifest": bind(manifest_full),
        "row_ids": audit_ids,
        "score_by_id": score_by_id,
        "threshold": threshold,
        "margins": margins,
        "v_cert": sum(
            margin > MARGIN_FLOOR
            for margin in margins.values()
        ),
        "v_amb": sum(
            margin <= MARGIN_FLOOR
            for margin in margins.values()
        ),
    }


def build_binary(binary: Path) -> None:
    binary.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["GOCACHE"] = (
        "/tmp/flipguard-finite-audit-gocache"
    )
    subprocess.run(
        [
            "go",
            "build",
            "-o",
            str(binary),
            "./cmd/flipguard",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def classify_failure(log_text: str) -> str:
    lowered = log_text.lower()
    if any(
        marker in lowered
        for marker in EXPECTED_PARAMETER_FAILURES
    ):
        return "EXPECTED_PARAMETER_FAILURE"
    return "UNEXPECTED_EXECUTION_FAILURE"


def validate_success_raw(
    summary_path: Path,
    records_path: Path,
    inputs: dict[str, Any],
    dataset: str,
    model: str,
    evaluation_mode: str,
) -> None:
    summaries = read_csv(summary_path)
    if len(summaries) != 1:
        raise ValueError(
            f"{summary_path}: expected exactly one summary row"
        )
    summary = summaries[0]
    if (
        summary["dataset_id"] != dataset
        or summary["model_id"] != model
        or summary["evaluation_mode"] != evaluation_mode
    ):
        raise ValueError(f"{summary_path}: identity mismatch")

    records = read_csv(records_path)
    row_ids = [row["row_id"] for row in records]
    if row_ids != inputs["row_ids"]:
        raise ValueError(f"{records_path}: audit row IDs changed")
    for row in records:
        row_id = row["row_id"]
        plain_score = parse_finite(
            row["plain_y"],
            f"{records_path} row {row_id} plain_y",
        )
        if not math.isclose(
            plain_score,
            inputs["score_by_id"][row_id],
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"{records_path}: row {row_id} plaintext score changed"
            )
        parse_finite(
            row["ckks_y"],
            f"{records_path} row {row_id} ckks_y",
        )
        parse_bool(
            row["plain_decision"],
            f"{records_path} row {row_id} plain_decision",
        )
        parse_bool(
            row["ckks_decision"],
            f"{records_path} row {row_id} ckks_decision",
        )


def attempt_identity(
    mode: str,
    seed: int,
    dataset: str,
    model: str,
    profile: str,
    path: str,
    key_run: int,
) -> tuple[str, str]:
    tag = (
        f"finiteauditv1_{mode}_seed{seed}_{dataset}_{model}_"
        f"{profile}_{path}_key{key_run}"
    )
    relative = (
        f"seed{seed}_{dataset}_{model}_{profile}_{path}_"
        f"key{key_run}"
    )
    return tag, relative


def expected_command(
    binary: Path,
    profile: str,
    evaluation_mode: str,
    tag: str,
) -> list[str]:
    return [
        str(binary),
        "-experiment",
        "ckks_tabular_inference",
        "-ckks-profile-name",
        profile,
        "-ckks-evaluation-mode",
        evaluation_mode,
        "-ckks-output-tag",
        tag,
    ]


def validate_attempt(
    binding_path: Path,
    source_digest: str,
    binary: Path,
    materialized_root: Path,
    inputs: dict[str, Any],
    mode: str,
    seed: int,
    dataset: str,
    model: str,
    profile: str,
    path: str,
    evaluation_mode: str,
    key_run: int,
) -> dict[str, Any]:
    binding = read_json(binding_path)
    tag, _ = attempt_identity(
        mode,
        seed,
        dataset,
        model,
        profile,
        path,
        key_run,
    )
    command = expected_command(
        binary,
        profile,
        evaluation_mode,
        tag,
    )
    if (
        binding.get("schema_version") != 1
        or binding.get("source_digest") != source_digest
        or binding.get("tag") != tag
        or binding.get("command") != command
        or binding.get("environment")
        != {
            "TABULAR_DATASET_ID": dataset,
            "TABULAR_MODEL_ID": model,
            "TABULAR_DATA_ROOT": str(materialized_root),
        }
    ):
        raise ValueError(f"{binding_path}: attempt identity changed")
    for name in ("model", "audit", "manifest"):
        expected = inputs[name]
        actual = binding["inputs"][name]
        if (
            actual["path"] != expected["path"]
            or actual["bytes"] != expected["bytes"]
            or actual["sha256"] != expected["sha256"]
        ):
            raise ValueError(
                f"{binding_path}: {name} binding changed"
            )

    log_item = binding["log"]
    log_path = resolve_path(log_item["path"])
    if (
        log_path.stat().st_size != log_item["bytes"]
        or sha256_path(log_path) != log_item["sha256"]
    ):
        raise ValueError(f"{binding_path}: log changed")
    log_text = log_path.read_text(encoding="utf-8")

    status = binding["status"]
    if status == "SUCCESS":
        if binding["exit_code"] != 0:
            raise ValueError(
                f"{binding_path}: successful exit code changed"
            )
        summary_item = binding["raw"]["summary"]
        records_item = binding["raw"]["records"]
        summary_path = resolve_path(summary_item["path"])
        records_path = resolve_path(records_item["path"])
        for raw_path, item in (
            (summary_path, summary_item),
            (records_path, records_item),
        ):
            if (
                raw_path.stat().st_size != item["bytes"]
                or sha256_path(raw_path) != item["sha256"]
            ):
                raise ValueError(
                    f"{binding_path}: raw output changed"
                )
        validate_success_raw(
            summary_path,
            records_path,
            inputs,
            dataset,
            model,
            evaluation_mode,
        )
    elif status == "FAILED":
        failure_class = classify_failure(log_text)
        if (
            binding["exit_code"] == 0
            or binding.get("failure_class") != failure_class
        ):
            raise ValueError(
                f"{binding_path}: failure classification changed"
            )
    else:
        raise ValueError(
            f"{binding_path}: unsupported status {status!r}"
        )
    return binding


def execute_attempt(
    output_root: Path,
    binary: Path,
    source_commit: str,
    source_digest: str,
    materialized_root: Path,
    inputs: dict[str, Any],
    mode: str,
    seed: int,
    dataset: str,
    model: str,
    profile: str,
    path: str,
    evaluation_mode: str,
    key_run: int,
) -> dict[str, Any]:
    tag, relative = attempt_identity(
        mode,
        seed,
        dataset,
        model,
        profile,
        path,
        key_run,
    )
    command = expected_command(
        binary,
        profile,
        evaluation_mode,
        tag,
    )
    log_path = output_root / "logs" / f"{relative}.log"
    binding_path = (
        output_root / "bindings" / f"{relative}.json"
    )
    raw_root = output_root / "raw" / relative
    global_raw = (
        REPO_ROOT / "results/ckks_tabular_inference" / tag
    )
    if global_raw.exists():
        shutil.rmtree(global_raw)
    if raw_root.exists():
        shutil.rmtree(raw_root)

    environment = os.environ.copy()
    environment.update(
        {
            "TABULAR_DATASET_ID": dataset,
            "TABULAR_MODEL_ID": model,
            "TABULAR_DATA_ROOT": str(materialized_root),
        }
    )
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "$ " + " ".join(command) + "\n"
        + completed.stdout
        + completed.stderr,
        encoding="utf-8",
    )

    status = "FAILED"
    raw: dict[str, Any] = {}
    failure_class = classify_failure(
        completed.stdout + completed.stderr
    )
    if completed.returncode == 0:
        source_summary = global_raw / "summary.csv"
        source_records = global_raw / "records.csv"
        if (
            not source_summary.is_file()
            or not source_records.is_file()
        ):
            raise RuntimeError(
                f"{tag}: successful command omitted raw artifacts"
            )
        raw_root.mkdir(parents=True, exist_ok=True)
        summary_path = raw_root / "summary.csv"
        records_path = raw_root / "records.csv"
        shutil.copy2(source_summary, summary_path)
        shutil.copy2(source_records, records_path)
        validate_success_raw(
            summary_path,
            records_path,
            inputs,
            dataset,
            model,
            evaluation_mode,
        )
        status = "SUCCESS"
        failure_class = ""
        raw = {
            "summary": bind(summary_path),
            "records": bind(records_path),
        }

    binding = {
        "schema_version": 1,
        "source_commit": source_commit,
        "source_digest": source_digest,
        "tag": tag,
        "command": command,
        "environment": {
            "TABULAR_DATASET_ID": dataset,
            "TABULAR_MODEL_ID": model,
            "TABULAR_DATA_ROOT": str(materialized_root),
        },
        "inputs": {
            name: inputs[name]
            for name in ("model", "audit", "manifest")
        },
        "status": status,
        "exit_code": completed.returncode,
        "failure_class": failure_class,
        "log": bind(log_path),
        "raw": raw,
    }
    write_json(binding_path, binding)
    return validate_attempt(
        binding_path,
        source_digest,
        binary,
        materialized_root,
        inputs,
        mode,
        seed,
        dataset,
        model,
        profile,
        path,
        evaluation_mode,
        key_run,
    )


def materialize_workload(
    output_root: Path,
    seed: int,
    dataset: str,
    model: str,
    inputs: dict[str, Any],
) -> Path:
    root = (
        output_root
        / "materialized"
        / f"split_seed_{seed}"
    )
    workload = root / dataset / model
    workload.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        REPO_ROOT / inputs["model_path"],
        workload / "model.json",
    )
    shutil.copy2(
        REPO_ROOT / inputs["audit_path"],
        workload / "test.csv",
    )
    return root


def load_retrospective_statuses() -> dict[
    tuple[int, str, str, str],
    str,
]:
    path = (
        REPO_ROOT
        / RETROSPECTIVE_ROOT
        / "restricted_candidate_certificates.csv"
    )
    rows = read_csv(path)
    result: dict[tuple[int, str, str, str], str] = {}
    for row in rows:
        if float(row["alpha"]) != SAFETY_FACTOR:
            continue
        key = (
            int(row["split_seed"]),
            row["dataset_id"],
            row["model_id"],
            row["candidate_id"],
        )
        if key in result:
            raise ValueError(
                f"{path}: duplicate retrospective candidate {key}"
            )
        result[key] = row["certificate_status"]
    if len(result) != 100 or any(
        status == "SAFE" for status in result.values()
    ):
        raise ValueError(
            f"{path}: retrospective finite domain changed"
        )
    return result


def aggregate_candidate(
    bindings: list[dict[str, Any]],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    expected_failures = sum(
        item["status"] == "FAILED"
        and item["failure_class"]
        == "EXPECTED_PARAMETER_FAILURE"
        for item in bindings
    )
    unexpected_failures = sum(
        item["status"] == "FAILED"
        and item["failure_class"]
        == "UNEXPECTED_EXECUTION_FAILURE"
        for item in bindings
    )
    successes = sum(
        item["status"] == "SUCCESS" for item in bindings
    )

    decision_flips = 0
    error_violations = 0
    max_error = 0.0
    max_budget_usage = 0.0
    total_ms: list[float] = []
    if expected_failures + unexpected_failures == 0:
        for binding in bindings:
            records = read_csv(
                resolve_path(binding["raw"]["records"]["path"])
            )
            summary = read_csv(
                resolve_path(binding["raw"]["summary"]["path"])
            )[0]
            total_ms.append(
                parse_finite(
                    summary["mean_total_eval_ms"],
                    "mean_total_eval_ms",
                )
            )
            for row in records:
                row_id = row["row_id"]
                margin = inputs["margins"][row_id]
                if margin <= MARGIN_FLOOR:
                    continue
                plain_score = inputs["score_by_id"][row_id]
                ckks_score = parse_finite(
                    row["ckks_y"],
                    f"row {row_id} ckks_y",
                )
                observed_error = abs(ckks_score - plain_score)
                protected_budget = SAFETY_FACTOR * margin
                max_error = max(max_error, observed_error)
                max_budget_usage = max(
                    max_budget_usage,
                    observed_error / protected_budget,
                )
                if (plain_score >= inputs["threshold"]) != (
                    ckks_score >= inputs["threshold"]
                ):
                    decision_flips += 1
                if observed_error >= protected_budget:
                    error_violations += 1

    if expected_failures + unexpected_failures:
        status = "FAILED"
    elif inputs["v_cert"] == 0:
        status = "AMBIGUOUS"
    elif decision_flips or error_violations:
        status = "REJECTED"
    else:
        status = "SAFE"

    return {
        "audit_status": status,
        "successful_key_runs": successes,
        "expected_parameter_failures": expected_failures,
        "unexpected_execution_failures": unexpected_failures,
        "decision_flips_v_cert": decision_flips,
        "error_violations_v_cert": error_violations,
        "max_error_v_cert": (
            format(max_error, ".12g")
            if successes
            and expected_failures + unexpected_failures == 0
            else ""
        ),
        "max_budget_usage_v_cert": (
            format(max_budget_usage, ".12g")
            if successes
            and expected_failures + unexpected_failures == 0
            else ""
        ),
        "mean_total_ms_across_keys": (
            format(sum(total_ms) / len(total_ms), ".12g")
            if total_ms
            else ""
        ),
    }


def collect_and_derive(
    output_root: Path,
    mode: str,
    source_digest: str,
    binary: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    scope = workload_scope(mode)
    key_repeats = 1 if mode == "smoke" else 3
    retrospective = load_retrospective_statuses()
    attempt_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    workload_rows: list[dict[str, Any]] = []
    input_bindings: dict[str, Any] = {}
    transition_counts: dict[str, int] = {}

    for seed, dataset, model in scope:
        inputs = validate_workload_inputs(seed, dataset, model)
        materialized_root = (
            output_root
            / "materialized"
            / f"split_seed_{seed}"
        )
        workload_key = f"seed{seed}/{dataset}/{model}"
        input_bindings[workload_key] = {
            name: inputs[name]
            for name in ("model", "audit", "manifest")
        }
        candidate_statuses = []
        for profile, path, evaluation_mode in DOMAIN:
            candidate = candidate_id(profile, path)
            bindings = []
            for key_run in range(1, key_repeats + 1):
                tag, relative = attempt_identity(
                    mode,
                    seed,
                    dataset,
                    model,
                    profile,
                    path,
                    key_run,
                )
                binding_path = (
                    output_root
                    / "bindings"
                    / f"{relative}.json"
                )
                binding = validate_attempt(
                    binding_path,
                    source_digest,
                    binary,
                    materialized_root,
                    inputs,
                    mode,
                    seed,
                    dataset,
                    model,
                    profile,
                    path,
                    evaluation_mode,
                    key_run,
                )
                bindings.append(binding)
                binding_item = bind(binding_path)
                attempt_rows.append(
                    {
                        "split_seed": seed,
                        "dataset_id": dataset,
                        "model_id": model,
                        "candidate_id": candidate,
                        "profile": profile,
                        "path": path,
                        "evaluation_mode": evaluation_mode,
                        "key_run": key_run,
                        "tag": tag,
                        "status": binding["status"],
                        "exit_code": binding["exit_code"],
                        "failure_class": binding[
                            "failure_class"
                        ],
                        "binding_path": binding_item["path"],
                        "binding_sha256": binding_item["sha256"],
                    }
                )

            aggregate = aggregate_candidate(bindings, inputs)
            validation_status = retrospective[
                (seed, dataset, model, candidate)
            ]
            transition = (
                f"{validation_status}->{aggregate['audit_status']}"
            )
            transition_counts[transition] = (
                transition_counts.get(transition, 0) + 1
            )
            row = {
                "split_seed": seed,
                "dataset_id": dataset,
                "model_id": model,
                "candidate_id": candidate,
                "profile": profile,
                "path": path,
                "evaluation_mode": evaluation_mode,
                "validation_status": validation_status,
                "audit_status": aggregate["audit_status"],
                "status_transition": transition,
                "key_repeats": key_repeats,
                "v_cert": inputs["v_cert"],
                "v_amb": inputs["v_amb"],
                **{
                    key: value
                    for key, value in aggregate.items()
                    if key != "audit_status"
                },
            }
            candidate_rows.append(row)
            candidate_statuses.append(
                (candidate, aggregate["audit_status"])
            )

        safe = [
            candidate
            for candidate, status in candidate_statuses
            if status == "SAFE"
        ]
        outcome = "SELECTED" if safe else "NO_SAFE"
        workload_rows.append(
            {
                "split_seed": seed,
                "dataset_id": dataset,
                "model_id": model,
                "domain_id": "short_chain_3_two_path_v1",
                "candidate_count": len(candidate_statuses),
                "safe_count": len(safe),
                "rejected_count": sum(
                    status == "REJECTED"
                    for _, status in candidate_statuses
                ),
                "failed_count": sum(
                    status == "FAILED"
                    for _, status in candidate_statuses
                ),
                "ambiguous_count": sum(
                    status == "AMBIGUOUS"
                    for _, status in candidate_statuses
                ),
                "audit_outcome": outcome,
                "safe_candidates": ",".join(safe),
            }
        )

    status_counts: dict[str, int] = {}
    for row in candidate_rows:
        status = str(row["audit_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    metrics = {
        "workloads": len(workload_rows),
        "candidate_rows": len(candidate_rows),
        "attempts": len(attempt_rows),
        "key_repeats": key_repeats,
        "candidate_statuses": status_counts,
        "status_transitions": transition_counts,
        "restricted_no_safe": sum(
            row["audit_outcome"] == "NO_SAFE"
            for row in workload_rows
        ),
        "restricted_selected": sum(
            row["audit_outcome"] == "SELECTED"
            for row in workload_rows
        ),
        "unexpected_execution_failures": sum(
            int(row["unexpected_execution_failures"])
            for row in candidate_rows
        ),
    }
    return (
        attempt_rows,
        candidate_rows,
        workload_rows,
        metrics,
        input_bindings,
    )


def expected_summary(
    output_root: Path,
    mode: str,
    source_commit: str,
    source_digest: str,
    source_dirty: bool,
    source_files: dict[str, Any],
    binary: Path,
    metrics: dict[str, Any],
    input_bindings: dict[str, Any],
) -> dict[str, Any]:
    expected_workloads = 1 if mode == "smoke" else 50
    control_pass = (
        metrics["workloads"] == expected_workloads
        and metrics["candidate_rows"] == expected_workloads * 2
        and metrics["attempts"]
        == expected_workloads * 2 * metrics["key_repeats"]
        and metrics["candidate_statuses"].get("SAFE", 0) == 0
        and metrics["restricted_no_safe"] == expected_workloads
        and metrics["unexpected_execution_failures"] == 0
    )
    outputs = {}
    for name in (
        "attempt_status.csv",
        "candidate_results.csv",
        "workload_results.csv",
    ):
        outputs[name.removesuffix(".csv")] = bind(
            output_root / "summary" / name
        )
    retrospective_summary = (
        REPO_ROOT / RETROSPECTIVE_ROOT / "summary.json"
    )
    retrospective_candidates = (
        REPO_ROOT
        / RETROSPECTIVE_ROOT
        / "restricted_candidate_certificates.csv"
    )
    return {
        "schema_version": 1,
        "execution_status": "COMPLETE",
        "control_result": "PASS" if control_pass else "FAIL",
        "evidence_status": (
            "SMOKE_ONLY"
            if mode == "smoke"
            else "CONFIRMATORY_DISJOINT_FINITE_DOMAIN"
        ),
        "mode": mode.upper(),
        "claim_boundary": (
            "NO_SAFE means that neither candidate in the declared "
            "short_chain_3 two-path finite domain was SAFE on the "
            "disjoint locked-audit partitions. It is not a global CKKS "
            "infeasibility claim."
        ),
        "protocol": {
            "partition": "locked_audit_test",
            "split_seeds": (
                [0] if mode == "smoke" else [0, 1, 2, 3, 4]
            ),
            "datasets": (
                ["banknote"] if mode == "smoke" else list(DATASETS)
            ),
            "models": (
                ["linear_poly3"]
                if mode == "smoke"
                else list(MODELS)
            ),
            "domain_id": "short_chain_3_two_path_v1",
            "candidate_ids": [
                candidate_id(profile, path)
                for profile, path, _ in DOMAIN
            ],
            "key_repeats": metrics["key_repeats"],
            "margin_floor": MARGIN_FLOOR,
            "safety_factor": SAFETY_FACTOR,
            "fresh_key_mechanism": (
                "one independent cmd/flipguard process per key_run"
            ),
            "selection_or_repair_performed": False,
        },
        "falsification": {
            "expected_workloads": expected_workloads,
            "expected_candidates_per_workload": 2,
            "require_zero_safe_candidates": True,
            "require_no_safe_for_every_workload": True,
            "forbid_unexpected_execution_failures": True,
            "validation_status_not_used_for_audit_admission": True,
        },
        "metrics": metrics,
        "source": {
            "commit": source_commit,
            "dirty": source_dirty,
            "digest": source_digest,
            "files": source_files,
        },
        "binary": bind(binary),
        "retrospective_inputs": {
            "summary": bind(retrospective_summary),
            "candidate_certificates": bind(
                retrospective_candidates
            ),
        },
        "audit_inputs": input_bindings,
        "outputs": outputs,
    }


def verify(output_root: Path) -> dict[str, Any]:
    summary_path = output_root / "summary/summary.json"
    summary = read_json(summary_path)
    if (
        summary.get("schema_version") != 1
        or summary.get("execution_status") != "COMPLETE"
        or summary.get("mode") not in {"SMOKE", "CONFIRM"}
    ):
        raise ValueError(f"{summary_path}: unsupported summary")
    mode = summary["mode"].lower()
    (
        source_commit,
        source_digest,
        source_dirty,
        source_files,
    ) = source_state()
    recorded_source = summary["source"]
    if (
        recorded_source["commit"] != source_commit
        or recorded_source["digest"] != source_digest
        or recorded_source["files"] != source_files
        or recorded_source["dirty"] != source_dirty
    ):
        raise ValueError(
            f"{summary_path}: runtime source state changed"
        )
    binary = resolve_path(summary["binary"]["path"])
    if (
        binary.stat().st_size != summary["binary"]["bytes"]
        or sha256_path(binary) != summary["binary"]["sha256"]
    ):
        raise ValueError(f"{binary}: binary changed")

    with tempfile.TemporaryDirectory(
        prefix="flipguard-finite-audit-verify-",
        dir="/tmp",
    ) as temporary:
        temporary_root = Path(temporary)
        (
            attempt_rows,
            candidate_rows,
            workload_rows,
            metrics,
            input_bindings,
        ) = collect_and_derive(
            output_root,
            mode,
            source_digest,
            binary,
        )
        expected_rows = (
            ("attempt_status.csv", attempt_rows),
            ("candidate_results.csv", candidate_rows),
            ("workload_results.csv", workload_rows),
        )
        for name, rows in expected_rows:
            regenerated = temporary_root / name
            write_csv(regenerated, rows)
            existing = output_root / "summary" / name
            if existing.read_bytes() != regenerated.read_bytes():
                raise ValueError(
                    f"{existing}: deterministic aggregation changed"
                )
        expected = expected_summary(
            output_root,
            mode,
            source_commit,
            source_digest,
            source_dirty,
            source_files,
            binary,
            metrics,
            input_bindings,
        )
        if summary != expected:
            raise ValueError(
                f"{summary_path}: summary does not reproduce"
            )
    print(
        "finite_domain_locked_audit=VERIFIED "
        f"mode={mode.upper()} "
        f"control={summary['control_result']} "
        f"workloads={summary['metrics']['workloads']} "
        f"candidates={summary['metrics']['candidate_rows']} "
        f"attempts={summary['metrics']['attempts']}"
    )
    return summary


def run(args: argparse.Namespace, output_root: Path) -> int:
    if output_root.exists() and args.force:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    (
        source_commit,
        source_digest,
        source_dirty,
        source_files,
    ) = source_state()
    if args.mode == "confirm" and source_dirty:
        raise ValueError(
            "confirm mode requires clean committed runtime source"
        )

    binary = output_root / "bin/flipguard"
    build_binary(binary)
    key_repeats = 1 if args.mode == "smoke" else 3
    for seed, dataset, model in workload_scope(args.mode):
        inputs = validate_workload_inputs(seed, dataset, model)
        materialized_root = materialize_workload(
            output_root,
            seed,
            dataset,
            model,
            inputs,
        )
        for profile, path, evaluation_mode in DOMAIN:
            for key_run in range(1, key_repeats + 1):
                _, relative = attempt_identity(
                    args.mode,
                    seed,
                    dataset,
                    model,
                    profile,
                    path,
                    key_run,
                )
                binding_path = (
                    output_root
                    / "bindings"
                    / f"{relative}.json"
                )
                action = "run"
                if binding_path.is_file() and not args.force:
                    validate_attempt(
                        binding_path,
                        source_digest,
                        binary,
                        materialized_root,
                        inputs,
                        args.mode,
                        seed,
                        dataset,
                        model,
                        profile,
                        path,
                        evaluation_mode,
                        key_run,
                    )
                    action = "skip"
                else:
                    execute_attempt(
                        output_root,
                        binary,
                        source_commit,
                        source_digest,
                        materialized_root,
                        inputs,
                        args.mode,
                        seed,
                        dataset,
                        model,
                        profile,
                        path,
                        evaluation_mode,
                        key_run,
                    )
                if not args.quiet:
                    print(
                        f"{action} seed{seed}/{dataset}/{model}/"
                        f"{profile}/{path}/key{key_run}"
                    )

    (
        attempt_rows,
        candidate_rows,
        workload_rows,
        metrics,
        input_bindings,
    ) = collect_and_derive(
        output_root,
        args.mode,
        source_digest,
        binary,
    )
    summary_root = output_root / "summary"
    write_csv(
        summary_root / "attempt_status.csv",
        attempt_rows,
    )
    write_csv(
        summary_root / "candidate_results.csv",
        candidate_rows,
    )
    write_csv(
        summary_root / "workload_results.csv",
        workload_rows,
    )
    summary = expected_summary(
        output_root,
        args.mode,
        source_commit,
        source_digest,
        source_dirty,
        source_files,
        binary,
        metrics,
        input_bindings,
    )
    write_json(summary_root / "summary.json", summary)
    verify(output_root)
    return 0


def main() -> int:
    args = parse_args()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output_root)
        return 0
    return run(args, output_root)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"finite-domain locked audit: ERROR: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1)
