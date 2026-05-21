#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODULE="github.com/tuneinsight/lattigo/v6"
RESULT_DIR="results/lattigo_compat"
RESULT_FILE="$RESULT_DIR/lattigo_compat.txt"

mkdir -p "$RESULT_DIR"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

{
  echo "== FlipGuard Lattigo compatibility probe =="
  echo "Repository: $REPO_ROOT"
  echo "Probe module: $MODULE"
  echo

  echo "== 1. Host Go environment =="
  go version
  go env GOVERSION GOOS GOARCH GOMOD GOTOOLCHAIN
  echo

  echo "== 2. FlipGuard module =="
  cat go.mod
  echo

  echo "== 3. Available Lattigo v6 versions =="
  go list -m -versions "$MODULE"
  echo

  echo "== 4. Latest Lattigo v6 module metadata =="
  go list -m -json "$MODULE@latest"
  echo

  echo "== 5. Temporary module resolution =="
  cd "$TMP_DIR"
  go mod init flipguard-lattigo-compat-probe
  go get "$MODULE@latest"
  go list -m all
  echo

  echo "== 6. Minimal import compile check =="
  cat > main.go <<'EOF'
package main

import (
	"fmt"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

func main() {
	fmt.Printf("ckks package probe: %T\n", ckks.Parameters{})
}
EOF

  go mod tidy
  go run .
  echo

  echo "== 7. Probe result =="
  echo "Lattigo module resolution and minimal ckks import compile check succeeded."
} | tee "$RESULT_FILE"

echo
echo "Compatibility probe written to $RESULT_FILE"