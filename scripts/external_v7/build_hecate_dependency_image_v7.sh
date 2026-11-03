#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
docker build \
  --file scripts/external_v7/Dockerfile.hecate-v7 \
  --tag flipguard/hecate-v7-deps:llvm18-cuda12.2 \
  scripts/external_v7
