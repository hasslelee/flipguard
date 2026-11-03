#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 PROVIDER" >&2
  exit 2
fi
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly RUNNER="$ROOT/scripts/external_v7/providers/run_${1//-/_}_v7.sh"
test -x "$RUNNER"
exec "$RUNNER"
