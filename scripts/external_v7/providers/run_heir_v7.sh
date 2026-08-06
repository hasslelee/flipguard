#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/heir"
readonly COMMIT="cb7a7a30bb4d995b50e33bb5cd82ff7434db3656"
readonly BAZELISK="$ROOT/external/v7/tools/bazelisk"
mkdir -p "$STATUS"

$STAGE --provider heir --run-id 0000-bazelisk --stage ENVIRONMENT_CREATE \
  --workload bazelisk-v1.26.0 --cwd . --output-path external/v7/tools/bazelisk -- \
  bash -lc 'mkdir -p external/v7/tools && curl -fL --retry 2 -o external/v7/tools/bazelisk https://github.com/bazelbuild/bazelisk/releases/download/v1.26.0/bazelisk-linux-amd64 && echo "6539c12842ad76966f3d493e8f80d67caa84ec4a000e220d5459833c967c12bc  external/v7/tools/bazelisk" | sha256sum -c - && chmod +x external/v7/tools/bazelisk'

$STAGE --provider heir --run-id 0001-source --stage SOURCE_CHECKOUT \
  --workload official-dot-product-8f --cwd . --output-path external/v7/sources/heir -- \
  bash -lc "git clone --filter=blob:none https://github.com/google/heir external/v7/sources/heir && git -C external/v7/sources/heir checkout --detach $COMMIT && test \"\$(git -C external/v7/sources/heir rev-parse HEAD)\" = $COMMIT"

$STAGE --provider heir --run-id 0002-openfhe-lattigo-e2e --stage ENCRYPTED_VALIDATION \
  --workload official-dot-product-8f --cwd external/v7/sources/heir \
  --source-path external/v7/sources/heir --output-path external/v7/builds/heir -- \
  "$BAZELISK" --output_user_root="$ROOT/external/v7/builds/heir" test \
    --jobs=2 --local_cpu_resources=2 --nocache_test_results --test_output=all \
    //tests/Examples/openfhe/ckks/dot_product_8f:dot_product_8f_test \
    //tests/Examples/lattigo/ckks/dot_product_8f:dotproduct8f_test

$STAGE --provider heir --run-id 0003-output-freeze --stage OUTPUT_NORMALIZATION \
  --workload official-dot-product-8f --cwd . --source-path external/v7/sources/heir \
  --output-path external/v7/outputs/heir/dot-product-8f-v1 -- bash -lc '
    set -euo pipefail
    out=external/v7/outputs/heir/dot-product-8f-v1
    test ! -e "$out"
    mkdir -p "$out/raw_logs"
    cp external/v7/sources/heir/tests/Examples/common/dot_product_8f.mlir "$out/source_graph.mlir"
    find external/v7/builds/heir -path "*/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test/test.log" -exec cp {} "$out/raw_logs/openfhe_test.log" \;
    find external/v7/builds/heir -path "*/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/dotproduct8f_test/test.log" -exec cp {} "$out/raw_logs/lattigo_test.log" \;
    test -s "$out/raw_logs/openfhe_test.log"
    test -s "$out/raw_logs/lattigo_test.log"
    printf "%s\n" "{\"schema_version\":\"flipguard_external_v7_heir_result_v1\",\"provider\":\"HEIR\",\"source_commit\":\"cb7a7a30bb4d995b50e33bb5cd82ff7434db3656\",\"workload\":\"official_dot_product_8f\",\"runtimes\":[\"OpenFHE\",\"Lattigo\"],\"evidence_level\":3,\"decision_rule\":\"NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD\",\"gate_state\":\"NOT_EVALUATED\"}" > "$out/manifest.json"
    (cd "$out" && sha256sum manifest.json source_graph.mlir raw_logs/*.log > SHA256SUMS)
  '

printf '%s\n' "ENCRYPTED_END_TO_END" > "$STATUS/final_state.txt"
