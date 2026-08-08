#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 docs/evidence/focused_external_comparison_v8/verify_focused_external_comparison_v8.py
python3 scripts/build_security_v2_static_artifacts.py \
  --output-root docs/evidence/security_v2_static_attestation_formal_v2 --verify
export PYTHONPYCACHEPREFIX=/tmp/flipguard-v8-final-pycache
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
git ls-files -z '*.py' | xargs -0 -r python3 -m py_compile
while IFS= read -r script; do
  bash -n "$script"
done < <(git ls-files '*.sh')
# The live tree contains 24 GB of Bazel-owned Go SDK negative-test fixtures
# under external/v7. Run the literal full-module gate from a clean archive so
# those provider caches cannot masquerade as FlipGuard packages.
scripts/external_v7/run_clean_source_go_gate_v7.sh
git diff --check
(cd docs/evidence/focused_external_comparison_v8 && sha256sum -c SHA256SUMS)
readonly SENSITIVE_PATTERN='/home/ckks2|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9]+'
if command -v rg >/dev/null 2>&1; then
  sensitive_matches="$(rg -n "$SENSITIVE_PATTERN" \
    docs/evidence/focused_external_comparison_v8 \
    results/thesis_grade_protocol/focused_external_comparison_v8 || true)"
else
  sensitive_matches="$(grep -RInE --exclude='*.pyc' "$SENSITIVE_PATTERN" \
    docs/evidence/focused_external_comparison_v8 \
    results/thesis_grade_protocol/focused_external_comparison_v8 || true)"
fi
if [[ -n "$sensitive_matches" ]]; then
  printf '%s\n' "$sensitive_matches"
  echo "sensitive/local path scan failed" >&2
  exit 1
fi

git add docs/evidence/focused_external_comparison_v8
# Thesis-grade result packs are ignored by default to prevent accidental bulk
# staging. This final, verifier-bound V8 pack is an intentional exception.
git add -f results/thesis_grade_protocol/focused_external_comparison_v8
if ! git diff --cached --quiet; then
  git commit -m "Freeze focused external comparison V8 evidence"
fi
git push origin experiments/focused-external-closure-v8
test -z "$(git status --short)"
