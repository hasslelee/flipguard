#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

go run ./cmd/flipguard \
  -experiment ckks_harris_corner_tuner \
  "$@"
