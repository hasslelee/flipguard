#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


PROFILES = [
    "default",
    "scale42",
    "scale40",
    "scale38",
    "deep_chain_8_scale45",
    "deep_chain_9_scale45",
    "short_chain_6_scale42",
    "short_chain_6_scale40",
    "short_chain_6_scale38",
    "short_chain_5",
    "short_chain_3",
]

PATHS = [
    "baseline_non_rescale",
    "rescale_aware",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

    return "sha256:" + digest


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(
                f"{path}: missing CSV header"
            )

        return list(reader)


def read_single_csv(path: Path) -> Dict[str, str]:
    rows = read_csv(path)

    if len(rows) != 1:
        raise ValueError(
            f"{path}: expected one row, found {len(rows)}"
        )

    return rows[0]


def write_csv(
    path: Path,
    rows: Iterable[Dict[str, object]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
    }:
        return False

    raise ValueError(
        f"invalid boolean value {value!r}"
    )


def parse_finite_float(
    value: str,
    label: str,
) -> float:
    parsed = float(value)

    if not math.isfinite(parsed):
        raise ValueError(
            f"{label} must be finite"
        )

    return parsed


def load_threshold(model_path: Path) -> float:
    payload = json.loads(
        model_path.read_text(encoding="utf-8")
    )

    threshold = payload.get(
        "polynomial_score",
        {},
    ).get(
        "decision_threshold"
    )

    if threshold is None:
        raise ValueError(
            f"{model_path}: missing decision threshold"
        )

    threshold = float(threshold)

    if not math.isfinite(threshold):
        raise ValueError(
            f"{model_path}: non-finite decision threshold"
        )

    return threshold


def build_split_index(
    split_summary_path: Path,
    margin_floor: float,
):
    payload = json.loads(
        split_summary_path.read_text(
            encoding="utf-8"
        )
    )

    records = payload["records"]

    index = {}
    coverage_rows = []

    for record in records:
        seed = int(record["seed"])
        dataset_id = record["dataset_id"]
        model_id = record["model_id"]

        key = (
            seed,
            dataset_id,
            model_id,
        )

        if key in index:
            raise ValueError(
                f"duplicate split identity {key}"
            )

        manifest_path = Path(
            record["manifest"]
        )

        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        validation_info = manifest[
            "configuration_validation"
        ]

        validation_path = Path(
            validation_info["path"]
        )

        model_path = Path(
            manifest["model_artifact"]
        )

        threshold = load_threshold(
            model_path
        )

        validation_rows = read_csv(
            validation_path
        )

        expected_row_ids = list(
            validation_info["row_ids"]
        )

        actual_row_ids = [
            row["row_id"]
            for row in validation_rows
        ]

        if actual_row_ids != expected_row_ids:
            raise ValueError(
                f"{key}: validation row order does not "
                "match the split manifest"
            )

        score_by_row_id = {}
        margins = []

        for row in validation_rows:
            row_id = row["row_id"]

            score = parse_finite_float(
                row["polynomial_score"],
                f"{key} row {row_id} polynomial score",
            )

            score_by_row_id[row_id] = score
            margins.append(
                abs(score - threshold)
            )

        v_amb = sum(
            margin <= margin_floor
            for margin in margins
        )

        v_cert = len(margins) - v_amb

        coverage_rows.append(
            {
                "split_seed": seed,
                "dataset_id": dataset_id,
                "model_id": model_id,
                "sample_count": len(margins),
                "margin_floor": margin_floor,
                "v_cert": v_cert,
                "v_amb": v_amb,
                "coverage_rate":
                    v_cert / len(margins),
                "threshold": threshold,
                "validation_csv":
                    str(validation_path),
                "validation_csv_digest":
                    sha256_file(validation_path),
                "model_artifact":
                    str(model_path),
                "model_artifact_digest":
                    sha256_file(model_path),
                "split_manifest":
                    str(manifest_path),
            }
        )

        index[key] = {
            "threshold": threshold,
            "row_ids": expected_row_ids,
            "score_by_row_id":
                score_by_row_id,
            "v_cert": v_cert,
            "v_amb": v_amb,
            "sample_count": len(margins),
        }

    return payload, index, coverage_rows


def validate_run_matrix(
    status_rows: Sequence[Dict[str, str]],
    split_payload: Dict[str, object],
    allow_incomplete: bool,
) -> None:
    seen = set()

    for row in status_rows:
        key = (
            int(row["split_seed"]),
            row["dataset_id"],
            row["model_id"],
            row["profile"],
            row["path"],
        )

        if key in seen:
            raise ValueError(
                f"duplicate run-status identity {key}"
            )

        seen.add(key)

    if allow_incomplete:
        return

    expected = set()

    for record in split_payload["records"]:
        base = (
            int(record["seed"]),
            record["dataset_id"],
            record["model_id"],
        )

        for profile in PROFILES:
            for path in PATHS:
                expected.add(
                    base
                    + (
                        profile,
                        path,
                    )
                )

    missing = sorted(
        expected.difference(seen)
    )

    unexpected = sorted(
        seen.difference(expected)
    )

    if missing:
        raise ValueError(
            "run matrix is incomplete; missing "
            f"{len(missing)} candidates; first={missing[0]}"
        )

    if unexpected:
        raise ValueError(
            "run matrix contains unexpected candidates; "
            f"first={unexpected[0]}"
        )


def build_candidate_rows(
    status_rows: Sequence[Dict[str, str]],
    split_index,
    alphas: Sequence[float],
    margin_floor: float,
):
    output = []

    for status_row in status_rows:
        seed = int(
            status_row["split_seed"]
        )

        dataset_id = status_row["dataset_id"]
        model_id = status_row["model_id"]
        profile = status_row["profile"]
        path = status_row["path"]

        split_key = (
            seed,
            dataset_id,
            model_id,
        )

        if split_key not in split_index:
            raise ValueError(
                f"run references unknown split {split_key}"
            )

        split = split_index[split_key]

        base = {
            "split_seed": seed,
            "dataset_id": dataset_id,
            "model_id": model_id,
            "candidate_id":
                status_row["candidate_id"],
            "profile": profile,
            "path": path,
            "evaluation_mode":
                status_row["evaluation_mode"],
            "run_tag": status_row["tag"],
            "run_status":
                status_row["status"],
            "exit_code":
                int(status_row["exit_code"]),
            "sample_count":
                split["sample_count"],
            "v_cert":
                split["v_cert"],
            "v_amb":
                split["v_amb"],
            "coverage_rate":
                split["v_cert"]
                / split["sample_count"],
            "margin_floor": margin_floor,
        }

        if status_row["status"] != "ok":
            for alpha in alphas:
                output.append(
                    {
                        **base,
                        "alpha": alpha,
                        "certificate_status":
                            "FAILED",
                        "decision_flips_v_cert": "",
                        "error_violations_v_cert": "",
                        "max_y_error_v_cert": "",
                        "mean_total_ms": "",
                        "median_total_ms": "",
                        "p95_total_ms": "",
                        "mean_eval_only_ms": "",
                    }
                )

            continue

        summary_path = Path(
            status_row["summary_path"]
        )

        records_path = Path(
            status_row["records_path"]
        )

        if not summary_path.is_file():
            raise ValueError(
                f"missing successful summary {summary_path}"
            )

        if not records_path.is_file():
            raise ValueError(
                f"missing successful records {records_path}"
            )

        summary = read_single_csv(
            summary_path
        )

        records = read_csv(
            records_path
        )

        actual_row_ids = [
            row["row_id"]
            for row in records
        ]

        if actual_row_ids != split["row_ids"]:
            raise ValueError(
                f"{split_key} {profile}/{path}: "
                "record row IDs do not match the locked "
                "configuration-validation split"
            )

        evaluated = []

        for record in records:
            row_id = record["row_id"]

            source_plain_y = split[
                "score_by_row_id"
            ][row_id]

            observed_plain_y = (
                parse_finite_float(
                    record["plain_y"],
                    f"{split_key} row {row_id} plain_y",
                )
            )

            if abs(
                source_plain_y
                - observed_plain_y
            ) > 1e-9:
                raise ValueError(
                    f"{split_key} row {row_id}: "
                    "runtime plain_y differs from split artifact"
                )

            margin = abs(
                source_plain_y
                - split["threshold"]
            )

            evaluated.append(
                {
                    "margin": margin,
                    "y_error":
                        parse_finite_float(
                            record["y_error"],
                            f"{split_key} row {row_id} y_error",
                        ),
                    "decision_flip":
                        parse_bool(
                            record["decision_flip"]
                        ),
                }
            )

        for alpha in alphas:
            v_cert_records = [
                record
                for record in evaluated
                if record["margin"] > margin_floor
            ]

            flips = sum(
                record["decision_flip"]
                for record in v_cert_records
            )

            violations = sum(
                record["y_error"]
                >= alpha * record["margin"]
                for record in v_cert_records
            )

            max_error = max(
                (
                    record["y_error"]
                    for record in v_cert_records
                ),
                default=0.0,
            )

            certificate_status = (
                "SAFE"
                if flips == 0
                and violations == 0
                else "REJECTED"
            )

            output.append(
                {
                    **base,
                    "alpha": alpha,
                    "certificate_status":
                        certificate_status,
                    "decision_flips_v_cert":
                        flips,
                    "error_violations_v_cert":
                        violations,
                    "max_y_error_v_cert":
                        max_error,
                    "mean_total_ms":
                        parse_finite_float(
                            summary[
                                "mean_total_eval_ms"
                            ],
                            "mean_total_eval_ms",
                        ),
                    "median_total_ms":
                        parse_finite_float(
                            summary[
                                "median_total_eval_ms"
                            ],
                            "median_total_eval_ms",
                        ),
                    "p95_total_ms":
                        parse_finite_float(
                            summary[
                                "p95_total_eval_ms"
                            ],
                            "p95_total_eval_ms",
                        ),
                    "mean_eval_only_ms":
                        parse_finite_float(
                            summary[
                                "mean_eval_only_ms"
                            ],
                            "mean_eval_only_ms",
                        ),
                }
            )

    return output


def numeric_latency(row: Dict[str, object]) -> float:
    value = row["mean_total_ms"]

    if value == "":
        return math.inf

    return float(value)


def build_oracle_rows(
    candidate_rows: Sequence[Dict[str, object]],
):
    grouped = defaultdict(list)

    for row in candidate_rows:
        key = (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["alpha"],
        )

        grouped[key].append(row)

    output = []

    for key in sorted(grouped):
        seed, dataset_id, model_id, alpha = key
        rows = grouped[key]

        completed = [
            row
            for row in rows
            if row["certificate_status"]
            != "FAILED"
        ]

        safe = [
            row
            for row in completed
            if row["certificate_status"]
            == "SAFE"
        ]

        rejected = [
            row
            for row in completed
            if row["certificate_status"]
            == "REJECTED"
        ]

        failed = [
            row
            for row in rows
            if row["certificate_status"]
            == "FAILED"
        ]

        latency_only = (
            min(
                completed,
                key=numeric_latency,
            )
            if completed
            else None
        )

        oracle = (
            min(
                safe,
                key=numeric_latency,
            )
            if safe
            else None
        )

        reference = next(
            (
                row
                for row in completed
                if row["candidate_id"]
                == "default__rescale_aware"
            ),
            None,
        )

        reference_ms = (
            numeric_latency(reference)
            if reference is not None
            else math.nan
        )

        oracle_ms = (
            numeric_latency(oracle)
            if oracle is not None
            else math.nan
        )

        speedup = (
            reference_ms / oracle_ms
            if reference is not None
            and oracle is not None
            and oracle_ms > 0
            else ""
        )

        output.append(
            {
                "split_seed": seed,
                "dataset_id": dataset_id,
                "model_id": model_id,
                "alpha": alpha,
                "outcome":
                    "SELECTED"
                    if oracle is not None
                    else "NO_SAFE",
                "candidate_count": len(rows),
                "safe_count": len(safe),
                "rejected_count":
                    len(rejected),
                "failed_count": len(failed),
                "v_cert":
                    rows[0]["v_cert"],
                "v_amb":
                    rows[0]["v_amb"],
                "coverage_rate":
                    rows[0]["coverage_rate"],
                "oracle_candidate":
                    oracle["candidate_id"]
                    if oracle is not None
                    else "",
                "oracle_mean_total_ms":
                    oracle_ms
                    if oracle is not None
                    else "",
                "reference_candidate":
                    reference["candidate_id"]
                    if reference is not None
                    else "",
                "reference_mean_total_ms":
                    reference_ms
                    if reference is not None
                    else "",
                "oracle_speedup_vs_reference":
                    speedup,
                "latency_only_candidate":
                    latency_only["candidate_id"]
                    if latency_only is not None
                    else "",
                "latency_only_status":
                    latency_only[
                        "certificate_status"
                    ]
                    if latency_only is not None
                    else "",
                "latency_only_mean_total_ms":
                    numeric_latency(
                        latency_only
                    )
                    if latency_only is not None
                    else "",
            }
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run-status",
        required=True,
    )

    parser.add_argument(
        "--split-summary",
        required=True,
    )

    parser.add_argument(
        "--output-root",
        required=True,
    )

    parser.add_argument(
        "--margin-floor",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--alphas",
        required=True,
    )

    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
    )

    args = parser.parse_args()

    if (
        not math.isfinite(args.margin_floor)
        or args.margin_floor < 0
    ):
        raise SystemExit(
            "margin floor must be finite and non-negative"
        )

    alphas = [
        float(value)
        for value in args.alphas.split(",")
        if value.strip() != ""
    ]

    if not alphas:
        raise SystemExit(
            "at least one alpha is required"
        )

    if len(alphas) != len(set(alphas)):
        raise SystemExit(
            "alphas must be unique"
        )

    for alpha in alphas:
        if (
            not math.isfinite(alpha)
            or alpha <= 0
            or alpha >= 1
        ):
            raise SystemExit(
                "each alpha must be finite and in (0, 1)"
            )

    run_status_path = Path(
        args.run_status
    )

    split_summary_path = Path(
        args.split_summary
    )

    output_root = Path(
        args.output_root
    )

    status_rows = read_csv(
        run_status_path
    )

    split_payload, split_index, coverage_rows = (
        build_split_index(
            split_summary_path,
            args.margin_floor,
        )
    )

    validate_run_matrix(
        status_rows,
        split_payload,
        args.allow_incomplete,
    )

    candidate_rows = build_candidate_rows(
        status_rows,
        split_index,
        alphas,
        args.margin_floor,
    )

    oracle_rows = build_oracle_rows(
        candidate_rows
    )

    candidate_fields = [
        "split_seed",
        "dataset_id",
        "model_id",
        "candidate_id",
        "profile",
        "path",
        "evaluation_mode",
        "alpha",
        "certificate_status",
        "run_status",
        "exit_code",
        "sample_count",
        "v_cert",
        "v_amb",
        "coverage_rate",
        "margin_floor",
        "decision_flips_v_cert",
        "error_violations_v_cert",
        "max_y_error_v_cert",
        "mean_total_ms",
        "median_total_ms",
        "p95_total_ms",
        "mean_eval_only_ms",
        "run_tag",
    ]

    oracle_fields = [
        "split_seed",
        "dataset_id",
        "model_id",
        "alpha",
        "outcome",
        "candidate_count",
        "safe_count",
        "rejected_count",
        "failed_count",
        "v_cert",
        "v_amb",
        "coverage_rate",
        "oracle_candidate",
        "oracle_mean_total_ms",
        "reference_candidate",
        "reference_mean_total_ms",
        "oracle_speedup_vs_reference",
        "latency_only_candidate",
        "latency_only_status",
        "latency_only_mean_total_ms",
    ]

    coverage_fields = [
        "split_seed",
        "dataset_id",
        "model_id",
        "sample_count",
        "margin_floor",
        "v_cert",
        "v_amb",
        "coverage_rate",
        "threshold",
        "validation_csv",
        "validation_csv_digest",
        "model_artifact",
        "model_artifact_digest",
        "split_manifest",
    ]

    write_csv(
        output_root
        / "candidate_certificates.csv",
        candidate_rows,
        candidate_fields,
    )

    write_csv(
        output_root
        / "oracle_selection.csv",
        oracle_rows,
        oracle_fields,
    )

    write_csv(
        output_root
        / "validation_coverage.csv",
        coverage_rows,
        coverage_fields,
    )

    status_counts = Counter(
        row["certificate_status"]
        for row in candidate_rows
    )

    outcome_counts = Counter(
        row["outcome"]
        for row in oracle_rows
    )

    summary = {
        "schema_version": 1,
        "allow_incomplete":
            args.allow_incomplete,
        "run_status":
            str(run_status_path),
        "run_status_digest":
            sha256_file(run_status_path),
        "split_summary":
            str(split_summary_path),
        "split_summary_digest":
            sha256_file(split_summary_path),
        "margin_floor":
            args.margin_floor,
        "alphas":
            alphas,
        "actual_run_count":
            len(status_rows),
        "expected_full_run_count":
            len(split_payload["records"])
            * len(PROFILES)
            * len(PATHS),
        "candidate_certificate_rows":
            len(candidate_rows),
        "oracle_rows":
            len(oracle_rows),
        "coverage_rows":
            len(coverage_rows),
        "certificate_status_counts":
            dict(sorted(status_counts.items())),
        "oracle_outcome_counts":
            dict(sorted(outcome_counts.items())),
    }

    write_json(
        output_root / "summary.json",
        summary,
    )

    print(
        "actual_run_count="
        + str(len(status_rows))
    )

    print(
        "expected_full_run_count="
        + str(
            summary[
                "expected_full_run_count"
            ]
        )
    )

    print(
        "candidate_certificate_rows="
        + str(len(candidate_rows))
    )

    print(
        "oracle_rows="
        + str(len(oracle_rows))
    )

    print(
        "certificate_status_counts="
        + json.dumps(
            dict(sorted(status_counts.items())),
            sort_keys=True,
        )
    )

    print(
        "oracle_outcome_counts="
        + json.dumps(
            dict(sorted(outcome_counts.items())),
            sort_keys=True,
        )
    )

    print(
        "summary_digest="
        + sha256_file(
            output_root / "summary.json"
        )
    )


if __name__ == "__main__":
    main()
