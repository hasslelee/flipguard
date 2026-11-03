#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly SOURCE="external/v7/sources/elasm"
readonly RUNTIME="external/v7/environments/elasm-runtime-r1"
test ! -e "$RUNTIME"
git clone --no-hardlinks "$SOURCE" "$RUNTIME"
git -C "$RUNTIME" remote set-url origin https://github.com/corelab-src/elasm
git -C "$RUNTIME" checkout --detach 3c37c11b29ca480525bb6681e0254bdf90029425
ln -s ../../builds/elasm/compiler "$RUNTIME/build"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  flipguard/mlir16-seal4:audit-v1 \
  bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends python3-numpy
    export HECATE=/work/external/v7/environments/elasm-runtime-r1
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH="$HECATE/python/hecate"
    export LD_LIBRARY_PATH="$HECATE/build/lib:/work/external/v7/builds/elasm/seal-install/lib:/usr/lib/llvm-16/lib:${LD_LIBRARY_PATH:-}"
    cd "$HECATE/examples"
    mkdir -p traced optimized/eva optimized/elasm
    python3 benchmarks/LinearRegression.py
    test -f traced/LinearRegression.mlir
    test -f traced/_hecate_LinearRegression.cst
  '
