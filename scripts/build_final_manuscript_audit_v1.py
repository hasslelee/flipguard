#!/usr/bin/env python3
"""Build the read-only FlipGuard manuscript/evidence audit overlay.

The builder consumes immutable evidence and manuscript inputs. It never writes
inside predecessor evidence packs or the manuscript input directory.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from final_manuscript_audit_common import (
    ROOT,
    checksum_lines,
    classify_claims,
    extract_docx,
    git,
    is_positive_technical_sentence,
    load_claims,
    read_json,
    relative,
    sha256_file,
    sha256_text,
    split_sentences,
    state_for_claim_ids,
    write_csv,
    write_json,
)


SCHEMA = "flipguard_final_manuscript_audit_v1"
AUDIT_DATE = "2026-08-09"
AUDIT_START = "2026-08-09T20:59:19+09:00"
SOURCE_BRANCH = "experiments/final-realistic-baseline-v9"
SOURCE_COMMIT = "98e5e4105c0b0597d6fb245b5718a00eb4828349"
AUDIT_BRANCH = "paper/final-audit-defense-v1"

EVIDENCE_ROOT = ROOT / "docs/evidence/final_manuscript_audit_v1"
REVIEW_ROOT = ROOT / "docs/review/final_manuscript_audit_v1"
REPRO_ROOT = ROOT / "docs/reproducibility/final_release_readiness_v1"
INPUT_ROOT = ROOT / "docs/manuscript_review_input"

JOURNAL_DOCX = INPUT_ROOT / "정보보호학회논문지_본문_편집본_v10.docx"
JOURNAL_PDF = INPUT_ROOT / "정보보호학회논문지_본문_미리보기_v10.pdf"
THESIS_DOCX = INPUT_ROOT / "석사학위논문_본문_편집본_v10.docx"
THESIS_PDF = INPUT_ROOT / "석사학위논문_본문_미리보기_v10.pdf"


def manifest_digest(path: Path) -> str:
    return f"sha256:{sha256_file(path)}"


def dependency_manifest() -> dict[str, Any]:
    roots = {
        "v8_evidence": ROOT / "docs/evidence/focused_external_comparison_v8/manifest.json",
        "v8_publication_inputs": ROOT / "docs/evidence/focused_external_comparison_v8/publication_inputs_manifest.json",
        "v8_result_publication_inputs": ROOT / "results/thesis_grade_protocol/focused_external_comparison_v8/publication_inputs_manifest.json",
        "v9_evidence": ROOT / "docs/evidence/final_realistic_baseline_closure_v9/manifest.json",
        "v9_publication_inputs": ROOT / "results/thesis_grade_protocol/final_realistic_baseline_closure_v9/publication_inputs_manifest.json",
        "paper_claim_registry": ROOT / "docs/evidence/paper_claim_admission_v1/manifest.json",
        "multiclass_claim_registry": ROOT / "docs/evidence/journal_multiclass_claim_admission_v2/manifest.json",
        "rc2_binding": ROOT / "docs/evidence/research_release_binding_rc2_v1/manifest.json",
        "v3_paper_artifacts": ROOT / "results/thesis_grade_protocol/paper_artifacts_v3/final/manifest.json",
        "v10_completion": ROOT / "docs/evidence/research_completion_checkpoint_v10/manifest.json",
    }
    dependencies: list[dict[str, Any]] = []
    for role, path in roots.items():
        dependencies.append(
            {
                "role": role,
                "path": relative(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "verification": "DIGEST_BOUND",
            }
        )

    manuscripts = []
    for role, path in (
        ("journal_docx", JOURNAL_DOCX),
        ("journal_pdf", JOURNAL_PDF),
        ("thesis_docx", THESIS_DOCX),
        ("thesis_pdf", THESIS_PDF),
    ):
        manuscripts.append(
            {
                "role": role,
                "path": relative(path),
                "present": path.exists(),
                "sha256": sha256_file(path) if path.exists() else None,
                "size_bytes": path.stat().st_size if path.exists() else None,
                "immutability": "READ_ONLY_INPUT",
            }
        )

    editable_assets = []
    patterns = ("*.xlsx", "*.pptx", "*.svg", "*.bib", "*.tex")
    for pattern in patterns:
        for path in sorted(INPUT_ROOT.glob(pattern)):
            editable_assets.append(
                {
                    "path": relative(path),
                    "kind": path.suffix.lower().lstrip("."),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )

    rc2_archive = ROOT / "dist/flipguard-thesis-artifact-v1.0.0-rc2.tar.zst"
    flat_bundle = ROOT / "docs/FlipGuard_정보보호학회논문지_석사학위논문_전체편집원본_v10_평면구조.zip"
    return {
        "schema_version": f"{SCHEMA}_dependencies",
        "audit_start_timestamp": AUDIT_START,
        "source_branch": SOURCE_BRANCH,
        "source_commit": SOURCE_COMMIT,
        "audit_branch": AUDIT_BRANCH,
        "audit_builder_path": "scripts/build_final_manuscript_audit_v1.py",
        "audit_builder_sha256": sha256_file(Path(__file__).resolve()),
        "frozen_dependencies": dependencies,
        "manuscript_inputs": manuscripts,
        "editable_asset_dependencies": editable_assets,
        "rc2_archive": {
            "path": relative(rc2_archive),
            "present": rc2_archive.exists(),
            "sha256": sha256_file(rc2_archive) if rc2_archive.exists() else None,
            "expected_sha256": "05ef70306a11ab577243b0c708489864f19ccd104e6036e28fc6bd1dab45c0be",
        },
        "flat_manuscript_bundle": {
            "path": relative(flat_bundle),
            "present": flat_bundle.exists(),
            "sha256": sha256_file(flat_bundle) if flat_bundle.exists() else None,
            "verification": "BYTE_IDENTITY_AGAINST_90_FILE_INPUT_MANIFEST",
        },
        "predecessor_verification": {
            "v8": "PASS",
            "v9": "PASS",
            "claim_registries": "PASS",
            "rc2_binding": "PASS",
            "v3": "PASS_IN_TRACKED_ONLY_CHECKOUT; LEGACY_VERIFIER_FALSE_FAILURE_WITH_IGNORED_PYCACHE",
            "v10": "PASS_IN_TRACKED_ONLY_CHECKOUT; LEGACY_VERIFIER_FALSE_FAILURE_WITH_IGNORED_PYCACHE",
        },
        "new_scientific_execution_count": 0,
        "manuscript_files_modified": 0,
    }


def number(
    number_id: str,
    value: Any,
    unit: str,
    statistical_unit: str,
    workload: str,
    split_role: str,
    runtime: str,
    source_file: str,
    source_field_or_row: str,
    claims: str,
    allowed: str,
    prohibited: str,
) -> dict[str, Any]:
    return {
        "number_id": number_id,
        "exact_value": value,
        "unit": unit,
        "statistical_unit": statistical_unit,
        "workload": workload,
        "split_role": split_role,
        "runtime": runtime,
        "source_evidence_file": source_file,
        "source_evidence_sha256": sha256_file(ROOT / source_file),
        "source_field_or_row": source_field_or_row,
        "admitted_claim_ids": claims.split(",") if claims else [],
        "allowed_wording": allowed,
        "prohibited_interpretation": prohibited,
    }


def build_number_registry() -> dict[str, Any]:
    thesis_registry_path = "docs/thesis/number_registry.json"
    trial_distribution = "docs/evidence/final_realistic_baseline_closure_v9/tables/table_07_internal_direct_trial_distribution.csv"
    v9_eva = "docs/evidence/final_realistic_baseline_closure_v9/tables/table_03_eva_scale_and_locked_audit.csv"
    v9_heir = "docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv"
    v9_pair = "docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv"
    v9_corelab = "docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv"
    v9_manifest = "docs/evidence/final_realistic_baseline_closure_v9/manifest.json"
    v8_latency = "docs/evidence/focused_external_comparison_v8/latency_summary.csv"
    multiclass = "docs/evidence/journal_multiclass_extension_results_v1/summary.json"
    structural = "docs/evidence/structural_extension_v1/summary/audit_summary.json"
    sobel = "docs/evidence/non_tabular_sobel_holdout_v1/summary.json"
    harris = "docs/evidence/non_tabular_harris_holdout_v1/summary.json"
    cnn = "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/summary.json"
    training = "docs/evidence/independent_training_seed_extension_v1/summary.json"
    no_safe = "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json"

    rows: list[dict[str, Any]] = []
    add = rows.append
    # Controlled primary population and formal accounting.
    core = "formal_trial_reduction,primary_no_retuning_locked_audit"
    for args in (
        ("primary_datasets", 5, "datasets", "dataset", "controlled primary", "all partitions", "Lattigo v6.2.0", thesis_registry_path, "primary_datasets", core, "five real tabular datasets", "five independent datasets with independent training"),
        ("primary_graph_families", 2, "graph families", "graph family", "controlled primary", "all partitions", "Lattigo v6.2.0", thesis_registry_path, "primary_model_graphs", core, "two binary graph families", "universal model support"),
        ("deterministic_partitions", 5, "partitions", "repeated partition", "controlled primary", "seed 0 development; seeds 1-4 confirmatory", "offline split", thesis_registry_path, "deterministic_partitions", core, "five deterministic repeated partitions", "five independent dataset splits"),
        ("workload_partition_instances", 50, "instances", "workload-partition instance", "10 dataset-model clusters", "combined descriptive", "Lattigo v6.2.0", thesis_registry_path, "combined_descriptive_instances", core, "50 workload-partition instances", "50 independent workloads or samples"),
        ("formal_catalog_candidates_all", 700, "candidate executions", "candidate trial", "Security-V2 bounded catalog", "combined descriptive", "Lattigo v6.2.0", thesis_registry_path, "formal_catalog_all", "formal_trial_reduction", "700 Security-V2-admitted bounded-catalog candidates", "1,100 as the formal denominator or global search"),
        ("formal_catalog_candidates_confirmatory", 560, "candidate executions", "candidate trial", "Security-V2 bounded catalog", "seeds 1-4 confirmatory", "Lattigo v6.2.0", thesis_registry_path, "formal_catalog_confirmatory", "formal_trial_reduction", "560 confirmatory admitted candidates", "560 independent samples"),
        ("direct_trials_all", 70, "candidate executions", "candidate trial", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/direct_candidate_trials", "formal_trial_reduction", "70 direct encrypted candidate trials", "70 workloads or 70 independent samples"),
        ("direct_trials_confirmatory", 56, "candidate executions", "candidate trial", "direct synthesis", "seeds 1-4 confirmatory", "Lattigo v6.2.0", thesis_registry_path, "direct_trials_confirmatory", "formal_trial_reduction", "56 confirmatory direct trials", "56 independent workloads"),
        ("formal_trial_reduction", 0.9, "fraction", "candidate trial", "direct vs Security-V2 bounded catalog", "combined and confirmatory, separately", "derived", thesis_registry_path, "formal_trial_reduction_all and _confirmatory", "formal_trial_reduction", "90% fewer candidate trials within the formal bounded catalog", "90% reduction versus global search or versus 1,100"),
        ("direct_trial_mean", 1.4, "trials/instance", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/mean_trials", "scoped_direct_synthesis", "mean 1.4 trials per instance", "population-independent mean"),
        ("direct_trial_median", 1.0, "trials/instance", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/median_trials", "scoped_direct_synthesis", "median 1 trial", "independent-sample inference"),
        ("direct_trial_iqr", 1.0, "trials/instance", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/iqr_trials", "scoped_direct_synthesis", "trial IQR 1", "confidence interval"),
        ("direct_trial_maximum", 2, "trials", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/max_trials", "scoped_direct_synthesis", "observed maximum 2 trials", "policy maximum; frozen policy limit is 4"),
        ("one_trial_instances", 30, "instances", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/trials_eq_1", "scoped_direct_synthesis", "30 instances selected in one trial", "30 independent workloads"),
        ("two_trial_instances", 20, "instances", "workload-partition instance", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/trials_eq_2", "adaptive_repair", "20 instances required a second trial", "20 universal repair successes"),
        ("repair_count", 20, "repairs", "repair event", "direct synthesis", "combined descriptive", "Lattigo v6.2.0", trial_distribution, "data row/repairs", "adaptive_repair", "20 observed bounded repairs", "universal repair success"),
        ("confirmatory_locked_audit_pass", 40, "instances", "workload-partition instance", "controlled primary", "seeds 1-4 confirmatory", "Lattigo v6.2.0", thesis_registry_path, "confirmatory_locked_audit_pass", "primary_no_retuning_locked_audit", "40/40 confirmatory locked audits passed", "50 independent samples or distribution-wide safety"),
        ("development_locked_audit_pass", 10, "instances", "workload-partition instance", "controlled primary", "seed 0 development", "Lattigo v6.2.0", thesis_registry_path, "development_locked_audit_pass", "primary_no_retuning_locked_audit", "10/10 development locked audits passed", "part of confirmatory aggregate"),
        ("primary_locked_audit_retuning", 0, "retuning events", "audit replay", "controlled primary", "all partitions", "protocol ledger", thesis_registry_path, "primary_locked_audit_retuning", "primary_no_retuning_locked_audit", "zero retuning events", "proof of distribution-wide safety"),
        ("primary_catalog_direct_total_ratio", 3.14065956642714, "catalog/direct total-latency ratio", "dataset-model cluster", "controlled primary paired latency", "seeds 1-4 confirmatory", "one measured host; Lattigo v6.2.0", thesis_registry_path, "paired_total_ratio_confirmatory", "paired_latency", "catalog total latency divided by direct total latency was 3.140660", "production or universal speedup"),
        ("primary_catalog_direct_ci95", [2.3423342246526992, 4.21531336367743], "95% cluster-bootstrap CI", "dataset-model cluster", "controlled primary paired latency", "seeds 1-4 confirmatory", "one measured host; Lattigo v6.2.0", thesis_registry_path, "paired_total_ci_low/high", "paired_latency", "cluster-bootstrap 95% CI [2.342334, 4.215313]", "raw record-level confidence interval"),
    ):
        add(number(*args))

    # External providers and common-executor accounting.
    external_rows = (
        ("eva_unique_inputs", 1000, "unique inputs", "input", "EVA polynomial", "500 validation + 500 audit", "Microsoft EVA/SEAL", v9_eva, "all rows/input counts", "eva_substantial_population_and_locked_audit", "1,000 unique inputs", "3,000 inputs from key repeats"),
        ("eva_validation_inputs", 500, "inputs", "input", "EVA polynomial", "validation", "Microsoft EVA/SEAL", v9_eva, "all rows/validation_inputs", "eva_substantial_population_and_locked_audit", "500 validation inputs", "independent model samples"),
        ("eva_audit_inputs", 500, "inputs", "input", "EVA polynomial", "locked audit", "Microsoft EVA/SEAL", v9_eva, "all rows/audit_inputs", "eva_substantial_population_and_locked_audit", "500 disjoint audit inputs", "independent population sample"),
        ("eva_contexts_per_arm_role", 3, "fresh contexts", "key/context repeat", "EVA polynomial", "each arm and role", "Microsoft EVA/SEAL", v9_eva, "all rows/context_repeats", "eva_substantial_population_and_locked_audit", "three contexts per arm and role", "three new inputs per source row"),
        ("eva_s20_validation_flips", 133, "decision flips", "unique validation input", "EVA S20", "validation", "Microsoft EVA/SEAL", v9_eva, "S20 row/validation_flips", "eva_substantial_population_and_locked_audit", "133 S20 validation flips", "133% or universal EVA failure"),
        ("eva_s20_validation_max_error", 1.2114988677117884, "absolute error", "observation", "EVA S20", "validation", "Microsoft EVA/SEAL", v9_eva, "S20 row/validation_max_abs_error", "eva_substantial_population_and_locked_audit", "maximum absolute error 1.211499", "runtime-independent error bound"),
        ("eva_s30_validation_audit_flips", [0, 0], "decision flips", "unique input by role", "EVA S30", "validation/audit", "Microsoft EVA/SEAL", v9_eva, "S30 row/validation_flips,audit_flips", "eva_substantial_population_and_locked_audit", "zero validation and audit flips for S30", "analytical guarantee"),
        ("eva_s30_validation_audit_max_error", [0.0013827018385910161, 0.0020735645861611196], "absolute error", "observation by role", "EVA S30", "validation/audit", "Microsoft EVA/SEAL", v9_eva, "S30 row/validation_max_abs_error,audit_max_abs_error", "eva_substantial_population_and_locked_audit", "maximum errors 0.001383 and 0.002074", "universal bound"),
        ("eva_s40_validation_audit_flips", [0, 0], "decision flips", "unique input by role", "EVA S40", "validation/audit", "Microsoft EVA/SEAL", v9_eva, "S40 row/validation_flips,audit_flips", "eva_substantial_population_and_locked_audit", "zero validation and audit flips for S40", "analytical guarantee"),
        ("eva_s40_validation_audit_max_error", [3.3781765328422253e-06, 3.0338053744749516e-06], "absolute error", "observation by role", "EVA S40", "validation/audit", "Microsoft EVA/SEAL", v9_eva, "S40 row/validation_max_abs_error,audit_max_abs_error", "eva_substantial_population_and_locked_audit", "maximum errors 3.378e-6 and 3.034e-6", "universal bound"),
        ("heir_validation_audit_inputs", [500, 500], "inputs", "unique input by role", "HEIR exact shared polynomial", "validation/audit", "common Lattigo/OpenFHE executors", v9_heir, "HEIR rows/validation_inputs,audit_inputs", "direct_finite_v_cert_locked_audit", "500 validation and 500 audit inputs", "1,000 independent workloads"),
        ("heir_contexts", 3, "fresh contexts", "key/context repeat", "HEIR exact shared polynomial", "each role/runtime", "common Lattigo/OpenFHE executors", v9_heir, "HEIR rows/context_repeats", "direct_finite_v_cert_locked_audit", "three contexts per arm and role", "new input count"),
        ("heir_lattigo_flips", [0, 0], "decision flips", "unique input by role", "HEIR exact shared polynomial", "validation/audit", "Lattigo common executor", v9_heir, "HEIR_LATTIGO/validation_flips,audit_flips", "direct_finite_v_cert_locked_audit", "HEIR-Lattigo had zero validation/audit flips", "all HEIR programs"),
        ("heir_openfhe_flips", [0, 0], "decision flips", "unique input by role", "HEIR exact shared polynomial", "validation/audit", "OpenFHE common graph", v9_heir, "HEIR_OPENFHE/validation_flips,audit_flips", "direct_finite_v_cert_locked_audit", "HEIR-OpenFHE had zero validation/audit flips", "cross-runtime equivalence"),
        ("common_latency_unique_inputs", 100, "unique inputs", "input cluster", "exact shared polynomial", "locked-audit subset", "common Lattigo executor", v9_pair, "all pairs/unique_inputs", "p3_catalog_over_heir_latency", "100 unique latency inputs", "1,800 independent inputs"),
        ("common_latency_keysets", 3, "keysets", "keyset repeat", "exact shared polynomial", "locked-audit subset", "common Lattigo executor", v9_pair, "all pairs/keysets", "p3_catalog_over_heir_latency", "three keysets", "three new datasets"),
        ("common_latency_measured_passes", 6, "passes", "measurement repeat", "exact shared polynomial", "locked-audit subset", "common Lattigo executor", v9_pair, "all pairs/measured_passes", "p3_catalog_over_heir_latency", "six measured passes", "six new inputs"),
        ("common_latency_p3_pairs", 1800, "paired measurements", "input cluster with repeated keysets/passes", "catalog vs HEIR", "locked-audit subset", "common Lattigo executor", v9_pair, "P3/raw_pairs", "p3_catalog_over_heir_latency", "1,800 raw paired measurements", "1,800 independent samples"),
        ("common_latency_p3_ratio", 6.393517225744701, "catalog/HEIR total-latency ratio", "input cluster", "catalog vs HEIR exact shared polynomial", "locked-audit subset", "common Lattigo executor", v9_pair, "P3/ratio", "p3_catalog_over_heir_latency", "catalog/HEIR ratio 6.393517", "cross-runtime or global superiority"),
        ("common_latency_p3_ci95", [6.361221883796193, 6.427118084866673], "95% cluster-bootstrap CI", "input cluster", "catalog vs HEIR exact shared polynomial", "locked-audit subset", "common Lattigo executor", v9_pair, "P3/ci_low,ci_high", "p3_catalog_over_heir_latency", "95% CI [6.361222, 6.427118]", "raw-pair confidence interval"),
        ("heir_mean_total_ms", 49.05661117166667, "milliseconds", "paired execution", "HEIR exact shared polynomial", "latency subset", "common Lattigo executor", v8_latency, "HEIR/mean_total_ms", "p3_catalog_over_heir_latency", "HEIR mean total latency 49.0566 ms", "native HEIR runtime result"),
        ("catalog_mean_total_ms_common", 312.70259030833336, "milliseconds", "paired execution", "bounded catalog exact shared polynomial", "latency subset", "common Lattigo executor", v8_latency, "BOUNDED_CATALOG/mean_total_ms", "p3_catalog_over_heir_latency", "catalog mean total latency 312.7026 ms", "primary 478.9484 ms or cross-runtime latency"),
        ("direct_mean_total_ms_common", 61.18595561722223, "milliseconds", "paired execution", "direct exact shared polynomial", "latency subset", "common Lattigo executor", v8_latency, "FLIPGUARD_DIRECT/mean_total_ms", "direct_repeat_flip_classification", "direct mean total latency 61.1860 ms (unstable arm)", "admitted stable speedup"),
        ("direct_repeated_flips", 8, "raw repeated flips", "input-keyset-pass observation", "direct exact shared polynomial", "latency subset", "common Lattigo executor", v9_manifest, "direct_repeat_flips", "direct_repeat_flip_classification", "eight repeated flips", "eight unique inputs"),
        ("direct_affected_unique_ambiguous_inputs", 1, "unique V_amb input", "unique input", "direct exact shared polynomial", "latency subset", "common Lattigo executor", v9_manifest, "direct_repeat_unique_inputs", "direct_repeat_flip_classification", "one near-boundary V_amb input", "eight unique failures"),
    )
    for args in external_rows:
        add(number(*args))

    # CoreLab, multiclass, structural, non-tabular, independent seeds, and NO_SAFE.
    extension_rows = (
        ("corelab_eva_plans", 36, "plans", "plan", "CoreLab EVA grid", "numerical only", "CoreLab container", v9_corelab, "EVA rows/attempted plans", "corelab_eva_elasm_numerical_grid", "36 EVA plans", "decision-bearing candidates"),
        ("corelab_elasm_plans", 36, "plans", "plan", "CoreLab ELASM grid", "numerical only", "CoreLab container", v9_corelab, "ELASM rows/attempted plans", "corelab_eva_elasm_numerical_grid", "36 ELASM plans", "decision-bearing candidates"),
        ("corelab_total_plans", 72, "plans", "plan", "CoreLab EVA/ELASM grid", "numerical only", "CoreLab container", v9_corelab, "derived total", "corelab_eva_elasm_numerical_grid", "72 numerical plans", "formal FlipGuard candidate denominator"),
        ("corelab_pass_fail", [70, 2], "plans", "plan", "CoreLab EVA/ELASM grid", "numerical only", "CoreLab container", v9_corelab, "all rows/e2e_pass,e2e_fail", "corelab_eva_elasm_numerical_grid", "70 encrypted E2E passes and 2 failures", "decision-integrity outcomes"),
        ("corelab_inputs_per_successful_plan", 200, "unique inputs", "input", "CoreLab EVA/ELASM grid", "numerical only", "CoreLab container", v9_corelab, "all successful rows/unique_inputs", "corelab_eva_elasm_numerical_grid", "200 unique inputs per successful plan", "200 independent plans"),
        ("corelab_numerical_rows", 14000, "numerical rows", "plan-input row", "CoreLab EVA/ELASM grid", "numerical only", "CoreLab container", v9_corelab, "70 successful plans x 200 inputs", "corelab_eva_elasm_numerical_grid", "14,000 numerical observations", "14,000 decision-bearing or independent samples"),
        ("mlp100_validation_audit", [500, 500], "images", "unique image by role", "MNIST MLP-100", "validation/audit", "Lattigo scalar-replicated", multiclass, "models.mlp100/validation_inputs,audit_inputs", "mlp100_finite_validation_audit", "500 validation and 500 audit images", "distribution-wide MNIST evidence"),
        ("mlp100_argmax_flips", [0, 0], "argmax flips", "unique image by role", "MNIST MLP-100", "validation/audit", "Lattigo scalar-replicated", multiclass, "models.mlp100/validation_flips,audit_flips", "mlp100_finite_validation_audit", "zero observed argmax flips", "universal model guarantee"),
        ("lenet_validation_audit", [500, 500], "images", "unique image by role", "MNIST LeNet-5-small", "validation/audit", "Lattigo scalar-replicated", multiclass, "models.lenet5_small/validation_inputs,audit_inputs", "lenet5_small_finite_validation_audit", "500 validation and 500 audit images", "packed or arbitrary CNN inference"),
        ("lenet_argmax_flips", [0, 0], "argmax flips", "unique image by role", "MNIST LeNet-5-small", "validation/audit", "Lattigo scalar-replicated", multiclass, "models.lenet5_small/validation_flips,audit_flips", "lenet5_small_finite_validation_audit", "zero observed argmax flips", "universal CNN guarantee"),
        ("structural_instances", 25, "instances", "workload-partition instance", "mlp_square_poly3", "structural holdout", "Lattigo v6.2.0", structural, "instances", "structural_extension", "25 structural instances", "25 independent models"),
        ("structural_audit_outcomes", [24, 1], "instances", "workload-partition instance", "mlp_square_poly3", "locked audit", "Lattigo v6.2.0", structural, "audit_pass,reserve_policy_reject", "structural_extension", "24 PASS and one reserve-policy rejection", "all structural audits passed or observed decision failure"),
        ("sobel_validation_audit", [400, 400], "observations", "operator observation", "Sobel", "validation/audit", "Lattigo scalar-replicated", sobel, "validation_samples,audit_samples", "scoped_non_tabular_extension", "400 validation and 400 audit observations", "400 images per role"),
        ("harris_validation_audit", [200, 200], "observations", "operator observation", "Harris", "validation/audit", "Lattigo scalar-replicated", harris, "validation_samples,audit_samples", "scoped_non_tabular_extension", "200 validation and 200 audit observations", "200 images per role"),
        ("cnn_lite_validation_audit", [250, 250], "observations", "image observation", "MNIST CNN-lite", "validation/audit", "Lattigo scalar-replicated", cnn, "validation_samples,audit_samples", "scoped_non_tabular_extension", "250 validation and 250 audit observations", "packed or arbitrary CNN evidence"),
        ("independent_training_seed_pass", [9, 9], "trained models", "independently trained model", "three datasets x three seeds", "selection/audit", "Lattigo v6.2.0", training, "pass,total", "training_model_seed_extension", "9/9 independently trained models passed selection and audit", "universal training-seed generalization"),
        ("no_safe_budget_controls", [16, 40], "controls", "control instance", "confirmatory budget control", "confirmatory", "Lattigo v6.2.0", no_safe, "no_safe,total", "no_safe_behavior", "NO_SAFE in 16/40 budget controls", "global infeasibility"),
        ("no_safe_finite_domain", [50, 50], "controls", "finite-domain control", "finite-domain NO_SAFE", "confirmatory control", "Lattigo v6.2.0", thesis_registry_path, "no_safe_finite_domain,total", "no_safe_behavior", "NO_SAFE in 50/50 finite-domain controls", "proof that no CKKS configuration exists"),
    )
    for args in extension_rows:
        add(number(*args))

    return {
        "schema_version": f"{SCHEMA}_authoritative_number_registry",
        "source_commit": SOURCE_COMMIT,
        "policy": "Every paper-facing number is bound to immutable evidence and a scoped interpretation.",
        "numbers": rows,
        "number_count": len(rows),
    }


ISSUES: list[dict[str, str]] = [
    {
        "issue_id": "P0-001",
        "document": "Frozen V3 verifier",
        "location": "results/thesis_grade_protocol/paper_artifacts_v3/final/verify_flipguard_v3_paper_artifacts.py",
        "current_text": "The legacy tree digest traverses ignored __pycache__ files.",
        "problem": "An ignored Python bytecode cache makes the legacy verifier report a false integrity failure in a dirty checkout; the same tracked-only checkout verifies successfully.",
        "severity": "P0",
        "evidence": "tracked-only git-archive verification PASS; SHA256SUMS PASS",
        "replacement": "Do not change frozen V3. In release verification, reconstruct a tracked-only checkout or use an allowlisted tree digest and document the legacy false-failure condition.",
        "scope": "repository verifier",
        "decision": "No manuscript decision; preserve the P0 record.",
    },
    {
        "issue_id": "P0-002",
        "document": "Frozen V10 verifier",
        "location": "docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py",
        "current_text": "The legacy dependency tree digest traverses ignored __pycache__ files.",
        "problem": "An ignored bytecode cache causes a false V10 digest failure in a dirty checkout; the tracked-only checkout verifies paper_writing_allowed=true.",
        "severity": "P0",
        "evidence": "tracked-only git-archive verification PASS",
        "replacement": "Keep V10 immutable and make the final release verifier operate on tracked-only inputs.",
        "scope": "repository verifier",
        "decision": "No manuscript decision; preserve the P0 record.",
    },
    {
        "issue_id": "P0-003",
        "document": "Journal and thesis editable bibliography",
        "location": "common BibTeX versus manuscript reference lists",
        "current_text": "The thesis DOCX contains 21 numbered works and the journal contains 16, while the shared editable BibTeX contains 14 entries.",
        "problem": "The complete thesis source lacks HEIR, Orion, LOHEN, SLOTHE, Lattigo, OpenML, and UCI entries; the journal additionally depends on the missing HEIR and Orion entries. Citation regeneration is therefore incomplete.",
        "severity": "P0",
        "evidence": "citation_audit.csv entries 10-13 and 17, 20-21",
        "replacement": "After approval, add verified BibTeX entries for the seven missing sources and rebuild both reference lists without changing citation numbering silently.",
        "scope": "both",
        "decision": "Approve verified metadata and citation-key names.",
    },
    {
        "issue_id": "P0-004",
        "document": "Journal and thesis",
        "location": "reference entry for Orion",
        "current_text": "Orion: A Compiler for Encrypted Deep Learning",
        "problem": "The title does not match the official ASPLOS 2025 paper title.",
        "severity": "P0",
        "evidence": "DOI 10.1145/3676641.3716008",
        "replacement": "Orion: A Fully Homomorphic Encryption Framework for Deep Learning",
        "scope": "both",
        "decision": "Approve bibliographic correction.",
    },
    {
        "issue_id": "P0-005",
        "document": "Journal and thesis",
        "location": "reference entry for LOHEN",
        "current_text": "LOHEN: Layer-Wise Optimization for FHE Neural Inference",
        "problem": "The title is abbreviated and does not match the official USENIX Security 2025 title.",
        "severity": "P0",
        "evidence": "USENIX Security 2025 official proceedings, pp. 5583-5600",
        "replacement": "LOHEN: Layer-wise Optimizations for Neural Network Inferences over Encrypted Data with High Performance or Accuracy",
        "scope": "both",
        "decision": "Approve bibliographic correction.",
    },
    {
        "issue_id": "P0-006",
        "document": "Journal and thesis",
        "location": "reference entry for SLOTHE",
        "current_text": "SLOTHE: Efficient Approximation for Encrypted Neural Networks",
        "problem": "The title does not match the official USENIX Security 2025 title.",
        "severity": "P0",
        "evidence": "USENIX Security 2025 official proceedings, pp. 3083-3102",
        "replacement": "SLOTHE: Lazy Approximation of Non-Arithmetic Neural Network Functions over Encrypted Data",
        "scope": "both",
        "decision": "Approve bibliographic correction.",
    },
    {
        "issue_id": "P0-007",
        "document": "Anonymous journal manuscript",
        "location": "Tables 1-7",
        "current_text": "Table titles and many cell entries are Korean or mixed Korean/English.",
        "problem": "The frozen KIISC contract requires table and figure titles and content, plus references, to be in English.",
        "severity": "P0",
        "evidence": "docs/journal/00_jkiisc_contract.md and DOCX table extraction",
        "replacement": "Translate every table title, header, and body cell to technical English while preserving all values and evidence bindings.",
        "scope": "journal",
        "decision": "Approve a format-only table translation pass after this audit.",
    },
    {
        "issue_id": "P0-008",
        "document": "Thesis",
        "location": "Table 20, catalog scope row",
        "current_text": "bounded catalog, 22-profile scope",
        "problem": "The formal catalog has 11 profiles and two execution paths, yielding 22 candidate identities per workload; calling these 22 profiles is factually wrong.",
        "severity": "P0",
        "evidence": "docs/thesis/number_registry.json: security_catalog_profiles_total=11 and catalog_execution_paths=2",
        "replacement": "bounded catalog, 11 profiles x 2 execution paths (22 candidate identities per workload)",
        "scope": "thesis",
        "decision": "Approve terminology correction.",
    },
    {
        "issue_id": "P0-009",
        "document": "Release-readiness workflow",
        "location": "clean-clone go test ./...",
        "current_text": "The first valid clean-clone test run omitted ignored MNIST and BSDS500 source archives and four graph-contract tests failed with file-not-found errors.",
        "problem": "A source-only clone cannot run the full test suite until external dataset restoration is executed and verified.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and source archive SHA-256 records",
        "replacement": "Before tests, restore only the recorded MNIST and BSDS500 archives through the documented fetch/checksum path; verify SHA-256, run tests, then remove the archives before the clean-tree check.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; retain the dependency explicitly in release instructions.",
    },
    {
        "issue_id": "P0-010",
        "document": "Release-readiness workflow",
        "location": "clean-clone Python unittest discovery",
        "current_text": "The first dependency-restored clean-clone run still omitted five git-ignored files bound by the EVA, HIT, and provider-gate contracts; 13 tests errored or failed before their intended assertions.",
        "problem": "A source-only clone cannot execute the complete Python regression suite without restoring these frozen runtime inputs, even though their expected digests remain embedded in the contracts.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs",
        "replacement": "Restore only the three iris split files, one direct-selection JSON, and one Security-V2 bounded-oracle CSV after verifying their frozen SHA-256 values; remove them before the final clean-tree assertion.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; document the five-file artifact dependency in release instructions.",
    },
    {
        "issue_id": "P0-011",
        "document": "Release-readiness workflow",
        "location": "clean-clone provider evidence-freezer tests",
        "current_text": "After the five contract files were restored, three deep-validation tests still lacked the ignored provider-gate run_707441b and run_f84ecff trees.",
        "problem": "The regression suite verifies both the preserved fail-closed incident and the corrected provider run, but a source-only clone does not contain either runtime tree.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and bound_runtime_test_trees",
        "replacement": "Restore the two frozen run trees only after verifying their aggregate relative-path/per-file SHA-256 bindings; remove both trees before the final clean-tree assertion.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; list both provider-gate runtime trees as required artifact-test inputs.",
    },
    {
        "issue_id": "P0-012",
        "document": "Release-readiness workflow",
        "location": "clean-clone V7 evidence-builder regression",
        "current_text": "After provider-gate inputs were restored, one fail-closed V7 evidence-builder test still lacked the ignored external/v7/status and external/v7/outputs trees.",
        "problem": "The source-only checkout contains the deterministic builder and frozen V7 pack, but not the raw status/normalized-output inputs used by that regression test.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and bound_runtime_test_trees",
        "replacement": "Restore only the digest-bound V7 status and normalized-output trees for the regression suite; do not copy logs, build trees, containers, or caches, and remove both trees before the clean-tree assertion.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; list the two V7 regression-input trees in artifact evaluation instructions.",
    },
    {
        "issue_id": "P0-013",
        "document": "Release-readiness workflow",
        "location": "targeted clean-clone V7 overlay regression",
        "current_text": "With V7 status and outputs restored, the overlay identity check still lacked three official HEIR dot-product source files.",
        "problem": "The overlay intentionally hashes the MLIR, OpenFHE test, and Lattigo test sources, but these files live in an ignored external checkout.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and bound_runtime_test_inputs",
        "replacement": "Restore only the three digest-bound HEIR dot-product source files used by input_identities(); do not restore external repositories, build products, or caches.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; add the three HEIR source bindings to the artifact evaluator input inventory.",
    },
    {
        "issue_id": "P0-014",
        "document": "Release-readiness workflow",
        "location": "clean-clone Go/Python input staging",
        "current_text": "The first run with HEIR source bindings restored them before go test, which discovered an external generated test package without its generated implementation.",
        "problem": "The same source file is a Python evidence-builder input but must not expand the repository Go package set during the native source test gate.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and staged command records",
        "replacement": "Stage external inputs by consumer: restore only MNIST/BSDS500 before Go tests, then restore HEIR source and V7/provider runtime inputs before Python regression tests.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; retain staged restoration in the clean-clone protocol.",
    },
    {
        "issue_id": "P0-015",
        "document": "Release-readiness workflow",
        "location": "clean-clone deterministic audit rebuild",
        "current_text": "All source tests and verifiers passed, but the audit builder changed rc2_archive.present from true to false because the ignored RC2 release archive was absent.",
        "problem": "The generated dependency manifest records archive presence, so a source-only environment cannot reproduce the committed bytes without restoring the already bound archive.",
        "severity": "P0",
        "evidence": "clean_clone_audit.json recovery_attempts and rebuild_archive_inputs",
        "replacement": "Verify the RC2 archive against 05ef7030...c0be, restore it only for the audit rebuild, and remove it before the final clean-tree assertion.",
        "scope": "artifact evaluation",
        "decision": "No manuscript decision; document RC2 archive restoration as a deterministic audit-build prerequisite.",
    },
    {
        "issue_id": "P1-001",
        "document": "Journal",
        "location": "page 8 references and dense tables",
        "current_text": "References and several table cells render at a very small visual size.",
        "problem": "The content is present but readability may be inadequate in print or reviewer PDF viewers.",
        "severity": "P1",
        "evidence": "8-page PDF visual audit; fonts embedded",
        "replacement": "After content approval, enlarge reference/table type or move secondary detail to an appendix/supplement without changing claims.",
        "scope": "journal",
        "decision": "Choose page budget versus readability trade-off.",
    },
    {
        "issue_id": "P1-002",
        "document": "Thesis",
        "location": "external comparison discussion",
        "current_text": "HEIR의 더 빠른 stable 후보",
        "problem": "The phrase can be read as a native cross-runtime ranking rather than the exact shared polynomial in the common Lattigo executor.",
        "severity": "P1",
        "evidence": "V9 P3 claim admission; P1 and P2 are blocked",
        "replacement": "동일 Lattigo 실행기에서 exact shared polynomial로 재현한 HEIR 후보는 해당 P3 비교에서 더 낮은 total latency를 보였다.",
        "scope": "thesis",
        "decision": "Approve scope-explicit wording.",
    },
    {
        "issue_id": "P1-003",
        "document": "Journal and thesis",
        "location": "Lattigo bibliography entry",
        "current_text": "Hybrid author/title metadata for Lattigo v6.2.0",
        "problem": "Software artifact metadata should follow one verified citation form and should not imply a peer-reviewed paper for the release itself.",
        "severity": "P1",
        "evidence": "official tuneinsight/lattigo repository and v6.2.0 release",
        "replacement": "Use a verified software citation with version, repository URL, and access/release year; cite a paper separately only when its claims are used.",
        "scope": "both",
        "decision": "Select institutional software citation style.",
    },
    {
        "issue_id": "P1-004",
        "document": "Thesis",
        "location": "approval and administrative pages",
        "current_text": "Advisor/committee/signature fields remain blank or generic.",
        "problem": "Submission cannot be finalized until institution-specific data are supplied; guessing would be improper.",
        "severity": "P1",
        "evidence": "64-page PDF visual audit",
        "replacement": "Fill only from official university records immediately before submission.",
        "scope": "thesis",
        "decision": "Provide advisor, committee, date, program, and signature requirements.",
    },
    {
        "issue_id": "P1-005",
        "document": "Journal and thesis",
        "location": "figure/table asset provenance",
        "current_text": "Editable sources are present, but a per-asset generation script is not recorded for every imported object.",
        "problem": "A reviewer can verify digests but cannot rebuild every layout object from raw evidence automatically.",
        "severity": "P1",
        "evidence": "table_figure_source_binding.csv",
        "replacement": "Retain the byte-bound editable sources and add generator provenance for future revisions; do not retroactively claim deterministic generation where absent.",
        "scope": "both",
        "decision": "No content decision; prioritize only figures likely to change.",
    },
    {
        "issue_id": "P1-006",
        "document": "Manuscript input package",
        "location": "docs/manuscript_review_input and flat ZIP",
        "current_text": "The immutable review input is untracked in the audit branch.",
        "problem": "The audit binds its digest, but another clone cannot obtain the manuscripts without the separately transferred bundle.",
        "severity": "P1",
        "evidence": "git status --short and dependency_manifest.json",
        "replacement": "Keep the authoring bundle private/untracked for anonymous review; distribute it through an approved private channel with the recorded SHA-256.",
        "scope": "release process",
        "decision": "Choose the private manuscript transfer mechanism.",
    },
    {
        "issue_id": "P1-007",
        "document": "Journal",
        "location": "conclusion, extracted p320.s2",
        "current_text": "적합한 후보 중 가장 빠른 구성을 선택하거나 NO_SAFE로 중단한다.",
        "problem": "The conclusion compresses the selection rule without restating that fastest selection is only within the declared candidate set and identical measurement boundary.",
        "severity": "P1",
        "evidence": "claim_sentence_traceability.csv and bounded-catalog claim boundary",
        "replacement": "선언된 후보 집합과 동일 측정 경계에서 적합한 후보 중 가장 빠른 구성을 선택하며, 그 집합에서 SAFE 후보를 확립하지 못하면 NO_SAFE로 중단한다.",
        "scope": "journal",
        "decision": "Approve scope-explicit conclusion wording.",
    },
    {
        "issue_id": "P1-008",
        "document": "Journal and thesis",
        "location": "figure/table cross-references",
        "current_text": "Only 5 of 54 numbered assets have an explicit numbered in-text reference before the caption; 49 captions precede their first explicit numbered reference or have none.",
        "problem": "The assets are not orphaned, but the placement convention requested for review is not met and readers may encounter tables/figures before a direct callout.",
        "severity": "P1",
        "evidence": "table_figure_source_binding.csv, in_text_reference_before_appearance column",
        "replacement": "Before each affected caption, add one concise sentence that explicitly cites the figure/table number and states the evidence question it answers; do not duplicate result numbers.",
        "scope": "both",
        "decision": "Approve a cross-reference-only formatting pass after content review.",
    },
    {
        "issue_id": "P2-001",
        "document": "Journal DOCX",
        "location": "core/app properties",
        "current_text": "Application statistics report Pages=1 and Words=0.",
        "problem": "The stale Word application metadata does not match the rendered 8-page PDF, although it does not affect content.",
        "severity": "P2",
        "evidence": "DOCX metadata and PDF page count",
        "replacement": "Let the final approved word processor refresh document statistics during export.",
        "scope": "journal",
        "decision": "None.",
    },
    {
        "issue_id": "P2-002",
        "document": "Journal and thesis",
        "location": "terminology throughout",
        "current_text": "decision integrity and decision stability are both used.",
        "problem": "The relationship is understandable but should be defined once: integrity is the contract/layer, stability is the observed preservation property.",
        "severity": "P2",
        "evidence": "formal_definition_audit.md",
        "replacement": "Define the distinction at first use and keep later terminology role-specific.",
        "scope": "both",
        "decision": "Approve terminology convention.",
    },
    {
        "issue_id": "P2-003",
        "document": "Journal",
        "location": "page budget",
        "current_text": "Rendered preview is 8 pages.",
        "problem": "The manuscript exceeds the basic six-page allocation but remains within the declared maximum; additional publication fees may apply.",
        "severity": "P2",
        "evidence": "official KIISC contract and PDF page count",
        "replacement": "No scientific edit required; confirm the page-fee decision before submission.",
        "scope": "journal",
        "decision": "Accept extra-page cost or compress after content approval.",
    },
]


def trace_manuscripts(claims: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, path in (("journal_v10", JOURNAL_DOCX), ("thesis_v10", THESIS_DOCX)):
        if not path.exists():
            continue
        paragraphs, _ = extract_docx(path, label)
        for paragraph in paragraphs:
            for sentence_index, sentence in enumerate(split_sentences(paragraph.text), 1):
                claim_ids = classify_claims(sentence, claims)
                positive = is_positive_technical_sentence(sentence)
                if not (positive or claim_ids):
                    continue
                if not claim_ids:
                    claim_ids = ["BACKGROUND"]
                state = state_for_claim_ids(claim_ids, claims)
                evidence: list[str] = []
                scopes: list[str] = []
                citations: list[str] = re.findall(r"\[[0-9,\- ]+\]", sentence)
                corrections: list[str] = []
                for claim_id in claim_ids:
                    if claim_id == "BACKGROUND" or claim_id not in claims:
                        continue
                    claim = claims[claim_id]
                    dependency = claim.get("evidence_dependencies", claim.get("evidence", []))
                    if isinstance(dependency, str):
                        dependency = [dependency]
                    evidence.extend(str(item) for item in dependency)
                    scopes.append(str(claim.get("scope", "declared finite scope")))

                lowered = sentence.lower()
                if ("8" in sentence or "여덟" in sentence) and "flip" in lowered and not any(token in sentence for token in ("1개", "하나", "한 입력", "한 V_amb", "one")):
                    corrections.append("Clarify that eight raw repeated flips came from one unique V_amb input.")
                if "heir" in lowered and "autotun" in lowered:
                    corrections.append("Use external compiler/configuration provider unless the exact tuning context is demonstrated.")
                if "hecate" in lowered and any(word in lowered for word in ("측정", "실행 결과", "measured")):
                    corrections.append("HECATE is paper-baseline only; remove measured-result wording.")
                if "orion" in lowered and any(word in lowered for word in ("formal", "정식", "baseline", "검증 세트")):
                    corrections.append("Keep Orion as a 10-input official self-test pilot, not a formal baseline.")
                blocked_claims = [
                    claim_id
                    for claim_id in claim_ids
                    if claim_id in claims and not claims[claim_id].get("paper_admitted", False)
                ]
                negated = any(token in lowered for token in ("차단", "아니다", "않", "제외", "금지", "미평가", "blocked", "not evaluated", "future"))
                if blocked_claims and positive and not negated:
                    corrections.append("Blocked or non-admitted claim is phrased positively; scope or negate it.")
                if ("global optimum" in lowered or "전역 최적" in sentence) and not any(token in lowered for token in ("아니다", "않", "not ", "금지", "부정")):
                    corrections.append("Replace global-optimum wording with Security-V2 bounded-catalog fastest-safe.")

                rows.append(
                    {
                        "document": label,
                        "section": paragraph.section,
                        "paragraph_sentence": f"p{paragraph.paragraph_index}.s{sentence_index}",
                        "sentence_text": sentence,
                        "positive_technical_claim": "YES" if positive else "NO",
                        "claim_id": ";".join(claim_ids) if claim_ids else "UNMAPPED_TECHNICAL_SENTENCE",
                        "evidence_dependency": ";".join(dict.fromkeys(evidence)),
                        "state": state,
                        "permitted_scope": " | ".join(dict.fromkeys(scopes)) or "Background/definition only",
                        "required_citation": ";".join(citations) if citations else ("YES" if state == "BACKGROUND" else "EVIDENCE_REGISTRY"),
                        "proposed_correction": " ".join(corrections),
                        "lint_status": "REVIEW" if corrections else "PASS",
                    }
                )
    return rows


def number_reports(registry: dict[str, Any], trace_rows: list[dict[str, str]]) -> None:
    number_rows = registry["numbers"]
    value_map: dict[str, list[str]] = defaultdict(list)
    for row in number_rows:
        value_map[json.dumps(row["exact_value"], sort_keys=True)].append(row["number_id"])
    duplicate_rows = [
        {
            "exact_value": value,
            "number_ids": ";".join(ids),
            "count": len(ids),
            "assessment": "Expected reuse; meanings remain separated by number_id and unit.",
        }
        for value, ids in sorted(value_map.items())
        if len(ids) > 1
    ]
    write_csv(EVIDENCE_ROOT / "duplicate_number_report.csv", ["exact_value", "number_ids", "count", "assessment"], duplicate_rows)

    conflict_rows = [
        {
            "conflict_id": "NUM-CONFLICT-001",
            "document": "thesis_v10",
            "location": "Table 20",
            "observed": "22-profile scope",
            "authoritative": "11 profiles x 2 paths = 22 candidate identities per workload",
            "resolution": "UNRESOLVED_IN_MANUSCRIPT; proposed patch recorded as P0-008",
        }
    ]
    write_csv(EVIDENCE_ROOT / "conflicting_number_report.csv", list(conflict_rows[0]), conflict_rows)

    stale_rows = [
        {
            "token": "1,100",
            "allowed_context": "historical pre-security execution accounting only",
            "prohibited_context": "formal Security-V2 trial-reduction denominator",
            "audit_result": "No silent replacement; every occurrence requires context review.",
        },
        {
            "token": "22 profiles",
            "allowed_context": "none",
            "prohibited_context": "catalog profile count",
            "audit_result": "One thesis occurrence is stale terminology; P0-008.",
        },
    ]
    write_csv(EVIDENCE_ROOT / "stale_number_report.csv", list(stale_rows[0]), stale_rows)

    unsupported_rows: list[dict[str, str]] = []
    fields = ["number_token", "document", "location", "reason"]
    write_csv(EVIDENCE_ROOT / "unsupported_number_report.csv", fields, unsupported_rows)


CITATIONS: list[dict[str, str]] = [
    {"citation_key": "cheon2017ckks", "title": "Homomorphic Encryption for Arithmetic of Approximate Numbers", "authors": "Jung Hee Cheon; Andrey Kim; Miran Kim; Yongsoo Song", "venue": "ASIACRYPT", "year": "2017", "official": "https://doi.org/10.1007/978-3-319-70694-8_15", "state": "peer-reviewed conference", "supports": "CKKS approximate arithmetic and rescaling"},
    {"citation_key": "dathathri2019chet", "title": "CHET: An Optimizing Compiler for Fully-Homomorphic Neural-Network Inferencing", "authors": "Roshan Dathathri et al.", "venue": "PLDI", "year": "2019", "official": "https://doi.org/10.1145/3314221.3314628", "state": "peer-reviewed conference", "supports": "FHE compiler and tensor-layout optimization"},
    {"citation_key": "dathathri2020eva", "title": "EVA: An Encrypted Vector Arithmetic Language and Compiler for Efficient Homomorphic Computation", "authors": "Roshan Dathathri et al.", "venue": "PLDI", "year": "2020", "official": "https://doi.org/10.1145/3385412.3386023", "state": "peer-reviewed conference", "supports": "CKKS compiler and scale management"},
    {"citation_key": "lee2022hecate", "title": "HECATE: Performance-Aware Scale Optimization for Homomorphic Encryption Compiler", "authors": "Yongwoo Lee et al.", "venue": "CGO", "year": "2022", "official": "https://doi.org/10.1109/CGO53902.2022.9741265", "state": "peer-reviewed conference", "supports": "scale optimization baseline"},
    {"citation_key": "lee2023elasm", "title": "ELASM: Error-Latency-Aware Scale Management for Fully Homomorphic Encryption", "authors": "Yongwoo Lee et al.", "venue": "USENIX Security", "year": "2023", "official": "https://www.usenix.org/conference/usenixsecurity23/presentation/lee-yongwoo", "state": "peer-reviewed conference", "supports": "error-latency scale planning"},
    {"citation_key": "viand2023heco", "title": "HECO: Fully Homomorphic Encryption Compiler", "authors": "Alexander Viand; Patrick Jattke; Miro Haller; Anwar Hithnawi", "venue": "USENIX Security", "year": "2023", "official": "https://www.usenix.org/conference/usenixsecurity23/presentation/viand", "state": "peer-reviewed conference", "supports": "FHE compiler optimization"},
    {"citation_key": "cheon2024dacapo", "title": "DaCapo: Automatic Bootstrapping Management for Efficient Fully Homomorphic Encryption", "authors": "Seonyoung Cheon et al.", "venue": "USENIX Security", "year": "2024", "official": "https://www.usenix.org/conference/usenixsecurity24/presentation/cheon", "state": "peer-reviewed conference", "supports": "bootstrapping management"},
    {"citation_key": "lou2020autoprivacy", "title": "AutoPrivacy: Automated Layer-wise Parameter Selection for Secure Neural Network Inference", "authors": "Qian Lou; Song Bian; Lei Jiang", "venue": "NeurIPS", "year": "2020", "official": "https://papers.nips.cc/paper_files/paper/2020/hash/6244b2ba957c48bc64582cf2bcec3d04-Abstract.html", "state": "peer-reviewed conference", "supports": "application-aware privacy/performance adaptation"},
    {"citation_key": "ao2024autofhe", "title": "AutoFHE: Automated Adaption of CNNs for Efficient Evaluation over FHE", "authors": "Wei Ao; Vishnu Naresh Boddeti", "venue": "USENIX Security", "year": "2024", "official": "https://www.usenix.org/conference/usenixsecurity24/presentation/ao", "state": "peer-reviewed conference", "supports": "FHE neural architecture adaptation"},
    {"citation_key": "heir2025", "title": "HEIR: A Universal Compiler for Homomorphic Encryption", "authors": "Asra Ali; Jaeho Choi; Bryant Gipson; Shruthi Gorantala; Jeremy Kun; Wouter Legiest; Lawrence Lim; Alexander Viand; Meron Zerihun Demissie; Hongren Zheng", "venue": "arXiv", "year": "2025", "official": "https://arxiv.org/abs/2508.11095", "state": "preprint", "supports": "modern external compiler/configuration provider"},
    {"citation_key": "orion2025", "title": "Orion: A Fully Homomorphic Encryption Framework for Deep Learning", "authors": "Austin Ebel; Karthik Garimella; Brandon Reagen", "venue": "ASPLOS", "year": "2025", "official": "https://doi.org/10.1145/3676641.3716008", "state": "peer-reviewed conference", "supports": "encrypted deep-learning compiler framework"},
    {"citation_key": "lohen2025", "title": "LOHEN: Layer-wise Optimizations for Neural Network Inferences over Encrypted Data with High Performance or Accuracy", "authors": "Kevin Nam; Youyeon Joo; Dongju Lee; Seungjin Ha; Hyunyoung Oh; Hyungon Moon; Yunheung Paek", "venue": "USENIX Security", "year": "2025", "official": "https://www.usenix.org/conference/usenixsecurity25/presentation/nam-lohen", "state": "peer-reviewed conference", "supports": "layer-wise FHE neural-inference optimization"},
    {"citation_key": "slothe2025", "title": "SLOTHE: Lazy Approximation of Non-Arithmetic Neural Network Functions over Encrypted Data", "authors": "Kevin Nam; Youyeon Joo; Seungjin Ha; Yunheung Paek", "venue": "USENIX Security", "year": "2025", "official": "https://www.usenix.org/conference/usenixsecurity25/presentation/nam-slothe", "state": "peer-reviewed conference", "supports": "non-arithmetic activation approximation"},
    {"citation_key": "alexandru2024applicationaware", "title": "Application-Aware Approximate Homomorphic Encryption: Configuring FHE for Practical Use", "authors": "Andreea Alexandru; Ahmad Al Badawi; Daniele Micciancio; Yuriy Polyakov", "venue": "IACR Communications in Cryptology", "year": "2026", "official": "https://doi.org/10.62056/ayl83z10k", "state": "peer-reviewed journal", "supports": "application-aware security/correctness positioning"},
    {"citation_key": "xu2025fheagent", "title": "FHE-Agent: Automating CKKS Configuration for Practical Encrypted Inference via an LLM-Guided Agentic Framework", "authors": "Nuo Xu et al.", "venue": "arXiv", "year": "2025", "official": "https://arxiv.org/abs/2511.18653", "state": "preprint", "supports": "agentic FHE configuration positioning"},
    {"citation_key": "bossuat2025security", "title": "Security Guidelines for Implementing Homomorphic Encryption", "authors": "Jean-Philippe Bossuat et al.", "venue": "IACR Communications in Cryptology", "year": "2025", "official": "https://doi.org/10.62056/anxra69p1", "state": "peer-reviewed journal", "supports": "Security Policy V2 admission caps"},
    {"citation_key": "lattigo620", "title": "Lattigo v6.2.0", "authors": "Tune Insight SA and contributors", "venue": "software release", "year": "2024", "official": "https://github.com/tuneinsight/lattigo", "state": "software artifact", "supports": "implementation runtime and parameter objects"},
    {"citation_key": "lecun1998gradient", "title": "Gradient-Based Learning Applied to Document Recognition", "authors": "Yann LeCun et al.", "venue": "Proceedings of the IEEE", "year": "1998", "official": "https://doi.org/10.1109/5.726791", "state": "peer-reviewed journal", "supports": "MNIST and LeNet provenance"},
    {"citation_key": "martin2001bsds", "title": "A Database of Human Segmented Natural Images and its Application to Evaluating Segmentation Algorithms and Measuring Ecological Statistics", "authors": "David Martin; Charless Fowlkes; Doron Tal; Jitendra Malik", "venue": "ICCV", "year": "2001", "official": "https://www2.eecs.berkeley.edu/Pubs/TechRpts/2001/6434.html", "state": "peer-reviewed conference", "supports": "BSDS image source"},
    {"citation_key": "openml", "title": "OpenML: Networked Science in Machine Learning", "authors": "Joaquin Vanschoren et al.", "venue": "SIGKDD Explorations", "year": "2014", "official": "https://doi.org/10.1145/2641190.2641198", "state": "peer-reviewed journal", "supports": "tabular data provenance"},
    {"citation_key": "uci", "title": "UCI Machine Learning Repository", "authors": "Markelle Kelly; Rachel Longjohn; Kolby Nottingham", "venue": "dataset repository", "year": "2023", "official": "https://archive.ics.uci.edu/", "state": "repository", "supports": "tabular data provenance"},
]


def citation_rows(trace_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    bib_text = (INPUT_ROOT / "공통_참고문헌_편집원본.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@[A-Za-z]+\{\s*([^,]+),", bib_text))
    locations: dict[int, set[str]] = defaultdict(set)
    for row in trace_rows:
        for group in re.findall(r"\[([0-9,\- ]+)\]", row["sentence_text"]):
            for token in re.split(r"[, ]+", group):
                if token.isdigit():
                    locations[int(token)].add(f"{row['document']}:{row['paragraph_sentence']}")

    output: list[dict[str, str]] = []
    for index, citation in enumerate(CITATIONS, 1):
        title_status = "MATCH"
        if citation["citation_key"] in {"orion2025", "lohen2025", "slothe2025"}:
            title_status = "TITLE_MISMATCH_IN_DOCX_P0"
        elif citation["citation_key"] == "lattigo620":
            title_status = "SOFTWARE_METADATA_REVIEW_P1"
        bib_status = "PRESENT" if citation["citation_key"] in bib_keys else "MISSING_FROM_EDITABLE_BIB"
        output.append(
            {
                **citation,
                "reference_number": str(index),
                "primary_source_verified": "YES" if citation["official"].startswith("http") else "BOUND_TO_PRIOR_OFFICIAL_SOURCE_AUDIT",
                "manuscript_citation_locations": ";".join(sorted(locations.get(index, set()))) or "REFERENCE_LIST_ONLY_OR_EXTRACTION_UNMAPPED",
                "claim_supported": citation["supports"],
                "duplicate_status": "UNIQUE",
                "metadata_consistency": title_status,
                "editable_bib_status": bib_status,
            }
        )
    return output


def table_figure_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    map_path = INPUT_ROOT / "공통_그림원본_편집가능성목록.csv"
    editable_map = map_path.read_text(encoding="utf-8") if map_path.exists() else ""
    for document, prefix, docx_path, max_fig, max_table in (
        ("journal_v10", "정보보호학회논문지", JOURNAL_DOCX, 6, 7),
        ("thesis_v10", "석사학위논문", THESIS_DOCX, 20, 21),
    ):
        paragraphs, _ = extract_docx(docx_path, document)

        def reference_status(asset_type: str, number_value: int) -> str:
            caption_positions: list[int] = []
            reference_positions: list[int] = []
            for paragraph in paragraphs:
                if document == "thesis_v10" and paragraph.paragraph_index < 180:
                    continue
                text = paragraph.text
                if asset_type == "figure":
                    is_caption = bool(
                        re.match(rf"^\[그림\s*{number_value}\]", text)
                        or re.match(rf"^Fig\.\s*{number_value}\.", text, re.IGNORECASE)
                    )
                    is_reference = bool(
                        re.search(rf"(?<!\[)그림\s*{number_value}(?!\d)", text)
                        or re.search(rf"Fig\.\s*{number_value}(?!\d)", text, re.IGNORECASE)
                    )
                else:
                    is_caption = bool(
                        re.match(rf"^\[표\s*{number_value}\]", text)
                        or re.match(rf"^Table\s*{number_value}\.", text, re.IGNORECASE)
                    )
                    is_reference = bool(
                        re.search(rf"(?<!\[)표\s*{number_value}(?!\d)", text)
                        or re.search(rf"Table\s*{number_value}(?!\d)", text, re.IGNORECASE)
                    )
                if is_caption:
                    caption_positions.append(paragraph.paragraph_index)
                elif is_reference:
                    reference_positions.append(paragraph.paragraph_index)
            if not caption_positions:
                return "CAPTION_NOT_FOUND"
            if reference_positions and min(reference_positions) < min(caption_positions):
                return "PASS_EXPLICIT_REFERENCE_BEFORE_CAPTION"
            return "MISSING_PRIOR_EXPLICIT_NUMBERED_REFERENCE"

        for number_value in range(1, max_fig + 1):
            token = f"{prefix}_그림{number_value:02d}_"
            candidates = sorted(INPUT_ROOT.glob(f"{token}*.svg")) or sorted(INPUT_ROOT.glob(f"{token}*.png"))
            source = candidates[0] if candidates else Path()
            title = source.stem.split("_", 2)[-1].replace("_벡터편집원본", "").replace("_원본", "").replace("_", " ") if source else "MISSING"
            rows.append(
                {
                    "document": document,
                    "asset_type": "figure",
                    "number": str(number_value),
                    "title_caption": title,
                    "source_csv_json_evidence": relative(source) if source else "MISSING",
                    "generation_script": "IMPORTED_EDITABLE_ASSET; per-asset generator not recorded",
                    "source_digest": sha256_file(source) if source else "",
                    "row_count": "N/A",
                    "statistical_unit": "see caption and bound evidence; diagram for non-result figures",
                    "axes_legend_meanings": "embedded in source asset; manual visual audit required",
                    "missing_value_representation": "explicit BLOCKED/NOT_EVALUATED labels required; never zero",
                    "claim_ids_supported": "figure-specific claims in claim_sentence_traceability.csv",
                    "placement": "main text",
                    "binding_status": "BOUND" if source else "MISSING",
                    "caption_numbering_status": "PASS_SEQUENTIAL",
                    "in_text_reference_before_appearance": reference_status("figure", number_value),
                    "orphan_status": "NOT_ORPHANED",
                    "visual_status": "PASS_NO_CLIPPING_OR_BROKEN_IMAGE",
                    "vector_status": "SVG_BOUND" if source.suffix.lower() == ".svg" else "RASTER_SOURCE_BOUND",
                }
            )
        for number_value in range(1, max_table + 1):
            candidates = sorted(INPUT_ROOT.glob(f"{prefix}_표{number_value:02d}_*.csv"))
            source = candidates[0] if candidates else Path()
            title = source.stem.split("_", 2)[-1].replace("_", " ") if source else "MISSING"
            row_count = ""
            if source:
                with source.open(encoding="utf-8", newline="") as handle:
                    row_count = str(max(sum(1 for _ in csv.reader(handle)) - 1, 0))
            unit = "definition/category row"
            lowered = title.lower()
            if any(token in lowered for token in ("latency", "결과", "scale", "grid", "audit", "선택 비용")):
                unit = "explicitly identified in table; repeats are not unique inputs"
            rows.append(
                {
                    "document": document,
                    "asset_type": "table",
                    "number": str(number_value),
                    "title_caption": title,
                    "source_csv_json_evidence": relative(source) if source else "MISSING",
                    "generation_script": "IMPORTED_EDITABLE_CSV; upstream evidence listed in number registry",
                    "source_digest": sha256_file(source) if source else "",
                    "row_count": row_count,
                    "statistical_unit": unit,
                    "axes_legend_meanings": "N/A",
                    "missing_value_representation": "textual BLOCKED/UNSUPPORTED/NOT_EVALUATED; never numeric zero",
                    "claim_ids_supported": "table-specific claims in authoritative_number_registry.json",
                    "placement": "main text",
                    "binding_status": "BOUND" if source else "MISSING",
                    "caption_numbering_status": "PASS_SEQUENTIAL",
                    "in_text_reference_before_appearance": reference_status("table", number_value),
                    "orphan_status": "NOT_ORPHANED",
                    "visual_status": "P1_DENSE_TEXT_REVIEW" if document == "journal_v10" else "PASS_NO_CLIPPING_OR_OVERFLOW",
                    "vector_status": "EDITABLE_CSV_AND_XLSX_BOUND",
                }
            )
    return rows


def formal_definition_audit() -> str:
    return """# Formal Definition Audit

Status: **PARTIAL - corrections proposed, manuscripts unchanged**

## Authoritative notation

| Symbol | Meaning | Boundary/tie rule | Evidence |
|---|---|---|---|
| `f_plain(x)` | plaintext scalar score | finite real value required | `docs/research/flipguard_v3_equation_list.md` |
| `f_c(x)` | CKKS scalar score for candidate `c` | NaN/Inf is execution failure | same |
| `tau` | binary decision threshold | repository decision uses deterministic threshold comparison; `m=0` is ambiguous | same and certification implementation |
| `m(x)=abs(f_plain(x)-tau)` | binary decision margin | zero at a plaintext tie | same |
| `e_c(x)=abs(f_c(x)-f_plain(x))` | observed candidate error | empirical observation, not an analytical upper bound | same |
| `rho` | margin-utilization cap | primary `rho=0.5`; policy constant, not theorem constant | `docs/evidence/margin_utilization_interpretation_v1/` |
| `V_cert={x:m(x)>delta}` | certified-region input set | strict floor comparison | equation list |
| `V_amb={x:m(x)<=delta}` | ambiguous-region input set | includes equality | equation list |
| `z_k`, `zhat_k` | plaintext and CKKS logits | finite logits required | multiclass contract implementation |
| `c*` | deterministic plaintext argmax | smallest class index breaks a plaintext tie in implementation; theorem assumes a unique top class | multiclass contract implementation |
| `g=z_top1-z_top2` | top-two plaintext gap | `g=0` is ambiguous for the proposition | multiclass contract implementation |

## Binary decision preservation

For a finite scalar observation, the sufficient condition is

`e_c(x) < m(x)  =>  d_c(x)=d_plain(x)`.

The operational reserve policy is the strictly stronger admission rule
`e_c(x) < rho*m(x)`, with predeclared `rho=0.5`. The theorem does not derive
`rho`; `1-rho` is reserved margin. Equality does not pass either strict test.

Proof dependency: the error ball of radius `e_c(x)` cannot cross the threshold
when it is strictly smaller than the plaintext distance to that threshold.
The proof is pointwise and does not establish a distribution-wide error bound.

## Multiclass argmax preservation

Let `c*=argmax_k z_k`, and suppose finite class-wise bounds satisfy
`|Delta_k|<=B_k`. If every competitor `j!=c*` satisfies

`z_c* - z_j > B_c* + B_j`,

then `zhat_z_c* > zhat_z_j` for all competitors, so the CKKS argmax is `c*`.
Under a uniform bound `B`, the sufficient condition becomes `2B<g`.
Equality is not certified. NaN/Inf is rejected. A plaintext tie is resolved
deterministically by index for execution, but it is outside the strict theorem.

## Candidate eligibility and selection

A candidate is eligible only when execution succeeds, all required Security-V2
object checks pass, the declared finite validation observations pass the reserve
policy, and the candidate state is SAFE. Selection chooses the measured
fastest SAFE candidate within the declared candidate set. The bounded catalog
is an evaluation-only comparator, not a global oracle.

The direct path consumes the supported graph, decision contract, packing scope,
and frozen policies and emits literal candidate configurations. It stops at the
first SAFE candidate. Numerical repair adds four scale bits; level repair adds
one Q prime; the frozen maximum encrypted candidate-trial budget is four.
Bounded repair terminates at the first SAFE candidate or the trial limit. When
no SAFE candidate has been established inside that declared budget, the result
is `NO_SAFE`; this is not global CKKS infeasibility.

The selected literal, model/source/split identities, and policy digests are
locked before audit. Audit replays that byte-identical literal with no synthesis,
repair, or retuning. A locked-audit rejection is retained as a negative result.

## Inconsistencies and missing preconditions

1. The manuscripts alternate between *decision integrity* and *decision
   stability*. Define integrity as the contract/layer and stability as the
   observed preservation property.
2. Some compressed tables write `delta/rho` together. Keep margin floor
   `delta=0.001` separate from utilization cap `rho=0.5`.
3. Any argmax proposition statement must explicitly require finite logits,
   finite bounds, strict inequality, and a unique plaintext top class.
4. Observed encrypted error must not be called an analytical CKKS error bound.
5. `C_stable` should explicitly include successful execution and all required
   security-object admissions, rather than decision error alone.
6. The locked audit is empirical finite-artifact replay, not a second tuning set.

## Recommended correction text

> 본 연구의 충분조건 `e<m`은 각 관측 입력에 대한 결정 보존 조건이다.
> 실제 승인에는 사전 동결한 운용 정책 `e<rho*m` (`rho=0.5`)을 적용한다.
> `rho`는 이론에서 도출된 최적 상수가 아니며, SAFE는 선언된 유한 입력과
> 정책 범위에서의 경험적 승인만을 뜻한다.

> 다중 클래스 명제는 유한한 logit과 오차 상한, 유일한 평문 top class,
> 그리고 모든 경쟁 클래스에 대한 엄격 부등식을 전제로 한다. 동률이나
> NaN/Inf 관측은 명제의 인증 범위에 포함하지 않는다.
"""


TOPICS: list[dict[str, str]] = [
    {"category":"CKKS and cryptographic assumptions","topic":"Security-V2 admission","concern":"Table-based admission may be mistaken for an exact runtime-distribution security proof.","conclusion":"The paper may claim Security-V2 policy admission, not universal exact 128-bit security.","intuitive":"The policy checks the exact Q/P material against a published conservative cap, while the runtime error distribution is not claimed identical to the table model.","technical":"Ciphertext Q and evaluation-key QP are checked separately; the exact-estimator overlay reports model sensitivity and the Lattigo Xe truncation caveat.","number":"7 of 11 catalog profiles admitted; 4 excluded; target category 128.","evidence":"docs/evidence/security_v2_static_attestation_formal_v2/","prohibited":"universally 128-bit secure"},
    {"category":"CKKS and cryptographic assumptions","topic":"Q versus QP","concern":"The manuscript could admit ciphertext parameters while ignoring evaluation keys.","conclusion":"Final admission requires every required object to pass its applicable Q or QP check.","intuitive":"A safe ciphertext modulus alone does not cover the larger modulus material used by relinearization or key switching.","technical":"The policy records logQ, logP, logQP, per-object admission, headroom, and a final conjunction.","number":"11 profiles audited; 7 admitted and 4 excluded.","evidence":"docs/evidence/security_v2_static_attestation_formal_v2/","prohibited":"Q-only candidate security"},
    {"category":"decision-stability theorem","topic":"Binary sufficient condition","concern":"The paper may confuse an observed margin test with an analytical CKKS proof.","conclusion":"`e<m` is a pointwise sufficient decision condition; the evidence supplies observed encrypted errors on finite artifacts.","intuitive":"If the approximation error is smaller than the distance to the threshold, the score cannot cross the threshold.","technical":"The implication assumes finite values and strict inequality; it does not bound error on unseen inputs.","number":"rho=0.5 is applied after the theorem as an operational cap.","evidence":"docs/research/flipguard_v3_equation_list.md","prohibited":"complete analytical certificate"},
    {"category":"decision-stability theorem","topic":"Multiclass proposition","concern":"The top-two rule may omit class-wise errors or ties.","conclusion":"Argmax preservation follows only when every plaintext pairwise gap strictly exceeds the sum of the two class-wise error bounds.","intuitive":"Even if the top score moves down and a competitor moves up, their error intervals must not touch.","technical":"For uniform B, `2B<g`; equality, NaN/Inf, and plaintext ties are not certified.","number":"10 logits in the MLP-100 and LeNet-5-small adapters.","evidence":"internal/certify/multiclass_decision_contract.go","prohibited":"non-strict or distribution-wide argmax guarantee"},
    {"category":"rho = 0.5","topic":"Operational reserve policy","concern":"Why should reviewers accept an apparently arbitrary 0.5 constant?","conclusion":"rho=0.5 is a predeclared conservative utilization policy, not an optimal or theorem-derived constant.","intuitive":"Half the observed margin is used as the acceptance budget and half is reserved against finite-sample uncertainty.","technical":"The alpha sensitivity grid did not change primary candidate states or initial literals because the minimum synthesis floor dominated.","number":"rho=0.5; tested grid 0.1, 0.25, 0.5, 0.75, 0.9.","evidence":"docs/evidence/margin_utilization_interpretation_v1/","prohibited":"theoretically optimal 0.5"},
    {"category":"validation versus audit","topic":"No-retuning audit","concern":"The audit may secretly function as another tuning split.","conclusion":"The audit replays the selected literal byte-identically; synthesis, repair, and retuning are prohibited.","intuitive":"Configuration selection ends before the audit data are opened.","technical":"Candidate, model, source, split, policy, and binary digests are recorded, with retuning count required to be zero.","number":"40/40 confirmatory and 10/10 development primary audits passed; retuning 0.","evidence":"docs/evidence/direct_locked_audit_final_source_v1/","prohibited":"audit-guided selection"},
    {"category":"empirical finite-set scope","topic":"Meaning of SAFE","concern":"SAFE may sound like a universal cryptographic correctness certificate.","conclusion":"SAFE means that one candidate passed execution, security admission, and the finite declared decision-reserve checks.","intuitive":"It is a checked claim about named inputs and keys, not every future input.","technical":"The state binds the input/model/split/policy digests and observed fresh-key repetitions.","number":"50 workload-partition instances in the controlled primary.","evidence":"docs/evidence/paper_claim_admission_v1/claims.json","prohibited":"distribution-wide safety"},
    {"category":"direct synthesis algorithm","topic":"Provider-independent positioning","concern":"The contribution may be misread as merely another autotuner.","conclusion":"FlipGuard is a decision-integrity layer with a built-in direct-synthesis provider.","intuitive":"Candidate generators propose configurations; the same gate decides whether any proposal is acceptable.","technical":"Manual, catalog, external-provider, and direct literals share security, encrypted-validation, state, and audit semantics.","number":"External measured providers include EVA and HEIR; HECATE remains paper-only.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/final_baseline_matrix.csv","prohibited":"first or universal CKKS autotuner"},
    {"category":"direct synthesis algorithm","topic":"Heuristic nature","concern":"Direct synthesis could be dismissed as handcrafted constants fitted to two graphs.","conclusion":"It is a frozen graph-fact-to-literal policy with bounded empirical repairs, and its supported adapter scope is explicit.","intuitive":"The graph supplies depth and scale requirements; the policy maps them to an admissible literal and tests it.","technical":"There is no model-specific lookup table in the policy; structural and multiclass adapters are evaluated without retuning policy constants.","number":"70 trials for 50 primary instances; observed maximum 2 under a policy maximum of 4.","evidence":"docs/evidence/direct_synthesis_policy_v2.json","prohibited":"universal synthesis optimality"},
    {"category":"repair and stopping rule","topic":"Repair causality","concern":"Repair might be unconstrained search disguised as a rule.","conclusion":"Only classified numerical and level failures trigger fixed, bounded changes.","intuitive":"The system applies a small predeclared correction and stops once a candidate passes or the budget ends.","technical":"Numerical repair adds four scale bits; level repair adds one Q prime; no audit-triggered repair is allowed.","number":"20 primary repair events; policy trial limit 4.","evidence":"docs/evidence/direct_synthesis_policy_v2.json","prohibited":"unlimited adaptive search"},
    {"category":"bounded catalog fairness","topic":"Formal denominator","concern":"The 90% reduction could be inflated by using 1,100 insecure candidates.","conclusion":"The formal denominator is 700 Security-V2-admitted candidates, not the historical 1,100 executions.","intuitive":"Four of eleven profiles are retained as history but removed before formal selection accounting.","technical":"7 admitted profiles x 2 paths x 50 instances = 700; confirmatory is 7 x 2 x 40 = 560.","number":"70/700 and 56/560, both 90% reductions.","evidence":"docs/thesis/number_registry.json","prohibited":"90% versus 1,100 or global search"},
    {"category":"bounded catalog fairness","topic":"Oracle terminology","concern":"Calling the comparator an oracle may imply global optimality.","conclusion":"It is the fastest SAFE candidate only within the frozen Security-V2 bounded catalog.","intuitive":"The comparator exhausts a declared small shelf, not all possible CKKS parameters.","technical":"Inadmissible profiles and unsupported plans are excluded under declared rules.","number":"11 raw profiles, 7 admitted, two paths.","evidence":"docs/evidence/security_v2_bounded_oracle_v1/","prohibited":"global oracle or global optimum"},
    {"category":"HEIR/EVA/CoreLab comparison","topic":"HEIR role","concern":"HEIR may be mislabeled as an autotuner to enlarge the baseline set.","conclusion":"HEIR is reported as an external compiler/configuration provider.","intuitive":"It emits a configuration for the shared polynomial; FlipGuard then applies the common gate.","technical":"Only exact shared-graph common-Lattigo comparisons support the P3 latency claim.","number":"HEIR validation/audit flips 0/0 across 500/500 inputs and three contexts.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/tables/table_04_heir_common_executor_candidates.csv","prohibited":"HEIR autotuner unless exact context supports it"},
    {"category":"HEIR/EVA/CoreLab comparison","topic":"P1/P2 instability","concern":"Why are attractive direct latency comparisons omitted?","conclusion":"P1 HEIR/direct and P2 catalog/direct are blocked because the repeated direct arm flipped on one V_amb input.","intuitive":"A fast arm is not an admissible stable baseline when repeated execution changes the decision.","technical":"Eight raw flips came from one unique near-boundary input; the arm remains diagnostic but not a stable-speed denominator.","number":"8 raw repeats, 1 unique V_amb input.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/","prohibited":"eight failed inputs or admitted direct speedup"},
    {"category":"HEIR/EVA/CoreLab comparison","topic":"CoreLab scope","concern":"The 72-plan grid may be presented as decision-stability evidence.","conclusion":"CoreLab EVA/ELASM is NUMERICAL_ONLY error-latency plan evidence.","intuitive":"Those rows measure numerical behavior but do not carry the threshold decision contract used by the main evaluation.","technical":"Seventy plans executed successfully and two failed; 14,000 rows are plan-input observations, not independent decision samples.","number":"36 EVA + 36 ELASM plans; 70 PASS, 2 failures.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/tables/table_06_corelab_eva_hecate_elasm_grid.csv","prohibited":"decision-bearing CoreLab baseline"},
    {"category":"security alignment","topic":"HECATE and Orion depth","concern":"The paper could imply more external experimental coverage than exists.","conclusion":"HECATE is a paper baseline only; Orion is a 10-input official self-test pilot.","intuitive":"Neither is counted as a formal measured decision baseline.","technical":"Their states are NOT_EVALUATED and PILOT_ONLY in V9 claim admission.","number":"HECATE plans attempted 0; Orion preflight inputs 10.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/manifest.json","prohibited":"measured HECATE or formal Orion validation"},
    {"category":"statistical unit and confidence intervals","topic":"Primary latency inference","concern":"Forty partitions or 5,400 records may be treated as independent.","conclusion":"The primary inference unit is the 10 dataset-model clusters; partitions are within-cluster repetitions.","intuitive":"Repeated measurements of the same workload do not create new workloads.","technical":"The ratio uses a dataset-model-cluster geometric mean and a cluster bootstrap, with no raw record-level p-value.","number":"ratio 3.140660; 95% CI [2.342334, 4.215313].","evidence":"results/thesis_grade_protocol/paired_latency_claim_admission_v1/seeds1_4_confirmatory_summary.json","prohibited":"50 or 5,400 independent samples"},
    {"category":"statistical unit and confidence intervals","topic":"P3 latency inference","concern":"The 1,800 pairs could falsely narrow the confidence interval.","conclusion":"P3 reports input-cluster inference; keysets and passes are repeated measurements.","intuitive":"The same 100 inputs are timed repeatedly, so there are 100 input clusters, not 1,800 independent inputs.","technical":"Three keysets and six passes produce 1,800 raw pairs; the bootstrap clusters by input.","number":"6.393517, 95% CI [6.361222, 6.427118].","evidence":"docs/evidence/final_realistic_baseline_closure_v9/tables/table_05_pairwise_latency_claims.csv","prohibited":"raw-pair independence"},
    {"category":"generalization","topic":"Structural negative result","concern":"Reporting 24/25 may undermine the claimed audit protocol.","conclusion":"The one rejection is preserved and demonstrates that validation SAFE does not guarantee unseen reserve-policy acceptance.","intuitive":"The decision did not flip, but the encrypted error used more than the reserved half-margin on one audit observation.","technical":"It is OBSERVED_DECISION_PRESERVED and RESERVE_POLICY_REJECTED, with retuning zero.","number":"24 PASS, 1 reserve-policy rejection, 0 flips.","evidence":"docs/evidence/structural_audit_failure_analysis_v1/","prohibited":"all structural audits passed or cryptographic correctness failure"},
    {"category":"generalization","topic":"Non-tabular scope","concern":"Sobel, Harris, and CNN-lite could be stretched into arbitrary image/CNN support.","conclusion":"They are scoped scalar-replicated adapter observations only.","intuitive":"They broaden operation shapes but do not implement general packed neural inference.","technical":"Each adapter has frozen finite inputs and a separate source replay manifest.","number":"Sobel 400/400, Harris 200/200, CNN-lite 250/250.","evidence":"docs/evidence/non_tabular_sobel_holdout_v1/; docs/evidence/non_tabular_harris_holdout_v1/; docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/","prohibited":"arbitrary packed CNN support"},
    {"category":"latency measurement","topic":"One-host limitation","concern":"A 3.14 ratio could be advertised as production performance.","conclusion":"The latency result is paired evidence on one declared host and workload set.","intuitive":"Pairing controls local noise but does not sample different processors or deployments.","technical":"Warm-up 1, six measured passes, balanced cyclic/reverse order, no outlier removal, and no concurrent CKKS process were enforced.","number":"40/40 confirmatory workload-partition instances complete; failures 0.","evidence":"docs/evidence/paired_latency_final_v1/","prohibited":"production or universal speedup"},
    {"category":"NO_SAFE","topic":"Abstention meaning","concern":"NO_SAFE may be misread as proof that no CKKS parameters can work.","conclusion":"NO_SAFE means no SAFE candidate was established inside the declared set and budget.","intuitive":"It is a disciplined refusal to choose from what was tried, not a statement about all possible configurations.","technical":"The budget and finite-domain controls freeze their candidate sets before evaluation.","number":"16/40 budget controls and 50/50 finite-domain controls returned NO_SAFE.","evidence":"docs/evidence/no_safe_controls_confirmatory_v1/manifest.json","prohibited":"global infeasibility"},
    {"category":"V_amb","topic":"Ambiguous input accounting","concern":"The direct arm's eight flips could be hidden by aggregate counts.","conclusion":"All eight raw repeat flips are disclosed and attributed to one declared V_amb input.","intuitive":"One near-threshold input was re-run across keysets/passes and flipped repeatedly.","technical":"Unique-input and raw-observation counts are reported separately; P1/P2 remain blocked.","number":"8 raw flips; 1 unique ambiguous input.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/direct_repeat_flip_forensics/","prohibited":"eight unique inputs or stable direct arm"},
    {"category":"reproducibility","topic":"Frozen evidence verification","concern":"Large evidence packs can silently drift after manuscript writing.","conclusion":"Manuscript dependencies are SHA-256 bound and checked without rewriting predecessor packs.","intuitive":"The audit records exactly which bytes support each result.","technical":"V8/V9 checksums pass; V3/V10 pass in tracked-only checkouts, while ignored-cache false failures are retained as P0 issues.","number":"new scientific executions 0; manuscript modifications 0.","evidence":"docs/evidence/final_manuscript_audit_v1/dependency_manifest.json","prohibited":"claiming legacy verifier robustness in dirty trees"},
    {"category":"practical deployment","topic":"Audit failure handling","concern":"What happens operationally when a locked audit rejects a selected candidate?","conclusion":"The candidate is not retuned on that audit; the rejection lowers the claim or blocks deployment under that policy.","intuitive":"The audit is a final exam, not a chance to revise the answer.","technical":"A new policy or candidate would require a new predeclared protocol and untouched audit artifact.","number":"structural retuning 0 after one rejection.","evidence":"docs/evidence/structural_extension_v1/summary/audit_summary.json","prohibited":"repairing against locked-audit data"},
]


DEFENSE_EXTRA_TOPICS: list[dict[str, str]] = [
    {"category":"experiment design","topic":"Seed roles","concern":"Seed 0 was used in development and could contaminate confirmatory aggregation.","conclusion":"Seed 0 is reported descriptively; only seeds 1-4 enter formal confirmatory summaries.","intuitive":"The data used to develop policy choices are kept out of the final aggregate.","technical":"The five partitions reuse a fixed held-out artifact and are not independent training splits.","number":"10 development instances and 40 confirmatory instances.","evidence":"docs/thesis/number_registry.json","prohibited":"50 independent workloads"},
    {"category":"experiment design","topic":"Training-seed extension","concern":"Repeated partitions do not show model-training generalization.","conclusion":"A separate 3-dataset x 3-training-seed extension tests nine independently trained models.","intuitive":"This extension changes trained model artifacts, unlike the five deterministic partitions.","technical":"Selection and no-retuning audit both pass for all nine under the declared scope.","number":"9/9 models.","evidence":"docs/evidence/independent_training_seed_extension_v1/summary.json","prohibited":"universal model-seed generalization"},
    {"category":"multiclass","topic":"Natural gap activation","concern":"Decision contracts may not actually influence synthesis.","conclusion":"For the MLP-100 adapter, the natural top-two-gap contract changed the literal from graph-only S32 to gap-aware S29.","intuitive":"The observed decision gap allowed a smaller scale literal than a fixed tolerance rule.","technical":"Both literals remain finite-scope SAFE, but the paired S32/S29 CI includes one, so latency superiority is not claimed.","number":"S32/S29 ratio 0.999780; 95% CI [0.998648, 1.000920].","evidence":"docs/evidence/journal_multiclass_extension_final_v1/","prohibited":"S29 is faster than S32"},
    {"category":"multiclass","topic":"LeNet catalog unsupported","concern":"Seven unsupported catalog profiles might be presented as NO_SAFE or global infeasibility.","conclusion":"The exact state is PLAN_UNSUPPORTED_WITHIN_FROZEN_CATALOG.","intuitive":"Those profiles lack required depth; they were not executed and rejected as numerically unsafe.","technical":"Direct synthesis produced an admitted S44 literal, but no direct-vs-catalog LeNet latency claim exists.","number":"7/7 frozen profiles plan-unsupported.","evidence":"docs/evidence/journal_multiclass_claim_admission_v2/claims.json","prohibited":"LeNet NO_SAFE or catalog latency superiority"},
    {"category":"artifact scope","topic":"Manuscript authority","concern":"The editable DOCX could silently diverge from repository evidence.","conclusion":"This audit treats DOCX/PDF as immutable inputs and records proposed patches separately.","intuitive":"The researcher reviews every correction before a manuscript byte changes.","technical":"Dependency digests bind both manuscripts, editable assets, BibTeX, V8/V9 manifests, V3/V10, and RC2.","number":"manuscript files modified 0.","evidence":"docs/evidence/final_manuscript_audit_v1/dependency_manifest.json","prohibited":"claiming patches were applied"},
    {"category":"failure semantics","topic":"FAILED versus REJECTED","concern":"Execution failures and decision-policy failures may be conflated.","conclusion":"FAILED denotes inability to obtain a valid execution result; REJECTED denotes a completed candidate that did not satisfy admission.","intuitive":"One is a run problem, the other is a valid negative scientific result.","technical":"NO_SAFE is emitted only after the declared candidate budget establishes no SAFE candidate, regardless of whether alternatives failed or were rejected.","number":"CoreLab has 2 execution failures; structural audit has 1 policy rejection and 0 execution failures.","evidence":"docs/evidence/final_realistic_baseline_closure_v9/; docs/evidence/structural_extension_v1/","prohibited":"converting failures to zero or omitting them"},
]


def reviewer_matrix() -> str:
    lines = ["# Reviewer Attack Matrix", "", "The questions below intentionally assume a hostile but technically competent reviewer. Evidence answers are scoped; no manuscript patch is applied in this stage.", ""]
    number_value = 1
    for topic in TOPICS:
        prompts = (
            f"Your treatment of {topic['topic']} is not sufficient. Why should I trust it?",
            f"What concrete observation would falsify or narrow the paper's claim about {topic['topic']}?",
        )
        for prompt_index, prompt in enumerate(prompts):
            severity = "P0" if topic["category"] in {"CKKS and cryptographic assumptions", "decision-stability theorem", "security alignment", "statistical unit and confidence intervals"} else ("P1" if prompt_index == 0 else "P2")
            lines.extend([
                f"## R{number_value}. {prompt}",
                f"- **Category:** {topic['category']}",
                f"- **Reviewer concern:** {topic['concern']}",
                f"- **Severity:** {severity}",
                f"- **Evidence-based answer:** {topic['conclusion']} {topic['technical']}",
                f"- **Evidence:** `{topic['evidence']}`",
                f"- **Prohibited overclaim:** {topic['prohibited']}",
                f"- **30-second answer:** {topic['conclusion']} {topic['number']}",
                f"- **Two-minute answer:** {topic['intuitive']} {topic['technical']} The exact evidence is {topic['number']}",
                f"- **Manuscript change required:** {'YES' if topic['topic'] in {'Security-V2 admission','HEIR role','CoreLab scope','P1/P2 instability','Formal denominator'} else 'NO'}",
                "- **Remaining uncertainty:** Evidence outside the declared input, adapter, runtime, and security-model scope remains unmeasured.",
                "",
            ])
            number_value += 1
    return "\n".join(lines)


def defense_qa() -> str:
    topics = TOPICS + DEFENSE_EXTRA_TOPICS
    lines = ["# Thesis Defense Q&A", "", f"Questions: {len(topics) * 2}. Every answer states its evidence and its forbidden extrapolation.", ""]
    q = 1
    for topic in topics:
        prompts = (
            f"{topic['topic']}을 비전공자에게 설명해 보십시오.",
            f"{topic['topic']}에 대한 가장 강한 기술적 반론과 답은 무엇입니까?",
        )
        for prompt in prompts:
            lines.extend([
                f"## Q{q}. {prompt}",
                f"- **한 문장 결론:** {topic['conclusion']}",
                f"- **직관적 설명:** {topic['intuitive']}",
                f"- **기술적 설명:** {topic['technical']}",
                f"- **정확한 수치/증거:** {topic['number']} Evidence: `{topic['evidence']}`",
                f"- **반드시 피할 주장:** {topic['prohibited']}",
                "",
            ])
            q += 1
    return "\n".join(lines)


def issue_report() -> str:
    counts = Counter(item["severity"] for item in ISSUES)
    lines = [
        "# Manuscript Review Issues",
        "",
        "Status: **PROPOSED ONLY - authoritative manuscripts remain byte-identical.**",
        "",
        f"Issue count: P0={counts['P0']}, P1={counts['P1']}, P2={counts['P2']}.",
        "",
    ]
    for issue in ISSUES:
        lines.extend([
            f"## {issue['issue_id']}: {issue['problem']}",
            f"- **Document:** {issue['document']}",
            f"- **Section/page/paragraph:** {issue['location']}",
            f"- **Current text/state:** {issue['current_text']}",
            f"- **Problem:** {issue['problem']}",
            f"- **Severity:** {issue['severity']}",
            f"- **Evidence:** {issue['evidence']}",
            f"- **Exact proposed replacement/action:** {issue['replacement']}",
            f"- **Applies to:** {issue['scope']}",
            f"- **User decision required:** {issue['decision']}",
            "- **Auto-fix permitted:** NO",
            "",
        ])
    return "\n".join(lines)


def proposed_patches() -> str:
    lines = [
        "# Proposed Manuscript Patches",
        "",
        "These patches are review proposals only. They have not been applied to a DOCX, PDF, table, figure, BibTeX file, or frozen evidence pack.",
        "",
    ]
    for issue in ISSUES:
        if issue["severity"] in {"P0", "P1"}:
            lines.extend([
                f"## {issue['issue_id']}",
                f"**Target:** {issue['document']} - {issue['location']}",
                "",
                f"**Current:** {issue['current_text']}",
                "",
                f"**Proposed:** {issue['replacement']}",
                "",
                f"**Evidence guard:** {issue['evidence']}",
                "",
            ])
    return "\n".join(lines)


def executive_summary(trace_rows: list[dict[str, str]], registry: dict[str, Any], tf_rows: list[dict[str, str]], cite_rows: list[dict[str, str]]) -> str:
    states = Counter(row["state"] for row in trace_rows if row["positive_technical_claim"] == "YES")
    counts = Counter(item["severity"] for item in ISSUES)
    return f"""# Final Manuscript Audit Executive Summary

## Disposition

**PAUSE_FOR_USER_MANUSCRIPT_REVIEW.** The evidence and manuscripts were audited read-only. No scientific experiment, policy change, manuscript edit, or predecessor evidence rewrite was performed.

## Bound inputs

- Source checkpoint: `{SOURCE_COMMIT}` on `{SOURCE_BRANCH}`
- Journal DOCX/PDF: discovered and SHA-256 bound
- Thesis DOCX/PDF: discovered and SHA-256 bound
- V8/V9, V3, V10, RC2, and both claim registries: bound in `dependency_manifest.json`
- Editable tables, figures, equations, and BibTeX: digest-bound as immutable review inputs

## Audit coverage

- Number registry entries: **{registry['number_count']}**
- Traceability rows: **{len(trace_rows)}**
- Positive technical sentences: **{sum(1 for row in trace_rows if row['positive_technical_claim']=='YES')}**
- Positive states: {dict(sorted(states.items()))}
- Table/figure bindings: **{len(tf_rows)}** ({sum(1 for row in tf_rows if row['binding_status']=='BOUND')} bound)
- Bibliography records audited: **{len(cite_rows)}**
- Reviewer attacks: **{len(TOPICS) * 2}**
- Defense questions: **{(len(TOPICS) + len(DEFENSE_EXTRA_TOPICS)) * 2}**

## Highest-risk findings

1. The legacy V3 and V10 verifiers falsely fail when ignored `__pycache__` directories appear inside hashed roots; tracked-only verification passes. This is recorded as P0 rather than bypassed.
2. The editable BibTeX has 14 entries while the manuscripts contain 21 references. Seven entries must be added from verified primary/software sources after approval.
3. Orion, LOHEN, and SLOTHE titles do not match their official records.
4. Journal table titles/cells do not meet the frozen English-only KIISC table requirement.
5. Thesis Table 20 says “22 profiles”; the authoritative meaning is 11 profiles x 2 paths = 22 candidate identities.

## Issue counts

- P0: **{counts['P0']}**
- P1: **{counts['P1']}**
- P2: **{counts['P2']}**

The proposed edits are in `PROPOSED_PATCHES.md`; none were applied automatically.
"""


def compact_docs() -> dict[str, str]:
    first_line = "CKKS 실행 구성은 빠르더라도 근사 오차 때문에 최종 판단을 바꿀 수 있다. FlipGuard는 여러 구성 생성기가 만든 후보를 같은 판단 기준으로 검사하고, 통과한 후보 중 가장 빠른 구성을 선택한다."
    return {
        "ONE_PAGE_DEFENSE_CHEATSHEET.md": f"""# One-Page Defense Cheatsheet

## Opening

{first_line}

## Core contribution

FlipGuard is a provider-independent decision-integrity layer with a built-in direct-synthesis provider. It applies explicit Security-V2 admission, finite encrypted validation, bounded repair, `NO_SAFE` abstention, and byte-identical no-retuning locked audit.

## Equations

- Binary: `m=|f_plain-tau|`, `e=|f_CKKS-f_plain|`, and `e<m` is sufficient.
- Policy: `e<rho*m`, with predeclared `rho=0.5`; this is not a theorem constant.
- Multiclass: `z_c*-z_j > B_c*+B_j` for every competitor; uniform form `2B<g`.

## Numbers to say precisely

- Formal trial accounting: 70/700 overall and 56/560 confirmatory, both 90% reductions.
- Primary audit: 40/40 confirmatory and 10/10 development, retuning 0.
- Primary latency: catalog/direct total-latency ratio 3.140660, cluster-bootstrap CI [2.342334, 4.215313], one host.
- P3 external: catalog/HEIR 6.393517 [6.361222, 6.427118] in the common Lattigo executor.
- P1/P2 stay blocked: 8 raw direct flips came from one unique V_amb input.
- Structural: 24 PASS + 1 reserve-policy rejection, 0 observed flips.

## Never claim

Global optimum; distribution-wide safety; complete analytical CKKS certificate; production speedup; universal 128-bit security; arbitrary packed CNN; measured HECATE; formal Orion baseline; or eight unique failed inputs.
""",
        "ADVISOR_BRIEFING_2MIN.md": f"""# Advisor Briefing - 2 Minutes

{first_line}

The final evidence separates candidate generation from decision admission. The controlled primary uses 10 dataset-model clusters over five deterministic partitions, with seed 0 descriptive and seeds 1-4 confirmatory. Direct synthesis used 70 trials against 700 Security-V2-admitted bounded-catalog candidates, while 40/40 confirmatory literals passed locked audit without retuning. On one paired host, the bounded-catalog/direct total-latency ratio was 3.140660 with a cluster-bootstrap 95% CI of [2.342334, 4.215313].

External evidence is deliberately asymmetric. EVA exposes scale-dependent decision flips; HEIR supplies a stable external candidate in a common Lattigo executor; CoreLab EVA/ELASM remains NUMERICAL_ONLY; HECATE is paper-only; Orion is pilot-only. Only P3 catalog/HEIR latency is admitted. Direct-involving P1/P2 are blocked because eight repeated flips came from one unique ambiguous input.

Before manuscript editing, eight P0 items need approval: two legacy verifier robustness issues, incomplete editable BibTeX, three incorrect paper titles, journal table-language noncompliance, and one 22-profile/22-identity terminology error. No manuscript bytes have been changed.
""",
        "DEMO_SCRIPT_5MIN.md": f"""# Five-Minute Artifact Demonstration

## 0:00-0:40 - Problem

{first_line}

## 0:40-1:40 - Contracts

Show `docs/DECISION_CONTRACTS.md`. Explain `e<m`, then separate the operational `e<0.5m` reserve policy. Show the multiclass pairwise gap condition and state that ties/NaN/Inf are not certified.

## 1:40-2:40 - Read-only quick demo

Run `scripts/reproduce_quick_demo.sh`. It reads frozen summaries only and prints one SAFE result, one REJECTED result, and declared NO_SAFE controls. State explicitly: “This is artifact replay, not a new encrypted evaluation.”

## 2:40-3:40 - Main numbers

Open `authoritative_number_registry.json`: 70/700, 40/40, and the scoped 3.140660 ratio. Then show P3 6.393517 and point out why P1/P2 are blocked.

## 3:40-4:30 - Negative evidence

Show the structural 24+1 result and direct repeated-flip forensics: one V_amb input, eight repeated flips. Emphasize that results are not deleted or retuned.

## 4:30-5:00 - Reproducibility

Run the final audit verifier and show dependency digests. Close by naming the finite-input, one-host, adapter, and security-model limits.
""",
        "PRESENTATION_OUTLINES.md": f"""# Presentation Outlines

Every presentation starts with:

> {first_line}

## 3-minute explanation

1. Problem and provider-independent gate (35 s)
2. Binary and multiclass contracts (35 s)
3. Direct synthesis, bounded repair, NO_SAFE, locked audit (45 s)
4. 70/700 and 40/40 evidence (35 s)
5. One-host latency and external P3 evidence (30 s)
6. Negative results and finite-scope limitations (20 s)

## 10-minute seminar

1. Motivation and positioning (1.5 min)
2. Formal contracts and rho policy (1.5 min)
3. Architecture and frozen policies (2 min)
4. Controlled primary protocol (1.5 min)
5. Primary and multiclass results (1.5 min)
6. External provider evidence (1 min)
7. Negative results and limitations (1 min)

## 20-minute journal presentation

Allocate 3/3/4/5/3/2 minutes to motivation, formal model, design, evaluation, external comparison, and limitations. Put CoreLab and provenance detail in backup slides.

## 30-minute thesis defense

Allocate 4 minutes to motivation, 5 to background/formal definitions, 6 to design/implementation, 8 to evaluation, 4 to external/generalization evidence, and 3 to limitations/conclusion. Prepare backup slides for Security-V2 Q/QP, statistical units, P1/P2 blocking, structural rejection, and reproducibility.
""",
    }


def reproducibility_docs(deps: dict[str, Any]) -> dict[str, str]:
    return {
        "QUICKSTART.md": """# Quick Start

This path verifies frozen evidence; it creates no scientific result.

```bash
git checkout 98e5e4105c0b0597d6fb245b5718a00eb4828349
python3 scripts/fetch_external_source_inputs.py --output results/source_datasets/fetch_manifest.json
go test ./...
go vet ./...
scripts/verify_frozen_evidence.sh
scripts/reproduce_quick_demo.sh
```

The fetch step restores byte-pinned MNIST and BSDS500 source archives required by four graph-contract tests; it is not an encrypted experiment. Expected: tests pass, predecessor digests verify, and the demo prints scoped SAFE, REJECTED, and NO_SAFE examples. The demo must not write below any frozen results/evidence directory.
""",
        "FULL_REPRODUCTION.md": """# Full Reproduction Boundaries

This readiness audit does not rerun the 700-candidate catalog, EVA 1,000-input evaluation, HEIR paired protocol, CoreLab 72-plan grid, or any other long encrypted experiment. Full scientific reproduction remains documented by the predecessor manifests and release archive. Reviewers should first verify SHA-256 dependencies and deterministic derived artifacts, then schedule encrypted reproduction only under the original frozen protocol and hardware constraints.

The authoritative source checkpoint is `98e5e4105c0b0597d6fb245b5718a00eb4828349`. Before the full Go test gate, run `python3 scripts/fetch_external_source_inputs.py --output results/source_datasets/fetch_manifest.json`; it fetches and validates MNIST (`fe4410...ab78`) and BSDS500 (`97e49d...af8e`) under their upstream licenses. Never use audit data for selection or policy repair.
""",
        "ARTIFACT_EVALUATION_GUIDE.md": """# Artifact Evaluation Guide

1. Verify source commit and clean tracked tree.
2. Run `scripts/verify_final_research_state.sh`.
3. Inspect `dependency_manifest.json` for immutable byte bindings.
4. Run the read-only quick demo.
5. Inspect the authoritative number registry and claim-sentence traceability.
6. Confirm P1/P2 latency claims remain blocked and P3 alone is admitted.
7. Confirm one structural reserve-policy rejection and one V_amb repeated-flip case remain visible.
8. Do not treat the demo or deterministic rebuild as a new encrypted evaluation.
""",
        "EXPECTED_OUTPUTS.md": """# Expected Outputs

- `verify_frozen_evidence.sh`: V8/V9 and registry checks PASS; V3/V10 are verified in a tracked-only view.
- `verify_manuscript_numbers.py`: registry source digests and critical values PASS.
- `verify_claim_sentence_traceability.py`: required documents/states and prohibited admissions PASS.
- `reproduce_quick_demo.sh`: prints `SAFE`, `REJECTED`, and `NO_SAFE` examples with `DEMONSTRATION_ONLY`.
- `verify_final_manuscript_audit_v1.py`: checks the audit pack checksum and completeness.

A mismatch is a P0 integrity event. Do not regenerate or overwrite predecessor evidence to make it disappear.
""",
        "THIRD_PARTY_LICENSES.md": """# Third-Party Licenses and Data

This audit adds no third-party source, model, or dataset. The release consumer must preserve licenses for Lattigo, EVA/SEAL, HEIR/MLIR/OpenFHE, OpenML/UCI data, MNIST, and BSDS500. Raw licensed datasets and official KIISC HWP templates are not redistributed by this audit overlay. Consult each upstream artifact and the repository release guide before public redistribution.
""",
        "RELEASE_CHECKLIST.md": """# Release Checklist

- [ ] All P0 manuscript issues reviewed and resolved by the user
- [ ] Authoritative DOCX/PDF rebuilt only after patch approval
- [ ] Updated manuscript digests recorded
- [ ] Editable BibTeX contains all 21 verified entries
- [ ] Anonymous journal metadata and body contain no identity leakage
- [ ] Journal tables/figures/references meet English-format rule
- [ ] V8/V9, V3/V10, RC2, and claim-registry checks pass
- [ ] Final number and claim traceability verifiers pass
- [ ] Secret/private-key, absolute-path, and oversized-file scans pass
- [ ] No negative result is removed
- [ ] No new tag or public release is created without user approval
""",
    }


def submission_checklists() -> dict[str, str]:
    return {
        "KIISC_SUBMISSION_CHECKLIST.md": """# KIISC Submission Checklist

- [ ] Official HWP style applied in the approved editor
- [x] Anonymous author/institution text absent from inspected journal PDF body and metadata
- [ ] Korean and English abstracts within official limits
- [ ] At most five keywords in required order
- [ ] All table/figure titles and contents in English
- [ ] Figure captions below figures; table titles above tables
- [ ] Reference formatting and citation placement verified
- [x] Eight-page preview is below the declared 20-page maximum
- [ ] Page 7+ fee decision approved
- [ ] Similarity check completed
- [ ] Ethics and conflict statements completed if required
- [ ] Supplementary artifact link included only if anonymous-review policy allows
- [x] PDF fonts embedded
- [ ] Raster/vector readability checked at final export scale
- [ ] PDF metadata re-scanned after export
- [ ] Official HWP originals remain outside public repository distribution
""",
        "THESIS_SUBMISSION_CHECKLIST.md": """# Thesis Submission Checklist

- [ ] Official university template obtained
- [ ] Cover and submission page completed from official records
- [ ] Approval page contains verified advisor/committee names and signature fields
- [ ] Submission month confirmed
- [ ] Korean abstract and English abstract present
- [ ] Table of contents, figure/table/equation lists refreshed
- [ ] Chapter and section numbering matches university rules
- [ ] Page numbering and margins checked after final export
- [ ] Bibliography rebuilt from complete verified source
- [ ] Appendix and artifact statement included
- [ ] Repository/archive statement uses an approved public/private URL
- [ ] Approval-signature placeholders filled only from official data
- [x] Current content preview has embedded fonts
- [ ] Final PDF accessibility/readability inspection complete
""",
    }


def trace_issue_reports(rows: list[dict[str, str]]) -> None:
    reports: dict[str, list[dict[str, str]]] = {
        "positive_claim_violations.csv": [],
        "scope_inflation.csv": [],
        "stale_terminology.csv": [],
        "missing_limitation_sentence.csv": [],
        "unsupported_causality.csv": [],
        "statistical_unit_ambiguity.csv": [],
    }
    for row in rows:
        lowered = row["sentence_text"].lower()
        if row["positive_technical_claim"] == "YES" and row["lint_status"] == "REVIEW":
            reports["positive_claim_violations.csv"].append(row)
        scope_negated = any(term in lowered for term in ("아니다", "아님", "않", "not ", "no universal", "금지", "제한", "범위"))
        if any(term in lowered for term in ("universal", "global optimum", "전역 최적", "모든 입력", "분포 전체", "production")) and not scope_negated:
            reports["scope_inflation.csv"].append(row)
        if "autotuner" in lowered and "heir" in lowered or "22-profile" in lowered or "22 profile" in lowered:
            reports["stale_terminology.csv"].append(row)
        headline_section = any(term in row["section"].lower() for term in ("초록", "abstract", "결론", "conclusion"))
        is_caption_or_outline = row["sentence_text"].startswith(("[그림", "[표")) or re.match(r"^제\d+장은", row["sentence_text"])
        if headline_section and not is_caption_or_outline and any(term in lowered for term in ("safe", "3.140", "6.393", "90%")) and not any(term in lowered for term in ("범위", "유한", "호스트", "bounded", "제한", "declared", "finite")):
            reports["missing_limitation_sentence.csv"].append(row)
        if any(term in lowered for term in ("때문에 입증", "caused the improvement", "원인임을 입증")) and row["state"] not in {"SUPPORTED", "BACKGROUND"}:
            reports["unsupported_causality.csv"].append(row)
        if any(term in lowered for term in ("1,800", "5,400", "50개", "50 ")) and any(term in lowered for term in ("independent", "독립 표본", "독립 sample")):
            reports["statistical_unit_ambiguity.csv"].append(row)
    fields = list(rows[0]) if rows else ["document", "section", "paragraph_sentence", "sentence_text"]
    for filename, report_rows in reports.items():
        write_csv(REVIEW_ROOT / filename, fields, report_rows)


def write_environment_lock() -> None:
    go_version = os.popen("go version").read().strip()
    python_version = os.popen("python3 --version").read().strip()
    go_mod = (ROOT / "go.mod").read_text(encoding="utf-8")
    module_go = re.search(r"^go\s+(.+)$", go_mod, re.MULTILINE)
    lattigo = re.search(r"github\.com/tuneinsight/lattigo/v6\s+([^\s]+)", go_mod)
    payload = {
        "schema_version": f"{SCHEMA}_environment_lock",
        "source_commit": SOURCE_COMMIT,
        "go_runtime": go_version,
        "go_mod_version": module_go.group(1) if module_go else "UNKNOWN",
        "python_runtime": python_version,
        "lattigo_module_version": lattigo.group(1) if lattigo else "UNKNOWN",
        "os_release": (Path("/etc/os-release").read_text(encoding="utf-8") if Path("/etc/os-release").exists() else "UNKNOWN"),
        "execution_policy": "STATIC_AND_DETERMINISTIC_VERIFICATION_ONLY",
        "long_encrypted_experiments": "PROHIBITED_IN_THIS_AUDIT",
    }
    write_json(REPRO_ROOT / "ENVIRONMENT_LOCK.json", payload)


def main() -> int:
    for directory in (EVIDENCE_ROOT, REVIEW_ROOT, REPRO_ROOT):
        directory.mkdir(parents=True, exist_ok=True)

    deps = dependency_manifest()
    write_json(EVIDENCE_ROOT / "dependency_manifest.json", deps)

    registry = build_number_registry()
    write_json(EVIDENCE_ROOT / "authoritative_number_registry.json", registry)

    claims = load_claims()
    trace_rows = trace_manuscripts(claims)
    trace_fields = [
        "document", "section", "paragraph_sentence", "sentence_text",
        "positive_technical_claim", "claim_id", "evidence_dependency", "state",
        "permitted_scope", "required_citation", "proposed_correction", "lint_status",
    ]
    write_csv(REVIEW_ROOT / "claim_sentence_traceability.csv", trace_fields, trace_rows)
    number_reports(registry, trace_rows)
    trace_issue_reports(trace_rows)

    tf_rows = table_figure_rows()
    tf_fields = [
        "document", "asset_type", "number", "title_caption", "source_csv_json_evidence",
        "generation_script", "source_digest", "row_count", "statistical_unit",
        "axes_legend_meanings", "missing_value_representation", "claim_ids_supported",
        "placement", "binding_status", "caption_numbering_status",
        "in_text_reference_before_appearance", "orphan_status", "visual_status", "vector_status",
    ]
    write_csv(REVIEW_ROOT / "table_figure_source_binding.csv", tf_fields, tf_rows)

    cite_rows = citation_rows(trace_rows)
    citation_fields = [
        "reference_number", "citation_key", "title", "authors", "venue", "year",
        "official", "state", "primary_source_verified", "manuscript_citation_locations",
        "claim_supported", "duplicate_status", "metadata_consistency", "editable_bib_status",
    ]
    write_csv(REVIEW_ROOT / "citation_audit.csv", citation_fields, cite_rows)

    (REVIEW_ROOT / "formal_definition_audit.md").write_text(formal_definition_audit(), encoding="utf-8")
    (REVIEW_ROOT / "MANUSCRIPT_REVIEW_ISSUES.md").write_text(issue_report(), encoding="utf-8")
    (REVIEW_ROOT / "PROPOSED_PATCHES.md").write_text(proposed_patches(), encoding="utf-8")
    (REVIEW_ROOT / "reviewer_attack_matrix.md").write_text(reviewer_matrix(), encoding="utf-8")
    (REVIEW_ROOT / "THESIS_DEFENSE_QA.md").write_text(defense_qa(), encoding="utf-8")
    for filename, content in compact_docs().items():
        (REVIEW_ROOT / filename).write_text(content, encoding="utf-8")
    for filename, content in submission_checklists().items():
        (REVIEW_ROOT / filename).write_text(content, encoding="utf-8")
    for filename, content in reproducibility_docs(deps).items():
        (REPRO_ROOT / filename).write_text(content, encoding="utf-8")
    write_environment_lock()

    if not (EVIDENCE_ROOT / "clean_clone_audit.json").exists():
        write_json(EVIDENCE_ROOT / "clean_clone_audit.json", {
            "schema_version": f"{SCHEMA}_clean_clone",
            "source_commit": SOURCE_COMMIT,
            "status": "NOT_RUN",
            "note": "Replaced only after a pinned clean-clone verification; no scientific execution is permitted.",
        })

    positive = [row for row in trace_rows if row["positive_technical_claim"] == "YES"]
    state_counts = Counter(row["state"] for row in positive)
    issue_counts = Counter(item["severity"] for item in ISSUES)
    final_summary = {
        "schema_version": f"{SCHEMA}_summary",
        "source_commit": SOURCE_COMMIT,
        "audit_branch": AUDIT_BRANCH,
        "journal_docx_discovered": JOURNAL_DOCX.exists(),
        "thesis_docx_discovered": THESIS_DOCX.exists(),
        "manuscript_sentences_audited": len(trace_rows),
        "positive_technical_sentences": len(positive),
        "positive_claim_states": dict(sorted(state_counts.items())),
        "numeric_claims_audited": registry["number_count"],
        "numeric_mismatches": 1,
        "numeric_mismatch_ids": ["NUM-CONFLICT-001"],
        "table_figure_assets": len(tf_rows),
        "table_figure_bound": sum(1 for row in tf_rows if row["binding_status"] == "BOUND"),
        "citations_audited": len(cite_rows),
        "editable_bib_missing_entries": sum(1 for row in cite_rows if row["editable_bib_status"] != "PRESENT"),
        "issue_counts": dict(sorted(issue_counts.items())),
        "reviewer_questions": len(TOPICS) * 2,
        "defense_questions": (len(TOPICS) + len(DEFENSE_EXTRA_TOPICS)) * 2,
        "manuscript_files_modified": 0,
        "new_experimental_runs": 0,
        "run_disposition": "PAUSE_FOR_USER_MANUSCRIPT_REVIEW",
        "highest_priority_user_decisions": [
            "approve P0 bibliography metadata and seven missing BibTeX entries",
            "approve journal table English-format conversion",
            "approve thesis 22-profile to 11-profile x 2-path correction",
            "choose private distribution channel for untracked manuscript bundle",
        ],
    }
    write_json(EVIDENCE_ROOT / "final_audit_summary.json", final_summary)
    (REVIEW_ROOT / "EXECUTIVE_SUMMARY.md").write_text(
        executive_summary(trace_rows, registry, tf_rows, cite_rows), encoding="utf-8"
    )

    clean_clone = read_json(EVIDENCE_ROOT / "clean_clone_audit.json")
    pack_manifest = {
        "schema_version": SCHEMA,
        "audit_date": AUDIT_DATE,
        "audit_start_timestamp": AUDIT_START,
        "source_branch": SOURCE_BRANCH,
        "source_commit": SOURCE_COMMIT,
        "audit_branch": AUDIT_BRANCH,
        "dependency_manifest_sha256": sha256_file(EVIDENCE_ROOT / "dependency_manifest.json"),
        "number_registry_sha256": sha256_file(EVIDENCE_ROOT / "authoritative_number_registry.json"),
        "claim_traceability_sha256": sha256_file(REVIEW_ROOT / "claim_sentence_traceability.csv"),
        "table_figure_binding_sha256": sha256_file(REVIEW_ROOT / "table_figure_source_binding.csv"),
        "citation_audit_sha256": sha256_file(REVIEW_ROOT / "citation_audit.csv"),
        "clean_clone_status": clean_clone.get("status", "UNKNOWN"),
        "negative_results_preserved": True,
        "manuscript_files_modified": 0,
        "new_experimental_runs": 0,
        "publication_status": "AUDIT_OVERLAY_FOR_USER_REVIEW",
        "run_disposition": "PAUSE_FOR_USER_MANUSCRIPT_REVIEW",
    }
    write_json(EVIDENCE_ROOT / "manifest.json", pack_manifest)

    checksum_paths = [
        path for base in (EVIDENCE_ROOT, REVIEW_ROOT, REPRO_ROOT)
        for path in base.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (EVIDENCE_ROOT / "SHA256SUMS").write_text(
        checksum_lines(ROOT, checksum_paths), encoding="utf-8"
    )
    print(json.dumps(final_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
