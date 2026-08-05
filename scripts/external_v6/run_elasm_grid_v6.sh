#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if [[ $# -ne 1 ]]; then
  echo "usage: $0 RUN_ID" >&2
  exit 2
fi
readonly RUN_ID="$1"
readonly RUNTIME="external/v6/environments/elasm-runtime"
readonly OUTPUT="external/v6/outputs/corelab/elasm-linear-regression-grid-v1"
test ! -e "$OUTPUT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  --env HECATE=/work/$RUNTIME \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONPATH=/work/$RUNTIME/python/hecate \
  --env LD_LIBRARY_PATH=/work/$RUNTIME/build/lib:/work/external/v6/builds/elasm/seal-install/lib:/usr/lib/llvm-16/lib \
  flipguard/mlir16-seal4:audit-v1 \
  python3 scripts/external_v6/run_elasm_grid_v6.py \
    --source-root external/v6/sources/elasm \
    --runtime-root "$RUNTIME" \
    --output-root "$OUTPUT" \
    --status-file "external/v6/status/corelab/$RUN_ID/completed_samples.txt" \
    --seed 20260805
