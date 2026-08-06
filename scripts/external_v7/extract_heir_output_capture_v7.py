#!/usr/bin/env python3
"""Extract deterministic HEIR decrypted scalar outputs from instrumented test logs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re


PATTERNS = {
    "OpenFHE": re.compile(r"FLIPGUARD_V7_OPENFHE_ACTUAL=([0-9.eE+-]+) EXPECTED=([0-9.eE+-]+)"),
    "Lattigo": re.compile(r"FLIPGUARD_V7_LATTIGO_ACTUAL=([0-9.eE+-]+) EXPECTED=([0-9.eE+-]+)"),
}


def extract(runtime: str, path: Path) -> dict[str, object]:
    matches = PATTERNS[runtime].findall(path.read_text(encoding="utf-8", errors="replace"))
    if len(matches) != 1:
        raise ValueError(f"expected one {runtime} output marker, found {len(matches)}")
    actual, expected = map(float, matches[0])
    return {
        "runtime": runtime,
        "input_id": "official_dot_product_8f_input_v1",
        "expected_output": expected,
        "decrypted_output": actual,
        "absolute_error": abs(actual - expected),
        "decision_rule": "NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD",
        "decision_state": "NOT_EVALUATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openfhe-log", required=True, type=Path)
    parser.add_argument("--lattigo-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [extract("OpenFHE", args.openfhe_log), extract("Lattigo", args.lattigo_log)]
    with args.output.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

