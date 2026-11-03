#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

docker build \
  --file scripts/external_v7/Dockerfile.hecate-runtime-v7 \
  --tag flipguard/hecate-v7-runtime:torch2.0.1-cpu \
  scripts/external_v7

