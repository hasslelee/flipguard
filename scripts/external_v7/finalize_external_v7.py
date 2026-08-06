#!/usr/bin/env python3
"""Create a fail-closed V7 checkpoint without inventing missing results."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_code_v7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    files = [path for path in sorted(EVIDENCE.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"]
    (EVIDENCE / "SHA256SUMS").write_text(
        "".join(f"{sha(path)}  {path.relative_to(EVIDENCE).as_posix()}\n" for path in files),
        encoding="utf-8",
    )
    state = {
        "schema_version": "flipguard_external_end_to_end_code_v7_checkpoint_v1",
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "paper_claim_allowed": False,
        "claim_state": "BLOCKED_PENDING_FINAL_VERIFICATION",
        "raw_status_root": "external/v7/status",
    }
    (EVIDENCE / "manifest.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
