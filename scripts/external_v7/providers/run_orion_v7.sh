#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/orion"
readonly COMMIT="be8a827350a147d610fe3bb998b5bea8de814ff8"
readonly VENV="$ROOT/external/v7/environments/orion-venv"
mkdir -p "$STATUS"

$STAGE --provider orion --run-id 0001-source --stage SOURCE_CHECKOUT \
  --workload official-helrm --cwd . --output-path external/v7/sources/orion -- \
  bash -lc "git clone --filter=blob:none https://github.com/baahl-nyu/orion external/v7/sources/orion && git -C external/v7/sources/orion checkout --detach $COMMIT && test \"\$(git -C external/v7/sources/orion rev-parse HEAD)\" = $COMMIT"

$STAGE --provider orion --run-id 0002-clean-environment --stage ENVIRONMENT_CREATE \
  --workload official-helrm --cwd . --source-path external/v7/sources/orion \
  --output-path external/v7/environments/orion-venv -- bash -lc '
    set -euo pipefail
    python3 -m venv external/v7/environments/orion-venv
    . external/v7/environments/orion-venv/bin/activate
    python -m pip install --upgrade pip wheel setuptools
    python -m pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu
    python -m pip install numpy==1.26.4 scipy==1.14.1 certifi PyYAML tqdm matplotlib h5py
    python -m pip install --no-build-isolation -e external/v7/sources/orion
  '

$STAGE --provider orion --run-id 0003-binary-verify --stage CLEAN_BUILD \
  --workload official-helrm --cwd . --source-path external/v7/sources/orion \
  --binary-path external/v7/sources/orion/orion/backend/lattigo/lattigo-linux.so -- \
  "$VENV/bin/python" -c 'import ctypes, orion; from pathlib import Path; p=Path("external/v7/sources/orion/orion/backend/lattigo/lattigo-linux.so"); assert p.is_file(); ctypes.CDLL(str(p.resolve())); print("ORION_LATTIGO_LOAD_PASS")'

set +e
$STAGE --provider orion --run-id 0004-official-path --stage ENCRYPTED_VALIDATION \
  --workload official-helrm-single-input --cwd external/v7/sources/orion \
  --source-path external/v7/sources/orion \
  --binary-path external/v7/sources/orion/orion/backend/lattigo/lattigo-linux.so -- \
  "$VENV/bin/python" examples/run_helrm.py
official_rc=$?
set -e

if [[ $official_rc -ne 0 ]]; then
  stderr="$ROOT/external/v7/logs/orion/0004-official-path/stderr.log"
  if ! rg -q "model/helrm\.pth|No such file or directory" "$stderr"; then
    printf '%s\n' "OFFICIAL_RUNTIME_FAILED" > "$STATUS/final_state.txt"
    exit "$official_rc"
  fi
  printf '%s\n' "$official_rc" > "$STATUS/original_official_exit_code.txt"
  mkdir -p external/v7/runners/orion-helrm/model
  ln -s "$ROOT/external/v7/sources/orion/configs" external/v7/runners/orion-helrm/configs
  ln -s "$ROOT/external/v7/sources/orion/model_state/helrm.pth" external/v7/runners/orion-helrm/model/helrm.pth
  ln -s "$ROOT/external/v7/sources/orion/examples/run_helrm.py" external/v7/runners/orion-helrm/run_helrm.py
  $STAGE --provider orion --run-id 0005-official-path-recovery --stage ENCRYPTED_VALIDATION \
    --workload official-helrm-single-input --cwd external/v7/runners/orion-helrm \
    --source-path external/v7/sources/orion \
    --binary-path external/v7/sources/orion/orion/backend/lattigo/lattigo-linux.so -- \
    "$VENV/bin/python" run_helrm.py
fi

$STAGE --provider orion --run-id 0006-output-freeze --stage OUTPUT_NORMALIZATION \
  --workload official-helrm-single-input --cwd . --source-path external/v7/sources/orion \
  --output-path external/v7/outputs/orion/official-helrm-single-v1 -- bash -lc '
    set -euo pipefail
    out=external/v7/outputs/orion/official-helrm-single-v1
    test ! -e "$out"
    mkdir -p "$out"
    log=external/v7/logs/orion/0004-official-path/stdout.log
    if [[ -s external/v7/logs/orion/0005-official-path-recovery/stdout.log ]]; then log=external/v7/logs/orion/0005-official-path-recovery/stdout.log; fi
    cp "$log" "$out/raw_output.log"
    printf "%s\n" "{\"schema_version\":\"flipguard_external_v7_orion_result_v1\",\"provider\":\"Orion\",\"source_commit\":\"be8a827350a147d610fe3bb998b5bea8de814ff8\",\"workload\":\"official_helrm_single_input\",\"unique_inputs\":1,\"evidence_level\":3,\"main_decision_comparison_eligible\":false,\"reason\":\"SINGLE_EXAMPLE_ONLY\"}" > "$out/manifest.json"
    (cd "$out" && sha256sum manifest.json raw_output.log > SHA256SUMS)
  '

printf '%s\n' "ENCRYPTED_END_TO_END" > "$STATUS/final_state.txt"
