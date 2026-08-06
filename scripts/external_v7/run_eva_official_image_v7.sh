#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v7/outputs/eva/official-image-v1"
test ! -e "$OUTPUT"
docker run --rm --cpuset-cpus 0,1 --volume "$ROOT:/work" --workdir /work \
  --env PYTHONPATH=/work/external/v7/builds/eva/eva/python \
  flipguard/mlir16-seal4:audit-v1 bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends libprotobuf23 python3-numpy python3-pil
    git config --global --add safe.directory /work/external/v7/sources/eva
    python3 scripts/external_v7/run_eva_official_image_v7.py \
      --eva-root external/v7/sources/eva \
      --output-root external/v7/outputs/eva/official-image-v1 \
      --key-contexts 3
  '
