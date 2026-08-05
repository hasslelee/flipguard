#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
SOURCE="$ROOT/external/v6/sources/hecate"
RUNTIME="$ROOT/external/v6/runners/hecate-runtime"
EXPECTED_COMMIT=aedca73dac27b86044721781b9fca8d12e665876

test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
test ! -e "$RUNTIME"

git clone --no-hardlinks --no-local "$SOURCE" "$RUNTIME"
git -C "$RUNTIME" checkout --detach "$EXPECTED_COMMIT"
test -z "$(git -C "$RUNTIME" status --porcelain)"
ln -s "$ROOT/external/v6/builds/hecate/compiler" "$RUNTIME/build"

printf '%s\n' "$EXPECTED_COMMIT" > "$RUNTIME/V6_SOURCE_COMMIT"

