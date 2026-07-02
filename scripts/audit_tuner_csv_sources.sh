#!/usr/bin/env bash
set -euo pipefail

sources=(
  "results/logreg_small/ckks_scale_plan_summary.csv"
  "results/ckks_profile_mode_comparison/comparison.csv"
  "results/ckks_policy_comparison/comparison.csv"
  "results/ckks_paper_table/table.csv"
)

base_out="results/ckks_auto_tuner_source_audit"
mkdir -p "${base_out}"

summary="${base_out}/audit_summary.csv"
echo "source_csv,exists,rows,selection_dir,reference_status,fastest_safe_status,latency_only_status,fastest_safe_id,latency_only_id" > "${summary}"

for src in "${sources[@]}"; do
  echo
  echo "================================================================"
  echo "Source: ${src}"
  echo "================================================================"

  if [[ ! -f "${src}" ]]; then
    echo "missing: ${src}"
    echo "${src},false,0,,,,,," >> "${summary}"
    continue
  fi

  rows=$(($(wc -l < "${src}") - 1))
  echo "rows: ${rows}"
  echo
  echo "header:"
  head -n 1 "${src}"
  echo
  echo "first rows:"
  head -n 5 "${src}"

  slug=$(echo "${src}" | sed 's#^results/##' | sed 's#/#__#g' | sed 's#\.csv$##')
  out_dir="${base_out}/${slug}"
  mkdir -p "${out_dir}"

  FLIPGUARD_TUNER_SOURCE_CSV="${src}" \
    go run ./cmd/flipguard -experiment ckks_auto_tuner_from_csv

  cp results/ckks_auto_tuner_from_csv/tuner_candidates.csv "${out_dir}/tuner_candidates.csv"
  cp results/ckks_auto_tuner_from_csv/tuner_selection.csv "${out_dir}/tuner_selection.csv"
  cp results/ckks_auto_tuner_from_csv/source_info.txt "${out_dir}/source_info.txt"

  reference_status=$(awk -F',' 'NR==2 {print $10}' "${out_dir}/tuner_selection.csv")
  fastest_safe_status=$(awk -F',' 'NR==3 {print $10}' "${out_dir}/tuner_selection.csv")
  latency_only_status=$(awk -F',' 'NR==4 {print $10}' "${out_dir}/tuner_selection.csv")
  fastest_safe_id=$(awk -F',' 'NR==3 {print $2}' "${out_dir}/tuner_selection.csv")
  latency_only_id=$(awk -F',' 'NR==4 {print $2}' "${out_dir}/tuner_selection.csv")

  echo "${src},true,${rows},${out_dir},${reference_status},${fastest_safe_status},${latency_only_status},${fastest_safe_id},${latency_only_id}" >> "${summary}"

  echo
  echo "selection:"
  cat "${out_dir}/tuner_selection.csv"
done

echo
echo "================================================================"
echo "Audit summary"
echo "================================================================"
cat "${summary}"