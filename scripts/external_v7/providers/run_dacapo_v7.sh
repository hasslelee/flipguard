#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"; cd "$ROOT"
python3 scripts/external_v7/run_stage_v7.py --provider dacapo --run-id 0001-source --stage SOURCE_CHECKOUT --workload official-artifact --cwd . --output-path external/v7/sources/dacapo -- bash -lc 'git clone --filter=blob:none https://github.com/corelab-src/dacapo external/v7/sources/dacapo && git -C external/v7/sources/dacapo checkout --detach 4616402710f39df3e5f5bd7930a6c036025aaac3 && test "$(git -C external/v7/sources/dacapo rev-parse HEAD)" = 4616402710f39df3e5f5bd7930a6c036025aaac3'
python3 scripts/external_v7/record_provider_terminal_v7.py --provider dacapo --state HARDWARE_BLOCKED_NO_GPU --reason "Official bootstrap workflow requires a supported CUDA device; none is visible on this host." --source-url https://github.com/corelab-src/dacapo --source-commit 4616402710f39df3e5f5bd7930a6c036025aaac3 --license MIT
