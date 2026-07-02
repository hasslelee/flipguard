#!/usr/bin/env bash
set -euo pipefail

go run ./cmd/flipguard -experiment ckks_auto_tuner_smoke

echo
echo "Generated artifacts:"
find results/ckks_auto_tuner_smoke -maxdepth 1 -type f | sort