#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1

(cd docs/evidence/focused_external_comparison_v8 && sha256sum -c SHA256SUMS)
(cd docs/evidence/final_realistic_baseline_closure_v9 && sha256sum -c SHA256SUMS)
(cd docs/evidence/paper_claim_admission_v1 && sha256sum -c SHA256SUMS)
(cd docs/evidence/journal_multiclass_claim_admission_v2 && sha256sum -c SHA256SUMS)
python3 docs/evidence/focused_external_comparison_v8/verify_focused_external_comparison_v8.py
python3 docs/evidence/final_realistic_baseline_closure_v9/verify_final_realistic_baseline_closure_v9.py
python3 docs/evidence/paper_claim_admission_v1/verify_paper_claim_admission.py
python3 docs/evidence/journal_multiclass_claim_admission_v2/verify_journal_multiclass_claim_admission_v2.py

echo "frozen_evidence=VERIFIED note=V3_and_V10_tracked_only_checks_run_by_verify_final_research_state"
