#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUTPUT="external/v7/outputs/eva/shared-polynomial-v1"
test ! -e "$OUTPUT"
readonly SOURCE_COMMIT="$(git rev-parse HEAD)"
docker run --rm --cpuset-cpus 0,1 --volume "$ROOT:/work" --workdir /work \
  --env PYTHONPATH=/work/external/v7/builds/eva/eva/python \
  flipguard/mlir16-seal4:audit-v1 bash -lc "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends libprotobuf23
    git config --global --add safe.directory /work
    python3 scripts/run_eva_native_scale_sensitivity.py \\
      --eva-root external/v7/sources/eva \\
      --seal-root external/v7/sources/seal-3.6.4 \\
      --output-root external/v7/outputs/eva/shared-polynomial-v1 \\
      --source-commit '$SOURCE_COMMIT' \\
      --action-run-id external-v7-eva-shared-polynomial-v1
  "
