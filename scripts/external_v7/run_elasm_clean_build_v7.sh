#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly BUILD_ROOT="external/v7/builds/elasm"
test -d external/v7/sources/elasm/.git
test -d external/v7/sources/seal-4.0.0/.git
test ! -e "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  flipguard/mlir16-seal4:audit-v1 \
  bash -lc '
    set -euo pipefail
    cmake -S external/v7/sources/seal-4.0.0 \
      -B external/v7/builds/elasm/seal \
      -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/work/external/v7/builds/elasm/seal-install \
      -DSEAL_USE_MSGSL=OFF \
      -DSEAL_USE_ZLIB=OFF \
      -DSEAL_USE_ZSTD=OFF \
      -DSEAL_BUILD_TESTS=OFF \
      -DSEAL_BUILD_EXAMPLES=OFF
    cmake --build external/v7/builds/elasm/seal --parallel 2
    cmake --install external/v7/builds/elasm/seal

    cmake -S external/v7/sources/elasm \
      -B external/v7/builds/elasm/compiler \
      -G Ninja \
      -DMLIR_ROOT=/usr/lib/llvm-16 \
      -DSEAL_ROOT=/work/external/v7/builds/elasm/seal-install \
      -DCMAKE_PREFIX_PATH="/usr/lib/llvm-16;/work/external/v7/builds/elasm/seal-install" \
      -DCMAKE_C_COMPILER=/usr/lib/llvm-16/bin/clang \
      -DCMAKE_CXX_COMPILER=/usr/lib/llvm-16/bin/clang++ \
      -DCMAKE_BUILD_TYPE=Release
    cmake --build external/v7/builds/elasm/compiler --parallel 2
  '
