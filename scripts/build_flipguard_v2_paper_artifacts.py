#!/usr/bin/env python3

"""Build paper-facing FlipGuard V2 tables and figures from verified evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/paper_artifacts_v2/current"
)
MANUSCRIPT_PATH = Path(
    "docs/research/flipguard_v2_manuscript_draft_ko.md"
)
MANUSCRIPT_ARTIFACTS = (
    "figures/figure_01_framework.svg",
    "figures/figure_02_search_effort.svg",
    "figures/figure_03_locked_audit.svg",
    "figures/figure_04_margin_floor_coverage.svg",
    "figures/figure_05_no_safe_controls.svg",
    "figures/figure_06_paired_latency.svg",
    "tables/01_direct_synthesis_locked_audit.md",
    "tables/02_search_effort_and_bounded_oracle.md",
    "tables/03_margin_floor_sensitivity.md",
    "tables/04_no_safe_controls.md",
    "tables/05_paired_latency.md",
)
PRELIMINARY_FORBIDDEN_HEADLINE_METRICS = (
    "70회",
    "210회",
    "1,100개",
    "93.64%",
    "150회",
    "1.9769",
    "50/50",
)
MANUSCRIPT_CLAIM_BLOCKS = {
    "result": (
        "<!-- BEGIN FINAL_RESULT_SENTENCE -->",
        "<!-- END FINAL_RESULT_SENTENCE -->",
        (
            "<!-- NON_AUTHORITATIVE_SCAFFOLD: no final result sentence "
            "is admissible. -->"
        ),
    ),
    "conclusion": (
        "<!-- BEGIN FINAL_CONCLUSION_SENTENCE -->",
        "<!-- END FINAL_CONCLUSION_SENTENCE -->",
        (
            "<!-- NON_AUTHORITATIVE_SCAFFOLD: no final conclusion "
            "is admissible. -->"
        ),
    ),
}

PRELIMINARY_PACKS = {
    "direct": Path(
        "docs/evidence/direct_locked_audit_five_split_v1"
    ),
    "oracle": Path("docs/evidence/full_oracle_comparison_v1"),
    "policy": Path("docs/evidence/policy_sensitivity_v1"),
    "no_safe": Path("docs/evidence/no_safe_controls_v1"),
    "paired": Path("docs/evidence/paired_latency_pilot_v1"),
    "security": Path(
        "docs/evidence/security_v2_static_attestation"
    ),
}

FINAL_PACKS = {
    "direct": Path(
        "docs/evidence/direct_locked_audit_final_source_v1"
    ),
    "no_safe": Path(
        "docs/evidence/no_safe_controls_confirmatory_v1"
    ),
    "structural": Path("docs/evidence/structural_extension_v1"),
    "paired": Path("docs/evidence/paired_latency_final_v1"),
}

COMMON_PACKS = {
    "oracle": Path("docs/evidence/full_oracle_comparison_v1"),
    "policy": Path("docs/evidence/policy_sensitivity_v1"),
    "security": Path(
        "docs/evidence/security_v2_static_attestation"
    ),
}

VERIFIERS = {
    "direct": "scripts/freeze_direct_locked_audit_evidence.py",
    "structural": "scripts/freeze_direct_locked_audit_evidence.py",
    "oracle": "scripts/freeze_full_oracle_comparison_evidence.py",
    "policy": "scripts/freeze_policy_sensitivity_evidence.py",
    "no_safe": "scripts/freeze_no_safe_control_evidence.py",
    "paired": "scripts/freeze_paired_latency_evidence.py",
    "security": "scripts/build_security_v2_static_artifacts.py",
}

FINAL_REQUIRED_WORKLOADS = {
    "direct": 50,
    "structural": 25,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic FlipGuard V2 paper tables and SVG figures "
            "from evidence packs that pass their native verifiers."
        )
    )
    parser.add_argument(
        "--profile",
        choices=("auto", "preliminary", "final"),
        default="auto",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def portable(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tree_digest(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest(), len(files)


def markdown_section(document: str, heading: str) -> str:
    try:
        start = document.index(heading) + len(heading)
    except ValueError as error:
        raise ValueError(
            f"manuscript is missing heading {heading!r}"
        ) from error
    next_heading = document.find("\n## ", start)
    return (
        document[start:]
        if next_heading < 0
        else document[start:next_heading]
    )


def manuscript_claim_block(document: str, name: str) -> str:
    begin, end, _ = MANUSCRIPT_CLAIM_BLOCKS[name]
    try:
        start = document.index(begin) + len(begin)
        finish = document.index(end, start)
    except ValueError as error:
        raise ValueError(
            f"manuscript is missing {name} claim block markers"
        ) from error
    return document[start:finish].strip()


def replace_manuscript_claim_block(
    document: str,
    name: str,
    content: str,
) -> str:
    begin, end, _ = MANUSCRIPT_CLAIM_BLOCKS[name]
    try:
        start = document.index(begin)
        finish = document.index(end, start) + len(end)
    except ValueError as error:
        raise ValueError(
            f"manuscript is missing {name} claim block markers"
        ) from error
    replacement = f"{begin}\n{content.strip()}\n{end}"
    return document[:start] + replacement + document[finish:]


def render_final_manuscript_claims(
    direct: dict[str, Any],
    oracle: dict[str, Any],
    no_safe: dict[str, Any],
    paired: dict[str, Any],
) -> dict[str, str]:
    if not paired["claim_allowed"]:
        raise ValueError(
            "final manuscript claims require claimable paired evidence"
        )
    workloads = int(direct["workloads"])
    audit_passes = int(direct["locked_audit_passes"])
    if audit_passes != workloads:
        raise ValueError(
            "final manuscript claims require every locked audit to pass"
        )
    if int(direct["decision_flips"]) != 0 or int(
        direct["error_violations"]
    ) != 0:
        raise ValueError(
            "final manuscript claims require zero direct/audit violations"
        )
    if (
        int(direct["selection_source_replay_workloads"])
        != workloads
        or int(direct["audit_source_replay_workloads"])
        != workloads
    ):
        raise ValueError(
            "final manuscript claims require complete dual source replay"
        )

    result = (
        f"최종 confirmatory {workloads}개 workload에서 직접 합성은 "
        f"{int(direct['configuration_trials'])}회의 configuration trial과 "
        f"{int(direct['selection_key_runs'])}회의 fresh-key validation "
        f"run으로 {workloads}개 literal을 선택했으며, "
        f"{int(oracle['catalog_executions']):,}회의 bounded-catalog "
        f"실행 대비 trial 수를 "
        f"{float(oracle['execution_reduction_pct']):.2f}% 줄였다. "
        f"선택 literal은 {int(direct['locked_audit_key_runs'])}회의 "
        f"fresh-key locked-audit run에서 {audit_passes}/{workloads} "
        "통과했고 decision flip과 error violation은 모두 0이었다. "
        f"Selection과 audit의 source replay도 각각 "
        f"{int(direct['selection_source_replay_workloads'])}/"
        f"{workloads}, "
        f"{int(direct['audit_source_replay_workloads'])}/"
        f"{workloads} workload에서 검증되었다. "
        f"동일 프로세스 paired 측정의 "
        f"{paired['numerator']}/{paired['denominator']} total-latency "
        f"geometric-mean ratio는 {float(paired['ratio']):.4f}"
        f"(95% workload-bootstrap CI "
        f"[{float(paired['ci_low']):.4f}, "
        f"{float(paired['ci_high']):.4f}])였다. "
        f"Budgeted abstention control의 unsafe selection은 0이었고, "
        f"disjoint finite all-unsafe domain은 "
        f"{int(no_safe['finite_workloads'])}/"
        f"{int(no_safe['finite_workloads'])} workload에서 "
        "`NO_SAFE`를 반환했다."
    )
    conclusion = (
        "동일 source commit에 결합된 최종 evidence에서 FlipGuard의 "
        "직접 합성, 실패 기반 repair, explicit abstention 및 "
        "no-retuning locked audit이 선언된 workload 범위의 결정을 "
        "보존했으며, paired 결과는 fixed catalog를 bounded "
        "comparison으로 유지한 상태에서 선택 literal의 실행 성능을 "
        "정량화했다. 이 결론은 관측된 validation/audit rows와 "
        "manifest에 기록된 policy 및 backend scope에 한정된다."
    )
    if int(no_safe["finite_no_safe"]) != int(
        no_safe["finite_workloads"]
    ) or int(no_safe["finite_selected"]) != 0 or int(
        no_safe["budget_unsafe_selected"]
    ) != 0:
        raise ValueError(
            "final manuscript claims require complete finite-domain NO_SAFE"
        )
    return {"result": result, "conclusion": conclusion}


def update_manuscript_claims(
    manuscript_path: Path,
    claims: dict[str, str],
) -> None:
    document = manuscript_path.read_text(encoding="utf-8")
    updated = document
    for name in sorted(MANUSCRIPT_CLAIM_BLOCKS):
        updated = replace_manuscript_claim_block(
            updated,
            name,
            claims[name],
        )
    if updated != document:
        manuscript_path.write_text(updated, encoding="utf-8")


def validate_manuscript_publication_gate(
    publication_status: str,
    output: Path,
    manuscript_path: Path | None = None,
    expected_claims: dict[str, str] | None = None,
) -> dict[str, Any]:
    path = resolve(manuscript_path or MANUSCRIPT_PATH)
    document = path.read_text(encoding="utf-8")
    abstract = markdown_section(document, "## 초록")
    conclusion = markdown_section(document, "## 10. 결론")
    claim_blocks = {
        name: manuscript_claim_block(document, name)
        for name in MANUSCRIPT_CLAIM_BLOCKS
    }

    if publication_status == "NON_AUTHORITATIVE_SCAFFOLD":
        for metric in PRELIMINARY_FORBIDDEN_HEADLINE_METRICS:
            if metric in abstract or metric in conclusion:
                raise ValueError(
                    "preliminary metric is forbidden in manuscript "
                    f"abstract/conclusion: {metric}"
                )
        for name, (_, _, placeholder) in (
            MANUSCRIPT_CLAIM_BLOCKS.items()
        ):
            if claim_blocks[name] != placeholder:
                raise ValueError(
                    "preliminary manuscript claim block changed: "
                    f"{name}"
                )
    elif publication_status == "FINAL_ADMISSIBLE":
        if expected_claims is None:
            raise ValueError(
                "final manuscript gate requires expected generated claims"
            )
        for name in MANUSCRIPT_CLAIM_BLOCKS:
            if claim_blocks[name] != expected_claims[name]:
                raise ValueError(
                    "final manuscript claim block does not match "
                    f"generated evidence: {name}"
                )
    else:
        raise ValueError(
            f"unsupported manuscript publication status {publication_status}"
        )

    for required in (
        "## 8. 논의",
        "## 9. 재현성 및 artifact",
        "## 10. 결론",
        "source_replay_verified",
    ):
        if required not in document:
            raise ValueError(
                f"manuscript is missing required content {required!r}"
            )
    for relative in MANUSCRIPT_ARTIFACTS:
        if relative not in document:
            raise ValueError(
                f"manuscript does not map generated artifact {relative}"
            )
        if not (output / relative).is_file():
            raise FileNotFoundError(
                f"manuscript-mapped artifact is missing: {relative}"
            )

    return {
        "path": portable(path),
        "sha256": sha256_file(path),
        "publication_status": publication_status,
        "mapped_artifacts": list(MANUSCRIPT_ARTIFACTS),
        "claim_blocks": claim_blocks,
    }


def select_packs(profile: str) -> tuple[str, dict[str, Path]]:
    final_exists = {
        name: resolve(path).is_dir()
        for name, path in FINAL_PACKS.items()
    }
    if profile == "final":
        missing = [name for name, exists in final_exists.items() if not exists]
        if missing:
            raise ValueError(
                "final profile is incomplete; missing evidence packs: "
                + ", ".join(sorted(missing))
            )
        selected = {**COMMON_PACKS, **FINAL_PACKS}
        return "final", selected
    if profile == "auto" and all(final_exists.values()):
        selected = {**COMMON_PACKS, **FINAL_PACKS}
        return "final", selected
    missing = [
        name
        for name, path in PRELIMINARY_PACKS.items()
        if not resolve(path).is_dir()
    ]
    if missing:
        raise ValueError(
            "preliminary profile is incomplete; missing evidence packs: "
            + ", ".join(sorted(missing))
        )
    return "preliminary", dict(PRELIMINARY_PACKS)


def verify_pack(name: str, root: Path) -> str:
    command = [
        sys.executable,
        str(REPO_ROOT / VERIFIERS[name]),
        "--output-root",
        str(root),
        "--verify",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part.strip()
    )
    if completed.returncode != 0:
        raise ValueError(
            f"{name} evidence verifier failed for {root}:\n{output}"
        )
    return output


def source_commit(name: str, manifest: dict[str, Any]) -> str:
    if name in {"direct", "structural"}:
        return str(manifest["source_code"]["git_commit"])
    if name == "no_safe":
        return str(
            manifest.get(
                "budget_source_commit",
                manifest.get("pilot_source_commit", ""),
            )
        )
    if name == "paired":
        return str(manifest["source"]["commit"])
    if name == "oracle":
        return str(manifest["source_code"]["git_commit"])
    if name == "policy":
        return str(manifest["source_commit"])
    if name == "security":
        return str(manifest["source_commit"])
    raise ValueError(f"unsupported evidence kind {name}")


def validate_direct_final(
    name: str,
    manifest: dict[str, Any],
) -> None:
    summary = manifest.get("structural_summary", {})
    scope_policy = manifest.get("scope_policy", {})
    workloads = manifest.get("workloads", [])
    expected = FINAL_REQUIRED_WORKLOADS[name]
    if (
        manifest.get("evidence_stage") != "confirmatory"
        or manifest.get("evidence_type")
        != "observed_no_retuning_locked_audit_confirmatory"
        or summary.get("complete") is not True
        or summary.get("recorded_runs") != expected
        or summary.get("locked_audit_passes") != expected
        or summary.get("locked_audit_fails") != 0
        or summary.get("retuned_runs") != 0
        or summary.get("zero_flip_passes") != expected
        or summary.get("zero_violation_passes") != expected
        or scope_policy.get("require_source_replay") is not True
        or not isinstance(workloads, list)
        or len(workloads) != expected
        or any(
            not isinstance(row, dict)
            or row.get("source_replay_verified") is not True
            or row.get("source_feature_space") != "model_input"
            or row.get("preprocessing_method")
            != "identity_model_input_v1"
            or row.get("audit_source_replay_verified") is not True
            or row.get("audit_source_feature_space")
            != "model_input"
            or row.get("audit_preprocessing_method")
            != "identity_model_input_v1"
            for row in workloads
        )
    ):
        raise ValueError(
            f"{name} pack does not satisfy final locked-audit "
            "and source-replay gates"
        )


def validate_final_profile(
    manifests: dict[str, dict[str, Any]],
) -> str:
    for name in ("direct", "structural"):
        validate_direct_final(name, manifests[name])

    security = manifests["security"]
    if (
        security.get("artifact_id")
        != "security_v2_static_attestation"
        or security.get("classification") != "PRELIMINARY"
        or security.get("encrypted_execution_performed") is not False
        or security.get("security_policy_id")
        != "security_guidelines_cic2025_table5_2_ternary_128_v2"
        or security.get("oracle_summary", {}).get(
            "allow_incomplete"
        )
        is not False
        or security.get("oracle_summary", {}).get(
            "reference_candidate_v2_admission"
        )
        != "PASS"
    ):
        raise ValueError(
            "security pack does not satisfy V2 static-attestation gates"
        )

    no_safe = manifests["no_safe"]
    if (
        no_safe.get("schema_version") != 2
        or no_safe.get("status")
        != "CONFIRMATORY_DISJOINT_CONTROLS"
        or no_safe.get("finite_audit_control_result") != "PASS"
        or no_safe.get("counts", {}).get(
            "finite_audit_attempts"
        )
        != 300
        or no_safe.get("counts", {}).get("finite_audit_no_safe")
        != 50
    ):
        raise ValueError(
            "no_safe pack does not satisfy final disjoint-control gates"
        )

    paired = manifests["paired"]
    if (
        paired.get("mode") != "FINAL"
        or paired.get("status") != "FINAL_PAIRED_VERIFIED"
        or paired.get("paper_latency_claim_allowed") is not True
        or paired.get("counts", {}).get("decision_flips") != 0
    ):
        raise ValueError(
            "paired pack does not satisfy final latency gates"
        )

    final_commits = {
        source_commit(name, manifests[name])
        for name in (
            "direct",
            "structural",
            "no_safe",
            "paired",
        )
    }
    finite_commit = str(
        no_safe.get("finite_audit_source_commit", "")
    )
    if len(final_commits) != 1 or finite_commit not in final_commits:
        raise ValueError(
            "final evidence packs do not share one source commit"
        )
    return next(iter(final_commits))


def format_number(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def write_csv(
    path: Path,
    headers: list[str],
    rows: Iterable[Iterable[Any]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)


def markdown_table(
    headers: list[str],
    rows: Iterable[Iterable[Any]],
) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "\\|") for value in row
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_table_pair(
    table_dir: Path,
    stem: str,
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    note: str,
) -> None:
    write_csv(table_dir / f"{stem}.csv", headers, rows)
    content = (
        f"# {title}\n\n"
        f"Evidence note: {note}\n\n"
        + markdown_table(headers, rows)
    )
    (table_dir / f"{stem}.md").write_text(
        content,
        encoding="utf-8",
    )


def direct_rows(root: Path) -> tuple[list[list[Any]], dict[str, int]]:
    audit_rows = read_csv(root / "outputs/locked_audit_results.csv")
    manifest = load_json(root / "manifest.json")
    replay_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in manifest.get("workloads", []):
        if isinstance(record, dict):
            replay_by_model[str(record.get("model_id", ""))].append(
                record
            )
    selections = [
        load_json(path)
        for path in sorted((root / "inputs/selections").glob("*.json"))
    ]
    selection_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for selection in selections:
        model = str(selection["plan"]["contract"]["model_id"])
        selection_by_model[model].append(selection)

    audit_by_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in audit_rows:
        audit_by_model[row["model_id"]].append(row)

    rows: list[list[Any]] = []
    totals = {
        "workloads": 0,
        "configuration_trials": 0,
        "selection_key_runs": 0,
        "locked_audit_key_runs": 0,
        "locked_audit_passes": 0,
        "decision_flips": 0,
        "error_violations": 0,
        "selection_source_replay_workloads": 0,
        "audit_source_replay_workloads": 0,
    }
    for model in sorted(audit_by_model):
        model_audits = audit_by_model[model]
        model_selections = selection_by_model[model]
        values = {
            "workloads": len(model_audits),
            "configuration_trials": sum(
                int(item["trials_used"]) for item in model_selections
            ),
            "selection_key_runs": sum(
                int(item["encrypted_key_runs"])
                for item in model_selections
            ),
            "locked_audit_key_runs": sum(
                int(item["key_repeats_completed"])
                for item in model_audits
            ),
            "locked_audit_passes": sum(
                row["outcome"] == "LOCKED_AUDIT_PASS"
                for row in model_audits
            ),
            "decision_flips": sum(
                int(row["decision_flips"]) for row in model_audits
            ),
            "error_violations": sum(
                int(row["error_violations"]) for row in model_audits
            ),
            "v_cert": sum(int(row["v_cert"]) for row in model_audits),
            "v_amb": sum(int(row["v_amb"]) for row in model_audits),
            "selection_source_replay_workloads": sum(
                record.get("source_replay_verified") is True
                for record in replay_by_model[model]
            ),
            "audit_source_replay_workloads": sum(
                record.get("audit_source_replay_verified") is True
                for record in replay_by_model[model]
            ),
        }
        for key in totals:
            totals[key] += values[key]
        rows.append(
            [
                model,
                values["workloads"],
                values["configuration_trials"],
                values["selection_key_runs"],
                values["locked_audit_key_runs"],
                values["locked_audit_passes"],
                values["decision_flips"],
                values["error_violations"],
                values["v_cert"],
                values["v_amb"],
                values["selection_source_replay_workloads"],
                values["audit_source_replay_workloads"],
            ]
        )
    rows.append(
        [
            "ALL",
            totals["workloads"],
            totals["configuration_trials"],
            totals["selection_key_runs"],
            totals["locked_audit_key_runs"],
            totals["locked_audit_passes"],
            totals["decision_flips"],
            totals["error_violations"],
            sum(int(row["v_cert"]) for row in audit_rows),
            sum(int(row["v_amb"]) for row in audit_rows),
            totals["selection_source_replay_workloads"],
            totals["audit_source_replay_workloads"],
        ]
    )
    return rows, totals


def oracle_rows(root: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    direct = load_json(root / "outputs/direct/summary.json")
    planner = load_json(
        root / "outputs/planner/derived_metrics.json"
    )
    catalog = int(direct["catalog_candidate_executions"])
    trials = int(direct["direct_trials"])
    reduction = 100.0 * (1.0 - trials / catalog)
    rows = [
        [
            "direct_synthesis",
            int(direct["complete_oracle_workloads_compared"]),
            trials,
            int(direct["direct_key_runs"]),
            int(direct["direct_key_runs"]),
            "input-conditioned synthesis + repair",
            "PRIMARY_METHOD_COUNT_COMPARISON",
        ],
        [
            "fixed_catalog_oracle",
            int(direct["complete_oracle_workloads_compared"]),
            catalog,
            catalog,
            catalog * 3,
            "22 candidates/workload",
            "BOUNDED_ORACLE_BASELINE",
        ],
        [
            "planner_projection",
            int(planner["all"]["rows"]),
            "",
            "",
            "",
            (
                "pruning="
                + format_number(
                    100.0 * float(planner["all"]["pruning_ratio"]),
                    2,
                )
                + "%; optimum recall="
                + format_number(
                    100.0 * float(planner["all"]["optimum_recall"]),
                    2,
                )
                + "%"
            ),
            "CANDIDATE_PROVIDER_ABLATION",
        ],
    ]
    metrics = {
        "catalog_executions": catalog,
        "catalog_three_key_runs": catalog * 3,
        "direct_trials": trials,
        "execution_reduction_pct": reduction,
        "direct_workloads": int(
            direct["complete_oracle_workloads_compared"]
        ),
        "planner": planner,
    }
    return rows, metrics


def policy_rows(root: Path) -> tuple[list[list[Any]], list[dict[str, str]]]:
    raw = read_csv(root / "results/synthesis_aggregate.csv")
    selected = [
        row
        for row in raw
        if row["partition"] == "configuration_validation"
        and float(row["alpha"]) == 0.5
    ]
    selected.sort(key=lambda row: float(row["margin_floor"]))
    rows = [
        [
            row["margin_floor"],
            row["workloads"],
            row["plan_ok"],
            row["no_certifiable_sample"],
            format_number(100.0 * float(row["aggregate_coverage"]), 4),
            row["candidate_signatures"],
        ]
        for row in selected
    ]
    return rows, selected


def no_safe_rows(root: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    manifest = load_json(root / "manifest.json")
    mode = str(manifest.get("budget_mode", "PILOT"))
    budget_dir = "budget_confirm" if mode == "CONFIRM" else "budget_pilot"
    budget = load_json(root / budget_dir / "summary/summary.json")
    counts = budget["counts"]
    outcomes = counts["outcomes"]
    rows = [
        [
            "budgeted_abstention",
            mode,
            counts["expected_workloads"],
            outcomes.get("NO_SAFE", 0),
            outcomes.get("SELECTED", 0),
            counts["unsafe_selected"],
            budget["control_result"],
            budget["claim_boundary"],
        ]
    ]
    metrics: dict[str, Any] = {
        "budget_mode": mode,
        "budget_workloads": counts["expected_workloads"],
        "budget_no_safe": outcomes.get("NO_SAFE", 0),
        "budget_selected": outcomes.get("SELECTED", 0),
        "budget_unsafe_selected": counts["unsafe_selected"],
    }
    audit_summary = (
        root / "finite_domain_locked_audit/summary/summary.json"
    )
    if audit_summary.is_file():
        finite = load_json(audit_summary)
        finite_metrics = finite["metrics"]
        rows.append(
            [
                "finite_domain_disjoint_audit",
                finite["mode"],
                finite_metrics["workloads"],
                finite_metrics["restricted_no_safe"],
                finite_metrics["restricted_selected"],
                finite_metrics["restricted_selected"],
                finite["control_result"],
                finite["claim_boundary"],
            ]
        )
        metrics.update(
            {
                "finite_kind": "DISJOINT_LOCKED_AUDIT",
                "finite_workloads": finite_metrics["workloads"],
                "finite_no_safe": finite_metrics[
                    "restricted_no_safe"
                ],
                "finite_selected": finite_metrics[
                    "restricted_selected"
                ],
                "finite_candidate_rows": finite_metrics[
                    "candidate_rows"
                ],
                "finite_attempts": finite_metrics["attempts"],
            }
        )
    else:
        finite = load_json(root / "finite_domain/summary.json")
        finite_metrics = finite["metrics"]
        rows.append(
            [
                "finite_domain_restricted",
                "RETROSPECTIVE",
                finite_metrics["workloads"],
                finite_metrics["restricted_no_safe"],
                finite_metrics["restricted_selected"],
                0,
                finite["control_result"],
                finite["claim_boundary"],
            ]
        )
        metrics.update(
            {
                "finite_kind": "RETROSPECTIVE",
                "finite_workloads": finite_metrics["workloads"],
                "finite_no_safe": finite_metrics[
                    "restricted_no_safe"
                ],
                "finite_selected": finite_metrics[
                    "restricted_selected"
                ],
                "finite_candidate_rows": finite_metrics[
                    "candidate_rows"
                ],
                "finite_attempts": "",
            }
        )
    return rows, metrics


def paired_rows(root: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    manifest = load_json(root / "manifest.json")
    pairs = read_csv(root / "summary/aggregate_pairs.csv")
    rows = [
        [
            row["numerator_arm_id"],
            row["denominator_arm_id"],
            row["workloads"],
            row["pairs"],
            format_number(
                float(row["geometric_mean_total_ratio"]), 6
            ),
            format_number(
                float(
                    row["total_ratio_workload_bootstrap_ci95_low"]
                ),
                6,
            ),
            format_number(
                float(
                    row["total_ratio_workload_bootstrap_ci95_high"]
                ),
                6,
            ),
            manifest["mode"],
            str(manifest["paper_latency_claim_allowed"]).lower(),
        ]
        for row in pairs
    ]
    primary = manifest["primary_pair"]
    metrics = {
        "mode": manifest["mode"],
        "claim_allowed": manifest["paper_latency_claim_allowed"],
        "ratio": float(primary["geometric_mean_total_ratio"]),
        "ci_low": float(primary["ci95_low"]),
        "ci_high": float(primary["ci95_high"]),
        "numerator": primary["numerator"],
        "denominator": primary["denominator"],
    }
    return rows, metrics


def svg_document(
    title: str,
    subtitle: str,
    body: str,
    width: int = 960,
    height: int = 540,
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="#ffffff"/>
  <text x="48" y="56" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="#111827">{html.escape(title)}</text>
  <text x="48" y="84" font-family="Arial, sans-serif" font-size="15" fill="#4b5563">{html.escape(subtitle)}</text>
  {body}
</svg>
"""


def framework_figure(path: Path, status: str) -> None:
    body = """
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4"
      orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z" fill="#374151"/>
    </marker>
    <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="4"
      orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z" fill="#dc2626"/>
    </marker>
  </defs>

  <rect x="48" y="112" width="190" height="66" rx="6"
    fill="#dbeafe" stroke="#2563eb" stroke-width="2"/>
  <text x="143" y="139" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="15" font-weight="700"
    fill="#111827">Model graph</text>
  <text x="143" y="161" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="13"
    fill="#374151">depth, ops, artifacts</text>

  <rect x="273" y="112" width="190" height="66" rx="6"
    fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
  <text x="368" y="139" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="15" font-weight="700"
    fill="#111827">Held-out feature data</text>
  <text x="368" y="161" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="13"
    fill="#374151">preprocess + score + decision</text>

  <rect x="498" y="112" width="190" height="66" rx="6"
    fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
  <text x="593" y="139" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="15" font-weight="700"
    fill="#111827">Policy contract</text>
  <text x="593" y="161" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="13"
    fill="#374151">security, alpha, floor</text>

  <rect x="723" y="112" width="189" height="66" rx="6"
    fill="#f3e8ff" stroke="#9333ea" stroke-width="2"/>
  <text x="817.5" y="139" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="15" font-weight="700"
    fill="#111827">Execution budget</text>
  <text x="817.5" y="161" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="13"
    fill="#374151">trials, keys, paths</text>

  <line x1="143" y1="178" x2="143" y2="207" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="368" y1="178" x2="368" y2="207" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="593" y1="178" x2="593" y2="207" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="817.5" y1="178" x2="817.5" y2="207" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>

  <rect x="48" y="211" width="864" height="48" rx="6"
    fill="#111827"/>
  <text x="480" y="241" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="17" font-weight="700"
    fill="#ffffff">Digest-bound workload contract</text>

  <rect x="48" y="300" width="158" height="92" rx="6"
    fill="#e0f2fe" stroke="#0284c7" stroke-width="2"/>
  <text x="127" y="330" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">1. Bind scope</text>
  <text x="127" y="352" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">model, source, prepared</text>
  <text x="127" y="371" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">and exact digests</text>

  <rect x="226" y="300" width="158" height="92" rx="6"
    fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
  <text x="305" y="330" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">2. Synthesize</text>
  <text x="305" y="352" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">direct CKKS literal</text>
  <text x="305" y="371" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">from graph and budget</text>

  <rect x="404" y="300" width="158" height="92" rx="6"
    fill="#fef3c7" stroke="#d97706" stroke-width="2"/>
  <text x="483" y="330" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">3. Validate</text>
  <text x="483" y="352" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">encrypted execution</text>
  <text x="483" y="371" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">flip and error gate</text>

  <rect x="582" y="300" width="158" height="92" rx="6"
    fill="#ffedd5" stroke="#ea580c" stroke-width="2"/>
  <text x="661" y="330" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">4. Repair on failure</text>
  <text x="661" y="352" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">increase scale or level</text>
  <text x="661" y="371" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">within frozen budget</text>

  <rect x="760" y="300" width="152" height="92" rx="6"
    fill="#ede9fe" stroke="#7c3aed" stroke-width="2"/>
  <text x="836" y="330" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">5. Decide</text>
  <text x="836" y="352" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">SAFE / REJECTED</text>
  <text x="836" y="371" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">FAILED / NO_SAFE</text>

  <line x1="206" y1="346" x2="222" y2="346" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="384" y1="346" x2="400" y2="346" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="562" y1="346" x2="578" y2="346" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <line x1="740" y1="346" x2="756" y2="346" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>

  <path d="M661,300 C661,274 483,274 483,296" fill="none"
    stroke="#ea580c" stroke-width="2" stroke-dasharray="5 4"
    marker-end="url(#arrow)"/>
  <text x="571" y="277" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="11"
    fill="#9a3412">retry only after observed failure</text>

  <line x1="836" y1="392" x2="836" y2="423" stroke="#374151"
    stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="538" y="430" width="374" height="62" rx="6"
    fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
  <text x="725" y="456" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#111827">SAFE: no-retuning locked audit</text>
  <text x="725" y="478" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#374151">fresh keys, disjoint rows, reproducible evidence pack</text>

  <path d="M800,392 C700,415 450,414 408,450" fill="none"
    stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-red)"/>
  <rect x="48" y="430" width="360" height="62" rx="6"
    fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>
  <text x="228" y="456" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="14" font-weight="700"
    fill="#991b1b">NO_SAFE: abstain within declared scope</text>
  <text x="228" y="478" text-anchor="middle"
    font-family="Arial, sans-serif" font-size="12"
    fill="#7f1d1d">never promote an uncertified candidate</text>
"""
    path.write_text(
        svg_document(
            "FlipGuard: Input-Conditioned CKKS Configuration Synthesis",
            (
                f"{status}; direct synthesis is primary; "
                "fixed catalogs are evaluation-only bounded oracles"
            ),
            body,
        ),
        encoding="utf-8",
    )


def bar_figure(
    path: Path,
    title: str,
    subtitle: str,
    values: list[tuple[str, float, str]],
    suffix: str = "",
) -> None:
    max_value = max(value for _, value, _ in values) or 1.0
    chart_left = 320
    chart_width = 560
    row_height = 88
    body = [
        f'<line x1="{chart_left}" y1="120" '
        f'x2="{chart_left}" y2="470" '
        'stroke="#9ca3af" stroke-width="1"/>'
    ]
    for index, (label, value, color) in enumerate(values):
        y = 130 + index * row_height
        width = chart_width * value / max_value
        body.extend(
            [
                (
                    f'<text x="48" y="{y + 31}" '
                    'font-family="Arial, sans-serif" font-size="15" '
                    f'fill="#1f2937">{html.escape(label)}</text>'
                ),
                (
                    f'<rect x="{chart_left}" y="{y}" width="{width:.2f}" '
                    f'height="42" rx="4" fill="{color}"/>'
                ),
                (
                    f'<text x="{min(chart_left + width + 12, 900):.2f}" '
                    f'y="{y + 28}" font-family="Arial, sans-serif" '
                    'font-size="16" font-weight="700" fill="#111827">'
                    f'{html.escape(format_number(value, 4) + suffix)}</text>'
                ),
            ]
        )
    path.write_text(
        svg_document(title, subtitle, "\n  ".join(body)),
        encoding="utf-8",
    )


def effort_figure(
    path: Path,
    status: str,
    metrics: dict[str, Any],
) -> None:
    reduction = metrics["execution_reduction_pct"]
    subtitle = (
        f"{status}; bounded catalog comparison only; "
        f"{format_number(reduction, 2)}% fewer configuration executions"
    )
    bar_figure(
        path,
        "Configuration Search Effort",
        subtitle,
        [
            (
                "Fixed 22-candidate catalog",
                float(metrics["catalog_executions"]),
                "#64748b",
            ),
            (
                "Input-conditioned direct synthesis",
                float(metrics["direct_trials"]),
                "#16a34a",
            ),
        ],
    )


def audit_figure(
    path: Path,
    status: str,
    rows: list[list[Any]],
) -> None:
    values = [
        (str(row[0]), float(row[5]), "#2563eb")
        for row in rows
        if row[0] != "ALL"
    ]
    bar_figure(
        path,
        "Disjoint Locked-Audit Passes",
        (
            f"{status}; zero decision flips and zero protected "
            "error-budget violations"
        ),
        values,
        suffix="/25",
    )


def policy_figure(
    path: Path,
    status: str,
    rows: list[dict[str, str]],
) -> None:
    left, top, width, height = 90.0, 125.0, 800.0, 310.0
    points = []
    body = [
        (
            f'<line x1="{left}" y1="{top + height}" '
            f'x2="{left + width}" y2="{top + height}" '
            'stroke="#6b7280"/>'
        ),
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" '
            f'y2="{top + height}" stroke="#6b7280"/>'
        ),
    ]
    for index, row in enumerate(rows):
        x = left + width * index / max(1, len(rows) - 1)
        coverage = float(row["aggregate_coverage"])
        y = top + height * (1.0 - coverage)
        points.append(f"{x:.2f},{y:.2f}")
        body.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#dc2626"/>'
        )
        body.append(
            f'<text x="{x:.2f}" y="{top + height + 28}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#374151">{html.escape(row["margin_floor"])}</text>'
        )
    body.append(
        '<polyline points="'
        + " ".join(points)
        + '" fill="none" stroke="#dc2626" stroke-width="3"/>'
    )
    for label, value in (("100%", 1.0), ("50%", 0.5), ("0%", 0.0)):
        y = top + height * (1.0 - value)
        body.append(
            f'<text x="{left - 14}" y="{y + 4:.2f}" text-anchor="end" '
            f'font-family="Arial, sans-serif" font-size="12" fill="#374151">{label}</text>'
        )
    body.append(
        '<text x="490" y="500" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#374151">'
        "Margin floor</text>"
    )
    path.write_text(
        svg_document(
            "Certified Coverage vs Margin Floor",
            (
                f"{status}; alpha=0.5, configuration-validation "
                "partition; static sensitivity, not per-floor CKKS recertification"
            ),
            "\n  ".join(body),
        ),
        encoding="utf-8",
    )


def no_safe_figure(
    path: Path,
    status: str,
    metrics: dict[str, Any],
) -> None:
    bar_figure(
        path,
        "Abstention Controls",
        (
            f"{status}; {metrics['finite_kind']}; NO_SAFE is scoped "
            "to the declared budget or finite domain"
        ),
        [
            (
                "Budgeted control: NO_SAFE",
                float(metrics["budget_no_safe"]),
                "#f59e0b",
            ),
            (
                "Finite-domain control: NO_SAFE",
                float(metrics["finite_no_safe"]),
                "#dc2626",
            ),
        ],
    )


def paired_figure(
    path: Path,
    status: str,
    metrics: dict[str, Any],
) -> None:
    x0, x1 = 120.0, 860.0
    low = min(0.8, metrics["ci_low"] - 0.1)
    high = max(2.2, metrics["ci_high"] + 0.1)

    def x(value: float) -> float:
        return x0 + (value - low) / (high - low) * (x1 - x0)

    y = 270
    body = [
        f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#6b7280"/>',
        (
            f'<line x1="{x(1.0):.2f}" y1="150" x2="{x(1.0):.2f}" '
            'y2="390" stroke="#9ca3af" stroke-dasharray="6 6"/>'
        ),
        (
            f'<line x1="{x(metrics["ci_low"]):.2f}" y1="{y}" '
            f'x2="{x(metrics["ci_high"]):.2f}" y2="{y}" '
            'stroke="#2563eb" stroke-width="8"/>'
        ),
        (
            f'<circle cx="{x(metrics["ratio"]):.2f}" cy="{y}" r="12" '
            'fill="#dc2626"/>'
        ),
        (
            f'<text x="{x(metrics["ratio"]):.2f}" y="{y - 30}" '
            'text-anchor="middle" font-family="Arial, sans-serif" '
            'font-size="17" font-weight="700" fill="#111827">'
            f'{format_number(metrics["ratio"], 4)}x</text>'
        ),
        (
            f'<text x="{x0}" y="330" font-family="Arial, sans-serif" '
            'font-size="14" fill="#374151">'
            f'95% interval [{format_number(metrics["ci_low"], 4)}, '
            f'{format_number(metrics["ci_high"], 4)}]</text>'
        ),
        (
            f'<text x="{x0}" y="360" font-family="Arial, sans-serif" '
            'font-size="14" fill="#374151">'
            f'{html.escape(str(metrics["numerator"]))} / '
            f'{html.escape(str(metrics["denominator"]))}</text>'
        ),
    ]
    subtitle = (
        f"{status}; mode={metrics['mode']}; paper latency claim "
        f"allowed={str(metrics['claim_allowed']).lower()}"
    )
    path.write_text(
        svg_document(
            "Paired Total-Latency Ratio",
            subtitle,
            "\n  ".join(body),
        ),
        encoding="utf-8",
    )


def build(
    output: Path,
    selected_profile: str,
    packs: dict[str, Path],
    force: bool,
) -> dict[str, Any]:
    if output.exists():
        if not force:
            raise FileExistsError(
                f"{output} already exists; pass --force to replace it"
            )
        shutil.rmtree(output)
    table_dir = output / "tables"
    figure_dir = output / "figures"
    appendix_dir = output / "appendix"
    table_dir.mkdir(parents=True)
    figure_dir.mkdir()
    appendix_dir.mkdir()

    resolved_packs = {
        name: resolve(path).resolve() for name, path in packs.items()
    }
    manifests: dict[str, dict[str, Any]] = {}
    verification: dict[str, str] = {}
    inputs: list[dict[str, Any]] = []
    for name in sorted(resolved_packs):
        root = resolved_packs[name]
        verification[name] = verify_pack(name, root)
        manifest_path = root / "manifest.json"
        manifest = load_json(manifest_path)
        manifests[name] = manifest
        digest, file_count = tree_digest(root)
        inputs.append(
            {
                "name": name,
                "evidence_id": manifest.get(
                    "evidence_id",
                    manifest.get("artifact_id", ""),
                ),
                "path": portable(root),
                "manifest_sha256": sha256_file(manifest_path),
                "tree_sha256": digest,
                "file_count": file_count,
                "source_commit": source_commit(name, manifest),
                "verifier": VERIFIERS[name],
            }
        )

    final_commit = ""
    if selected_profile == "final":
        final_commit = validate_final_profile(manifests)
        publication_status = "FINAL_ADMISSIBLE"
    else:
        publication_status = "NON_AUTHORITATIVE_SCAFFOLD"

    status_label = (
        "Final confirmatory evidence"
        if publication_status == "FINAL_ADMISSIBLE"
        else "Preliminary evidence only"
    )

    direct_table, direct_metrics = direct_rows(
        resolved_packs["direct"]
    )
    direct_headers = [
        "model_id",
        "workloads",
        "configuration_trials",
        "selection_key_runs",
        "locked_audit_key_runs",
        "locked_audit_passes",
        "decision_flips",
        "error_violations",
        "v_cert",
        "v_amb",
        "selection_source_replay_workloads",
        "audit_source_replay_workloads",
    ]
    write_table_pair(
        table_dir,
        "01_direct_synthesis_locked_audit",
        "Direct Synthesis and Locked Audit",
        direct_headers,
        direct_table,
        (
            f"{status_label}. The audit reuses the selected candidate "
            "without retuning on a disjoint locked split."
        ),
    )

    oracle_table, oracle_metrics = oracle_rows(
        resolved_packs["oracle"]
    )
    oracle_table[0][2] = direct_metrics["configuration_trials"]
    oracle_table[0][3] = direct_metrics["selection_key_runs"]
    oracle_table[0][4] = direct_metrics["selection_key_runs"]
    oracle_metrics["direct_trials"] = direct_metrics[
        "configuration_trials"
    ]
    oracle_metrics["execution_reduction_pct"] = 100.0 * (
        1.0
        - direct_metrics["configuration_trials"]
        / oracle_metrics["catalog_executions"]
    )
    write_table_pair(
        table_dir,
        "02_search_effort_and_bounded_oracle",
        "Search Effort and Bounded Oracle",
        [
            "method",
            "workloads_or_rows",
            "configuration_candidates_evaluated",
            "observed_encrypted_runs",
            "normalized_three_key_runs",
            "scope",
            "evidence_role",
        ],
        oracle_table,
        (
            "The fixed catalog is a 22-candidate bounded oracle and "
            "baseline. Unpaired timing fields are excluded from claims."
        ),
    )

    policy_table, policy_raw = policy_rows(
        resolved_packs["policy"]
    )
    write_table_pair(
        table_dir,
        "03_margin_floor_sensitivity",
        "Margin-Floor Sensitivity",
        [
            "margin_floor",
            "workloads",
            "plan_ok",
            "no_certifiable_sample",
            "aggregate_coverage_pct",
            "candidate_signatures",
        ],
        policy_table,
        (
            "Static synthesis sensitivity at alpha=0.5. It does not "
            "replace encrypted recertification of a chosen final floor."
        ),
    )

    no_safe_table, no_safe_metrics = no_safe_rows(
        resolved_packs["no_safe"]
    )
    write_table_pair(
        table_dir,
        "04_no_safe_controls",
        "NO_SAFE Controls",
        [
            "control",
            "mode",
            "workloads",
            "no_safe",
            "selected",
            "unsafe_selected",
            "control_result",
            "claim_boundary",
        ],
        no_safe_table,
        (
            f"{status_label}. NO_SAFE is never interpreted as a global "
            "claim outside the declared budget or finite candidate domain."
        ),
    )

    paired_table, paired_metrics = paired_rows(
        resolved_packs["paired"]
    )
    write_table_pair(
        table_dir,
        "05_paired_latency",
        "Paired Latency",
        [
            "numerator",
            "denominator",
            "workloads",
            "pairs",
            "geometric_mean_total_ratio",
            "ci95_low",
            "ci95_high",
            "mode",
            "paper_claim_allowed",
        ],
        paired_table,
        (
            "Only a FINAL pack with paper_claim_allowed=true supports "
            "a paper latency claim. PILOT values tune the protocol only."
        ),
    )

    scope_rows = [
        [
            "direct synthesis + disjoint locked audit",
            "primary",
            publication_status,
            (
                "Observed decision preservation on frozen V_cert and "
                "disjoint locked-audit rows; no universal guarantee."
            ),
        ],
        [
            "fixed 22-candidate grid",
            "bounded oracle/baseline",
            "BOUNDED_DOMAIN_ONLY",
            (
                "Measures performance within the declared catalog; "
                "does not establish an optimum outside that domain."
            ),
        ],
        [
            "linear zero-gain / rejected candidates",
            "negative control",
            "CONTROL_EVIDENCE",
            (
                "Demonstrates abstention/rejection behavior; it is not "
                "evidence that all linear workloads have no useful plan."
            ),
        ],
        [
            "paired latency",
            "diagnostic"
            if not paired_metrics["claim_allowed"]
            else "confirmatory",
            (
                "PILOT_ONLY"
                if not paired_metrics["claim_allowed"]
                else "FINAL_PAIRED_VERIFIED"
            ),
            (
                "Pilot values are excluded from the abstract, main "
                "claim, and final performance comparison."
            ),
        ],
    ]
    if "structural" in resolved_packs:
        structural_table, _ = direct_rows(
            resolved_packs["structural"]
        )
        write_table_pair(
            table_dir,
            "06_structural_extension_locked_audit",
            "Structural Extension Locked Audit",
            direct_headers,
            structural_table,
            (
                "Depth-3 polynomial MLP extension under the same "
                "no-retuning locked-audit protocol."
            ),
        )
        scope_rows.append(
            [
                "depth-3 structural extension",
                "scope extension",
                publication_status,
                "Supports the declared mlp_square_poly3 scope only.",
            ]
        )
    else:
        scope_rows.append(
            [
                "depth-3 structural extension",
                "pending scope extension",
                "STATIC_ONLY_PENDING_EXECUTION",
                (
                    "Static feasibility is not promoted to encrypted "
                    "execution or locked-audit evidence."
                ),
            ]
        )
    write_table_pair(
        table_dir,
        "00_claim_evidence_registry",
        "Claim and Evidence Registry",
        ["claim", "role", "status", "allowed_interpretation"],
        scope_rows,
        "This registry controls how every numerical result may be used.",
    )

    framework_figure(
        figure_dir / "figure_01_framework.svg",
        status_label,
    )
    effort_figure(
        figure_dir / "figure_02_search_effort.svg",
        status_label,
        oracle_metrics,
    )
    audit_figure(
        figure_dir / "figure_03_locked_audit.svg",
        status_label,
        direct_table,
    )
    policy_figure(
        figure_dir / "figure_04_margin_floor_coverage.svg",
        status_label,
        policy_raw,
    )
    no_safe_figure(
        figure_dir / "figure_05_no_safe_controls.svg",
        status_label,
        no_safe_metrics,
    )
    paired_figure(
        figure_dir / "figure_06_paired_latency.svg",
        status_label,
        paired_metrics,
    )

    readme = f"""# FlipGuard V2 paper artifacts

- Publication status: `{publication_status}`
- Evidence profile: `{selected_profile}`
- Final source commit: `{final_commit or "N/A"}`

All tables and figures in this directory were derived only after every
selected evidence pack passed its native verifier. The output manifest
binds the exact input trees and generated files. Its `manuscript_gate`
also binds the manuscript digest, Figure/Table mapping, and the exact
evidence-conditioned final result and conclusion claim blocks.

## Interpretation

The proposed method is input-conditioned direct configuration synthesis,
encrypted certification, bounded repair, explicit rejection/NO_SAFE, and a
no-retuning disjoint locked audit. The fixed 22-candidate experiment is kept
as a bounded oracle and baseline. It is not described as the tuner.

`NON_AUTHORITATIVE_SCAFFOLD` values must not be used as final abstract, conclusion, or
headline performance claims. A `FINAL_ADMISSIBLE` build requires the four
confirmatory packs, their semantic gates, workload-complete selection and
locked-audit source replay in the direct/structural packs, the independently
verified Security V2 static pack, and one shared execution source commit.

## Files

- `tables/00_claim_evidence_registry.*`: allowed claim roles and boundaries.
- `tables/01_direct_synthesis_locked_audit.*`: primary safety workflow.
- `tables/02_search_effort_and_bounded_oracle.*`: direct versus bounded grid.
- `tables/03_margin_floor_sensitivity.*`: static policy sensitivity.
- `tables/04_no_safe_controls.*`: abstention falsification controls.
- `tables/05_paired_latency.*`: paired protocol, pilot or final as marked.
- `figures/figure_01_framework.svg`: input-conditioned primary workflow.
- `figures/*.svg`: deterministic paper figures with evidence status labels.
- `appendix/evidence_manifest.json`: evidence, output, and manuscript bindings.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    expected_manuscript_claims = None
    if publication_status == "FINAL_ADMISSIBLE":
        expected_manuscript_claims = render_final_manuscript_claims(
            direct_metrics,
            oracle_metrics,
            no_safe_metrics,
            paired_metrics,
        )
        update_manuscript_claims(
            resolve(MANUSCRIPT_PATH),
            expected_manuscript_claims,
        )
    manuscript_gate = validate_manuscript_publication_gate(
        publication_status,
        output,
        expected_claims=expected_manuscript_claims,
    )

    generated = sorted(
        path
        for path in output.rglob("*")
        if path.is_file()
        and path != appendix_dir / "evidence_manifest.json"
    )
    manifest = {
        "schema_version": 1,
        "artifact_id": "flipguard_v2_paper_artifacts",
        "publication_status": publication_status,
        "evidence_profile": selected_profile,
        "final_source_commit": final_commit or None,
        "builder": {
            "path": portable(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
        "manuscript_gate": manuscript_gate,
        "inputs": inputs,
        "verification": verification,
        "derived_metrics": {
            "direct_workloads": direct_metrics["workloads"],
            "direct_configuration_trials": direct_metrics[
                "configuration_trials"
            ],
            "direct_selection_key_runs": direct_metrics[
                "selection_key_runs"
            ],
            "direct_locked_audit_key_runs": direct_metrics[
                "locked_audit_key_runs"
            ],
            "direct_locked_audit_passes": direct_metrics[
                "locked_audit_passes"
            ],
            "direct_decision_flips": direct_metrics[
                "decision_flips"
            ],
            "direct_error_violations": direct_metrics[
                "error_violations"
            ],
            "direct_selection_source_replay_workloads": direct_metrics[
                "selection_source_replay_workloads"
            ],
            "direct_audit_source_replay_workloads": direct_metrics[
                "audit_source_replay_workloads"
            ],
            "catalog_candidate_executions": oracle_metrics[
                "catalog_executions"
            ],
            "catalog_normalized_three_key_runs": oracle_metrics[
                "catalog_three_key_runs"
            ],
            "direct_vs_catalog_execution_reduction_pct": (
                oracle_metrics["execution_reduction_pct"]
            ),
            "no_safe": no_safe_metrics,
            "paired_latency": paired_metrics,
        },
        "outputs": [
            {
                "path": str(path.relative_to(output)),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in generated
        ],
        "claim_boundary": (
            "The fixed catalog is a bounded oracle/baseline. "
            "Decision preservation is observed on declared validation "
            "and locked-audit rows, not proven over an input "
            "distribution. NO_SAFE is scoped to a declared budget or "
            "finite domain. Latency is claimable only when the paired "
            "evidence pack explicitly permits it."
        ),
    }
    (appendix_dir / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = {
        path.relative_to(expected)
        for path in expected.rglob("*")
        if path.is_file()
    }
    actual_files = {
        path.relative_to(actual)
        for path in actual.rglob("*")
        if path.is_file()
    }
    if expected_files != actual_files:
        raise ValueError(
            "paper artifact file set changed: "
            f"missing={sorted(expected_files - actual_files)} "
            f"extra={sorted(actual_files - expected_files)}"
        )
    changed = [
        str(path)
        for path in sorted(expected_files)
        if sha256_file(expected / path) != sha256_file(actual / path)
    ]
    if changed:
        raise ValueError(
            "paper artifact content changed: " + ", ".join(changed)
        )


def verify_output(
    output: Path,
    selected_profile: str,
    packs: dict[str, Path],
) -> None:
    if not output.is_dir():
        raise FileNotFoundError(f"missing paper artifact root: {output}")
    manifest_path = output / "appendix/evidence_manifest.json"
    manifest = load_json(manifest_path)
    if (
        manifest.get("artifact_id")
        != "flipguard_v2_paper_artifacts"
        or manifest.get("evidence_profile") != selected_profile
    ):
        raise ValueError("paper artifact manifest/profile changed")
    with tempfile.TemporaryDirectory(
        prefix="flipguard-paper-artifacts-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        build(rebuilt, selected_profile, packs, force=False)
        compare_trees(output, rebuilt)
    print(
        "flipguard_v2_paper_artifacts=VERIFIED "
        f"profile={selected_profile} "
        f"publication_status={manifest['publication_status']} "
        f"files={len(manifest['outputs']) + 1}"
    )


def main() -> int:
    args = parse_args()
    selected_profile, packs = select_packs(args.profile)
    output = resolve(args.output_root).resolve()
    if args.verify:
        verify_output(output, selected_profile, packs)
    else:
        manifest = build(
            output,
            selected_profile,
            packs,
            force=args.force,
        )
        print(
            "flipguard_v2_paper_artifacts=BUILT "
            f"profile={selected_profile} "
            f"publication_status={manifest['publication_status']} "
            f"output={portable(output)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
