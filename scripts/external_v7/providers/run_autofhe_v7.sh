#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"; cd "$ROOT"
if [[ ! -f external/v7/status/autofhe/0001-source/current_stage.txt ]] || \
  [[ "$(<external/v7/status/autofhe/0001-source/current_stage.txt)" != PASS ]]; then
  python3 scripts/external_v7/run_stage_v7.py --provider autofhe --run-id 0001-source --stage SOURCE_CHECKOUT --workload official-artifact --cwd . --output-path external/v7/sources/autofhe -- bash -lc 'git clone --filter=blob:none https://github.com/human-analysis/AutoFHE external/v7/sources/autofhe && git -C external/v7/sources/autofhe checkout --detach a43af0453e5237e2ff4a5630a10ece1a062b9d88 && test "$(git -C external/v7/sources/autofhe rev-parse HEAD)" = a43af0453e5237e2ff4a5630a10ece1a062b9d88'
fi
test "$(git -C external/v7/sources/autofhe rev-parse HEAD)" = a43af0453e5237e2ff4a5630a10ece1a062b9d88
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  python3 scripts/external_v7/record_provider_terminal_v7.py --provider autofhe --state CLEAN_BUILD_BLOCKED --reason "GPU unexpectedly visible but no frozen V7 GPU execution adapter is declared." --source-url https://github.com/human-analysis/AutoFHE --source-commit a43af0453e5237e2ff4a5630a10ece1a062b9d88 --license MIT
else
  python3 scripts/external_v7/record_provider_terminal_v7.py --provider autofhe --state HARDWARE_BLOCKED_NO_GPU --reason "Official search and encrypted inference path requires CUDA; this host exposes no supported GPU and no official CPU path." --source-url https://github.com/human-analysis/AutoFHE --source-commit a43af0453e5237e2ff4a5630a10ece1a062b9d88 --license MIT
fi
