#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1

scripts/verify_frozen_evidence.sh
python3 scripts/verify_tracked_predecessors.py
python3 scripts/verify_manuscript_numbers.py
python3 scripts/verify_claim_sentence_traceability.py
python3 docs/evidence/final_manuscript_audit_v1/verify_final_manuscript_audit_v1.py "$@"
scripts/reproduce_quick_demo.sh
