#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUT="external/v8/outputs/flipguard/shared-polynomial-threshold-v8"
if [[ -f "$OUT/manifest.json" ]]; then
  python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "PASS"' "$OUT/manifest.json"
  exit 0
fi
mkdir -p external/v8/binaries "$OUT"

go build -trimpath -o external/v8/binaries/flipguard-autotune-v8 ./cmd/flipguard-autotune
go build -trimpath -o external/v8/binaries/flipguard-certify-candidate-v8 ./cmd/flipguard-certify-candidate
go build -trimpath -o external/v8/binaries/flipguard-audit-candidate-v8 ./cmd/flipguard-audit-candidate
python3 scripts/external_v8/prepare_heir_shared_polynomial_v8.py \
  --output-root external/v8/translations/heir-shared-polynomial-v8 >/dev/null
go build -tags externalv8 -trimpath \
  -o external/v8/binaries/flipguard-external-v8-common \
  ./cmd/flipguard-external-v8-common

python3 scripts/external_v8/run_flipguard_shared_polynomial_v8.py \
  --binary-root external/v8/binaries \
  --common-binary external/v8/binaries/flipguard-external-v8-common \
  --output-root "$OUT"
