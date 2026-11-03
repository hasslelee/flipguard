#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 SOURCE_COMMIT" >&2
  exit 2
fi
readonly SOURCE_COMMIT="$1"
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v6/outputs/eva/shared-polynomial-v1"
test ! -e "$OUTPUT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  --env PYTHONPATH=/work/external/v6/builds/eva/eva/python \
  flipguard/mlir16-seal4:audit-v1 \
  bash -lc "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends libprotobuf23
    git config --global --add safe.directory /work
    python3 scripts/run_eva_native_scale_sensitivity.py \\
      --eva-root external/v6/sources/eva \\
      --seal-root external/v6/sources/seal-3.6.4 \\
      --output-root external/v6/outputs/eva/shared-polynomial-v1 \\
      --source-commit '$SOURCE_COMMIT' \\
      --action-run-id external-v6-eva-shared-polynomial-v1
  "
