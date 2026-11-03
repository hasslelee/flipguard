#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/corelab"
mkdir -p "$STATUS"

if [[ -d "$STATUS/0001-elasm-source" ]]; then
  exec scripts/external_v7/providers/run_corelab_recovery_v7.sh
fi

$STAGE --provider corelab --run-id 0001-elasm-source --stage SOURCE_CHECKOUT \
  --workload official-source --cwd . --output-path external/v7/sources/elasm -- \
  bash -lc 'git clone --filter=blob:none https://github.com/corelab-src/elasm external/v7/sources/elasm && git -C external/v7/sources/elasm checkout --detach 3c37c11b29ca480525bb6681e0254bdf90029425 && test "$(git -C external/v7/sources/elasm rev-parse HEAD)" = 3c37c11b29ca480525bb6681e0254bdf90029425'

$STAGE --provider corelab --run-id 0002-seal4-source --stage SOURCE_CHECKOUT \
  --workload seal-4.0.0 --cwd . --output-path external/v7/sources/seal-4.0.0 -- \
  bash -lc 'git clone --filter=blob:none --branch v4.0.0 https://github.com/microsoft/SEAL external/v7/sources/seal-4.0.0 && test "$(git -C external/v7/sources/seal-4.0.0 describe --tags --exact-match)" = v4.0.0'

$STAGE --provider corelab --run-id 0003-elasm-build --stage CLEAN_BUILD \
  --workload official-linear-regression --cwd . --source-path external/v7/sources/elasm \
  --output-path external/v7/builds/elasm -- scripts/external_v7/run_elasm_clean_build_v7.sh

$STAGE --provider corelab --run-id 0004-elasm-runtime --stage ENVIRONMENT_CREATE \
  --workload official-linear-regression --cwd . --source-path external/v7/sources/elasm \
  --output-path external/v7/environments/elasm-runtime-r1 -- scripts/external_v7/prepare_elasm_runtime_v7.sh

$STAGE --provider corelab --run-id 0005-elasm-grid --stage ENCRYPTED_VALIDATION \
  --workload official-linear-regression-grid --cwd . --source-path external/v7/sources/elasm \
  --binary-path external/v7/builds/elasm/compiler/bin/hecate-opt \
  --output-path external/v7/outputs/corelab/elasm-linear-regression-grid-v1 -- \
  scripts/external_v7/run_elasm_grid_v7.sh 0005-elasm-grid

$STAGE --provider corelab --run-id 0006-hecate-source --stage SOURCE_CHECKOUT \
  --workload official-source --cwd . --output-path external/v7/sources/hecate -- \
  bash -lc 'git clone --filter=blob:none https://github.com/corelab-src/hecate-compiler external/v7/sources/hecate && git -C external/v7/sources/hecate checkout --detach aedca73dac27b86044721781b9fca8d12e665876 && test "$(git -C external/v7/sources/hecate rev-parse HEAD)" = aedca73dac27b86044721781b9fca8d12e665876'

$STAGE --provider corelab --run-id 0007-hecate-deps --stage ENVIRONMENT_CREATE \
  --workload hecate-dependencies --cwd . --output-path external/v7/logical-images/hecate-deps.complete -- \
  bash -lc 'scripts/external_v7/build_hecate_dependency_image_v7.sh && mkdir -p external/v7/logical-images && docker image inspect flipguard/hecate-v7-deps:llvm18-cuda12.2 > external/v7/logical-images/hecate-deps.complete'

$STAGE --provider corelab --run-id 0008-hecate-build --stage CLEAN_BUILD \
  --workload official-linear-regression --cwd . --source-path external/v7/sources/hecate \
  --output-path external/v7/builds/hecate -- scripts/external_v7/run_hecate_clean_build_v7.sh

$STAGE --provider corelab --run-id 0009-hecate-runtime-image --stage ENVIRONMENT_CREATE \
  --workload hecate-runtime --cwd . --output-path external/v7/logical-images/hecate-runtime.complete -- \
  bash -lc 'scripts/external_v7/build_hecate_runtime_image_v7.sh && docker image inspect flipguard/hecate-v7-runtime:torch2.0.1-cpu > external/v7/logical-images/hecate-runtime.complete'

$STAGE --provider corelab --run-id 0010-hecate-runtime --stage ENVIRONMENT_CREATE \
  --workload official-linear-regression --cwd . --source-path external/v7/sources/hecate \
  --output-path external/v7/runners/hecate-runtime -- scripts/external_v7/prepare_hecate_runtime_v7.sh

$STAGE --provider corelab --run-id 0011-hecate-e2e --stage ENCRYPTED_VALIDATION \
  --workload official-linear-regression --cwd . --source-path external/v7/runners/hecate-runtime \
  --binary-path external/v7/builds/hecate/compiler/bin/hecate-opt \
  --output-path external/v7/outputs/corelab/hecate-official-linear-v1 -- \
  scripts/external_v7/run_hecate_official_linear_v7.sh 0011-hecate-e2e

printf '%s\n' "ENCRYPTED_END_TO_END" > "$STATUS/final_state.txt"
