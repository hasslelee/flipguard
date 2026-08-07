#!/usr/bin/env bash
set -euo pipefail

readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
readonly OUT="external/v8/outputs/heir/shared-polynomial-threshold-v8"
if [[ -f "$OUT/manifest.json" ]]; then
  exit 0
fi
mkdir -p "$OUT"
mkdir -p external/v8/binaries

readonly TRANSLATION="external/v8/translations/heir-shared-polynomial-v8"
if [[ -e "$TRANSLATION" && ! -f "$TRANSLATION/manifest.json" ]]; then
  mkdir -p external/v8/failed_intermediates/heir
  mv "$TRANSLATION" "external/v8/failed_intermediates/heir/translation-$(date -u +%Y%m%dT%H%M%SZ)"
fi
if [[ -e external/v8/sources/heir && ! -f "$TRANSLATION/manifest.json" ]]; then
  mkdir -p external/v8/failed_intermediates/heir
  mv external/v8/sources/heir "external/v8/failed_intermediates/heir/source-$(date -u +%Y%m%dT%H%M%SZ)"
fi

python3 scripts/external_v8/prepare_heir_shared_polynomial_v8.py \
  --output-root "$TRANSLATION"

readonly INPUT_ROOT="docs/evidence/focused_external_comparison_v8/input_manifests/shared_polynomial_threshold_v8"
readonly GO_ROOT="$TRANSLATION/lattigo_v6_2"
(
  cd "$GO_ROOT"
  go mod tidy
  go build -trimpath -o "$ROOT/external/v8/binaries/heir-shared-poly-lattigo-v8" .
)

for role in configuration_validation locked_audit; do
  input="$INPUT_ROOT/$([[ "$role" == configuration_validation ]] && printf configuration_validation.csv || printf locked_audit.csv)"
  final="$OUT/lattigo_${role}.jsonl"
  if [[ ! -f "$final" ]]; then
    partial="$final.partial"
    rm -f "$partial"
    external/v8/binaries/heir-shared-poly-lattigo-v8 \
      --input "$input" --role "$role" --contexts 3 \
      --output "$partial"
    mv "$partial" "$final"
  fi
done

readonly HEIR_ROOT="external/v8/sources/heir"
readonly BAZELISK="external/v7/tools/bazelisk"
"$BAZELISK" --output_user_root="$ROOT/external/v8/builds/heir" build \
  --jobs=2 --local_cpu_resources=2 \
  //tests/Examples/openfhe/ckks/shared_polynomial_v8:runner
readonly OPENFHE_RUNNER="$HEIR_ROOT/bazel-bin/tests/Examples/openfhe/ckks/shared_polynomial_v8/runner"
for role in configuration_validation locked_audit; do
  input="$ROOT/$INPUT_ROOT/$([[ "$role" == configuration_validation ]] && printf configuration_validation.csv || printf locked_audit.csv)"
  final="$OUT/openfhe_${role}.csv"
  if [[ ! -f "$final" ]]; then
    partial="$final.partial"
    rm -f "$partial"
    "$OPENFHE_RUNNER" "$input" "$role" "$partial" 3
    mv "$partial" "$final"
  fi
done

python3 scripts/external_v8/summarize_heir_v8.py --output-root "$OUT"
