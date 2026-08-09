#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT

python3 - <<'PY'
import csv
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
print("mode=DEMONSTRATION_ONLY encrypted_execution=0")

with (root / "docs/evidence/final_realistic_baseline_closure_v9/tables/table_03_eva_scale_and_locked_audit.csv").open(encoding="utf-8", newline="") as handle:
    eva = {(row["scale_bits"], row["role"]): row for row in csv.DictReader(handle)}
s30_validation = eva[("30", "configuration_validation")]
s30_audit = eva[("30", "locked_audit")]
s20_validation = eva[("20", "configuration_validation")]
print(f"example=SAFE arm=EVA_S30 validation_flips={s30_validation['decision_flips']} audit_flips={s30_audit['decision_flips']}")
print(f"example=REJECTED arm=EVA_S20 validation_flips={s20_validation['decision_flips']} scope=validation")

controls = json.loads((root / "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json").read_text())
print(f"example=NO_SAFE controls={controls['counts']['budget_no_safe']}/{controls['counts']['budget_workloads']} scope=declared_one_candidate_budget")
print("result=PASS note=frozen_evidence_read_only")
PY
