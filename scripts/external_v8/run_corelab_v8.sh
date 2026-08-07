#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v8/outputs/corelab/linear-regression-multi-input-v8"
if [[ -f "$OUTPUT/manifest.json" ]]; then
  exit 0
fi
mkdir -p "$OUTPUT"

docker run --rm --cpuset-cpus 0,1 --volume "$ROOT:/work" --workdir /work \
  --env HECATE=/work/external/v7/environments/elasm-runtime-r1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONPATH=/work/external/v7/environments/elasm-runtime-r1/python/hecate \
  --env LD_LIBRARY_PATH=/work/external/v7/environments/elasm-runtime-r1/build/lib:/work/external/v7/builds/elasm/seal-install/lib:/usr/lib/llvm-16/lib \
  flipguard/mlir16-seal4:audit-v1 bash -lc '
    set -euo pipefail
    if ! python3 -c "import numpy" >/dev/null 2>&1; then
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -qq
      apt-get install -y -qq --no-install-recommends python3-numpy
    fi
    git config --global --add safe.directory /work/external/v7/environments/elasm-runtime-r1
    python3 scripts/external_v8/run_corelab_multi_input_v8.py \
      --runtime-root external/v7/environments/elasm-runtime-r1 \
      --v7-output-root external/v7/outputs/corelab/elasm-linear-regression-grid-v1 \
      --output-root external/v8/outputs/corelab/linear-regression-multi-input-v8
  '
