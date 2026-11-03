#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v6/outputs/eva/official-image-v1"
test ! -e "$OUTPUT"

docker run --rm \
  --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" \
  --workdir /work \
  --env PYTHONPATH=/work/external/v6/builds/eva/eva/python \
  flipguard/mlir16-seal4:audit-v1 \
  bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends libprotobuf23 python3-numpy python3-pil
    git config --global --add safe.directory /work/external/v6/sources/eva
    python3 scripts/external_v6/run_eva_official_image_v6.py \
      --eva-root external/v6/sources/eva \
      --output-root external/v6/outputs/eva/official-image-v1 \
      --key-contexts 3
  '
