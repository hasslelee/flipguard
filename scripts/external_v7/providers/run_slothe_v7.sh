#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"; cd "$ROOT"
python3 scripts/external_v7/run_stage_v7.py --provider slothe --run-id 0001-source --stage SOURCE_CHECKOUT --workload official-artifact --cwd . --output-path external/v7/sources/slothe -- bash -lc 'git clone --filter=blob:none https://github.com/SNUSOR-PECT/SLOTHE external/v7/sources/slothe && git -C external/v7/sources/slothe checkout --detach 33ccff3519c9df1dc255420e8a1bfe4da501b1f0 && test "$(git -C external/v7/sources/slothe rev-parse HEAD)" = 33ccff3519c9df1dc255420e8a1bfe4da501b1f0'
python3 scripts/external_v7/record_provider_terminal_v7.py --provider slothe --state LICENSE_BLOCKED --reason "Pinned repository contains no declared software license; no experimental build is promoted." --source-url https://github.com/SNUSOR-PECT/SLOTHE --source-commit 33ccff3519c9df1dc255420e8a1bfe4da501b1f0 --license NO_LICENSE_DECLARED
