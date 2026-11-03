#!/usr/bin/env python3
"""Build the canonical FlipGuard paper-claim admission registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("docs/evidence/paper_claim_admission_v1")
VERIFIER = Path("scripts/verify_paper_claim_admission.py")
STATES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "BLOCKED",
    "NOT_EVALUATED",
    "SUPERSEDED",
    "PILOT_ONLY",
}

DEPENDENCIES = {
    "direct_confirmatory": Path(
        "docs/evidence/direct_locked_audit_final_source_v1/manifest.json"
    ),
    "direct_development": Path(
        "docs/evidence/direct_locked_audit_seed0_development_v1/manifest.json"
    ),
    "direct_ablation": Path(
        "docs/evidence/direct_synthesis_ablation_v1/manifest.json"
    ),
    "final_suite": Path(
        "docs/evidence/final_confirmatory_suite_v1/manifest.json"
    ),
    "bounded_oracle": Path(
        "docs/evidence/security_v2_bounded_oracle_v1/manifest.json"
    ),
    "no_safe": Path(
        "docs/evidence/no_safe_controls_confirmatory_v1/manifest.json"
    ),
    "paired_latency_admission": Path(
        "results/thesis_grade_protocol/"
        "paired_latency_claim_admission_v1/manifest.json"
    ),
    "margin_interpretation": Path(
        "docs/evidence/margin_utilization_interpretation_v1/manifest.json"
    ),
    "structural": Path(
        "docs/evidence/structural_extension_v1/manifest.json"
    ),
    "structural_failure": Path(
        "docs/evidence/structural_audit_failure_analysis_v1/manifest.json"
    ),
    "sobel": Path(
        "docs/evidence/non_tabular_sobel_holdout_v1/manifest.json"
    ),
    "harris": Path(
        "docs/evidence/non_tabular_harris_holdout_v1/manifest.json"
    ),
    "cnn_lite": Path(
        "docs/evidence/non_tabular_mnist_cnn_lite_holdout_v1/manifest.json"
    ),
    "training_seed": Path(
        "docs/evidence/independent_training_seed_extension_v1/manifest.json"
    ),
    "security_attestation": Path(
        "docs/evidence/security_v2_static_attestation_formal_v2/manifest.json"
    ),
    "exact_estimator": Path(
        "docs/evidence/exact_security_estimator_v1/manifest.json"
    ),
    "policy_sensitivity": Path(
        "docs/evidence/policy_sensitivity_v1/manifest.json"
    ),
    "decision_activation": Path(
        "docs/evidence/decision_contract_activation_control_v1/manifest.json"
    ),
}


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def canonical_commit(revision: str) -> str:
    value = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError(f"{revision}: not a canonical commit")
    return value


def claim(
    claim_id: str,
    title: str,
    state: str,
    admitted: bool,
    ko: str,
    en: str,
    scope: str,
    dependencies: list[str],
    unit: str,
    limitations: list[str],
    prohibited: list[str],
    rationale: str,
    source_commit: str,
) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"{claim_id}: invalid state")
    return {
        "claim_id": claim_id,
        "title": title,
        "state": state,
        "paper_admitted": admitted,
        "exact_allowed_wording_ko": ko if admitted else "",
        "exact_allowed_wording_en": en if admitted else "",
        "scope": scope,
        "evidence_dependencies": dependencies,
        "statistical_unit": unit,
        "limitations": limitations,
        "prohibited_overclaim": prohibited,
        "reviewer_rationale": rationale,
        "source_commit": source_commit,
    }


def claims(source_commit: str) -> list[dict[str, Any]]:
    admitted = [
        claim(
            "scoped_direct_synthesis",
            "Scoped direct CKKS configuration synthesis",
            "SUPPORTED",
            True,
            "FlipGuard는 선언된 graph adapter와 동결 정책 범위에서 computation graph와 threshold decision-integrity contract로부터 CKKS literal을 직접 합성했다.",
            "Within the declared graph adapters and frozen policies, FlipGuard directly synthesized CKKS literals from computation graphs and threshold decision-integrity contracts.",
            "declared tabular, polynomial, Sobel, Harris, and scalar-replicated CNN-lite adapters",
            ["direct_confirmatory", "direct_development", "final_suite"],
            "workload-partition instance, with seed roles reported separately",
            ["finite adapter set", "scalar-replicated packing scope"],
            ["universal graph support", "first direct CKKS synthesizer"],
            "All declared primary instances produced admitted literals under the frozen policy; breadth beyond the adapters was not evaluated.",
            source_commit,
        ),
        claim(
            "adaptive_repair",
            "Bounded failure-aware repair",
            "SUPPORTED",
            True,
            "FlipGuard의 동결된 bounded repair는 선언된 개발 ablation에서 one-shot 실패 네 건을 SAFE 선택으로 전환했으며, 이는 보편적 repair 성공을 뜻하지 않는다.",
            "In the declared development ablation, FlipGuard's frozen bounded repair converted four one-shot failures into SAFE selections; this does not imply universal repair success.",
            "predeclared development ablation and observed repair causes",
            ["direct_ablation", "direct_confirmatory"],
            "development workload",
            ["four causal ablation cases", "bounded repair budget"],
            ["universal repair success", "first repair-based selector"],
            "The one-shot/full contrast isolates empirical repair value while retaining failures and bounded termination.",
            source_commit,
        ),
        claim(
            "formal_trial_reduction",
            "Formal Security-V2 trial reduction",
            "SUPPORTED",
            True,
            "FlipGuard는 Security-V2 bounded catalog의 700개 후보 대비 전체 70회, confirmatory 560개 후보 대비 56회의 encrypted candidate trial을 사용해 두 경우 모두 90% 감소를 기록했다.",
            "FlipGuard used 70 encrypted candidate trials versus 700 Security-V2 bounded-catalog candidates overall and 56 versus 560 in the confirmatory partitions, a 90% reduction in both cases.",
            "Security-V2-admitted 7 profiles x 2 paths over the declared instances",
            ["final_suite", "bounded_oracle"],
            "candidate trial",
            ["1,100 executions are historical pre-security accounting only"],
            ["trial reduction against 1,100", "global search-space reduction"],
            "The denominator excludes 400 Security-V2-inadmissible candidates and separates seed 0 from seeds 1-4.",
            source_commit,
        ),
        claim(
            "primary_no_retuning_locked_audit",
            "Primary no-retuning locked audit",
            "SUPPORTED",
            True,
            "동결 literal의 no-retuning locked audit은 confirmatory seeds 1-4에서 40/40, development seed 0에서 10/10 통과했다.",
            "Byte-identical frozen literals passed no-retuning locked audit in 40/40 confirmatory seed-1-4 instances and 10/10 development seed-0 instances.",
            "10 dataset-model workloads and five deterministic repeated partitions",
            ["direct_confirmatory", "direct_development"],
            "10 dataset-model workloads with repeated partitions; seed 0 is descriptive",
            ["fixed held-out artifacts", "not independent model seeds"],
            ["50 independent samples", "distribution-wide locked-audit guarantee"],
            "The audit replays the selected literal without synthesis or repair and preserves the seed-role distinction.",
            source_commit,
        ),
        claim(
            "no_safe_behavior",
            "Scoped NO_SAFE abstention",
            "SUPPORTED",
            True,
            "사전동결 budget control은 40건 중 16건에서 NO_SAFE를, 선언된 finite-domain control은 50/50에서 NO_SAFE를 반환했다.",
            "The predeclared budget control returned NO_SAFE in 16/40 instances, and the declared finite-domain control returned NO_SAFE in 50/50 instances.",
            "one-candidate budget control and declared two-candidate finite domain",
            ["no_safe"],
            "control workload-partition instance",
            ["finite candidate budgets and domains"],
            ["global CKKS infeasibility", "NO_SAFE proves no possible configuration"],
            "The controls demonstrate fail-closed abstention only within their predeclared candidate budgets.",
            source_commit,
        ),
        claim(
            "paired_latency",
            "Confirmatory paired latency",
            "PARTIALLY_SUPPORTED",
            True,
            "선언된 post-freeze workload partition에서 direct configuration은 Security-V2 bounded-catalog fastest-safe configuration보다 paired total inference latency를 줄였으며, 정확한 clustered geometric-mean ratio와 confidence interval을 함께 보고한다.",
            "Across the declared post-freeze workload partitions, FlipGuard's directly synthesized configurations reduced paired total inference latency relative to the Security-V2-compliant bounded-catalog fastest-safe configurations; the exact clustered geometric-mean ratio and confidence interval are reported.",
            "one host, frozen direct and Security-V2 bounded-catalog arms",
            ["paired_latency_admission", "bounded_oracle"],
            "10 dataset-model clusters; seeds 1-4 repeat within cluster",
            ["one measured host", "declared workloads"],
            ["production speedup", "universal speedup", "raw pair-level p-value", "global-optimal baseline"],
            "All 40 confirmatory instances are complete and the cluster-bootstrap lower bound exceeds one, but hardware and workload generality are limited.",
            source_commit,
        ),
        claim(
            "structural_extension",
            "Deeper polynomial structural extension",
            "PARTIALLY_SUPPORTED",
            True,
            "mlp_square_poly3는 25/25 선택됐고 no-retuning audit에서 24건 PASS와 decision flip 없는 reserve-policy REJECT 1건을 기록했다.",
            "For mlp_square_poly3, 25/25 instances were selected and no-retuning audit produced 24 PASS results and one reserve-policy REJECT without a decision flip.",
            "five datasets x five deterministic partitions for mlp_square_poly3",
            ["structural", "structural_failure", "margin_interpretation"],
            "workload-partition instance",
            ["one disclosed audit policy rejection", "single deeper polynomial graph family"],
            ["25/25 audit PASS", "unseen audits always preserve the reserve policy", "arbitrary graph support"],
            "The valid negative result lowers the claim and demonstrates that selection success is not audit success.",
            source_commit,
        ),
        claim(
            "scoped_non_tabular_extension",
            "Scoped non-tabular adapters",
            "PARTIALLY_SUPPORTED",
            True,
            "Sobel, Harris, CNN-lite adapter는 각 선언된 finite input과 scalar-replicated execution 범위에서 selection과 no-retuning audit evidence를 제공한다.",
            "The Sobel, Harris, and CNN-lite adapters provide selection and no-retuning audit evidence only for their declared finite inputs and scalar-replicated execution scopes.",
            "BSDS500 Sobel/Harris patches and MNIST CNN-lite scalar-replicated adapter",
            ["sobel", "harris", "cnn_lite"],
            "declared image cluster or image input, as specified by each pack",
            ["no packed CNN", "no full-image operator accuracy claim"],
            ["general CNN support", "image-processing generalization", "universal graph support"],
            "Multiple non-tabular adapters broaden finite scope but do not establish arbitrary packed graph support.",
            source_commit,
        ),
        claim(
            "training_model_seed_extension",
            "Independent training/data-seed extension",
            "PARTIALLY_SUPPORTED",
            True,
            "세 dataset과 세 independent training/data seed로 생성한 9개 model instance가 9/9 selection과 no-retuning audit PASS를 기록했다.",
            "Nine model instances from three datasets and three independent training/data seeds achieved 9/9 selection and no-retuning audit PASS.",
            "3 datasets x 3 predeclared independent training/data seeds",
            ["training_seed"],
            "trained model instance, grouped by dataset",
            ["three datasets", "three seeds"],
            ["universal model-seed generalization", "nine independent datasets"],
            "The extension addresses fixed-model reuse but remains too small for universal training generalization.",
            source_commit,
        ),
        claim(
            "security_attestation",
            "Security-V2 and exact-Q/P attestation",
            "PARTIALLY_SUPPORTED",
            True,
            "선택 후보의 exact Q/P를 Security Policy V2와 두 estimator model에서 재감사했으며, 실제 Lattigo Xe truncation과 estimator 분포의 exact equivalence는 주장하지 않는다.",
            "Selected exact Q/P literals were re-attested under Security Policy V2 and two estimator models; exact equivalence to Lattigo's truncated Xe distribution is not claimed.",
            "attested direct, catalog, reference, and latency-arm literals",
            ["security_attestation", "exact_estimator"],
            "distinct cryptographic object and estimator model",
            ["conservative table admission", "explicit Gaussian truncation caveat"],
            ["exact distribution equivalence", "universal 128-bit security for arbitrary runtimes"],
            "Q and QP are checked separately and estimator sensitivity is complete for the declared objects, with an explicit distribution caveat.",
            source_commit,
        ),
        claim(
            "finite_scope_decision_integrity",
            "Finite-scope decision-integrity admission",
            "PARTIALLY_SUPPORTED",
            True,
            "FlipGuard는 선언된 finite validation에서 관측 error와 decision margin을 결합해 후보를 certify-or-reject하고, disjoint audit에서 동결 literal을 재생한다.",
            "FlipGuard combines observed error and decision margin to certify or reject candidates on declared finite validation artifacts and replays the frozen literal on disjoint audits.",
            "declared finite validation and locked-audit artifacts",
            ["direct_confirmatory", "direct_development", "margin_interpretation", "no_safe"],
            "certifiable sample-key observation within each declared artifact",
            ["empirical finite-set certificate", "rho=0.5 is operational"],
            ["distribution-wide safety", "instantiated analytical CKKS certificate"],
            "The evidence supports the gate behavior and observed finite-set outcomes, not a domain-wide approximation theorem.",
            source_commit,
        ),
    ]
    blocked_specs = [
        ("natural_data_margin_literal_effect", "Natural-data decision margin changes the synthesized literal", "BLOCKED", ["direct_ablation", "policy_sensitivity"], "The primary natural range showed zero literal changes because the minimum synthesis floor dominated."),
        ("instantiated_analytical_ckks_certificate", "Instantiated analytical CKKS certificate", "BLOCKED", [], "Primitive CKKS residual bounds are not instantiated."),
        ("distribution_wide_safety", "Distribution-wide decision safety", "BLOCKED", [], "Finite observed artifacts do not establish distribution-wide safety."),
        ("arbitrary_graph_support", "Arbitrary graph support", "NOT_EVALUATED", [], "Only declared adapters were evaluated."),
        ("global_optimum", "Global optimality", "BLOCKED", ["bounded_oracle"], "The comparator is a finite Security-V2 bounded catalog."),
        ("cross_runtime_numerical_equivalence", "Cross-runtime numerical equivalence", "NOT_EVALUATED", [], "Matched Lattigo-SEAL execution was intentionally stopped."),
        ("general_external_autotuner_integration", "General external-autotuner integration", "NOT_EVALUATED", [], "Provider artifacts are scoped appendix evidence."),
        ("production_latency", "Production latency", "NOT_EVALUATED", ["paired_latency_admission"], "One research host does not establish production performance."),
        ("universal_runtime_security", "Universal 128-bit runtime security", "NOT_EVALUATED", ["security_attestation", "exact_estimator"], "Runtime distributions and implementations are not universally covered."),
    ]
    for claim_id, title, state, dependencies, rationale in blocked_specs:
        admitted.append(
            claim(
                claim_id,
                title,
                state,
                False,
                "",
                "",
                "not admitted",
                dependencies,
                "not applicable",
                [rationale],
                [title],
                rationale,
                source_commit,
            )
        )
    return admitted


def build(output: Path, source_commit: str) -> None:
    if output.exists():
        raise ValueError(f"{output} already exists")
    dependency_records = {}
    for dependency_id, relative in DEPENDENCIES.items():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"{relative}: missing dependency")
        dependency_records[dependency_id] = {
            "path": str(relative),
            "manifest_sha256": sha256(path),
        }

    claim_rows = claims(source_commit)
    output.mkdir(parents=True)
    claims_document = {
        "schema_version": 1,
        "registry_id": "paper_claim_admission_v1",
        "semantics": (
            "paper_claim_allowed means that the paper may use only claims "
            "whose paper_admitted field is true"
        ),
        "paper_claim_allowed": True,
        "claim_vocabulary": sorted(STATES),
        "claims": claim_rows,
    }
    (output / "claims.json").write_text(
        json.dumps(claims_document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    dependency_rows = []
    for item in claim_rows:
        for dependency_id in item["evidence_dependencies"]:
            record = dependency_records[dependency_id]
            dependency_rows.append(
                {
                    "claim_id": item["claim_id"],
                    "dependency_id": dependency_id,
                    "evidence_path": record["path"],
                    "manifest_sha256": record["manifest_sha256"],
                    "required_for_claim": True,
                    "verification_status": "DIGEST_BOUND",
                }
            )
    with (output / "claim_evidence_dependencies.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dependency_rows[0]))
        writer.writeheader()
        writer.writerows(dependency_rows)

    allowed_lines = [
        "# Allowed Paper Sentences",
        "",
        "Only the exact scoped sentences below are admitted. Numerical tables may",
        "substitute verified values without broadening the sentence.",
        "",
    ]
    for item in claim_rows:
        if item["paper_admitted"]:
            allowed_lines.extend(
                [
                    f"## {item['claim_id']}",
                    "",
                    f"- KO: {item['exact_allowed_wording_ko']}",
                    f"- EN: {item['exact_allowed_wording_en']}",
                    "",
                ]
            )
    (output / "allowed_sentences.md").write_text(
        "\n".join(allowed_lines) + "\n", encoding="utf-8"
    )

    prohibited_lines = [
        "# Prohibited Paper Sentences",
        "",
        "- FlipGuard is the first CKKS autotuner.",
        "- FlipGuard is the first direct CKKS configuration synthesizer.",
        "- FlipGuard is the first application-aware CKKS configurator.",
        "- FlipGuard is the first repair-based selector.",
        "- FlipGuard supports arbitrary CKKS graphs or universal models.",
        "- The bounded catalog is a global optimum.",
        "- The 50 repeated-partition rows are independent samples.",
        "- The 1,100 historical executions are the formal Security-V2 denominator.",
        "- The paired result is a production or universal speedup.",
        "- SAFE establishes distribution-wide or analytical CKKS correctness.",
        "- The security result proves exact runtime-distribution equivalence.",
        "- Provider appendix evidence establishes general external-autotuner support.",
        "",
    ]
    (output / "prohibited_sentences.md").write_text(
        "\n".join(prohibited_lines), encoding="utf-8"
    )

    rationale_lines = [
        "# Reviewer Rationale",
        "",
        "The registry admits claim sentences rather than requiring every research",
        "direction to be supported. A blocked auxiliary claim remains visible but",
        "does not prevent writing with admitted sentences.",
        "",
    ]
    for item in claim_rows:
        rationale_lines.extend(
            [
                f"## {item['claim_id']}: {item['state']}",
                "",
                item["reviewer_rationale"],
                "",
            ]
        )
    (output / "reviewer_rationale.md").write_text(
        "\n".join(rationale_lines), encoding="utf-8"
    )
    shutil.copy2(ROOT / VERIFIER, output / "verify_paper_claim_admission.py")

    admitted_count = sum(item["paper_admitted"] for item in claim_rows)
    blocked_count = sum(not item["paper_admitted"] for item in claim_rows)
    manifest = {
        "schema_version": 1,
        "evidence_id": "paper_claim_admission_v1",
        "artifact_class": "CANONICAL_CLAIM_ADMISSION_OVERLAY",
        "source_commit": source_commit,
        "paper_claim_allowed": True,
        "paper_claim_allowed_semantics": (
            "the paper may use only claims.json entries with "
            "paper_admitted=true"
        ),
        "admitted_claim_count": admitted_count,
        "blocked_or_not_admitted_claim_count": blocked_count,
        "frozen_evidence_manifests_modified": False,
        "dependency_records": dependency_records,
        "files": {},
    }
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}:
            manifest["files"][path.name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths = sorted(
        path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  {path.name}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source-commit", default="HEAD")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    build(output, canonical_commit(args.source_commit))
    subprocess.run(
        [
            "python3",
            str(output / "verify_paper_claim_admission.py"),
            "--evidence-root",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"paper_claim_admission=BUILT output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
