#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly EVIDENCE="docs/evidence/external_end_to_end_code_v7"
readonly STATUS="external/v7/status"
readonly LOG_DIR="external/v7/logs/finalization"
readonly BRANCH="experiments/external-e2e-code-v7"
cd "$ROOT"
mkdir -p "$LOG_DIR"

exec > >(tee "$LOG_DIR/final_qa_commit.log") 2>&1

python3 - <<'PY'
import datetime as dt
from pathlib import Path
pause = dt.datetime.fromisoformat(Path("external/v7/status/hard_pause_timestamp.txt").read_text().strip())
if dt.datetime.now().astimezone() < pause:
    raise SystemExit(f"final QA/commit blocked until {pause.isoformat()}")
PY

test "$(git branch --show-current)" = "$BRANCH"
test "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")"

python3 "$EVIDENCE/verify_external_end_to_end_code_v7.py"
python3 scripts/build_security_v2_static_artifacts.py \
  --output-root docs/evidence/security_v2_static_attestation_formal_v2 --verify
python3 docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py

export PYTHONPYCACHEPREFIX="/tmp/flipguard-v7-final-pycache"
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
git ls-files -z '*.py' | xargs -0 -r python3 -m py_compile
while IFS= read -r script; do
  bash -n "$script"
done < <(git ls-files '*.sh')
scripts/external_v7/run_clean_source_go_gate_v7.sh
git diff --check
(cd "$EVIDENCE" && sha256sum -c SHA256SUMS)

python3 - <<'PY'
import subprocess
allowed = "docs/evidence/external_end_to_end_code_v7/"
unexpected = []
for line in subprocess.check_output(["git", "status", "--porcelain=v1"], text=True).splitlines():
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    if not path.startswith(allowed):
        unexpected.append(line)
if unexpected:
    raise SystemExit("unexpected working-tree changes before final V7 commit:\n" + "\n".join(unexpected))
PY

git add "$EVIDENCE"
git diff --cached --check
if git diff --cached --quiet; then
  echo "V7 evidence already committed"
else
  git commit -m "Freeze external V7 24-hour checkpoint"
fi
git push origin "$BRANCH"
test -z "$(git status --short)"
git rev-parse HEAD > "$STATUS/final_evidence_commit.txt"
git rev-parse "origin/$BRANCH" > "$STATUS/final_origin_commit.txt"
printf '%s\n' "PASS" > "$STATUS/final_qa_commit_state.txt"
