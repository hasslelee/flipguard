#!/usr/bin/env python3
"""Freeze the complete structural extension, including its preserved rejection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SELECTION_ROOT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3"
)
AUDIT_ROOT = SELECTION_ROOT / (
    "locked_audit/"
    "full_structural_poly3_inputmodel_floor18_keys3_locked_audit_keys3"
)
PROTOCOL = SELECTION_ROOT / "summary/structural_protocol.json"
DEFAULT_OUTPUT = Path("docs/evidence/structural_extension_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def copy_bound(
    source: Path,
    output: Path,
    relative: Path,
    external: dict[str, dict[str, Any]],
) -> None:
    source = (REPO_ROOT / source).resolve()
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    external[str(source.relative_to(REPO_ROOT))] = {
        "bytes": source.stat().st_size,
        "sha256": sha256(source),
        "snapshot": str(relative),
    }


def generate(output: Path) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    protocol = read_json(REPO_ROOT / PROTOCOL)
    if (
        protocol.get("stage_status") != "PARTIAL_SCIENTIFIC_RESULT"
        or protocol.get("claim_state") != "PARTIALLY_SUPPORTED"
        or protocol.get("counts", {}).get("locked_audit_pass") != 24
        or protocol.get("counts", {}).get("locked_audit_rejected") != 1
        or protocol.get("counts", {}).get("policy_modification_after_audit") != 0
    ):
        raise ValueError("structural protocol is not the preserved partial result")

    selection_rows_path = REPO_ROOT / SELECTION_ROOT / "summary/workload_results.csv"
    audit_rows_path = REPO_ROOT / AUDIT_ROOT / "summary/locked_audit_results.csv"
    selection_rows = read_csv(selection_rows_path)
    audit_rows = read_csv(audit_rows_path)
    if len(selection_rows) != 25 or len(audit_rows) != 25:
        raise ValueError("structural evidence does not contain 25 paired instances")

    output.mkdir(parents=True)
    external: dict[str, dict[str, Any]] = {}
    fixed = {
        SELECTION_ROOT / "summary/summary.json": Path("summary/selection_summary.json"),
        SELECTION_ROOT / "summary/workload_results.csv": Path(
            "summary/selection_rows.csv"
        ),
        AUDIT_ROOT / "summary/summary.json": Path("summary/audit_summary.json"),
        AUDIT_ROOT / "summary/locked_audit_results.csv": Path(
            "summary/audit_rows.csv"
        ),
        PROTOCOL: Path("summary/structural_protocol.json"),
        Path(
            "results/thesis_grade_protocol/structural_extension_splits_v1/"
            "summary.json"
        ): Path("inputs/split_summary.json"),
        Path(
            "results/thesis_grade_protocol/structural_extension_v1/"
            "static_plans/summary.json"
        ): Path("inputs/static_plan_summary.json"),
        Path(
            "results/thesis_grade_protocol/structural_extension_v1/"
            "static_plans/plans.csv"
        ): Path("inputs/static_plans.csv"),
        Path(
            "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
            "run_manifest/run_manifest.json"
        ): Path("provenance/run_manifest.json"),
        Path(
            "results/thesis_grade_protocol/final_confirmatory_suite_v1/"
            "resume_provenance/resume_provenance.json"
        ): Path("provenance/resume_provenance.json"),
    }
    for source, relative in fixed.items():
        copy_bound(source, output, relative, external)

    seen_models: set[Path] = set()
    seen_inputs: set[Path] = set()
    for row in selection_rows:
        result_path = Path(row["result_path"])
        result = read_json(REPO_ROOT / result_path)
        seed = row["split_seed"]
        dataset = row["dataset_id"]
        tag = f"seed{seed}_{dataset}_mlp_square_poly3"
        copy_bound(
            result_path,
            output,
            Path("results/selection") / f"{tag}.json",
            external,
        )
        contract = result["plan"]["contract"]
        for item in ("validation_data", "source_data"):
            path = Path(contract[item]["path"])
            if path not in seen_inputs:
                seen_inputs.add(path)
                copy_bound(
                    path,
                    output,
                    Path("inputs/selection") / f"{tag}_{item}{path.suffix}",
                    external,
                )
        model = Path(contract["model_artifact"]["path"])
        if model not in seen_models:
            seen_models.add(model)
            copy_bound(
                model,
                output,
                Path("models") / dataset / model.name,
                external,
            )

    failures: list[dict[str, Any]] = []
    for row in audit_rows:
        result_path = Path(row["result_path"])
        result = read_json(REPO_ROOT / result_path)
        seed = row["split_seed"]
        dataset = row["dataset_id"]
        tag = f"seed{seed}_{dataset}_mlp_square_poly3"
        copy_bound(
            result_path,
            output,
            Path("results/audit") / f"{tag}.json",
            external,
        )
        contract = result["audit_contract"]
        for item in ("validation_data", "source_data"):
            path = Path(contract[item]["path"])
            if path not in seen_inputs:
                seen_inputs.add(path)
                copy_bound(
                    path,
                    output,
                    Path("inputs/audit") / f"{tag}_{item}{path.suffix}",
                    external,
                )
        split_manifest = Path(result["split_manifest"]["path"])
        if split_manifest not in seen_inputs:
            seen_inputs.add(split_manifest)
            copy_bound(
                split_manifest,
                output,
                Path("inputs/splits") / f"{tag}_split_manifest.json",
                external,
            )
        if result["outcome"] != "LOCKED_AUDIT_PASS":
            failures.append(
                {
                    "failure_class": (
                        "VALIDATION_NEAR_BUDGET_LIMIT_AUDIT_OVERRUN"
                    ),
                    "seed": int(seed),
                    "dataset": dataset,
                    "model": row["model_id"],
                    "candidate_literal": row["candidate_id"],
                    "selection_status": "SAFE",
                    "audit_status": row["trial_status"],
                    "audit_failure_signal": result["audit_trial"]["failure_signal"],
                    "audit_flips": int(row["decision_flips"]),
                    "audit_violations": int(row["error_violations"]),
                    "audit_max_usage": float(row["max_error_budget_usage"]),
                    "retuning": row["retuning_performed"] == "True",
                    "result_path": row["result_path"],
                    "result_sha256": sha256(REPO_ROOT / result_path),
                }
            )
    if len(failures) != 1:
        raise ValueError("expected one structural scientific negative result")
    (output / "summary/failure_record.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage_status": "PARTIAL_SCIENTIFIC_RESULT",
                "claim_state": "PARTIALLY_SUPPORTED",
                "failures": failures,
                "policy_modification_after_audit": 0,
                "candidate_reselection_after_audit": 0,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    readme = """# Structural extension evidence

This immutable pack preserves the frozen `mlp_square_poly3` selection and
no-retuning locked audit. Selection completed for 25/25 instances. Locked audit
passed 24/25 instances and numerically rejected one instance without a decision
flip. The scientific negative result lowers structural generalization to
`PARTIALLY_SUPPORTED`; it does not authorize repair or reselection.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    internal_files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name not in {"manifest.json", "SHA256SUMS"}
    )
    manifest = {
        "schema_version": 2,
        "evidence_id": "structural_extension_v1",
        "status": "PARTIAL_SCIENTIFIC_RESULT",
        "claim_state": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
        "block_reason": (
            "one of 25 no-retuning locked audits was numerically rejected; "
            "non-tabular structural holdout remains not evaluated"
        ),
        "counts": protocol["counts"],
        "negative_result": protocol["negative_result"],
        "source_code": {
            "git_commit": protocol["provenance"][
                "direct_selection_execution_commit"
            ],
            "execution_critical_source_digest": protocol["provenance"][
                "execution_critical_source_digest"
            ],
        },
        "provenance": protocol["provenance"],
        "external_artifacts": external,
        "files": {
            str(path.relative_to(output)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in internal_files
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_files = sorted(internal_files + [output / "manifest.json"])
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
            for path in checksum_files
        ),
        encoding="utf-8",
    )


def verify(output: Path) -> None:
    manifest = read_json(output / "manifest.json")
    if (
        manifest.get("status") != "PARTIAL_SCIENTIFIC_RESULT"
        or manifest.get("claim_state") != "PARTIALLY_SUPPORTED"
        or manifest.get("paper_claim_allowed") is not False
        or manifest.get("counts", {}).get("selection_selected") != 25
        or manifest.get("counts", {}).get("locked_audit_pass") != 24
        or manifest.get("counts", {}).get("locked_audit_rejected") != 1
        or manifest.get("counts", {}).get("locked_audit_failed") != 0
        or manifest.get("counts", {}).get("retuning") != 0
        or manifest.get("counts", {}).get("flip_count") != 0
        or manifest.get("counts", {}).get("violation_count") != 1
        or manifest.get("counts", {}).get("policy_modification_after_audit") != 0
    ):
        raise ValueError("structural evidence classification changed")
    for relative, expected in manifest["files"].items():
        path = output / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: frozen structural file changed")
    for relative, expected in manifest["external_artifacts"].items():
        source = REPO_ROOT / relative
        if (
            not source.is_file()
            or source.stat().st_size != expected["bytes"]
            or sha256(source) != expected["sha256"]
        ):
            raise ValueError(f"{source}: structural source artifact changed")
        snapshot = output / expected["snapshot"]
        if sha256(snapshot) != expected["sha256"]:
            raise ValueError(f"{snapshot}: structural snapshot binding changed")
    expected_lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        expected_lines.append(
            f"{sha256(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output)}\n"
        )
    if (output / "SHA256SUMS").read_text(encoding="utf-8") != "".join(
        expected_lines
    ):
        raise ValueError("structural SHA256SUMS changed")
    print(
        "structural_evidence=VERIFIED status=PARTIAL_SCIENTIFIC_RESULT "
        "selection=25 audit_pass=24 audit_rejected=1"
    )


def main() -> int:
    args = parse_args()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output)
        return 0
    if output.exists():
        if not args.force:
            raise ValueError(f"{output} exists; use --force")
        shutil.rmtree(output)
    generate(output)
    verify(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
