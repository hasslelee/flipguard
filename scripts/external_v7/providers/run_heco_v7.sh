#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/heco"
readonly COMMIT="cf396f05029930b6476c10266853b2099e23bd32"
mkdir -p "$STATUS"

$STAGE --provider heco --run-id 0001-source --stage SOURCE_CHECKOUT \
  --workload official-artifact --cwd . --output-path external/v7/sources/heco -- \
  bash -lc "git clone --filter=blob:none https://github.com/MarbleHE/HECO external/v7/sources/heco && git -C external/v7/sources/heco checkout --detach $COMMIT && test \"\$(git -C external/v7/sources/heco rev-parse HEAD)\" = $COMMIT"

$STAGE --provider heco --run-id 0002-clean-build --stage CLEAN_BUILD \
  --workload official-benchmark --cwd . --source-path external/v7/sources/heco \
  --output-path external/v7/builds/heco -- docker run --rm --cpuset-cpus 0,1 \
  -e OMP_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 -e MKL_NUM_THREADS=2 \
  -v "$ROOT:/work" -w /work flipguard/mlir17-seal4:audit-v1 bash -lc '
    set -euo pipefail
    mkdir -p external/v7/builds/heco/src
    cp -a external/v7/sources/heco/. external/v7/builds/heco/src/
    cmake -S external/v7/builds/heco/src -B external/v7/builds/heco/build -G Ninja \
      -DMLIR_DIR=/usr/lib/llvm-17/lib/cmake/mlir \
      -DCMAKE_PREFIX_PATH="/usr/lib/llvm-17;/opt/seal4" \
      -DCMAKE_C_COMPILER=/usr/bin/clang-17 -DCMAKE_CXX_COMPILER=/usr/bin/clang++-17 \
      -DCMAKE_BUILD_TYPE=Release
    cmake --build external/v7/builds/heco/build --target heco emitc-translate --parallel 2
    test -x external/v7/builds/heco/build/bin/heco
    test -x external/v7/builds/heco/build/bin/emitc-translate
  '

$STAGE --provider heco --run-id 0003-official-pipeline --stage OFFICIAL_PIPELINE \
  --workload official-benchmark --cwd . --source-path external/v7/sources/heco \
  --binary-path external/v7/builds/heco/build/bin/heco -- docker run --rm --cpuset-cpus 0,1 \
  -e OMP_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 -e MKL_NUM_THREADS=2 \
  -v "$ROOT:/work" -w /work flipguard/mlir17-seal4:audit-v1 bash -lc '
    set -euo pipefail
    cd external/v7/builds/heco/src
    if [[ ! -e build ]]; then ln -s ../build build; fi
    bash evaluation/benchmark/heco_helper.sh
    bash evaluation/comparison/heco_helper.sh
    cd /work
    cmake --build external/v7/builds/heco/build --target benchmark comparison --parallel 2
    test -x external/v7/builds/heco/build/bin/benchmark
  '

$STAGE --provider heco --run-id 0004-official-encrypted-benchmark --stage ENCRYPTED_VALIDATION \
  --workload official-benchmark --cwd external/v7/builds/heco/src \
  --source-path external/v7/sources/heco --binary-path external/v7/builds/heco/build/bin/benchmark -- \
  docker run --rm --cpuset-cpus 0,1 -e OMP_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=2 \
  -e MKL_NUM_THREADS=2 -v "$ROOT:/work" -w /work/external/v7/builds/heco/src \
  flipguard/mlir17-seal4:audit-v1 ../build/bin/benchmark

$STAGE --provider heco --run-id 0005-output-freeze --stage OUTPUT_NORMALIZATION \
  --workload official-benchmark --cwd . --source-path external/v7/sources/heco \
  --output-path external/v7/outputs/heco/official-benchmark-v1 -- bash -lc '
    set -euo pipefail
    out=external/v7/outputs/heco/official-benchmark-v1
    test ! -e "$out"
    mkdir -p "$out/csv"
    find external/v7/builds/heco/src -type f -name "*.csv" -exec cp {} "$out/csv/" \;
    printf "%s\n" "{\"schema_version\":\"flipguard_external_v7_heco_result_v1\",\"provider\":\"HECO\",\"source_commit\":\"cf396f05029930b6476c10266853b2099e23bd32\",\"implemented_scheme\":\"BFV\",\"ckks_eligible\":false,\"official_harness_raw_decrypted_output\":false,\"evidence_level\":2,\"terminal_capability\":\"OFFICIAL_PIPELINE_ONLY\",\"gate_state\":\"NOT_EVALUATED\"}" > "$out/manifest.json"
    (cd "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
  '

printf '%s\n' "OFFICIAL_PIPELINE_ONLY" > "$STATUS/final_state.txt"
