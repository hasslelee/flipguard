#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 RUN_ID" >&2
  exit 2
fi
readonly RUN_ID="$1"
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly RUNTIME="external/v7/environments/elasm-runtime-r1"
readonly OUTPUT="external/v7/outputs/corelab/elasm-linear-regression-grid-v1"
test ! -e "$OUTPUT"

docker run --rm --cpuset-cpus 0,1 --volume "$ROOT:/work" --workdir /work \
  --env HECATE=/work/$RUNTIME --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONPATH=/work/$RUNTIME/python/hecate \
  --env LD_LIBRARY_PATH=/work/$RUNTIME/build/lib:/work/external/v7/builds/elasm/seal-install/lib:/usr/lib/llvm-16/lib \
  flipguard/mlir16-seal4:audit-v1 bash -lc "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends python3-numpy
    git config --global --add safe.directory /work/external/v7/sources/elasm
    git config --global --add safe.directory /work/$RUNTIME
    python3 scripts/external_v7/run_elasm_grid_v7.py \\
      --source-root external/v7/sources/elasm \\
      --runtime-root '$RUNTIME' \\
      --output-root '$OUTPUT' \\
      --status-file 'external/v7/status/corelab/$RUN_ID/completed_samples.txt' \\
      --seed 20260805
  "
