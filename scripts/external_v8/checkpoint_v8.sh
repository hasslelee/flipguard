#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 docs/evidence/focused_external_comparison_v8/verify_focused_external_comparison_v8.py
python3 -m py_compile scripts/external_v8/*.py docs/evidence/focused_external_comparison_v8/verify_focused_external_comparison_v8.py
bash -n scripts/external_v8/*.sh
# The live tree contains 24 GB of Bazel-owned Go SDK negative-test fixtures
# under external/v7. Run the literal full-module gate from a clean archive so
# those provider caches cannot masquerade as FlipGuard packages.
scripts/external_v7/run_clean_source_go_gate_v7.sh
git diff --check

git add docs/evidence/focused_external_comparison_v8 results/thesis_grade_protocol/focused_external_comparison_v8
if ! git diff --cached --quiet; then
  git commit -m "Freeze focused external comparison V8 evidence"
fi
git push origin experiments/focused-external-closure-v8
test -z "$(git status --short)"
