#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 RUN_ID" >&2
  exit 2
fi
readonly RUN_ID="$1"
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly RUNTIME="$ROOT/external/v7/runners/hecate-runtime"
readonly OUTPUT="$ROOT/external/v7/outputs/corelab/hecate-official-linear-v1"
test "$(git -C "$RUNTIME" rev-parse HEAD)" = aedca73dac27b86044721781b9fca8d12e665876
test ! -e "$OUTPUT"

docker run --rm --cpuset-cpus 0,1 --network none \
  -e HECATE=/work/external/v7/runners/hecate-runtime \
  -e OMP_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 -e MKL_NUM_THREADS=2 \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$ROOT:/work" -w /work --entrypoint bash \
  flipguard/hecate-v7-runtime:torch2.0.1-cpu -lc \
  "git config --global --add safe.directory /work/external/v7/runners/hecate-runtime; \
   export LD_LIBRARY_PATH=/work/external/v7/builds/hecate/seal-install/lib:/work/external/v7/builds/hecate/compiler/lib:/usr/lib/llvm-18/lib; \
   exec python3 scripts/external_v7/run_hecate_official_linear_v7.py \
     --runtime-root external/v7/runners/hecate-runtime \
     --output-root external/v7/outputs/corelab/hecate-official-linear-v1 \
     --status-file external/v7/status/corelab/$RUN_ID/completed_samples.txt"
