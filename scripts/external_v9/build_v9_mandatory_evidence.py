#!/usr/bin/env python3
"""Build the immutable-record V9 literature, flip-forensic, and pairwise overlays."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
V8_OUT = ROOT / "external/v8/outputs"
V9 = ROOT / "docs/evidence/final_realistic_baseline_closure_v9"
FORENSICS = V9 / "direct_repeat_flip_forensics"
THRESHOLD = 0.5
RHO = 0.5
MARGIN_FLOOR = 0.001


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_file(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("geometric mean requires positive values")
    return math.exp(statistics.fmean(math.log(value) for value in values))


def paired_ratio(records: list[dict[str, str]], numerator: str, denominator: str) -> dict[str, object]:
    grouped: dict[tuple[int, int, int], dict[str, dict[str, str]]] = {}
    for row in records:
        key = (int(row["keyset"]), int(row["pass"]), int(row["row_id"]))
        grouped.setdefault(key, {})[row["arm"]] = row
    ratios: dict[int, list[float]] = {}
    incomplete = 0
    for (_, _, row_id), arms in grouped.items():
        if numerator not in arms or denominator not in arms:
            incomplete += 1
            continue
        ratios.setdefault(row_id, []).append(
            float(arms[numerator]["total_ms"]) / float(arms[denominator]["total_ms"])
        )
    by_input = {row_id: geometric_mean(values) for row_id, values in ratios.items()}
    ids = sorted(by_input)
    observed = geometric_mean([by_input[row_id] for row_id in ids])
    generator = random.Random(20260807)
    bootstrap = sorted(
        geometric_mean([by_input[ids[generator.randrange(len(ids))]] for _ in ids])
        for _ in range(5000)
    )
    return {
        "comparison": f"{numerator}/{denominator}",
        "unique_input_clusters": len(ids),
        "raw_pairs": sum(len(values) for values in ratios.values()),
        "incomplete_pair_groups": incomplete,
        "geometric_mean_total_ratio": observed,
        "cluster_bootstrap_ci_low": bootstrap[int(0.025 * len(bootstrap))],
        "cluster_bootstrap_ci_high": bootstrap[int(0.975 * len(bootstrap))],
        "bootstrap_repetitions": len(bootstrap),
    }


def literature_rows() -> list[dict[str, object]]:
    common = {
        "every_related_system_compared": "NO",
        "audit_method": "official publication PDF inspected directly; page numbers are PDF pages",
    }
    return [
        {
            **common,
            "paper": "HECATE",
            "venue_year": "IEEE/ACM CGO 2022",
            "primary_optimization_objective": "joint scale/level management for CKKS latency under an error bound",
            "external_baseline_count": 1,
            "external_baseline_names": "EVA",
            "internal_ablation_count": 2,
            "internal_ablation_names": "PARS; SMSE",
            "workload_application_family_count": 6,
            "benchmark_variant_count": 8,
            "dataset_input_population": "4096 pixels for image processing; 16384 random packed regression inputs; one random MNIST input for DNNs",
            "backend_runtime": "Microsoft SEAL 3.5.9",
            "hardware": "Intel Core i7-8700 3.20 GHz, 6 physical cores, 64 GB RAM",
            "common_runtime": "YES",
            "authors_reimplemented_baselines": "YES; EVA components reimplemented in the HECATE framework",
            "incompatible_system_handling": "Related compilers outside the scale-management question are discussed, not executed in the main panel.",
            "exact_locator": "Sec. VII-A/B, PDF pp. 8-9; Table II; Figs. 7-8",
            "official_url": "https://doi.org/10.1109/CGO53902.2022.9741265",
            "verified_detail": "36 waterlines for each of 8 variants and 4 schemes; Fig. 8 reports 1,152 settings",
            "lesson_for_flipguard": "One aligned external baseline plus mechanism ablations and workload breadth was considered sufficient; common-runtime reimplementation was disclosed.",
        },
        {
            **common,
            "paper": "ELASM",
            "venue_year": "USENIX Security 2023",
            "primary_optimization_objective": "error-latency-aware CKKS scale management",
            "external_baseline_count": 2,
            "external_baseline_names": "EVA; HECATE",
            "internal_ablation_count": 0,
            "internal_ablation_names": "NONE_IN_MAIN_SYSTEM_PANEL",
            "workload_application_family_count": 5,
            "benchmark_variant_count": 10,
            "dataset_input_population": "4096-pixel images; 16384 random regression inputs; one random MNIST input for DNN benchmarks; MNIST subset in LeNet case study",
            "backend_runtime": "Microsoft SEAL 3.5.9",
            "hardware": "Intel Core i7-8700 3.20 GHz, 64 GB RAM; 12 search threads",
            "common_runtime": "YES",
            "authors_reimplemented_baselines": "YES; all three compilers evaluated with the same RNS-CKKS settings/runtime",
            "incompatible_system_handling": "Bootstrapping-based larger applications are stated as outside the evaluated compiler scope.",
            "exact_locator": "Sec. 7.1, PDF pp. 11-14; Figs. 11-15",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity23-lee-yongwoo.pdf",
            "verified_detail": "10 named benchmark variants; ELASM samples 12,000 plans with 12 threads",
            "lesson_for_flipguard": "Two directly aligned external scale managers, ten variants, and same-setting execution carry more weight than an exhaustive compiler census.",
        },
        {
            **common,
            "paper": "DaCapo",
            "venue_year": "USENIX Security 2024",
            "primary_optimization_objective": "automatic CKKS bootstrapping placement",
            "external_baseline_count": 1,
            "external_baseline_names": "Manual placement",
            "internal_ablation_count": 2,
            "internal_ablation_names": "Liveness; Bypass",
            "workload_application_family_count": 6,
            "benchmark_variant_count": 12,
            "dataset_input_population": "six CIFAR-10 DNNs, each with ReLU and SiLU/pooling variants; single-image latency and multi-image accuracy",
            "backend_runtime": "GPU-accelerated HEaaN",
            "hardware": "Intel Core i7-12700; NVIDIA GeForce RTX 3090 24 GB with UVM",
            "common_runtime": "YES_WITHIN_DACAPO_PANEL",
            "authors_reimplemented_baselines": "YES; manual baseline and ablations share the implementation",
            "incompatible_system_handling": "HECATE/ELASM are described as scale-management complements; no direct runtime panel against them.",
            "exact_locator": "Sec. 8.1-8.3, PDF pp. 10-12; Table 3; Figs. 4-5",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity24-cheon.pdf",
            "verified_detail": "Manual/Liveness/Bypass/DaCapo over 12 model-activation variants",
            "lesson_for_flipguard": "A focused system may use one task-matched baseline and two causal ablations rather than force comparison with complementary objectives.",
        },
        {
            **common,
            "paper": "Orion",
            "venue_year": "ACM ASPLOS 2025",
            "primary_optimization_objective": "FHE DNN compilation, packing, scale management, and bootstrap placement",
            "external_baseline_count": 5,
            "external_baseline_names": "Fhelipe; Lee et al.; DaCapo; EVA; HeLayers",
            "internal_ablation_count": 3,
            "internal_ablation_names": "packing/rotation comparison; Fhelipe source-of-improvement breakdown; bootstrap-placement scalability",
            "workload_application_family_count": 5,
            "benchmark_variant_count": 12,
            "dataset_input_population": "MNIST, CIFAR-10, Tiny ImageNet, ImageNet-1k, and PASCAL VOC; validation uses clear/FHE accuracy and representative encrypted inference",
            "backend_runtime": "Lattigo v5.0.2, single-threaded CPU",
            "hardware": "Google Cloud C4, Intel Xeon Platinum 8581C 2.3 GHz, 512 GB RAM",
            "common_runtime": "PARTIAL_BY_SUBQUESTION",
            "authors_reimplemented_baselines": "PARTIAL; Lee et al. and Fhelipe rerun on the same C4 host, while EVA/HeLayers comparisons use their relevant reported or matched panels",
            "incompatible_system_handling": "Baseline changes by research sub-question; there is no one all-system timing panel.",
            "exact_locator": "Sec. 7 and Sec. 8, PDF pp. 10-13; Tables 2-5",
            "official_url": "https://doi.org/10.1145/3676641.3716008",
            "verified_detail": "Table 2 spans MLP/LoLA/LeNet through ResNet-50; Tables 3-5 use different baselines for rotations, source breakdown, and bootstrap scaling",
            "lesson_for_flipguard": "Sub-question-specific panels are legitimate when timing provenance and runtime differences are explicit.",
        },
        {
            **common,
            "paper": "HECO",
            "venue_year": "USENIX Security 2023",
            "primary_optimization_objective": "MLIR-based automatic batching and FHE code optimization",
            "external_baseline_count": 1,
            "external_baseline_names": "Porcupine",
            "internal_ablation_count": 1,
            "internal_ablation_names": "Naive non-batched implementation",
            "workload_application_family_count": 8,
            "benchmark_variant_count": 8,
            "dataset_input_population": "eight example applications over varied vector/image/database problem sizes",
            "backend_runtime": "SEAL-based HECO runtime",
            "hardware": "single evaluation host reported in Sec. 6 setup",
            "common_runtime": "YES_FOR_NAIVE_HECO; DEFENSIBLE_MAPPING_FOR_PORCUPINE",
            "authors_reimplemented_baselines": "YES for naive; Porcupine synthesized comparison where supported",
            "incompatible_system_handling": "Porcupine scalability limits are reported rather than imputed as timings.",
            "exact_locator": "Sec. 6, PDF pp. 12-15; Table 1; Figs. 5-6",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity23-viand.pdf",
            "verified_detail": "Main comparisons are Naive/HECO and, for synthesizable examples, Porcupine",
            "lesson_for_flipguard": "A compiler paper can center one external synthesis baseline and an internal naive control when workload scalability differs.",
        },
        {
            **common,
            "paper": "AutoFHE",
            "venue_year": "USENIX Security 2024",
            "primary_optimization_objective": "joint polynomial architecture and bootstrap-placement search for encrypted CNNs",
            "external_baseline_count": 3,
            "external_baseline_names": "MPCNN; AESPA; REDsec",
            "internal_ablation_count": 2,
            "internal_ablation_names": "evolution/search analyses; layerwise polynomial/bootstrapping design analyses",
            "workload_application_family_count": 4,
            "benchmark_variant_count": 6,
            "dataset_input_population": "VGG11 and ResNet20/32/44 across CIFAR-10/CIFAR-100 model-dataset combinations",
            "backend_runtime": "RNS-CKKS GPU execution; TFHE only for REDsec comparison",
            "hardware": "NVIDIA RTX A6000 for search; search times 13-88 hours depending on network",
            "common_runtime": "NO_FOR_REDSEC; ALIGNED_RNS_CKKS_FOR_MPCNN_AESPA",
            "authors_reimplemented_baselines": "MIXED; matched RNS-CKKS baselines plus paper-reported/different-scheme REDsec",
            "incompatible_system_handling": "Cross-scheme REDsec is labeled separately instead of treated as an identical runtime arm.",
            "exact_locator": "Sec. 5.1-5.3, PDF pp. 10-13; Tables 3-5",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity24-ao.pdf",
            "verified_detail": "Table 3 separates CKKS MPCNN/AESPA from TFHE REDsec; search uses substantial GPU time",
            "lesson_for_flipguard": "Three application-aligned baselines are enough when incompatible schemes and large search budgets are qualified.",
        },
        {
            **common,
            "paper": "LOHEN",
            "venue_year": "USENIX Security 2025",
            "primary_optimization_objective": "layer-wise ciphertext configuration and scheme conversion for encrypted CNN inference",
            "external_baseline_count": 2,
            "external_baseline_names": "FHE-MP-CNN or LoLaT; multi-scheme HEIR/HEIR+Opt panel",
            "internal_ablation_count": 1,
            "internal_ablation_names": "AllRepack",
            "workload_application_family_count": 4,
            "benchmark_variant_count": 6,
            "dataset_input_population": "six model-dataset workloads using ResNet, SqueezeNet, and MobileNetV2 over CIFAR-10 and ImageNet",
            "backend_runtime": "customized Liberate-FHE GPU runtime",
            "hardware": "GPU execution environment described in Sec. 5.1",
            "common_runtime": "YES_WITHIN_EACH_PANEL",
            "authors_reimplemented_baselines": "YES; FHE-MP-CNN rerun in the authors' Liberate-FHE environment and AllRepack built in the same runtime",
            "incompatible_system_handling": "CKKS-only and multi-scheme results are separated into different panels.",
            "exact_locator": "Sec. 5.1-5.4, PDF pp. 12-14; Tables 12-16; Figs. 11-13",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity25-nam-lohen.pdf",
            "verified_detail": "Six workloads; FHE-MP-CNN/LoLaT baselines, AllRepack ablation, and separate multi-scheme comparison",
            "lesson_for_flipguard": "Reimplementation and panel separation are explicit when runtime or cryptographic scheme differs.",
        },
        {
            **common,
            "paper": "SLOTHE",
            "venue_year": "USENIX Security 2025",
            "primary_optimization_objective": "automatic approximation of non-arithmetic neural-network functions",
            "external_baseline_count": 3,
            "external_baseline_names": "function-level approximation set; NEXUS; HEIR/IRON for LUT or MPC panels",
            "internal_ablation_count": 2,
            "internal_ablation_names": "Naive-LA; minErr/minTime modes",
            "workload_application_family_count": 3,
            "benchmark_variant_count": 9,
            "dataset_input_population": "BERT-base, RoBERTa-L, and ALBERT-xxl on QNLI, CoLA, and RACE; 10,000 points for NAF error evaluation",
            "backend_runtime": "Liberate-FHE on GPU; TFHE-rs and MPC implementations only in their corresponding panels",
            "hardware": "Intel Xeon Gold 6326, 1 TB RAM, NVIDIA A6000 40 GB",
            "common_runtime": "PARTIAL_BY_PANEL",
            "authors_reimplemented_baselines": "YES where feasible; NEXUS rerun on one A6000, separate libraries for LUT/MPC baselines",
            "incompatible_system_handling": "Function, full-network, LUT, and MPC comparisons are separate rather than merged into raw latency rankings.",
            "exact_locator": "Sec. 5.1-5.4, PDF pp. 11-15; Figs. 4-7; Tables 5-9",
            "official_url": "https://www.usenix.org/system/files/usenixsecurity25-nam-slothe.pdf",
            "verified_detail": "Three models by three datasets for the full-network panel; multiple function-specific baselines and NEXUS as the network baseline",
            "lesson_for_flipguard": "The baseline set follows the claim unit; incompatible function/runtime comparisons are kept in distinct panels.",
        },
    ]


def build_literature() -> None:
    rows = literature_rows()
    fields = list(rows[0])
    write_csv(V9 / "literature_baseline_practice.csv", fields, rows)
    prose = """# FHE System Baseline-Practice Audit

## Reviewer concern

The number of externally executed systems should be justified by comparable systems-paper practice, not by accumulating tool names. This audit therefore examines eight official publication PDFs and separates external baselines from internal mechanism ablations.

## Literature precedent

The papers do not use one universal all-system panel. HECATE uses one external system (EVA) and two internal ablations across eight variants and 36 waterlines. ELASM uses two aligned external systems across ten variants and 12,000 sampled plans. DaCapo uses a manual baseline and two mechanism ablations across twelve DNN variants, while treating scale managers as complementary. Orion changes the baseline by sub-question. HECO centers a naive control and Porcupine where synthesis is feasible. AutoFHE, LOHEN, and SLOTHE separate incompatible schemes, runtimes, or comparison units into distinct panels. Exact locators and system-specific details are in `literature_baseline_practice.csv`.

## Implementation requirement

FlipGuard's final external comparison must prioritize exact graph/input/runtime equivalence and independently admissible pairwise claims. The main measured set may be smaller than the related-work census. Numerical-only CoreLab plans, native-runtime panels, common-executor exact arms, and paper-reported systems must remain separate evidence tiers.

## Falsification test

The baseline justification fails if it calls paper-reported systems measured, combines incompatible raw runtimes into a speed ranking, counts internal ablations as independent external systems, or claims that representative systems papers execute every related system.

## Answers to the audit questions

1. **Do top systems papers execute every related system?** No. They select baselines by the research sub-question and often discuss incompatible systems without a shared runtime experiment.
2. **How many direct baselines are typical?** The audited main panels use roughly one to three directly aligned external baselines; Orion is the exception only when its separate sub-question panels are aggregated.
3. **What is the external-to-ablation balance?** Mechanism-focused papers commonly pair one or two external references with one or more internal ablations that establish causality.
4. **What matters more, breadth or baseline count?** Exact workload breadth and a defensible comparison unit matter more than the raw number of tool names.
5. **How are different objectives or runtimes handled?** They are separated into dedicated panels, rerun on a common host when feasible, or left as paper-reported context.
6. **Is V8 categorically insufficient?** No. V8 already contains two external decision-bearing providers, a common Lattigo executor, and a 72-plan CoreLab grid. Its scientific weakness is the unclassified direct repeated flips and pairwise overblocking, not merely provider count.
7. **What is the marginal value of HECATE or Orion?** HECATE adds value only if the pinned artifact exposes an official mode on the same CoreLab graph. Orion has higher marginal breadth as a decision-bearing DNN provider, but only after an actual encrypted-logit preflight with bounded ETA.

## Sources

Only official proceedings, DOI landing pages, or author-hosted publication copies were used. No search snippet or blog was used as evidence.
"""
    (V9 / "baseline_practice_audit.md").write_text(prose, encoding="utf-8")
    (ROOT / "docs/research/step_12a_fhe_system_baseline_practice_audit.md").write_text(prose, encoding="utf-8")


def build_forensics() -> None:
    common_path = V8 / "common_executor_records.csv"
    records = csv_file(common_path)
    direct = [row for row in records if row["arm"] == "flipguard_direct"]
    row_records = [row for row in direct if row["row_id"] == "711"]
    affected = [row for row in row_records if row["decision_flip"] == "True"]
    if len(row_records) != 18 or len(affected) != 8:
        raise RuntimeError("unexpected V8 row-711 accounting")
    input_rows = csv_file(V8 / "input_manifests/shared_polynomial_threshold_v8/locked_audit.csv")
    source = next(row for row in input_rows if row["row_id"] == "711")
    plain = float(source["polynomial_score"])
    margin = abs(plain - THRESHOLD)
    if not margin < MARGIN_FLOOR:
        raise RuntimeError("row 711 is not within the frozen ambiguity region")

    provider = json_file(V8 / "provider_candidate_manifests/direct.json")
    candidate_id = affected[0]["candidate_id"]
    common_binary = ROOT / "external/v8/binaries/flipguard-external-v8-common"
    audit_binary = ROOT / "external/v8/binaries/flipguard-audit-candidate-v8-split-identity-v2"
    model = V8 / "workload_contracts/shared_polynomial_model_v8.json"
    workload = V8 / "workload_contracts/shared_polynomial_threshold_v8.json"
    audit_input = V8 / "input_manifests/shared_polynomial_threshold_v8/locked_audit.csv"
    audit_result_path = V8_OUT / "flipguard/shared-polynomial-threshold-v8/direct_locked_audit.json"
    audit_result = json_file(audit_result_path)
    original = audit_result["audit_trial"]

    observation_fields = [
        "canonical_input_id", "source_row_id", "validation_audit_role", "keyset_context_id",
        "pass_index", "arm_position", "candidate_id", "log_n", "q", "p", "scale_bits",
        "binary_digest", "graph_digest", "input_digest", "threshold", "plaintext_score",
        "decrypted_score", "margin", "absolute_error", "normalized_error_budget_usage",
        "plaintext_decision", "encrypted_decision", "flip", "original_locked_audit_score",
        "original_locked_audit_decision", "original_locked_audit_aggregate_flips",
    ]

    def enriched(row: dict[str, str]) -> dict[str, object]:
        decrypted = float(row["decrypted"])
        error = float(row["absolute_error"])
        return {
            "canonical_input_id": "shared_polynomial_threshold_v8:locked_audit:711",
            "source_row_id": 711,
            "validation_audit_role": "locked_audit_latency_subset",
            "keyset_context_id": row["keyset"],
            "pass_index": row["pass"],
            "arm_position": row["order_position"],
            "candidate_id": candidate_id,
            "log_n": provider["parameters"]["log_n"],
            "q": ";".join(map(str, provider["parameters"]["log_q"])),
            "p": ";".join(map(str, provider["parameters"]["log_p"])),
            "scale_bits": provider["parameters"]["log_default_scale"],
            "binary_digest": sha256(common_binary),
            "graph_digest": sha256(model),
            "input_digest": sha256(audit_input),
            "threshold": THRESHOLD,
            "plaintext_score": plain,
            "decrypted_score": decrypted,
            "margin": margin,
            "absolute_error": error,
            "normalized_error_budget_usage": error / (RHO * margin),
            "plaintext_decision": plain >= THRESHOLD,
            "encrypted_decision": decrypted >= THRESHOLD,
            "flip": row["decision_flip"],
            "original_locked_audit_score": "NOT_RECORDED_IN_FROZEN_SUMMARY",
            "original_locked_audit_decision": "NOT_RECORDED_IN_FROZEN_SUMMARY",
            "original_locked_audit_aggregate_flips": original["decision_flips"],
        }

    write_csv(FORENSICS / "affected_observations.csv", observation_fields, [enriched(row) for row in affected])
    matrix_fields = observation_fields + ["raw_record_reserve_violation", "frozen_scope"]
    matrix = []
    for row in row_records:
        item = enriched(row)
        item["raw_record_reserve_violation"] = row["reserve_violation"]
        item["frozen_scope"] = "V_amb"
        matrix.append(item)
    write_csv(FORENSICS / "input_keyset_pass_matrix.csv", matrix_fields, matrix)
    write_csv(
        FORENSICS / "margin_error_analysis.csv",
        ["keyset", "pass", "plaintext_score", "threshold", "margin", "margin_floor", "rho", "acceptance_budget", "absolute_error", "normalized_usage", "decision_flip", "frozen_scope"],
        [{
            "keyset": row["keyset"], "pass": row["pass"], "plaintext_score": plain,
            "threshold": THRESHOLD, "margin": margin, "margin_floor": MARGIN_FLOOR,
            "rho": RHO, "acceptance_budget": RHO * margin,
            "absolute_error": row["absolute_error"],
            "normalized_usage": float(row["absolute_error"]) / (RHO * margin),
            "decision_flip": row["decision_flip"], "frozen_scope": "V_amb",
        } for row in row_records],
    )
    write_csv(
        FORENSICS / "original_audit_comparison.csv",
        ["source_row_id", "candidate_id", "audit_binary_digest", "audit_unique_inputs", "audit_key_repeats", "audit_v_cert", "audit_v_amb", "aggregate_flips", "aggregate_violations", "per_row_decrypted_score", "per_row_encrypted_decision", "interpretation"],
        [{
            "source_row_id": 711, "candidate_id": candidate_id,
            "audit_binary_digest": sha256(audit_binary), "audit_unique_inputs": 500,
            "audit_key_repeats": original["key_repeats_completed"], "audit_v_cert": original["v_cert"],
            "audit_v_amb": original["v_amb"], "aggregate_flips": original["decision_flips"],
            "aggregate_violations": original["error_violations"],
            "per_row_decrypted_score": "NOT_RECORDED_IN_FROZEN_SUMMARY",
            "per_row_encrypted_decision": "NOT_RECORDED_IN_FROZEN_SUMMARY",
            "interpretation": "The aggregate certifier excludes V_amb from the V_cert flip/violation claim; the common executor retained raw repeated decisions.",
        }],
    )

    write_json(FORENSICS / "candidate_identity.json", {
        "candidate_id": candidate_id,
        "source_synthesis_candidate_id": "synth_repair_scale_1_rescale_N13_Q7_S24_d58042962022",
        "provider_manifest": str((V8 / "provider_candidate_manifests/direct.json").relative_to(ROOT)),
        "provider_manifest_sha256": sha256(V8 / "provider_candidate_manifests/direct.json"),
        "parameters": provider["parameters"],
        "common_record_candidate_ids": sorted({row["candidate_id"] for row in direct}),
        "original_locked_audit_candidate_id": audit_result["selected_candidate"]["id"],
        "identity_match": candidate_id == audit_result["selected_candidate"]["id"],
    })
    write_json(FORENSICS / "graph_identity.json", {
        "model_path": str(model.relative_to(ROOT)), "model_sha256": sha256(model),
        "workload_contract_path": str(workload.relative_to(ROOT)), "workload_contract_sha256": sha256(workload),
        "formula": "score = 0.5 + 0.197*z - 0.004*z^3",
        "common_executor_source": "cmd/flipguard-external-v8-common/main.go",
        "common_executor_source_sha256": sha256(ROOT / "cmd/flipguard-external-v8-common/main.go"),
        "graph_identity": "EXACT_DECLARED_GRAPH",
    })
    write_json(FORENSICS / "input_identity.json", {
        "canonical_input_id": "shared_polynomial_threshold_v8:locked_audit:711",
        "source_row_id": 711, "source_role": "locked_audit",
        "source_csv": str(audit_input.relative_to(ROOT)), "source_csv_sha256": sha256(audit_input),
        "row": source, "latency_subset_membership": True,
        "common_executor_observations": len(row_records), "unique_input_count": 1,
    })
    write_json(FORENSICS / "binary_identity.json", {
        "original_locked_audit_binary": str(audit_binary.relative_to(ROOT)),
        "original_locked_audit_binary_sha256": sha256(audit_binary),
        "common_executor_binary": str(common_binary.relative_to(ROOT)),
        "common_executor_binary_sha256": sha256(common_binary),
        "binaries_byte_identical": False,
        "reason": "Purpose-specific binaries share the frozen V8 execution closure but emit different evidence granularity; no binary equivalence is asserted.",
        "v8_execution_critical_source_digest": json_file(V8 / "manifest.json")["execution_critical_source_digest"],
    })
    write_json(FORENSICS / "packing_and_slot_identity.json", {
        "original_locked_audit_packing": audit_result["audit_contract"]["deployment"]["packing_strategy"],
        "original_required_slots": audit_result["audit_contract"]["deployment"]["required_slots"],
        "common_executor_direct_runtime": "internal/ckksbackend.NewExternalV8TabularRuntime",
        "common_executor_input_width": 3,
        "identity_state": "SAME_SCALAR_REPLICATED_RUNTIME_PATH",
    })
    write_json(FORENSICS / "threshold_and_tie_identity.json", {
        "threshold": THRESHOLD, "plaintext_decision_rule": "score >= threshold",
        "encrypted_decision_rule": "score >= threshold", "tie_break": "positive class on equality",
        "margin_floor": MARGIN_FLOOR, "rho": RHO, "row_711_margin": margin,
        "row_711_scope": "V_amb", "within_ambiguity_scope": margin < MARGIN_FLOOR,
    })
    classification = {
        "classification": "F4_NEAR_BOUNDARY_AMBIGUITY",
        "classification_complete": True,
        "affected_unique_inputs": 1,
        "affected_input_ids": [711],
        "affected_keysets": sorted({int(row["keyset"]) for row in affected}),
        "affected_passes": sorted({int(row["pass"]) for row in affected}),
        "affected_observations": len(affected),
        "all_row_711_measurement_observations": len(row_records),
        "plaintext_margin": margin,
        "declared_ambiguity_margin_floor": MARGIN_FLOOR,
        "reason": "The sole affected input has plaintext margin below the predeclared margin floor and belongs to V_amb. The prior locked-audit SAFE claim applies to V_cert; raw repeated measurements expose decision variability inside the explicitly ambiguous scope.",
        "targeted_encrypted_replay_performed": False,
        "targeted_replay_reason": "PROHIBITED_AND_UNNECESSARY_FOR_F4",
        "claim_effect": "Direct repeated-stability is not admitted for V_amb; P1/P2 remain blocked when they include the direct arm. The original finite V_cert locked-audit claim is preserved with explicit scope.",
    }
    write_json(FORENSICS / "final_classification.json", classification)
    write_json(FORENSICS / "manifest.json", {
        "schema_version": "flipguard_direct_repeat_flip_forensics_v1",
        "source_evidence": "docs/evidence/focused_external_comparison_v8",
        "source_records_sha256": sha256(common_path),
        "source_locked_audit_sha256": sha256(audit_result_path),
        "classification": classification["classification"],
        "frozen_v8_modified": False,
        "new_encrypted_execution": 0,
    })
    readme = f"""# Direct Repeated-Flip Forensics

The eight V8 common-executor flips all occur on locked-audit row 711. Its plaintext score is `{plain:.17g}`, only `{margin:.17g}` from threshold `0.5`, below the frozen ambiguity floor `{MARGIN_FLOOR}`. It is therefore `V_amb`, and the final class is `F4_NEAR_BOUNDARY_AMBIGUITY`.

The original locked-audit summary retained aggregate V_cert counts but no per-row decrypted values. This pack records those unavailable fields as `NOT_RECORDED_IN_FROZEN_SUMMARY`; it does not impute zeros. No encrypted replay was run because V9 permits targeted replay only for F1/F2. The direct arm remains in diagnostic latency data, while comparisons that require its repeated decision stability are blocked.
"""
    (FORENSICS / "README.md").write_text(readme, encoding="utf-8")


def build_pairwise() -> None:
    records = csv_file(V8 / "common_executor_records.csv")
    direct_audit = json_file(V8_OUT / "flipguard/shared-polynomial-threshold-v8/direct_locked_audit.json")
    catalog_audit = json_file(V8_OUT / "flipguard/shared-polynomial-threshold-v8/catalog_fastest_safe_locked_audit.json")
    heir = json_file(V8_OUT / "heir/shared-polynomial-threshold-v8/manifest.json")
    arms = {arm: [row for row in records if row["arm"] == arm] for arm in ("flipguard_direct", "bounded_catalog", "heir_generated")}
    flips = {arm: sum(row["decision_flip"] == "True" for row in rows) for arm, rows in arms.items()}
    cases = [
        ("P1", "heir_generated", "flipguard_direct", "BLOCKED_UNSTABLE_ARM"),
        ("P2", "bounded_catalog", "flipguard_direct", "BLOCKED_UNSTABLE_ARM"),
        ("P3", "bounded_catalog", "heir_generated", "PAPER_ADMITTED"),
    ]
    claims = []
    for pair_id, numerator, denominator, state in cases:
        summary = paired_ratio(records, numerator, denominator)
        pair_flips = {numerator: flips[numerator], denominator: flips[denominator]}
        claims.append({
            "pair_id": pair_id, "numerator_arm": numerator, "denominator_arm": denominator,
            "state": state, **summary,
            "graph_identity": "EXACT_SHARED_POLYNOMIAL_OPERATION_ORDER",
            "input_identity": "100_FROZEN_LOCKED_AUDIT_INPUTS",
            "runtime": "Lattigo v6.2.0 common harness",
            "keyset_pairing": "3 keysets; each keyset/pass/input has both arms",
            "timing_boundary": "per-input encrypt + evaluate + decrypt total_ms",
            "security_v2": "PASS_BOTH_ARMS",
            "validation_state": "ZERO_FLIP_BOTH_ARMS",
            "locked_audit_state": "ZERO_FLIP_BOTH_ARMS_ON_ORIGINAL_500_INPUT_AUDITS",
            "measurement_repeat_flips": pair_flips,
            "predeclared_comparison": True,
            "outlier_removal": False,
            "post_hoc": False,
            "reason": "Direct arm has 8 raw repeated flips on one V_amb input." if "flipguard_direct" in (numerator, denominator) else "Catalog and HEIR are fully paired, Security-V2 aligned, and have zero validation, audit, and measurement-repeat flips.",
        })
    result = {
        "schema_version": "flipguard_pairwise_latency_claim_admission_v9",
        "source_records": "docs/evidence/focused_external_comparison_v8/common_executor_records.csv",
        "source_records_sha256": sha256(V8 / "common_executor_records.csv"),
        "protocol": {"unique_inputs": 100, "keysets": 3, "passes": 6, "raw_pairs_per_comparison": 1800, "bootstrap_repetitions": 5000, "bootstrap_seed": 20260807},
        "arm_measurement_flips": flips,
        "original_audits": {
            "direct": {"outcome": direct_audit["outcome"], "flips": direct_audit["audit_trial"]["decision_flips"], "scope": f"V_cert={direct_audit['audit_trial']['v_cert']};V_amb={direct_audit['audit_trial']['v_amb']}"},
            "catalog": {"outcome": catalog_audit["outcome"], "flips": catalog_audit["audit_trial"]["decision_flips"]},
            "heir": {"outcome": "LOCKED_AUDIT_PASS", "flips": next(row for row in heir["runtime_summaries"]["lattigo_v6_2"] if row["role"] == "locked_audit")["decision_flips"]},
        },
        "claims": claims,
        "direct_instability_does_not_leak_into_p3": claims[2]["measurement_repeat_flips"] == {"bounded_catalog": 0, "heir_generated": 0},
        "prohibited": ["HEIR is globally optimal", "HEIR is always faster", "ratio applies to other workloads", "all compilers outperform direct synthesis"],
    }
    write_json(V9 / "pairwise_latency_claim_admission.json", result)


def write_forensic_checksums() -> None:
    verifier = FORENSICS / "verify_direct_repeat_flip_forensics.py"
    if not verifier.exists():
        raise FileNotFoundError(verifier)
    lines = [
        f"{sha256(path)[7:]}  {path.relative_to(FORENSICS).as_posix()}"
        for path in sorted(FORENSICS.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (FORENSICS / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    V9.mkdir(parents=True, exist_ok=True)
    FORENSICS.mkdir(parents=True, exist_ok=True)
    build_literature()
    build_forensics()
    build_pairwise()
    write_forensic_checksums()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
