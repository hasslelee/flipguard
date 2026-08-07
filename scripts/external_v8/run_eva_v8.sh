#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v8/outputs/eva/shared-polynomial-threshold-v8"
if [[ -f "$OUTPUT/manifest.json" ]]; then
  exit 0
fi
readonly PARTIAL="${OUTPUT}.partial"
if [[ -e "$PARTIAL" ]]; then
  mkdir -p external/v8/failed_intermediates/eva
  mv "$PARTIAL" "external/v8/failed_intermediates/eva/shared-polynomial-$(date -u +%Y%m%dT%H%M%SZ)"
fi

docker run --rm --cpuset-cpus 0,1 \
  --volume "$ROOT:/work" --workdir /work \
  --env PYTHONPATH=/work/external/v7/builds/eva/eva/python \
  flipguard/mlir16-seal4:audit-v1 bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    if ! ldconfig -p | grep -q libprotobuf.so.23; then
      apt-get update -qq
      apt-get install -y -qq --no-install-recommends libprotobuf23
    fi
    git config --global --add safe.directory /work/external/v7/sources/eva
    python3 scripts/external_v8/run_eva_shared_polynomial_v8.py \
      --eva-root external/v7/sources/eva \
      --input-root docs/evidence/focused_external_comparison_v8/input_manifests/shared_polynomial_threshold_v8 \
      --output-root external/v8/outputs/eva/shared-polynomial-threshold-v8.partial \
      --contexts 3
  '
mv "$PARTIAL" "$OUTPUT"
