#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/heir"
readonly SOURCE="external/v7/sources/heir"
readonly COMMIT="cb7a7a30bb4d995b50e33bb5cd82ff7434db3656"
readonly PATCH="scripts/external_v7/patches/heir-dot-product-output-capture-v1.patch"
readonly BUILD_ROOT="$ROOT/external/v7/builds/heir-output-capture-v1"
readonly OUTPUT="external/v7/outputs/heir/dot-product-8f-output-capture-v1"
readonly BAZELISK="$ROOT/external/v7/tools/bazelisk"

test "$(git -C "$SOURCE" rev-parse HEAD)" = "$COMMIT"
test -z "$(git -C "$SOURCE" status --short)"
test "$(<"$STATUS/0002-openfhe-lattigo-e2e/current_stage.txt")" = PASS
test ! -e "$BUILD_ROOT"
test ! -e "$OUTPUT"
git -C "$SOURCE" apply --check "$ROOT/$PATCH"

$STAGE --provider heir --run-id 0004-output-capture-patch-v1 --stage SOURCE_VERIFY \
  --workload official-dot-product-8f-output-capture --cwd . \
  --source-path "$SOURCE" --input-path "$PATCH" \
  --output-path external/v7/runners/heir-output-capture-patch-v1.json -- \
  bash -lc '
    set -euo pipefail
    git -C external/v7/sources/heir apply \
      "$PWD/scripts/external_v7/patches/heir-dot-product-output-capture-v1.patch"
    git -C external/v7/sources/heir diff --check
    test "$(git -C external/v7/sources/heir diff --numstat | awk "{a+=\$1; d+=\$2} END {print a+0, d+0}")" = "6 0"
    mkdir -p external/v7/runners
    printf "%s\n" \
      "{\"schema_version\":\"flipguard_external_v7_heir_output_patch_v1\",\"base_commit\":\"cb7a7a30bb4d995b50e33bb5cd82ff7434db3656\",\"semantic_change\":false,\"output_only\":true}" \
      > external/v7/runners/heir-output-capture-patch-v1.json
  '

$STAGE --provider heir --run-id 0005-output-capture-e2e-v1 --stage ENCRYPTED_VALIDATION \
  --workload official-dot-product-8f-output-capture --cwd "$SOURCE" \
  --source-path "$SOURCE" --input-path "$PATCH" --output-path "$BUILD_ROOT" -- \
  "$BAZELISK" --output_user_root="$BUILD_ROOT" test \
    --jobs=2 --local_cpu_resources=2 --nocache_test_results --test_output=all \
    //tests/Examples/openfhe/ckks/dot_product_8f:dot_product_8f_test \
    //tests/Examples/lattigo/ckks/dot_product_8f:dotproduct8f_test

mapfile -t openfhe_logs < <(
  find "$BUILD_ROOT" \
    -path '*/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test/test.log' \
    -type f -print
)
mapfile -t lattigo_logs < <(
  find "$BUILD_ROOT" \
    -path '*/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/dotproduct8f_test/test.log' \
    -type f -print
)
test "${#openfhe_logs[@]}" -eq 1
test "${#lattigo_logs[@]}" -eq 1
grep -Eq 'FLIPGUARD_V7_OPENFHE_ACTUAL=[0-9.eE+-]+ EXPECTED=[0-9.eE+-]+' "${openfhe_logs[0]}"
grep -Eq 'FLIPGUARD_V7_LATTIGO_ACTUAL=[0-9.eE+-]+ EXPECTED=[0-9.eE+-]+' "${lattigo_logs[0]}"

$STAGE --provider heir --run-id 0006-output-capture-freeze-v1 \
  --stage OUTPUT_NORMALIZATION --workload official-dot-product-8f-output-capture \
  --cwd . --source-path "$SOURCE" --input-path "$PATCH" --output-path "$OUTPUT" -- \
  bash -lc '
    set -euo pipefail
    out=external/v7/outputs/heir/dot-product-8f-output-capture-v1
    test ! -e "$out"
    mkdir -p "$out/raw_logs"
    openfhe=$(find external/v7/builds/heir-output-capture-v1 \
      -path "*/testlogs/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test/test.log" \
      -type f -print)
    lattigo=$(find external/v7/builds/heir-output-capture-v1 \
      -path "*/testlogs/tests/Examples/lattigo/ckks/dot_product_8f/dotproduct8f_test/test.log" \
      -type f -print)
    cp "$openfhe" "$out/raw_logs/openfhe_test.log"
    cp "$lattigo" "$out/raw_logs/lattigo_test.log"
    cp external/v7/status/heir/0005-output-capture-e2e-v1/run_manifest.json \
      "$out/execution_stage_manifest.json"
    python3 scripts/external_v7/extract_heir_output_capture_v7.py \
      --openfhe-log "$out/raw_logs/openfhe_test.log" \
      --lattigo-log "$out/raw_logs/lattigo_test.log" \
      --output "$out/decrypted_outputs.csv"
    printf "%s\n" \
      "{\"schema_version\":\"flipguard_external_v7_heir_output_capture_v1\",\"provider\":\"HEIR\",\"source_commit\":\"cb7a7a30bb4d995b50e33bb5cd82ff7434db3656\",\"patch_semantic_change\":false,\"workload\":\"official_dot_product_8f\",\"runtimes\":[\"OpenFHE\",\"Lattigo\"],\"evidence_level\":3,\"raw_decrypted_output_available\":true,\"decision_rule\":\"NOT_AVAILABLE_IN_OFFICIAL_WORKLOAD\",\"gate_state\":\"NOT_EVALUATED\"}" \
      > "$out/manifest.json"
    (cd "$out" && sha256sum decrypted_outputs.csv execution_stage_manifest.json \
      manifest.json raw_logs/*.log > SHA256SUMS)
  '

printf '%s\n' "ENCRYPTED_END_TO_END_RAW_OUTPUT" > "$STATUS/final_state.txt"
printf '{"timestamp":"%s","provider":"heir","provider_attempt":3,"state":"COMPLETED_SUPPLEMENTARY_OUTPUT_CAPTURE","encrypted_execution":true,"semantic_change":false}\n' \
  "$(date --iso-8601=seconds)" >> external/v7/status/supplementary_jobs.jsonl

