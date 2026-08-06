#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"; cd "$ROOT"
python3 scripts/external_v7/run_stage_v7.py --provider ant-ace --run-id 0001-source --stage SOURCE_CHECKOUT --workload official-artifact --cwd . --output-path external/v7/sources/ant-ace -- bash -lc 'git clone --filter=blob:none https://github.com/ant-research/ace-compiler external/v7/sources/ant-ace && git -C external/v7/sources/ant-ace checkout --detach 15c95a7346d89355d68d5bf4fe8ab3b952740e1a && test "$(git -C external/v7/sources/ant-ace rev-parse HEAD)" = 15c95a7346d89355d68d5bf4fe8ab3b952740e1a'
python3 scripts/external_v7/record_provider_terminal_v7.py --provider ant-ace --state LICENSE_BLOCKED --reason "Pinned official artifact declares no software license; execution cannot be redistributed or promoted." --source-url https://github.com/ant-research/ace-compiler --source-commit 15c95a7346d89355d68d5bf4fe8ab3b952740e1a --license NO_LICENSE_DECLARED
