#!/usr/bin/env python3
"""Freeze the valid HEIR OpenFHE capture while failing closed on Lattigo output."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "external/v7/builds/heir-output-capture-v1"
STATUS = ROOT / "external/v7/status/heir/0005-output-capture-e2e-v1"
OUTPUT = ROOT / "external/v7/outputs/heir/dot-product-8f-output-capture-v1"
SUPPLEMENTARY = ROOT / "external/v7/status/supplementary_jobs.jsonl"
OPENFHE_PATTERN = re.compile(
    r"FLIPGUARD_V7_OPENFHE_ACTUAL=([0-9.eE+-]+) EXPECTED=([0-9.eE+-]+)"
)
LATTIGO_PATTERN = re.compile(
    r"FLIPGUARD_V7_LATTIGO_ACTUAL=([0-9.eE+-]+) EXPECTED=([0-9.eE+-]+)"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def find_one(pattern: str) -> Path:
    matches = sorted(BUILD.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"expected one HEIR log for {pattern}, found {len(matches)}")
    return matches[0]


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-unit", default="flipguard-external-v7-heir-output-capture.service")
    args = parser.parse_args()
    active_result = subprocess.run(
        ["systemctl", "--user", "is-active", args.service_unit],
        text=True,
        capture_output=True,
        check=False,
    )
    active = active_result.stdout.strip()
    if active not in {"failed", "inactive"}:
        raise RuntimeError(f"HEIR capture service is not terminal: {active}")
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite HEIR capture: {OUTPUT}")
    stage = json.loads((STATUS / "run_manifest.json").read_text(encoding="utf-8"))
    if stage["state"] != "PASS" or stage["return_code"] != 0:
        raise ValueError("HEIR encrypted output-capture stage did not pass")

    openfhe = find_one(
        "**/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/"
        "dot_product_8f_test/test.log"
    )
    lattigo = find_one(
        "**/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/"
        "dotproduct8f_test/test.log"
    )
    openfhe_text = openfhe.read_text(encoding="utf-8", errors="replace")
    lattigo_text = lattigo.read_text(encoding="utf-8", errors="replace")
    openfhe_matches = OPENFHE_PATTERN.findall(openfhe_text)
    lattigo_matches = LATTIGO_PATTERN.findall(lattigo_text)
    if len(openfhe_matches) != 1 or lattigo_matches or "PASS" not in lattigo_text:
        raise ValueError("unexpected HEIR partial-output marker state")
    actual, expected = map(float, openfhe_matches[0])

    OUTPUT.mkdir(parents=True)
    (OUTPUT / "raw_logs").mkdir()
    shutil.copy2(openfhe, OUTPUT / "raw_logs/openfhe_test.log")
    shutil.copy2(lattigo, OUTPUT / "raw_logs/lattigo_test.log")
    shutil.copy2(STATUS / "run_manifest.json", OUTPUT / "execution_stage_manifest.json")
    with (OUTPUT / "decrypted_outputs.csv").open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "runtime", "input_id", "expected_output", "decrypted_output",
            "absolute_error", "decision_rule", "decision_state",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "runtime": "OpenFHE",
                "input_id": "official_dot_product_8f_input_v1",
                "expected_output": expected,
                "decrypted_output": actual,
                "absolute_error": abs(actual - expected),
                "decision_rule": "NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD",
                "decision_state": "NOT_EVALUATED",
            }
        )
    with (OUTPUT / "runtime_output_status.csv").open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "runtime", "encrypted_execution", "official_assertion", "raw_output_available",
            "evidence_level", "reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {
                    "runtime": "OpenFHE",
                    "encrypted_execution": True,
                    "official_assertion": "PASS_EXPECT_NEAR_1E-3",
                    "raw_output_available": True,
                    "evidence_level": 3,
                    "reason": "output marker persisted",
                },
                {
                    "runtime": "Lattigo",
                    "encrypted_execution": True,
                    "official_assertion": "PASS_ABS_ERROR_LE_1E-4",
                    "raw_output_available": False,
                    "evidence_level": 2,
                    "reason": "testing.T.Logf suppressed for successful non-verbose Go test",
                },
            ]
        )
    manifest = {
        "schema_version": "flipguard_external_v7_heir_partial_output_capture_v1",
        "provider": "HEIR",
        "source_commit": "cb7a7a30bb4d995b50e33bb5cd82ff7434db3656",
        "patch_semantic_change": False,
        "workload": "official_dot_product_8f",
        "runtimes": ["OpenFHE", "Lattigo"],
        "raw_decrypted_output_available": True,
        "raw_decrypted_output_runtimes": ["OpenFHE"],
        "raw_decrypted_output_unavailable_runtimes": ["Lattigo"],
        "maximum_evidence_level": 3,
        "decision_rule": "NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD",
        "gate_state": "NOT_EVALUATED",
        "encrypted_rerun_performed_by_normalization": False,
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in OUTPUT.rglob("*") if path.is_file())
    (OUTPUT / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  {path.relative_to(OUTPUT).as_posix()}\n"
            for path in files
        ),
        encoding="ascii",
    )
    append_jsonl(
        SUPPLEMENTARY,
        {
            "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "provider": "heir",
            "provider_attempt": 3,
            "state": "PARTIAL_RAW_OUTPUT_CAPTURE_NORMALIZED",
            "encrypted_execution": True,
            "semantic_change": False,
            "raw_output_runtimes": ["OpenFHE"],
            "output_unavailable_runtimes": ["Lattigo"],
        },
    )
    print(json.dumps({"state": "PASS", "output": OUTPUT.relative_to(ROOT).as_posix()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
