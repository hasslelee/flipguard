#!/usr/bin/env python3
"""Freeze or verify a compact direct locked-audit evidence snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "seed0_floor18_keys3/locked_audit/"
    "seed0_floor18_keys3_locked_audit_keys3"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/direct_locked_audit_seed0_v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--evidence-id",
        default="direct_locked_audit_seed0_v1",
    )
    parser.add_argument(
        "--selection-run-id",
        default="seed0_floor18_keys3",
    )
    parser.add_argument(
        "--audit-run-id",
        default="seed0_floor18_keys3_locked_audit_keys3",
    )
    parser.add_argument(
        "--split-seeds",
        default="0",
        help="comma-separated split seeds represented by the checkpoint",
    )
    parser.add_argument(
        "--execution-command",
        default=(
            "scripts/run_direct_tabular_locked_audit_matrix.sh "
            "--seed0 --force"
        ),
    )
    parser.add_argument("--allow-checkpoint", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return require_dict(
        json.loads(path.read_text(encoding="utf-8")),
        str(path),
    )


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source artifact {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def freeze(args: argparse.Namespace) -> None:
    if not args.source_commit:
        raise ValueError("--source-commit is required when freezing")
    source_commit = git_text("rev-parse", args.source_commit)
    git_text("cat-file", "-e", source_commit + "^{commit}")

    source = args.source_root
    output = args.output_root
    status_path = source / "locked_audit_status.csv"
    summary_path = source / "summary" / "summary.json"
    results_csv_path = (
        source / "summary" / "locked_audit_results.csv"
    )
    summary = load_json(summary_path)
    if not summary.get("complete") and not args.allow_checkpoint:
        raise ValueError("source locked-audit matrix is incomplete")
    if summary.get("locked_audit_fails") != 0:
        raise ValueError("source contains locked-audit failures")
    if summary.get("failed_executions") != 0:
        raise ValueError("source contains execution failures")

    with status_path.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        status_rows = list(csv.DictReader(handle))
    if len(status_rows) != int(summary["expected_runs"]):
        if not args.allow_checkpoint:
            raise ValueError(
                "source status row count does not match expected runs"
            )
        if len(status_rows) != int(summary["recorded_runs"]):
            raise ValueError(
                "checkpoint status row count does not match recorded runs"
            )
    if any(row["status"] != "ok" for row in status_rows):
        raise ValueError("source status contains failed rows")

    if output.exists():
        if not args.force:
            raise ValueError(
                f"{output} already exists; use --force to replace it"
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)

    def snapshot(source_path: Path, relative: Path) -> Path:
        target = output / relative
        copy_file(source_path, target)
        return target

    snapshot(
        status_path,
        Path("source_locked_audit_status.csv"),
    )
    snapshot(summary_path, Path("outputs/summary.json"))
    snapshot(
        results_csv_path,
        Path("outputs/locked_audit_results.csv"),
    )

    external_inputs: list[dict[str, Any]] = []
    workload_records: list[dict[str, Any]] = []
    for row in sorted(
        status_rows,
        key=lambda value: (
            int(value["split_seed"]),
            value["dataset_id"],
            value["model_id"],
        ),
    ):
        identity = (
            f"seed{row['split_seed']}__"
            f"{row['dataset_id']}__{row['model_id']}"
        )
        result_source = Path(row["result_path"])
        selection_source = Path(row["selection_path"])
        manifest_source = Path(row["manifest_path"])
        audit_source = Path(row["audit_path"])

        result_target = snapshot(
            result_source,
            Path("outputs/audit_results") / f"{identity}.json",
        )
        selection_target = snapshot(
            selection_source,
            Path("inputs/selections") / f"{identity}.json",
        )
        manifest_target = snapshot(
            manifest_source,
            Path("inputs/split_manifests") / f"{identity}.json",
        )

        result = load_json(result_source)
        selection = load_json(selection_source)
        split_manifest = load_json(manifest_source)
        selection_contract = require_dict(
            require_dict(
                selection.get("plan"),
                f"{selection_source}: plan",
            ).get("contract"),
            f"{selection_source}: contract",
        )
        model_binding = require_dict(
            selection_contract.get("model_artifact"),
            f"{selection_source}: model artifact",
        )
        validation_binding = require_dict(
            selection_contract.get("validation_data"),
            f"{selection_source}: validation artifact",
        )
        source_test_path = Path(
            str(split_manifest["source_test_csv"])
        )

        bindings = [
            (
                "model_artifact",
                Path(str(model_binding["path"])),
                str(model_binding["sha256"]),
            ),
            (
                "configuration_validation",
                Path(str(validation_binding["path"])),
                str(validation_binding["sha256"]),
            ),
            (
                "locked_audit_test",
                audit_source,
                str(
                    require_dict(
                        split_manifest["locked_audit_test"],
                        "locked audit manifest partition",
                    )["csv_digest"]
                ),
            ),
            (
                "source_test_csv",
                source_test_path,
                str(split_manifest["source_test_csv_digest"]),
            ),
        ]
        for kind, path, expected_digest in bindings:
            actual = "sha256:" + sha256_file(path)
            if actual != expected_digest:
                raise ValueError(
                    f"{identity}: {kind} digest {actual} "
                    f"!= {expected_digest}"
                )
            external_inputs.append(
                {
                    "workload": identity,
                    "kind": kind,
                    "path": str(path),
                    "sha256": actual,
                    "size_bytes": path.stat().st_size,
                }
            )

        trial = require_dict(
            result.get("audit_trial"),
            f"{result_source}: audit trial",
        )
        candidate = require_dict(
            result.get("selected_candidate"),
            f"{result_source}: selected candidate",
        )
        parameters = require_dict(
            candidate.get("parameters"),
            f"{result_source}: parameters",
        )
        workload_records.append(
            {
                "workload": identity,
                "outcome": result["outcome"],
                "candidate_id": candidate["id"],
                "log_n": parameters["log_n"],
                "q_prime_count": len(parameters["log_q"]),
                "log_default_scale": parameters[
                    "log_default_scale"
                ],
                "key_repeats_completed": trial[
                    "key_repeats_completed"
                ],
                "decision_flips": trial["decision_flips"],
                "error_violations": trial["error_violations"],
                "v_cert": trial["v_cert"],
                "v_amb": trial["v_amb"],
                "audit_result_snapshot": str(
                    result_target.relative_to(output)
                ),
                "selection_snapshot": str(
                    selection_target.relative_to(output)
                ),
                "split_manifest_snapshot": str(
                    manifest_target.relative_to(output)
                ),
            }
        )

    split_seeds = [
        int(value.strip())
        for value in args.split_seeds.split(",")
        if value.strip()
    ]
    if not split_seeds:
        raise ValueError("--split-seeds contains no seeds")

    manifest = {
        "schema_version": 1,
        "evidence_id": args.evidence_id,
        "evidence_type": (
            "observed_no_retuning_locked_audit_preliminary"
        ),
        "source_code": {
            "git_commit": source_commit,
            "commit_time": git_text(
                "show", "-s", "--format=%cI", source_commit
            ),
            "subject": git_text(
                "show", "-s", "--format=%s", source_commit
            ),
        },
        "execution": {
            "selection_run_id": args.selection_run_id,
            "audit_run_id": args.audit_run_id,
            "command": args.execution_command,
            "split_seeds": split_seeds,
            "key_repeats": 3,
            "retuning_allowed": False,
            "checkpoint": not bool(summary.get("complete")),
        },
        "structural_summary": summary,
        "workloads": workload_records,
        "external_inputs": external_inputs,
        "claim_boundary": (
            "All frozen candidates in the recorded split checkpoint "
            "remained SAFE with "
            "zero flips and zero protected error-budget violations "
            "on the disjoint locked-audit V_cert rows across three "
            "fresh keypairs. This is limited observed evidence, "
            "not a distribution-wide, split-independent, "
            "key-independent, or analytical safety guarantee."
        ),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    readme = f"""# Direct Locked Audit Evidence: {args.evidence_id}

## Result

- Split seeds in this pack: `{",".join(map(str, split_seeds))}`
- Frozen configurations audited: `{len(workload_records)}`
- Locked-audit PASS: `{summary["locked_audit_passes"]}/{len(workload_records)}`
- Configuration trials: `{summary["total_configuration_trials"]}`
- Fresh-key runs: `{summary["total_fresh_key_runs"]}`
- Retuning during audit: `{summary["retuned_runs"]}`
- Total audit V_cert: `{summary["total_v_cert"]}`
- Total audit V_amb: `{summary["total_v_amb"]}`
- Matrix complete: `{str(bool(summary.get("complete"))).lower()}`

The audit command evaluated each validation-selected CKKS literal exactly
once on the disjoint `locked_audit_test.csv` partition with three fresh
keypairs. It did not call synthesis or candidate repair.

## Reproduce

Regenerate the deterministic split artifacts, regenerate the selection run,
and execute:

```bash
scripts/run_direct_tabular_locked_audit_matrix.sh --seed0 --force
```

Verify this compact snapshot:

```bash
python3 scripts/freeze_direct_locked_audit_evidence.py \\
  --output-root docs/evidence/{args.evidence_id} \\
  --verify
```

The large audit CSV files are not duplicated here. `manifest.json` binds them
and their tracked source test CSVs by SHA-256. The snapshot includes all ten
selection results, split manifests, locked-audit results, the execution
ledger, and aggregate CSV/JSON outputs.

## Claim Boundary

This is frozen preliminary evidence for the recorded split checkpoint and three
fresh keypairs. It supports no-retuning held-out decision stability for the
recorded workloads. It does not establish split independence, key
independence, distribution-wide safety, a sound analytical error bound, or
final latency claims.
"""
    readme_path = output / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    checksum_paths = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_text = "".join(
        f"{sha256_file(path)}  {path.relative_to(output)}\n"
        for path in checksum_paths
    )
    (output / "SHA256SUMS").write_text(
        checksum_text,
        encoding="utf-8",
    )

    print(
        "direct_locked_audit_evidence=FROZEN_PRELIMINARY "
        f"workloads={len(workload_records)} "
        f"files={len(checksum_paths)} output={output}"
    )


def verify(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{checksum_path}: checksum list is empty")
    declared: set[Path] = set()
    for line_number, line in enumerate(lines, start=1):
        digest, separator, relative_text = line.partition("  ")
        if (
            len(digest) != 64
            or not separator
            or not relative_text
        ):
            raise ValueError(
                f"{checksum_path}: invalid line {line_number}"
            )
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"{checksum_path}: unsafe path {relative}"
            )
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing snapshot file {path}")
        actual = sha256_file(path)
        if actual != digest:
            raise ValueError(
                f"{path}: digest {actual} != {digest}"
            )
        declared.add(relative)

    actual_files = {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual_files != declared:
        raise ValueError(
            "snapshot file set does not match SHA256SUMS"
        )

    manifest = load_json(root / "manifest.json")
    summary = require_dict(
        manifest.get("structural_summary"),
        f"{root}/manifest.json: structural_summary",
    )
    workloads = manifest.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("snapshot contains no workloads")
    if (
        not manifest.get("evidence_id")
        or summary.get("locked_audit_passes") != len(workloads)
        or summary.get("locked_audit_fails") != 0
        or summary.get("retuned_runs") != 0
        or summary.get("total_fresh_key_runs")
        != sum(
            int(row.get("key_repeats_completed", -1))
            for row in workloads
        )
    ):
        raise ValueError("snapshot structural summary is invalid")
    if any(
        row.get("outcome") != "LOCKED_AUDIT_PASS"
        or row.get("decision_flips") != 0
        or row.get("error_violations") != 0
        for row in workloads
    ):
        raise ValueError("snapshot contains a failed audit workload")

    print(
        "direct_locked_audit_evidence=VERIFIED "
        f"files={len(declared)} workloads={len(workloads)}"
    )


def main() -> int:
    args = parse_args()
    if args.verify:
        verify(args.output_root)
    else:
        freeze(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
