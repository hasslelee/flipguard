#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly BUILD_ROOT="external/v7/builds/eva"
test -d external/v7/sources/eva/.git
test -d external/v7/sources/seal-3.6.4/.git
test ! -e "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

docker run --rm --cpuset-cpus 0,1 --volume "$ROOT:/work" --workdir /work \
  flipguard/mlir16-seal4:audit-v1 bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends libboost-all-dev libprotobuf-dev protobuf-compiler
    export CXXFLAGS="-include mutex"
    cmake -S external/v7/sources/seal-3.6.4 -B external/v7/builds/eva/seal -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/work/external/v7/builds/eva/seal-install \
      -DSEAL_THROW_ON_TRANSPARENT_CIPHERTEXT=OFF -DSEAL_USE_GAUSSIAN_NOISE=OFF \
      -DSEAL_USE_MSGSL=OFF -DSEAL_USE_ZLIB=OFF -DSEAL_USE_ZSTD=OFF \
      -DSEAL_BUILD_TESTS=OFF -DSEAL_BUILD_EXAMPLES=OFF
    cmake --build external/v7/builds/eva/seal --parallel 2
    cmake --install external/v7/builds/eva/seal
    cmake -S external/v7/sources/eva -B external/v7/builds/eva/eva -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/work/external/v7/builds/eva/seal-install -DUSE_GALOIS=OFF
    cmake --build external/v7/builds/eva/eva --parallel 2
  '
