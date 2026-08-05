#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
docker build \
  --file scripts/external_v6/Dockerfile.hecate-v6 \
  --tag flipguard/hecate-v6-deps:llvm18-cuda12.2 \
  .

