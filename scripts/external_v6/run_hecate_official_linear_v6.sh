#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
RUNTIME="$ROOT/external/v6/runners/hecate-runtime"
OUTPUT="$ROOT/external/v6/outputs/hecate/official-linear-v1"
STATUS="$ROOT/external/v6/status/corelab-hecate/0024-hecate-official-linear/completed_samples.txt"

test "$(git -C "$RUNTIME" rev-parse HEAD)" = aedca73dac27b86044721781b9fca8d12e665876
test ! -e "$OUTPUT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --network none \
  -e HECATE=/work/external/v6/runners/hecate-runtime \
  -e OMP_NUM_THREADS=2 \
  -e OPENBLAS_NUM_THREADS=2 \
  -e MKL_NUM_THREADS=2 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$ROOT:/work" \
  -w /work \
  --entrypoint bash \
  flipguard/hecate-v6-runtime:torch2.0.1-cpu \
  -lc 'export LD_LIBRARY_PATH=/work/external/v6/builds/hecate/seal-install/lib:/work/external/v6/builds/hecate/compiler/lib:/usr/lib/llvm-18/lib; exec python3 scripts/external_v6/run_hecate_official_linear_v6.py --runtime-root external/v6/runners/hecate-runtime --output-root external/v6/outputs/hecate/official-linear-v1 --status-file external/v6/status/corelab-hecate/0024-hecate-official-linear/completed_samples.txt'

