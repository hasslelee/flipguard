#!/usr/bin/env python3
"""Record an evidence-bound provider terminal state without inventing execution."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    "NO_EXECUTABLE_ARTIFACT", "LICENSE_BLOCKED", "CREDENTIAL_BLOCKED",
    "HARDWARE_BLOCKED_NO_GPU", "DISK_BUDGET_BLOCKED", "CLEAN_BUILD_BLOCKED",
    "OFFICIAL_PIPELINE_ONLY", "ENCRYPTED_END_TO_END", "MULTI_SAMPLE_END_TO_END",
    "DECISION_BEARING_VALIDATION", "DECISION_BEARING_LOCKED_AUDIT",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--state", required=True, choices=sorted(ALLOWED))
    parser.add_argument("--reason", required=True)
    parser.add_argument("--source-url", default="NOT_AVAILABLE")
    parser.add_argument("--source-commit", default="NOT_AVAILABLE")
    parser.add_argument("--license", default="NOT_REPORTED")
    args = parser.parse_args()
    output = ROOT / "external/v7/outputs" / args.provider / "terminal-state-v1"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    manifest = {
        "schema_version": "flipguard_external_v7_provider_terminal_v1",
        "provider": args.provider,
        "terminal_state": args.state,
        "reason": args.reason,
        "source_url": args.source_url,
        "source_commit": args.source_commit,
        "license": args.license,
        "encrypted_execution_count": 0,
        "evidence_level": 0 if args.state == "NO_EXECUTABLE_ARTIFACT" else 1,
        "recorded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "missing_values_are_not_zero": True,
    }
    path = output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  manifest.json\n", encoding="ascii")
    status = ROOT / "external/v7/status" / args.provider
    status.mkdir(parents=True, exist_ok=True)
    (status / "final_state.txt").write_text(args.state + "\n", encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
