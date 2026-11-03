#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

readonly BUILD_ROOT="external/v6/builds/eva"
readonly EVA_SOURCE="external/v6/sources/eva"
readonly SEAL_SOURCE="external/v6/sources/seal-3.6.4"
readonly IMAGE="flipguard/mlir16-seal4:audit-v1"

test -d "$EVA_SOURCE/.git"
test -d "$SEAL_SOURCE/.git"
test ! -e "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends \
      libboost-all-dev libprotobuf-dev protobuf-compiler

    export CXXFLAGS="-include mutex"
    cmake -S external/v6/sources/seal-3.6.4 \
      -B external/v6/builds/eva/seal \
      -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/work/external/v6/builds/eva/seal-install \
      -DSEAL_THROW_ON_TRANSPARENT_CIPHERTEXT=OFF \
      -DSEAL_USE_GAUSSIAN_NOISE=OFF \
      -DSEAL_USE_MSGSL=OFF \
      -DSEAL_USE_ZLIB=OFF \
      -DSEAL_USE_ZSTD=OFF \
      -DSEAL_BUILD_TESTS=OFF \
      -DSEAL_BUILD_EXAMPLES=OFF
    cmake --build external/v6/builds/eva/seal --parallel 2
    cmake --install external/v6/builds/eva/seal

    cmake -S external/v6/sources/eva \
      -B external/v6/builds/eva/eva \
      -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/work/external/v6/builds/eva/seal-install \
      -DUSE_GALOIS=OFF
    cmake --build external/v6/builds/eva/eva --parallel 2
  '
