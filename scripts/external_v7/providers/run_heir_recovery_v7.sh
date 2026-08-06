#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/heir"
readonly COMMIT="cb7a7a30bb4d995b50e33bb5cd82ff7434db3656"
readonly OUTPUT="external/v7/outputs/heir/dot-product-8f-v1"

test "$(git -C external/v7/sources/heir rev-parse HEAD)" = "$COMMIT"
test "$(<"$STATUS/0002-openfhe-lattigo-e2e/current_stage.txt")" = PASS
test "$(<"$STATUS/0002-openfhe-lattigo-e2e/exit_code.txt")" = 0

mapfile -t openfhe_logs < <(
  find external/v7/builds/heir \
    -path '*/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test/test.log' \
    -type f -print
)
mapfile -t lattigo_logs < <(
  find external/v7/builds/heir \
    -path '*/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/dotproduct8f_test/test.log' \
    -type f -print
)
test "${#openfhe_logs[@]}" -eq 1
test "${#lattigo_logs[@]}" -eq 1
grep -Fq '[  PASSED  ] 1 test.' "${openfhe_logs[0]}"
grep -Fq 'PASS' "${lattigo_logs[0]}"
test ! -e "$OUTPUT"

$STAGE --provider heir --run-id 0003-output-freeze-retry1 \
  --stage OUTPUT_NORMALIZATION --workload official-dot-product-8f --cwd . \
  --source-path external/v7/sources/heir --output-path "$OUTPUT" -- \
  bash -lc '
    set -euo pipefail
    out=external/v7/outputs/heir/dot-product-8f-v1
    mkdir -p "$out/raw_logs"
    cp external/v7/sources/heir/tests/Examples/common/dot_product_8f.mlir \
      "$out/source_graph.mlir"
    cp external/v7/status/heir/0002-openfhe-lattigo-e2e/run_manifest.json \
      "$out/execution_stage_manifest.json"
    find external/v7/builds/heir \
      -path "*/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test/test.log" \
      -type f -exec cp {} "$out/raw_logs/openfhe_test.log" \;
    find external/v7/builds/heir \
      -path "*/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/dotproduct8f_test/test.log" \
      -type f -exec cp {} "$out/raw_logs/lattigo_test.log" \;
    test "$(find "$out/raw_logs" -maxdepth 1 -type f | wc -l)" -eq 2
    grep -Fq "[  PASSED  ] 1 test." "$out/raw_logs/openfhe_test.log"
    grep -Fq PASS "$out/raw_logs/lattigo_test.log"
    printf "%s\n" "{\"schema_version\":\"flipguard_external_v7_heir_result_v1\",\"provider\":\"HEIR\",\"source_commit\":\"cb7a7a30bb4d995b50e33bb5cd82ff7434db3656\",\"workload\":\"official_dot_product_8f\",\"runtimes\":[\"OpenFHE\",\"Lattigo\"],\"evidence_level\":3,\"encrypted_execution_reused\":true,\"encrypted_execution_run_id\":\"0002-openfhe-lattigo-e2e\",\"decision_rule\":\"NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD\",\"gate_state\":\"NOT_EVALUATED\"}" > "$out/manifest.json"
    (cd "$out" && sha256sum execution_stage_manifest.json manifest.json \
      source_graph.mlir raw_logs/*.log > SHA256SUMS)
  '

printf '%s\n' "ENCRYPTED_END_TO_END" > "$STATUS/final_state.txt"
