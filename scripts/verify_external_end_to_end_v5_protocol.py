#!/usr/bin/env python3
"""Verify the frozen V5 execution protocol without running a provider."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/evidence/external_end_to_end_24h_v5"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protocol = json.loads((PACK / "protocol_manifest.json").read_text())
    predecessor = json.loads((PACK / "predecessor_v3.json").read_text())
    environment = json.loads((PACK / "environment_manifest.json").read_text())
    queue = json.loads((PACK / "execution_queue.json").read_text())
    states = json.loads((PACK / "state_vocabulary.json").read_text())
    assert protocol["schema_version"] == "flipguard_external_end_to_end_24h_v5_protocol"
    assert protocol["predecessor_commit"] == "5592b5d2c415eb08c040e7e2b04dd9b6346eb6b8"
    assert sha(ROOT / predecessor["manifest"]) == predecessor["manifest_sha256"] == protocol["predecessor_manifest_sha256"]
    assert protocol["frozen_evidence_modification_allowed"] is False
    assert protocol["policy_retuning_allowed"] is False
    assert protocol["measurement_parallelism"] == 1
    assert protocol["missing_value_imputation_allowed"] is False
    assert protocol["normal_pause_before_hard_pause"] is False
    assert environment["allocated_logical_cpus"] == 2
    assert environment["background_ckks_processes"] == 0
    assert environment["gpu"] == "NOT_VISIBLE_VMWARE_SVGA_ONLY"
    assert len(queue["entries"]) == 17
    assert [row["order"] for row in queue["entries"]] == list(range(1, 18))
    assert len(states["levels"]) == 6
    assert "NOT_EVALUATED" in states["missing"]
    print("external_end_to_end_v5_protocol=PASS queue=17 measurement_parallelism=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
