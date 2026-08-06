#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly STATUS="external/v7/status"
readonly OUTPUTS="external/v7/outputs"
readonly PRESERVED="external/v7/failed_intermediates/outputs-root-owned-attempt1"

state="$(python3 - <<'PY'
import json
from pathlib import Path
path = Path("external/v7/status/master_state.json")
print(json.loads(path.read_text(encoding="utf-8"))["state"] if path.exists() else "MISSING")
PY
)"
if [[ "$state" != QUEUE_EXHAUSTED_QA_WAIT ]]; then
  echo "refusing output-root repair outside QUEUE_EXHAUSTED_QA_WAIT: $state" >&2
  exit 3
fi

exec 9>/tmp/flipguard-v7-measurement.lock
if ! flock -n 9; then
  echo "refusing output-root repair while a measured stage holds the lock" >&2
  exit 4
fi

if [[ -w "$OUTPUTS" ]]; then
  printf '%s\n' "OUTPUT_ROOT_ALREADY_WRITABLE"
  exit 0
fi
test -d "$OUTPUTS"
test ! -e "$PRESERVED"
mkdir -p "$(dirname "$PRESERVED")"
mv "$OUTPUTS" "$PRESERVED"
install -d -m 0775 "$OUTPUTS"
test -w "$OUTPUTS"

python3 - <<'PY'
import datetime as dt
import hashlib
import json
from pathlib import Path

root = Path("external/v7")
preserved = root / "failed_intermediates/outputs-root-owned-attempt1"

def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()

record = {
    "schema_version": "flipguard_external_v7_output_root_recovery_v1",
    "timestamp": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    "reason": "DOCKER_CREATED_OUTPUT_ROOT_ROOT_OWNED_0755",
    "preserved_path": str(preserved),
    "preserved_tree_sha256": tree_digest(preserved),
    "replacement_path": "external/v7/outputs",
    "replacement_mode": "0775",
    "encrypted_execution": 0,
    "frozen_evidence_overwritten": False,
}
target = root / "status/output_root_recovery.json"
temporary = target.with_suffix(".json.tmp")
temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(target)
PY
