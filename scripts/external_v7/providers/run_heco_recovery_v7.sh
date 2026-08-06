#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
readonly STAGE="python3 scripts/external_v7/run_stage_v7.py"
readonly STATUS="external/v7/status/heco"
readonly COMMIT="cf396f05029930b6476c10266853b2099e23bd32"
readonly OUTPUT="external/v7/outputs/heco/official-benchmark-v1"

test "$(git -C external/v7/sources/heco rev-parse HEAD)" = "$COMMIT"
test "$(<"$STATUS/0004-official-encrypted-benchmark/current_stage.txt")" = PASS
test "$(<"$STATUS/0004-official-encrypted-benchmark/exit_code.txt")" = 0
test "$(find external/v7/builds/heco/src/evaluation/plotting/data/benchmark \
  -maxdepth 1 -type f -name '*.csv' | wc -l)" -eq 24
test ! -e "$OUTPUT"

$STAGE --provider heco --run-id 0005-output-freeze-retry1 \
  --stage OUTPUT_NORMALIZATION --workload official-benchmark --cwd . \
  --source-path external/v7/sources/heco --output-path "$OUTPUT" -- \
  bash -lc '
    set -euo pipefail
    out=external/v7/outputs/heco/official-benchmark-v1
    mkdir -p "$out/csv" "$out/raw_logs"
    cp external/v7/builds/heco/src/evaluation/plotting/data/benchmark/*.csv "$out/csv/"
    cp external/v7/status/heco/0004-official-encrypted-benchmark/run_manifest.json \
      "$out/execution_stage_manifest.json"
    cp external/v7/logs/heco/0004-official-encrypted-benchmark/stdout.log \
      "$out/raw_logs/benchmark_stdout.log"
    test "$(find "$out/csv" -maxdepth 1 -type f -name "*.csv" | wc -l)" -eq 24
    grep -Fq "Running BoxBlurBench (4096) HECO Version" \
      "$out/raw_logs/benchmark_stdout.log"
    grep -Fq "Running RobertsCrossBench (64) HECO Version" \
      "$out/raw_logs/benchmark_stdout.log"
    printf "%s\n" "{\"schema_version\":\"flipguard_external_v7_heco_result_v1\",\"provider\":\"HECO\",\"source_commit\":\"cf396f05029930b6476c10266853b2099e23bd32\",\"implemented_scheme\":\"BFV\",\"ckks_eligible\":false,\"official_harness_raw_decrypted_output\":false,\"evidence_level\":2,\"encrypted_execution_reused\":true,\"encrypted_execution_run_id\":\"0004-official-encrypted-benchmark\",\"terminal_capability\":\"OFFICIAL_PIPELINE_ONLY\",\"gate_state\":\"NOT_EVALUATED\"}" > "$out/manifest.json"
    (cd "$out" && find . -type f ! -name SHA256SUMS -print0 | sort -z | \
      xargs -0 sha256sum > SHA256SUMS)
  '

printf '%s\n' "OFFICIAL_PIPELINE_ONLY" > "$STATUS/final_state.txt"
