#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly BUILD_ROOT="external/v6/builds/hecate"
test ! -e "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  flipguard/hecate-v6-deps:llvm18-cuda12.2 \
  bash -lc '
    set -euo pipefail
    cmake -S external/v6/sources/seal-4.0.0 -B external/v6/builds/hecate/seal-build \
      -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/work/external/v6/builds/hecate/seal-install \
      -DSEAL_BUILD_DEPS=ON \
      -DSEAL_BUILD_TESTS=OFF \
      -DSEAL_BUILD_EXAMPLES=OFF
    cmake --build external/v6/builds/hecate/seal-build --parallel 2
    cmake --install external/v6/builds/hecate/seal-build

    cmake -S external/v6/sources/hecate -B external/v6/builds/hecate/compiler \
      -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=/usr/bin/clang-18 \
      -DCMAKE_CXX_COMPILER=/usr/bin/clang++-18 \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir \
      -DLLVM_DIR=/usr/lib/llvm-18/lib/cmake/llvm \
      -DMLIR_ROOT=/usr/lib/llvm-18 \
      -DSEAL_DIR=/work/external/v6/builds/hecate/seal-install/lib/cmake/SEAL-4.0 \
      -DSEAL_ROOT=/work/external/v6/builds/hecate/seal-install
    cmake --build external/v6/builds/hecate/compiler --parallel 2
    test -x external/v6/builds/hecate/compiler/bin/hecate-opt
    test -f external/v6/builds/hecate/compiler/lib/libSEAL_HEVM.so
  '

