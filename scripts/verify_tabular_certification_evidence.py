#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"

    if not checksum_path.is_file():
        raise SystemExit(
            f"missing checksum file: {checksum_path}"
        )

    for line_number, line in enumerate(
        checksum_path.read_text().splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            expected_hash, relative_text = line.split(
                "  ",
                1,
            )
        except ValueError as error:
            raise SystemExit(
                f"invalid SHA256SUMS line {line_number}: "
                f"{line!r}"
            ) from error

        path = root / relative_text

        if not path.is_file():
            raise SystemExit(
                f"checksummed file is missing: {path}"
            )

        actual_hash = sha256_file(path)

        if actual_hash != expected_hash:
            raise SystemExit(
                f"checksum mismatch: {path}\n"
                f"actual={actual_hash}\n"
                f"expected={expected_hash}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "evidence_dir",
        nargs="?",
        default=(
            "docs/evidence/"
            "tabular_certification_observed_v1"
        ),
    )

    args = parser.parse_args()
    root = Path(args.evidence_dir)

    verify_checksums(root)

    manifest_path = root / "manifest.json"

    if not manifest_path.is_file():
        raise SystemExit(
            f"missing manifest: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text()
    )

    if manifest["schema_version"] != 1:
        raise SystemExit(
            "unsupported evidence schema version"
        )

    if manifest["evidence_type"] != (
        "observed_validation_snapshot"
    ):
        raise SystemExit(
            "unexpected evidence type"
        )

    if len(manifest["scoped_inputs"]) != 20:
        raise SystemExit(
            "expected exactly 20 scoped input files"
        )

    source_status = root / "source_run_status.csv"
    status_rows = read_csv(source_status)

    latest_by_tag = {}

    for row in status_rows:
        latest_by_tag[row["tag"]] = row

    raw_rows = len(status_rows)
    latest_rows = len(latest_by_tag)
    duplicate_tags = raw_rows - latest_rows

    recorded_source = manifest["source_status"]

    for key, actual in [
        ("raw_rows", raw_rows),
        ("latest_rows", latest_rows),
        ("duplicate_tags", duplicate_tags),
    ]:
        expected = recorded_source[key]

        if actual != expected:
            raise SystemExit(
                f"{key}: actual={actual}, "
                f"expected={expected}"
            )

    output_root = root / "outputs"

    certificates = read_csv(
        output_root / "certificates.csv"
    )
    workloads = read_csv(
        output_root / "workload_summary.csv"
    )
    selected = read_csv(
        output_root / "selected_configurations.csv"
    )
    coverage = read_csv(
        output_root / "validation_coverage.csv"
    )

    summary = {
        "certificate_rows": len(certificates),
        "workload_rows": len(workloads),
        "selection_rows": len(selected),
        "coverage_rows": len(coverage),

        "certificate_statuses": dict(sorted(
            Counter(
                row["status"]
                for row in certificates
            ).items()
        )),

        "certificate_assurances": dict(sorted(
            Counter(
                row["assurance"]
                for row in certificates
            ).items()
        )),

        "workload_outcomes": dict(sorted(
            Counter(
                row["outcome"]
                for row in workloads
            ).items()
        )),

        "selected_workloads": sum(
            row["candidate_id"] != ""
            for row in selected
        ),

        "selected_v_cert_flips": sum(
            int(row["decision_flips_v_cert"])
            for row in selected
            if row["candidate_id"]
        ),

        "selected_v_cert_violations": sum(
            int(row["error_violations_v_cert"])
            for row in selected
            if row["candidate_id"]
        ),

        "total_samples": sum(
            int(row["sample_count"])
            for row in coverage
        ),

        "total_v_cert": sum(
            int(row["v_cert"])
            for row in coverage
        ),

        "total_v_amb": sum(
            int(row["v_amb"])
            for row in coverage
        ),

        "latency_only_non_safe_workloads": sum(
            row["latency_only_status"] != "SAFE"
            for row in workloads
        ),
    }

    if summary != manifest["structural_summary"]:
        raise SystemExit(
            "structural summary does not match manifest"
        )

    canonical = json.dumps(
        summary,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    structural_hash = hashlib.sha256(
        canonical
    ).hexdigest()

    if structural_hash != (
        manifest["structural_summary_sha256"]
    ):
        raise SystemExit(
            "structural summary hash mismatch"
        )

    selected_certificates = [
        row
        for row in certificates
        if row["selected"] == "true"
    ]

    if len(selected_certificates) != 10:
        raise SystemExit(
            "expected 10 selected certificates"
        )

    for row in selected_certificates:
        if row["status"] != "SAFE":
            raise SystemExit(
                "selected certificate is not SAFE: "
                f"{row['workload_id']}/"
                f"{row['candidate_id']}"
            )
        if int(row["decision_flips_v_cert"]) != 0:
            raise SystemExit(
                "selected certificate has V_cert flips"
            )
        if int(
            row["error_violations_v_cert"]
        ) != 0:
            raise SystemExit(
                "selected certificate has V_cert violations"
            )

    print(f"evidence_dir={root}")
    print(f"source_commit={manifest['source_code']['git_commit']}")
    print(f"certificate_rows={len(certificates)}")
    print(f"selected_workloads={summary['selected_workloads']}")
    print(f"total_samples={summary['total_samples']}")
    print(f"total_v_cert={summary['total_v_cert']}")
    print(f"total_v_amb={summary['total_v_amb']}")
    print(
        "structural_summary_sha256="
        f"{structural_hash}"
    )
    print("evidence_verification=PASS")


if __name__ == "__main__":
    main()
