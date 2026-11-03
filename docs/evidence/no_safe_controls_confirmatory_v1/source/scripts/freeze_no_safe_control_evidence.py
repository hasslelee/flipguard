#!/usr/bin/env python3
"""Freeze and independently verify FlipGuard NO_SAFE controls."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PILOT_ROOT = Path(
    "results/thesis_grade_protocol/"
    "no_safe_budget_control_v1/pilot_seed0"
)
DEFAULT_FINITE_ROOT = Path(
    "results/thesis_grade_protocol/"
    "finite_domain_no_safe_control_v1/full"
)
DEFAULT_FINITE_AUDIT_ROOT = Path(
    "results/thesis_grade_protocol/"
    "finite_domain_no_safe_locked_audit_v1/full"
)
DEFAULT_OUTPUT_ROOT = Path(
    "docs/evidence/no_safe_controls_v1"
)
BUDGET_SUMMARY_FILES = (
    Path("summary/summary.json"),
    Path("summary/run_status.csv"),
    Path("summary/workload_results.csv"),
)
FINITE_FILES = (
    Path("summary.json"),
    Path("restricted_candidate_certificates.csv"),
    Path("restricted_oracle_selection.csv"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--budget-root",
        "--pilot-root",
        dest="budget_root",
        type=Path,
        default=DEFAULT_PILOT_ROOT,
    )
    parser.add_argument(
        "--finite-root",
        type=Path,
        default=DEFAULT_FINITE_ROOT,
    )
    parser.add_argument(
        "--finite-audit-root",
        type=Path,
        default=None,
        help=(
            "optional disjoint finite-domain locked-audit result; "
            "required by the final confirmatory suite"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument(
        "--evidence-id",
        default="no_safe_controls_v1",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source file {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def current_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_budgeted(
    budget_root: Path,
) -> tuple[dict[str, Any], list[Path], list[dict[str, Any]]]:
    summary = load_json(budget_root / "summary/summary.json")
    mode = summary.get("mode")
    if mode == "PILOT":
        evidence_status = "PILOT_ONLY"
        expected_workloads = 10
        expected_outcomes = {"NO_SAFE": 4, "SELECTED": 6}
        expected_by_model = {
            "linear_poly3": {"NO_SAFE": 4, "SELECTED": 1},
            "mlp_square_linear_score": {"SELECTED": 5},
        }
        expected_key_repeats = 1
    elif mode == "CONFIRM":
        evidence_status = "CONFIRMATORY_NEGATIVE_CONTROL"
        expected_workloads = 40
        expected_outcomes = {"NO_SAFE": 16, "SELECTED": 24}
        expected_by_model = {
            "linear_poly3": {"NO_SAFE": 16, "SELECTED": 4},
            "mlp_square_linear_score": {"SELECTED": 20},
        }
        expected_key_repeats = 3
    else:
        raise ValueError(f"unsupported budgeted NO_SAFE mode {mode!r}")
    if (
        summary.get("control_result") != "PASS"
        or summary.get("evidence_status") != evidence_status
        or summary["protocol"]["key_repeats"]
        != expected_key_repeats
        or (
            mode == "CONFIRM"
            and (
                summary["source"].get("dirty") is not False
                or summary["source"].get("commit")
                != current_commit()
            )
        )
    ):
        raise ValueError(
            f"budgeted NO_SAFE {mode} result is not admissible"
        )
    counts = summary.get("counts", {})
    expected_counts = {
        "expected_workloads": expected_workloads,
        "successful_workloads": expected_workloads,
        "failed_workloads": 0,
        "outcomes": expected_outcomes,
        "outcomes_by_model": expected_by_model,
        "unsafe_selected": 0,
        "no_safe_with_selection": 0,
        "no_safe_non_linear": 0,
        "unexpected_outcomes": 0,
    }
    if counts != expected_counts:
        raise ValueError(
            f"budgeted {mode.lower()} counts changed: {counts}"
        )

    result_paths = sorted((budget_root / "results").glob("*.json"))
    binding_paths = sorted((budget_root / "bindings").glob("*.json"))
    if (
        len(result_paths) != expected_workloads
        or len(binding_paths) != expected_workloads
    ):
        raise ValueError(
            f"budgeted {mode.lower()} must contain "
            f"{expected_workloads} results and bindings"
        )
    bindings_by_name = {
        path.name: load_json(path) for path in binding_paths
    }
    external: dict[str, dict[str, Any]] = {}
    for result_path in result_paths:
        item = bindings_by_name.get(result_path.name)
        if item is None:
            raise ValueError(
                f"missing binding for {result_path.name}"
            )
        if item["result"]["sha256"] != sha256_path(result_path):
            raise ValueError(
                f"{result_path}: binding digest mismatch"
            )
        result = load_json(result_path)
        outcome = result["outcome"]
        trials = result["trials"]
        if result["trials_used"] != 1 or len(trials) != 1:
            raise ValueError(
                f"{result_path}: expected one trial"
            )
        trial = trials[0]
        if (
            trial.get("key_repeats_completed")
            != expected_key_repeats
        ):
            raise ValueError(
                f"{result_path}: fresh-key repeat count changed"
            )
        if outcome == "SELECTED":
            max_budget_usage = trial.get("max_error_budget_usage")
            if (
                trial["status"] != "SAFE"
                or trial["decision_flips"] != 0
                or trial["error_violations"] != 0
                or result.get("selected") != trial["candidate"]
                or (
                    mode == "CONFIRM"
                    and (
                        not isinstance(
                            max_budget_usage,
                            (int, float),
                        )
                        or not math.isfinite(
                            float(max_budget_usage)
                        )
                        or float(max_budget_usage) >= 1
                    )
                )
            ):
                raise ValueError(
                    f"{result_path}: invalid selected evidence"
                )
        elif outcome == "NO_SAFE":
            if (
                trial["status"] == "SAFE"
                or result.get("selected") is not None
            ):
                raise ValueError(
                    f"{result_path}: invalid NO_SAFE evidence"
                )
        else:
            raise ValueError(
                f"{result_path}: unsupported outcome {outcome}"
            )

        for label in ("model", "validation"):
            source = REPO_ROOT / item[label]["path"]
            if sha256_path(source) != item[label]["sha256"]:
                raise ValueError(
                    f"{source}: external digest changed"
                )
            external[str(source.relative_to(REPO_ROOT))] = binding(
                source
            )

    source_files = []
    source_digest = hashlib.sha256()
    for relative, expected in summary["source"]["files"].items():
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError(
                f"unsafe budgeted source path {relative_path}"
            )
        source = REPO_ROOT / relative
        if (
            sha256_path(source) != expected["sha256"]
            or source.stat().st_size != expected["bytes"]
        ):
            raise ValueError(
                f"{source}: budgeted source snapshot changed"
            )
        source_files.append(source)
        source_digest.update(relative.encode("utf-8"))
        source_digest.update(b"\0")
        source_digest.update(expected["sha256"].encode("ascii"))
        source_digest.update(b"\n")
    if (
        "sha256:" + source_digest.hexdigest()
        != summary["source"]["digest"]
    ):
        raise ValueError("budgeted composite source digest changed")

    for output in summary["outputs"].values():
        output_path = REPO_ROOT / output["path"]
        if sha256_path(output_path) != output["sha256"]:
            raise ValueError(
                f"{output_path}: budgeted output digest changed"
            )

    return (
        summary,
        result_paths + binding_paths + source_files,
        [external[key] for key in sorted(external)],
    )


def validate_finite(
    finite_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = load_json(finite_root / "summary.json")
    if (
        summary.get("control_result") != "PASS"
        or summary.get("evidence_status")
        != "RETROSPECTIVE_DERIVED_CONTROL"
    ):
        raise ValueError("finite-domain control is not PASS")
    expected_metrics = {
        "workloads": 50,
        "candidate_rows": 100,
        "candidate_statuses": {
            "SAFE": 0,
            "REJECTED": 75,
            "FAILED": 25,
        },
        "restricted_no_safe": 50,
        "restricted_selected": 0,
        "full_catalog_selected": 50,
    }
    if summary.get("metrics") != expected_metrics:
        raise ValueError(
            f"finite-domain metrics changed: "
            f"{summary.get('metrics')}"
        )

    external = []
    for item in summary["inputs"].values():
        source = REPO_ROOT / item["path"]
        if sha256_path(source) != item["sha256"]:
            raise ValueError(
                f"{source}: finite-domain input digest changed"
            )
        external.append(binding(source))
    return summary, external


def validate_finite_audit(
    finite_audit_root: Path,
) -> tuple[
    dict[str, Any],
    list[Path],
    list[dict[str, Any]],
]:
    subprocess.run(
        [
            sys.executable,
            str(
                REPO_ROOT
                / "scripts/"
                "run_finite_domain_no_safe_locked_audit.py"
            ),
            "--output-root",
            str(finite_audit_root),
            "--verify",
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    summary = load_json(
        finite_audit_root / "summary/summary.json"
    )
    mode = summary.get("mode")
    if mode == "SMOKE":
        evidence_status = "SMOKE_ONLY"
        expected_workloads = 1
        expected_candidates = 2
        expected_attempts = 2
        expected_key_repeats = 1
    elif mode == "CONFIRM":
        evidence_status = (
            "CONFIRMATORY_DISJOINT_FINITE_DOMAIN"
        )
        expected_workloads = 50
        expected_candidates = 100
        expected_attempts = 300
        expected_key_repeats = 3
    else:
        raise ValueError(
            f"unsupported finite-audit mode {mode!r}"
        )
    metrics = summary.get("metrics", {})
    statuses = metrics.get("candidate_statuses", {})
    safe = int(statuses.get("SAFE", 0))
    expected_control = (
        "PASS"
        if safe == 0
        and metrics.get("restricted_no_safe")
        == expected_workloads
        else "FAIL"
    )
    if (
        summary.get("execution_status") != "COMPLETE"
        or summary.get("evidence_status")
        != evidence_status
        or summary.get("control_result") != expected_control
        or metrics.get("workloads") != expected_workloads
        or metrics.get("candidate_rows") != expected_candidates
        or metrics.get("attempts") != expected_attempts
        or metrics.get("key_repeats") != expected_key_repeats
        or sum(int(value) for value in statuses.values())
        != expected_candidates
        or (
            metrics.get("restricted_no_safe", 0)
            + metrics.get("restricted_selected", 0)
            != expected_workloads
        )
        or metrics.get("unexpected_execution_failures") != 0
        or (
            mode == "CONFIRM"
            and summary["source"].get("dirty") is not False
        )
        or summary["source"].get("commit") != current_commit()
    ):
        raise ValueError(
            "finite-domain locked audit is not admissible"
        )

    files = sorted(
        path
        for directory in ("summary", "bindings", "logs", "raw")
        for path in (finite_audit_root / directory).rglob("*")
        if path.is_file()
    )
    bindings = [
        path
        for path in files
        if path.is_relative_to(
            finite_audit_root / "bindings"
        )
    ]
    logs = [
        path
        for path in files
        if path.is_relative_to(finite_audit_root / "logs")
    ]
    attempt_rows = []
    with (
        finite_audit_root / "summary/attempt_status.csv"
    ).open(newline="", encoding="utf-8") as handle:
        attempt_rows = list(csv.DictReader(handle))
    successes = sum(
        row["status"] == "SUCCESS" for row in attempt_rows
    )
    raw_files = [
        path
        for path in files
        if path.is_relative_to(finite_audit_root / "raw")
    ]
    if (
        len(bindings) != expected_attempts
        or len(logs) != expected_attempts
        or len(attempt_rows) != expected_attempts
        or len(raw_files) != successes * 2
    ):
        raise ValueError(
            "finite-domain locked-audit raw file matrix changed"
        )

    source_files = []
    source_digest = hashlib.sha256()
    for relative, expected in summary["source"]["files"].items():
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError(
                f"unsafe finite-audit source path {relative_path}"
            )
        source = REPO_ROOT / relative_path
        if (
            source.stat().st_size != expected["bytes"]
            or sha256_path(source) != expected["sha256"]
        ):
            raise ValueError(
                f"{source}: finite-audit source changed"
            )
        source_files.append(source)
        source_digest.update(relative.encode("utf-8"))
        source_digest.update(b"\0")
        source_digest.update(expected["sha256"].encode("ascii"))
        source_digest.update(b"\n")
    if (
        "sha256:" + source_digest.hexdigest()
        != summary["source"]["digest"]
    ):
        raise ValueError(
            "finite-audit composite source digest changed"
        )

    external_by_path: dict[str, dict[str, Any]] = {}
    external_groups = [
        summary["retrospective_inputs"].values(),
        (
            item
            for workload in summary["audit_inputs"].values()
            for item in workload.values()
        ),
    ]
    for group in external_groups:
        for item in group:
            source = REPO_ROOT / item["path"]
            if (
                source.stat().st_size != item["bytes"]
                or sha256_path(source) != item["sha256"]
            ):
                raise ValueError(
                    f"{source}: finite-audit external changed"
                )
            external_by_path[item["path"]] = binding(source)
    return (
        summary,
        files + source_files,
        [
            external_by_path[key]
            for key in sorted(external_by_path)
        ],
    )


def write_readme(
    path: Path,
    budget_summary: dict[str, Any],
    finite_summary: dict[str, Any],
    finite_audit_summary: dict[str, Any] | None,
    evidence_id: str,
) -> None:
    budget_counts = budget_summary["counts"]
    mode = budget_summary["mode"]
    finite_audit_section = ""
    control_count = "two"
    if finite_audit_summary is not None:
        control_count = "three"
        audit_metrics = finite_audit_summary["metrics"]
        audit_statuses = audit_metrics["candidate_statuses"]
        finite_audit_section = f"""
## Disjoint finite-domain locked audit

- Workloads: `{audit_metrics["workloads"]}`
- Candidate rows: `{audit_metrics["candidate_rows"]}`
- Fresh-key attempts: `{audit_metrics["attempts"]}`
- Candidate states: `{audit_statuses}`
- Restricted outcome: `NO_SAFE={audit_metrics["restricted_no_safe"]}/50`
- Control result: `{finite_audit_summary["control_result"]}`

The two fixed candidates were re-executed on each split's disjoint
`locked_audit_test` partition in independent processes. Validation status was
retained only for transition reporting and was not used to admit audit
candidates.
"""
    path.write_text(
        f"""# FlipGuard NO_SAFE Control Evidence

This pack freezes {control_count} scope-separated controls.

## Budgeted abstention {mode.lower()}

- Workloads: `{budget_counts["successful_workloads"]}/{budget_counts["expected_workloads"]}`
- Outcomes: `NO_SAFE={budget_counts["outcomes"]["NO_SAFE"]}`, `SELECTED={budget_counts["outcomes"]["SELECTED"]}`
- Unsafe selected: `0`
- Partition: disjoint locked-audit test
- Split seeds: `{budget_summary["protocol"]["split_seeds"]}`
- Fresh-key repeats: `{budget_summary["protocol"]["key_repeats"]}`
- Trial budget: one encrypted candidate
- Claim boundary: `NO_SAFE` is budget-scoped, not global infeasibility

The pack includes every result JSON, every input/result binding sidecar, the
aggregate tables, and the exact source snapshots whose composite digest is
recorded by the budgeted control.

## Finite-domain control

- Domain: `short_chain_3` baseline and rescale-aware paths
- Candidate certificates: `100`
- States: `SAFE=0`, `REJECTED=75`, `FAILED=25`
- Restricted outcome: `NO_SAFE=50/50`
- Full catalog outcome on the same workloads: `SELECTED=50/50`

This control is retrospective and only proves the declared two-candidate
domain. It is not a global CKKS infeasibility claim.
{finite_audit_section}

## Verification

```bash
python3 scripts/freeze_no_safe_control_evidence.py \\
  --output-root docs/evidence/{evidence_id} \\
  --verify
```

The manifest checks every copied file and every externally bound model,
validation/audit split, and full-oracle input.
""",
        encoding="utf-8",
    )


def generate(
    budget_root: Path,
    finite_root: Path,
    finite_audit_root: Path | None,
    output_root: Path,
    evidence_id: str,
    force: bool,
) -> None:
    budget_summary, budget_files, budget_external = (
        validate_budgeted(
            budget_root
        )
    )
    finite_summary, finite_external = validate_finite(finite_root)
    finite_audit_summary = None
    finite_audit_files: list[Path] = []
    finite_audit_external: list[dict[str, Any]] = []
    if finite_audit_root is not None:
        (
            finite_audit_summary,
            finite_audit_files,
            finite_audit_external,
        ) = validate_finite_audit(finite_audit_root)
        if (
            (
                budget_summary["mode"],
                finite_audit_summary["mode"],
            )
            not in {
                ("PILOT", "SMOKE"),
                ("CONFIRM", "CONFIRM"),
            }
            or budget_summary["source"]["commit"]
            != finite_audit_summary["source"]["commit"]
        ):
            raise ValueError(
                "budget and finite-audit modes/commits do not match"
            )

    if output_root.exists():
        if not force:
            raise ValueError(
                f"{output_root} exists; use --force"
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    budget_snapshot_dir = (
        "budget_pilot"
        if budget_summary["mode"] == "PILOT"
        else "budget_confirmatory"
    )
    for relative in BUDGET_SUMMARY_FILES:
        copy_file(
            budget_root / relative,
            output_root / budget_snapshot_dir / relative,
        )
    for source in budget_files:
        if source.is_relative_to(budget_root / "results"):
            destination = (
                output_root / budget_snapshot_dir / "results" / source.name
            )
        elif source.is_relative_to(budget_root / "bindings"):
            destination = (
                output_root / budget_snapshot_dir / "bindings" / source.name
            )
        else:
            destination = (
                output_root
                / "source"
                / source.relative_to(REPO_ROOT)
            )
        copy_file(source, destination)

    for relative in FINITE_FILES:
        copy_file(
            finite_root / relative,
            output_root / "finite_domain" / relative,
        )
    copy_file(
        REPO_ROOT / "scripts/build_finite_domain_no_safe_control.py",
        output_root
        / "source/scripts/build_finite_domain_no_safe_control.py",
    )
    copy_file(
        REPO_ROOT / "scripts/freeze_no_safe_control_evidence.py",
        output_root
        / "source/scripts/freeze_no_safe_control_evidence.py",
    )
    if finite_audit_root is not None:
        for source in finite_audit_files:
            if source.is_relative_to(finite_audit_root):
                destination = (
                    output_root
                    / "finite_domain_locked_audit"
                    / source.relative_to(finite_audit_root)
                )
            else:
                destination = (
                    output_root
                    / "source"
                    / source.relative_to(REPO_ROOT)
                )
            copy_file(source, destination)
    write_readme(
        output_root / "README.md",
        budget_summary,
        finite_summary,
        finite_audit_summary,
        evidence_id,
    )

    copied = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    external_by_path = {
        item["path"]: item
        for item in (
            budget_external
            + finite_external
            + finite_audit_external
        )
    }
    manifest = {
        "schema_version": (
            2 if finite_audit_summary is not None else 1
        ),
        "evidence_id": evidence_id,
        "status": (
            "PILOT_AND_RETROSPECTIVE_CONTROL"
            if (
                budget_summary["mode"] == "PILOT"
                and finite_audit_summary is None
            )
            else (
                "CONFIRMATORY_DISJOINT_CONTROLS"
                if budget_summary["mode"] == "CONFIRM"
                and finite_audit_summary is not None
                else (
                    "PILOT_DISJOINT_CONTROLS"
                    if finite_audit_summary is not None
                    else "CONFIRMATORY_AND_RETROSPECTIVE_CONTROL"
                )
            )
        ),
        "budget_mode": budget_summary["mode"],
        "budget_snapshot_dir": budget_snapshot_dir,
        "claim_boundary": (
            "NO_SAFE is scoped to the one-candidate encrypted budget, "
            "and the all-unsafe result is scoped to the declared "
            "two-candidate finite domain. No result establishes global "
            "CKKS infeasibility."
        ),
        "budget_source_commit": budget_summary["source"]["commit"],
        "budget_source_digest": budget_summary["source"]["digest"],
        "finite_audit_source_commit": (
            finite_audit_summary["source"]["commit"]
            if finite_audit_summary is not None
            else None
        ),
        "finite_audit_source_digest": (
            finite_audit_summary["source"]["digest"]
            if finite_audit_summary is not None
            else None
        ),
        "finite_audit_control_result": (
            finite_audit_summary["control_result"]
            if finite_audit_summary is not None
            else None
        ),
        "counts": {
            "budget_workloads":
                budget_summary["counts"]["expected_workloads"],
            "budget_no_safe":
                budget_summary["counts"]["outcomes"]["NO_SAFE"],
            "budget_selected":
                budget_summary["counts"]["outcomes"]["SELECTED"],
            "finite_domain_workloads": 50,
            "finite_domain_candidate_rows": 100,
            "finite_audit_workloads": (
                finite_audit_summary["metrics"]["workloads"]
                if finite_audit_summary is not None
                else 0
            ),
            "finite_audit_candidate_rows": (
                finite_audit_summary["metrics"]["candidate_rows"]
                if finite_audit_summary is not None
                else 0
            ),
            "finite_audit_attempts": (
                finite_audit_summary["metrics"]["attempts"]
                if finite_audit_summary is not None
                else 0
            ),
            "finite_audit_no_safe": (
                finite_audit_summary["metrics"][
                    "restricted_no_safe"
                ]
                if finite_audit_summary is not None
                else 0
            ),
            "internal_files": len(copied),
            "external_artifacts": len(external_by_path),
        },
        "files": {
            str(path.relative_to(output_root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
            for path in copied
        },
        "external_artifacts": [
            external_by_path[key]
            for key in sorted(external_by_path)
        ],
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(output_root: Path) -> None:
    manifest_path = output_root / "manifest.json"
    manifest = load_json(manifest_path)
    budget_mode = manifest.get("budget_mode")
    if (
        budget_mode is None
        and manifest.get("status")
        == "PILOT_AND_RETROSPECTIVE_CONTROL"
    ):
        budget_mode = "PILOT"
    budget_snapshot_dir = manifest.get(
        "budget_snapshot_dir",
        "budget_pilot" if budget_mode == "PILOT" else "",
    )
    schema_version = manifest.get("schema_version")
    if (
        schema_version not in {1, 2}
        or not manifest.get("evidence_id")
        or budget_mode not in {"PILOT", "CONFIRM"}
        or not budget_snapshot_dir
        or Path(budget_snapshot_dir).is_absolute()
        or ".." in Path(budget_snapshot_dir).parts
    ):
        raise ValueError("unsupported NO_SAFE evidence manifest")

    expected_files = set(manifest["files"])
    actual_files = {
        str(path.relative_to(output_root))
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_files != expected_files:
        raise ValueError(
            "NO_SAFE evidence file set changed: "
            f"missing={sorted(expected_files - actual_files)} "
            f"unexpected={sorted(actual_files - expected_files)}"
        )
    for relative, expected in manifest["files"].items():
        path = output_root / relative
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: checksum mismatch")
    for expected in manifest["external_artifacts"]:
        path = REPO_ROOT / expected["path"]
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: external checksum mismatch")

    budget_summary = load_json(
        output_root
        / budget_snapshot_dir
        / "summary/summary.json"
    )
    finite_summary = load_json(
        output_root / "finite_domain/summary.json"
    )
    if (
        budget_summary["control_result"] != "PASS"
        or budget_summary["mode"] != budget_mode
        or budget_summary["counts"]["unsafe_selected"] != 0
        or budget_summary["counts"]["outcomes"]["NO_SAFE"]
        != manifest["counts"].get(
            "budget_no_safe",
            manifest["counts"].get("budget_pilot_no_safe"),
        )
        or budget_summary["counts"]["outcomes"]["SELECTED"]
        != manifest["counts"].get(
            "budget_selected",
            manifest["counts"].get("budget_pilot_selected"),
        )
    ):
        raise ValueError("frozen budgeted-control semantics changed")
    if (
        finite_summary["control_result"] != "PASS"
        or finite_summary["metrics"]["restricted_no_safe"] != 50
        or finite_summary["metrics"]["candidate_statuses"]
        != {"SAFE": 0, "REJECTED": 75, "FAILED": 25}
    ):
        raise ValueError("frozen finite-domain semantics changed")

    if schema_version == 2:
        finite_audit_root = (
            output_root / "finite_domain_locked_audit"
        )
        finite_audit_summary = load_json(
            finite_audit_root / "summary/summary.json"
        )
        metrics = finite_audit_summary["metrics"]
        statuses = metrics["candidate_statuses"]
        finite_audit_mode = finite_audit_summary["mode"]
        if finite_audit_mode == "SMOKE":
            expected_audit_status = "SMOKE_ONLY"
            expected_candidates = 2
            expected_pack_status = "PILOT_DISJOINT_CONTROLS"
            expected_mode_pair = ("PILOT", "SMOKE")
        elif finite_audit_mode == "CONFIRM":
            expected_audit_status = (
                "CONFIRMATORY_DISJOINT_FINITE_DOMAIN"
            )
            expected_candidates = 100
            expected_pack_status = (
                "CONFIRMATORY_DISJOINT_CONTROLS"
            )
            expected_mode_pair = ("CONFIRM", "CONFIRM")
        else:
            raise ValueError(
                "frozen finite-audit mode is unsupported"
            )
        if (
            finite_audit_summary["execution_status"]
            != "COMPLETE"
            or finite_audit_summary["evidence_status"]
            != expected_audit_status
            or (budget_mode, finite_audit_mode)
            != expected_mode_pair
            or manifest["status"] != expected_pack_status
            or finite_audit_summary["control_result"]
            != manifest["finite_audit_control_result"]
            or metrics["workloads"]
            != manifest["counts"]["finite_audit_workloads"]
            or metrics["candidate_rows"]
            != manifest["counts"]["finite_audit_candidate_rows"]
            or metrics["attempts"]
            != manifest["counts"]["finite_audit_attempts"]
            or metrics["restricted_no_safe"]
            != manifest["counts"]["finite_audit_no_safe"]
            or metrics["unexpected_execution_failures"] != 0
            or sum(int(value) for value in statuses.values())
            != expected_candidates
            or manifest["finite_audit_source_commit"]
            != manifest["budget_source_commit"]
        ):
            raise ValueError(
                "frozen finite-domain locked-audit semantics changed"
            )

        original_binary = resolve_path(
            finite_audit_summary["binary"]["path"]
        )
        original_root = original_binary.parent.parent
        for binding_path in sorted(
            (finite_audit_root / "bindings").glob("*.json")
        ):
            attempt = load_json(binding_path)
            artifact_items = [attempt["log"]]
            if attempt["status"] == "SUCCESS":
                artifact_items.extend(
                    attempt["raw"].values()
                )
            for item in artifact_items:
                original = resolve_path(item["path"])
                if not original.is_relative_to(original_root):
                    raise ValueError(
                        f"{binding_path}: artifact escaped run root"
                    )
                frozen = (
                    finite_audit_root
                    / original.relative_to(original_root)
                )
                if (
                    frozen.stat().st_size != item["bytes"]
                    or sha256_path(frozen) != item["sha256"]
                ):
                    raise ValueError(
                        f"{frozen}: frozen attempt artifact changed"
                    )

    print(
        "no_safe_control_evidence=VERIFIED "
        f"files={len(expected_files)} "
        f"external_artifacts="
        f"{len(manifest['external_artifacts'])}"
    )


def main() -> int:
    args = parse_args()
    budget_root = (REPO_ROOT / args.budget_root).resolve()
    finite_root = (REPO_ROOT / args.finite_root).resolve()
    finite_audit_root = (
        (REPO_ROOT / args.finite_audit_root).resolve()
        if args.finite_audit_root is not None
        else None
    )
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output_root)
    else:
        generate(
            budget_root,
            finite_root,
            finite_audit_root,
            output_root,
            args.evidence_id,
            args.force,
        )
        verify(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
