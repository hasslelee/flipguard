#!/usr/bin/env python3
"""Fail-closed verification for the immutable V6 start protocol."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/external_end_to_end_clean_v6"


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def main() -> int:
    protocol = load("protocol_manifest.json")
    environment = load("environment_start.json")
    queue = load("execution_queue.json")
    states = load("state_vocabulary.json")
    assert protocol["schema_version"] == "flipguard_external_end_to_end_clean_v6_protocol_v1"
    assert protocol["canonical_predecessor_commit"] == "5592b5d2c415eb08c040e7e2b04dd9b6346eb6b8"
    assert protocol["policy_retuning"] == 0
    assert protocol["new_flipguard_datasets_or_models"] == 0
    start = dt.datetime.fromisoformat(protocol["autonomous_start_timestamp"])
    pause = dt.datetime.fromisoformat(protocol["hard_pause_timestamp"])
    assert pause - start == dt.timedelta(hours=24)
    assert environment["working_tree_clean"] is True
    assert environment["root_disk"]["free_bytes"] >= 180 * 1024**3
    assert environment["root_disk"]["inode_free"] / environment["root_disk"]["inode_total"] > 0.2
    assert environment["systemd_user_manager"]["exit_code"] == 0
    assert len(queue["providers"]) >= 17
    assert "LEVEL_6_DECISION_BEARING_LOCKED_AUDIT" in states["evidence_levels"]
    assert states["headline_minimum_level"] == 3
    assert states["gate_minimum_level"] == 5
    print(
        "external_end_to_end_clean_v6_protocol=PASS "
        f"providers={len(queue['providers'])} hard_pause={protocol['hard_pause_timestamp']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
