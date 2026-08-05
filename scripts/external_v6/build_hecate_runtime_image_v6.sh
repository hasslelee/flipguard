#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

docker build \
  --file scripts/external_v6/Dockerfile.hecate-runtime-v6 \
  --tag flipguard/hecate-v6-runtime:torch2.0.1-cpu \
  scripts/external_v6

