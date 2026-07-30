#!/usr/bin/env python3
"""Build or verify the finite-domain all-unsafe NO_SAFE control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CERTIFICATES = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/"
    "full/summary/candidate_certificates.csv"
)
DEFAULT_ORACLE = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/"
    "full/summary/oracle_selection.csv"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/"
    "finite_domain_no_safe_control_v1/full"
)
DOMAIN_CANDIDATES = (
    "short_chain_3__baseline_non_rescale",
    "short_chain_3__rescale_aware",
)
ALPHA = "0.5"
EXPECTED_WORKLOADS = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-certificates",
        type=Path,
        default=DEFAULT_CERTIFICATES,
    )
    parser.add_argument(
        "--oracle-selection",
        type=Path,
        default=DEFAULT_ORACLE,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def workload_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (
        int(row["split_seed"]),
        row["dataset_id"],
        row["model_id"],
    )


def derive(
    certificate_path: Path,
    oracle_path: Path,
) -> tuple[
    list[str],
    list[dict[str, str]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    certificate_fields, all_certificates = read_csv(
        certificate_path
    )
    _, all_oracles = read_csv(oracle_path)

    restricted = [
        row
        for row in all_certificates
        if row["alpha"] == ALPHA
        and row["candidate_id"] in DOMAIN_CANDIDATES
    ]
    restricted.sort(
        key=lambda row: (
            *workload_key(row),
            row["candidate_id"],
        )
    )
    if len(restricted) != EXPECTED_WORKLOADS * len(
        DOMAIN_CANDIDATES
    ):
        raise ValueError(
            f"restricted domain has {len(restricted)} rows, expected "
            f"{EXPECTED_WORKLOADS * len(DOMAIN_CANDIDATES)}"
        )

    full_oracles = {
        workload_key(row): row
        for row in all_oracles
        if row["alpha"] == ALPHA
    }
    if len(full_oracles) != EXPECTED_WORKLOADS:
        raise ValueError(
            f"full oracle has {len(full_oracles)} workloads at alpha "
            f"{ALPHA}, expected {EXPECTED_WORKLOADS}"
        )

    grouped: dict[
        tuple[int, str, str],
        list[dict[str, str]],
    ] = {}
    for row in restricted:
        grouped.setdefault(workload_key(row), []).append(row)
    if len(grouped) != EXPECTED_WORKLOADS:
        raise ValueError(
            f"restricted domain has {len(grouped)} workloads"
        )

    selection_rows: list[dict[str, Any]] = []
    status_counts = {"SAFE": 0, "REJECTED": 0, "FAILED": 0}
    for key, rows in sorted(grouped.items()):
        identities = [row["candidate_id"] for row in rows]
        if identities != sorted(DOMAIN_CANDIDATES):
            raise ValueError(
                f"workload {key} candidate identities changed: "
                f"{identities}"
            )
        for row in rows:
            status = row["certificate_status"]
            if status not in status_counts:
                raise ValueError(
                    f"workload {key} has unknown status {status}"
                )
            status_counts[status] += 1

        safe = sum(
            row["certificate_status"] == "SAFE"
            for row in rows
        )
        rejected = sum(
            row["certificate_status"] == "REJECTED"
            for row in rows
        )
        failed = sum(
            row["certificate_status"] == "FAILED"
            for row in rows
        )
        outcome = "SELECTED" if safe else "NO_SAFE"
        full_oracle = full_oracles.get(key)
        if full_oracle is None:
            raise ValueError(f"workload {key} missing full oracle")
        selection_rows.append(
            {
                "split_seed": key[0],
                "dataset_id": key[1],
                "model_id": key[2],
                "alpha": ALPHA,
                "domain_id": "short_chain_3_two_path_v1",
                "candidate_count": len(rows),
                "safe_count": safe,
                "rejected_count": rejected,
                "failed_count": failed,
                "restricted_outcome": outcome,
                "selected_candidate": "",
                "full_catalog_outcome": full_oracle["outcome"],
                "full_catalog_candidate": full_oracle[
                    "oracle_candidate"
                ],
            }
        )

    no_safe = sum(
        row["restricted_outcome"] == "NO_SAFE"
        for row in selection_rows
    )
    full_selected = sum(
        row["full_catalog_outcome"] == "SELECTED"
        for row in selection_rows
    )
    if (
        status_counts != {
            "SAFE": 0,
            "REJECTED": 75,
            "FAILED": 25,
        }
        or no_safe != EXPECTED_WORKLOADS
        or full_selected != EXPECTED_WORKLOADS
    ):
        raise ValueError(
            "finite-domain falsification counts changed: "
            f"statuses={status_counts} no_safe={no_safe} "
            f"full_selected={full_selected}"
        )

    metrics = {
        "workloads": len(selection_rows),
        "candidate_rows": len(restricted),
        "candidate_statuses": status_counts,
        "restricted_no_safe": no_safe,
        "restricted_selected": len(selection_rows) - no_safe,
        "full_catalog_selected": full_selected,
    }
    return (
        certificate_fields,
        restricted,
        selection_rows,
        metrics,
    )


def expected_summary(
    certificate_path: Path,
    oracle_path: Path,
    output_root: Path,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    certificates_output = (
        output_root / "restricted_candidate_certificates.csv"
    )
    selection_output = (
        output_root / "restricted_oracle_selection.csv"
    )
    return {
        "schema_version": 1,
        "control_result": "PASS",
        "evidence_status": "RETROSPECTIVE_DERIVED_CONTROL",
        "alpha": float(ALPHA),
        "domain": {
            "id": "short_chain_3_two_path_v1",
            "candidate_ids": list(DOMAIN_CANDIDATES),
            "scope": (
                "exactly two lowest-cost built-in profile/path "
                "candidates, not the global CKKS configuration space"
            ),
        },
        "claim_boundary": (
            "All candidates in this declared two-candidate finite domain "
            "are independently REJECTED or FAILED, so NO_SAFE is correct "
            "within the domain. The complete 22-candidate catalog contains "
            "SAFE candidates for the same workloads."
        ),
        "metrics": metrics,
        "falsification": {
            "expected_workloads": 50,
            "expected_candidate_rows": 100,
            "expected_statuses": {
                "SAFE": 0,
                "REJECTED": 75,
                "FAILED": 25,
            },
            "expected_restricted_no_safe": 50,
            "expected_full_catalog_selected": 50,
        },
        "inputs": {
            "candidate_certificates": {
                "path": str(
                    certificate_path.relative_to(REPO_ROOT)
                ),
                "sha256": sha256_path(certificate_path),
            },
            "oracle_selection": {
                "path": str(oracle_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(oracle_path),
            },
        },
        "outputs": {
            "restricted_candidate_certificates": {
                "path": str(
                    certificates_output.relative_to(REPO_ROOT)
                ),
                "sha256": sha256_path(certificates_output),
            },
            "restricted_oracle_selection": {
                "path": str(
                    selection_output.relative_to(REPO_ROOT)
                ),
                "sha256": sha256_path(selection_output),
            },
        },
    }


def verify(
    certificate_path: Path,
    oracle_path: Path,
    output_root: Path,
) -> None:
    summary_path = output_root / "summary.json"
    if not summary_path.is_file():
        raise ValueError(f"missing summary {summary_path}")
    actual = json.loads(summary_path.read_text(encoding="utf-8"))
    _, _, _, metrics = derive(certificate_path, oracle_path)
    expected = expected_summary(
        certificate_path,
        oracle_path,
        output_root,
        metrics,
    )
    if actual != expected:
        raise ValueError(
            "finite-domain NO_SAFE summary does not reproduce"
        )
    print(
        "finite_domain_no_safe=VERIFIED "
        f"workloads={metrics['workloads']} "
        f"candidate_rows={metrics['candidate_rows']}"
    )


def main() -> int:
    args = parse_args()
    certificate_path = (
        REPO_ROOT / args.candidate_certificates
    ).resolve()
    oracle_path = (
        REPO_ROOT / args.oracle_selection
    ).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()

    if args.verify:
        verify(certificate_path, oracle_path, output_root)
        return 0
    if output_root.exists():
        if not args.force:
            raise ValueError(
                f"{output_root} exists; use --force"
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    (
        certificate_fields,
        restricted,
        selection_rows,
        metrics,
    ) = derive(certificate_path, oracle_path)
    write_csv(
        output_root / "restricted_candidate_certificates.csv",
        certificate_fields,
        restricted,
    )
    selection_fields = list(selection_rows[0])
    write_csv(
        output_root / "restricted_oracle_selection.csv",
        selection_fields,
        selection_rows,
    )
    summary = expected_summary(
        certificate_path,
        oracle_path,
        output_root,
        metrics,
    )
    (output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify(certificate_path, oracle_path, output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
