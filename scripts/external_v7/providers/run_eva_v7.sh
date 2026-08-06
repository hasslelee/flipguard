#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/eva"
mkdir -p "$STATUS"

$STAGE --provider eva --run-id 0001-eva-source --stage SOURCE_CHECKOUT \
  --workload official-source --cwd . --output-path external/v7/sources/eva -- \
  bash -lc 'git clone --filter=blob:none https://github.com/microsoft/EVA external/v7/sources/eva && git -C external/v7/sources/eva checkout --detach 4cd3254c9c51340ae30c451495ce5378135758c0 && test "$(git -C external/v7/sources/eva rev-parse HEAD)" = 4cd3254c9c51340ae30c451495ce5378135758c0'

$STAGE --provider eva --run-id 0002-seal-source --stage SOURCE_CHECKOUT \
  --workload seal-3.6.4 --cwd . --output-path external/v7/sources/seal-3.6.4 -- \
  bash -lc 'git clone --filter=blob:none --branch v3.6.4 https://github.com/microsoft/SEAL external/v7/sources/seal-3.6.4 && test "$(git -C external/v7/sources/seal-3.6.4 describe --tags --exact-match)" = v3.6.4'

$STAGE --provider eva --run-id 0003-clean-build --stage CLEAN_BUILD \
  --workload eva-v1.0.1 --cwd . --source-path external/v7/sources/eva \
  --output-path external/v7/builds/eva -- scripts/external_v7/build_eva_v7.sh

$STAGE --provider eva --run-id 0004-official-image --stage ENCRYPTED_VALIDATION \
  --workload eva-official-sobel-harris --cwd . --source-path external/v7/sources/eva \
  --binary-path external/v7/builds/eva/eva/python \
  --input-path docs/evidence/external_end_to_end_code_v7/input_manifests/eva_official_image_v1.json \
  --output-path external/v7/outputs/eva/official-image-v1 -- scripts/external_v7/run_eva_official_image_v7.sh

$STAGE --provider eva --run-id 0005-shared-polynomial --stage ENCRYPTED_AUDIT \
  --workload shared-polynomial-v1 --cwd . --source-path external/v7/sources/eva \
  --binary-path external/v7/builds/eva/eva/python \
  --input-path docs/evidence/external_end_to_end_code_v7/input_manifests/eva_shared_polynomial_v1.json \
  --output-path external/v7/outputs/eva/shared-polynomial-v1 -- scripts/external_v7/run_eva_shared_polynomial_v7.sh

printf '%s\n' "DECISION_BEARING_LOCKED_AUDIT" > "$STATUS/final_state.txt"
