#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly TEMP_ROOT="$(mktemp -d /tmp/flipguard-v7-go-gate.XXXXXX)"

cleanup() {
  chmod -R u+w "$TEMP_ROOT" 2>/dev/null || true
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$TEMP_ROOT"
while IFS= read -r fixture; do
  test -f "$ROOT/$fixture"
  mkdir -p "$TEMP_ROOT/$(dirname "$fixture")"
  cp --preserve=mode,timestamps "$ROOT/$fixture" "$TEMP_ROOT/$fixture"
done <<'EOF'
results/source_datasets/mnist/mnist_784.arff.gz
results/source_datasets/bsds500/BSR_bsds500.tgz
EOF
cd "$TEMP_ROOT"
go test ./...
go vet ./...
