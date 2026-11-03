#!/usr/bin/env python3
"""Freeze or verify the strict oracle and comparison evidence snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ORACLE_ROOT = Path(
    "results/thesis_grade_protocol/tabular_validation_oracle_v1/full"
)
DEFAULT_DIRECT_ROOT = Path(
    "results/thesis_grade_protocol/direct_vs_catalog_oracle_v1/full"
)
DEFAULT_PLANNER_ROOT = Path(
    "results/thesis_grade_protocol/planner_oracle_comparison_v1/full"
)
DEFAULT_DIRECT_SOURCE_ROOT = Path(
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_floor18_keys3/summary"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/full_oracle_comparison_v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-root", type=Path, default=DEFAULT_ORACLE_ROOT)
    parser.add_argument("--direct-root", type=Path, default=DEFAULT_DIRECT_ROOT)
    parser.add_argument(
        "--planner-root",
        type=Path,
        default=DEFAULT_PLANNER_ROOT,
    )
    parser.add_argument(
        "--direct-source-root",
        type=Path,
        default=DEFAULT_DIRECT_SOURCE_ROOT,
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence-id",
        default="full_oracle_comparison_v1",
    )
    parser.add_argument("--source-commit")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError(f"missing source artifact {path}")
    return path


def git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def mean_field(rows: Iterable[dict[str, str]], field: str) -> float:
    values = [
        float(row[field])
        for row in rows
        if row.get(field, "") != ""
    ]
    if not values:
        raise ValueError(f"no defined values for {field}")
    return statistics.fmean(values)


def planner_metrics(
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    def scope_metrics(scope_rows: list[dict[str, str]]) -> dict[str, Any]:
        regrets = [
            float(row["latency_regret"])
            for row in scope_rows
            if row["latency_regret"] != ""
        ]
        if not regrets:
            raise ValueError("planner scope contains no defined regret")
        return {
            "rows": len(scope_rows),
            "false_no_safe": sum(
                row["false_no_safe"] == "true"
                for row in scope_rows
            ),
            "optimum_recall": mean_field(
                scope_rows,
                "optimum_recall",
            ),
            "safe_recall": mean_field(scope_rows, "safe_recall"),
            "latency_regret_mean": statistics.fmean(regrets),
            "latency_regret_median": statistics.median(regrets),
            "latency_regret_max": max(regrets),
            "pruning_ratio": mean_field(
                scope_rows,
                "pruning_ratio",
            ),
            "planning_overhead_us": mean_field(
                scope_rows,
                "planning_overhead_us",
            ),
        }

    models = sorted({row["model_id"] for row in rows})
    return {
        "all": scope_metrics(rows),
        "by_model": {
            model: scope_metrics(
                [row for row in rows if row["model_id"] == model]
            )
            for model in models
        },
    }


def validate_oracle(
    summary: dict[str, Any],
    run_rows: list[dict[str, str]],
    certificate_rows: list[dict[str, str]],
    oracle_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
) -> None:
    expected_summary = {
        "actual_run_count": 1100,
        "expected_full_run_count": 1100,
        "allow_incomplete": False,
        "candidate_certificate_rows": 5500,
        "oracle_rows": 250,
        "coverage_rows": 50,
        "certificate_status_counts": {
            "FAILED": 250,
            "REJECTED": 1500,
            "SAFE": 3750,
        },
        "oracle_outcome_counts": {"SELECTED": 250},
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise ValueError(
                f"oracle summary {key}={summary.get(key)!r}, "
                f"expected {expected!r}"
            )

    if len(run_rows) != 1100:
        raise ValueError("oracle run_status must contain 1100 rows")
    identities = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["profile"],
            row["path"],
        )
        for row in run_rows
    }
    if len(identities) != 1100:
        raise ValueError("oracle run_status identities are not unique")
    statuses = {"ok": 0, "failed": 0}
    for row in run_rows:
        status = row["status"]
        if status not in statuses:
            raise ValueError(f"unexpected run status {status}")
        statuses[status] += 1
        expected_exit = "0" if status == "ok" else "1"
        if row["exit_code"] != expected_exit:
            raise ValueError(
                f"{row['tag']}: status/exit-code mismatch"
            )
    if statuses != {"ok": 1050, "failed": 50}:
        raise ValueError(f"unexpected run status counts {statuses}")

    if len(certificate_rows) != 5500:
        raise ValueError("candidate certificates must contain 5500 rows")
    certificate_counts: dict[str, int] = {}
    for row in certificate_rows:
        status = row["certificate_status"]
        certificate_counts[status] = (
            certificate_counts.get(status, 0) + 1
        )
    if certificate_counts != {
        "FAILED": 250,
        "REJECTED": 1500,
        "SAFE": 3750,
    }:
        raise ValueError(
            f"unexpected certificate counts {certificate_counts}"
        )

    if len(oracle_rows) != 250 or any(
        row["outcome"] != "SELECTED" for row in oracle_rows
    ):
        raise ValueError("oracle selection rows are incomplete")
    if len(coverage_rows) != 50:
        raise ValueError("validation coverage must contain 50 rows")


def validate_direct(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
) -> None:
    expected = {
        "allow_incomplete": False,
        "oracle_matrix_complete": True,
        "complete_oracle_workloads_compared": 50,
        "expected_workloads": 50,
        "catalog_candidate_executions": 1100,
        "catalog_selected": 50,
        "direct_selected": 50,
        "direct_trials": 70,
        "direct_key_runs": 210,
        "latency_evidence": "UNPAIRED_DIAGNOSTIC",
        "paper_latency_claim_allowed": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError(
                f"direct summary {key}={summary.get(key)!r}, "
                f"expected {value!r}"
            )
    if len(rows) != 50:
        raise ValueError("direct comparison must contain 50 rows")
    identities = {
        (row["split_seed"], row["dataset_id"], row["model_id"])
        for row in rows
    }
    if len(identities) != 50:
        raise ValueError("direct comparison identities are not unique")
    if any(
        row["catalog_outcome"] != "SELECTED"
        or row["direct_outcome"] != "SELECTED"
        or row["catalog_candidate_count"] != "22"
        or row["latency_evidence"] != "UNPAIRED_DIAGNOSTIC"
        for row in rows
    ):
        raise ValueError("direct comparison contains an invalid row")


def validate_planner(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("planner summary counts are missing")
    expected_counts = {
        "comparison_rows": 250,
        "false_no_safe_rows": 0,
        "latency_regret_defined_rows": 250,
        "optimum_recall_defined_rows": 250,
        "oracle_no_safe_rows": 0,
        "planner_candidate_rows": 1750,
        "planner_no_safe_rows": 0,
        "safe_recall_defined_rows": 250,
    }
    if counts != expected_counts:
        raise ValueError(
            f"unexpected planner summary counts {counts}"
        )
    if len(rows) != 250:
        raise ValueError("planner comparison must contain 250 rows")
    identities = {
        (
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["alpha"],
        )
        for row in rows
    }
    if len(identities) != 250:
        raise ValueError("planner comparison identities are not unique")
    if any(
        row["oracle_outcome"] != "SELECTED"
        or row["planner_outcome"] != "SELECTED"
        or row["false_no_safe"] != "false"
        for row in rows
    ):
        raise ValueError("planner comparison contains an invalid row")
    return planner_metrics(rows)


def artifact_record(
    source: Path,
    snapshot: Path | None = None,
    *,
    kind: str | None = None,
    identity: str | None = None,
) -> dict[str, Any]:
    require_file(source)
    record: dict[str, Any] = {
        "source": str(source),
        "sha256": "sha256:" + sha256_file(source),
        "size_bytes": source.stat().st_size,
    }
    if snapshot is not None:
        record["snapshot"] = str(snapshot)
    if kind is not None:
        record["kind"] = kind
    if identity is not None:
        record["identity"] = identity
    return record


def freeze(args: argparse.Namespace) -> None:
    if not args.source_commit:
        raise ValueError("--source-commit is required when freezing")
    source_commit = git_text("rev-parse", args.source_commit)
    git_text("cat-file", "-e", source_commit + "^{commit}")

    oracle_summary_path = args.oracle_root / "summary" / "summary.json"
    run_status_path = args.oracle_root / "run_status.csv"
    certificate_path = (
        args.oracle_root / "summary" / "candidate_certificates.csv"
    )
    oracle_selection_path = (
        args.oracle_root / "summary" / "oracle_selection.csv"
    )
    coverage_path = (
        args.oracle_root / "summary" / "validation_coverage.csv"
    )
    direct_summary_path = args.direct_root / "summary.json"
    direct_comparison_path = args.direct_root / "comparison.csv"
    planner_summary_path = args.planner_root / "summary.json"
    planner_comparison_path = args.planner_root / "comparison.csv"

    oracle_summary = load_json(oracle_summary_path)
    run_rows = load_csv(run_status_path)
    certificate_rows = load_csv(certificate_path)
    oracle_rows = load_csv(oracle_selection_path)
    coverage_rows = load_csv(coverage_path)
    direct_summary = load_json(direct_summary_path)
    direct_rows = load_csv(direct_comparison_path)
    planner_summary = load_json(planner_summary_path)
    planner_rows = load_csv(planner_comparison_path)

    validate_oracle(
        oracle_summary,
        run_rows,
        certificate_rows,
        oracle_rows,
        coverage_rows,
    )
    validate_direct(direct_summary, direct_rows)
    derived_planner = validate_planner(
        planner_summary,
        planner_rows,
    )

    output = args.output_root
    if output.exists():
        if not args.force:
            raise ValueError(
                f"{output} already exists; use --force to replace it"
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)

    sources = [
        ("oracle/run_status.csv", run_status_path),
        ("oracle/candidate_certificates.csv", certificate_path),
        ("oracle/oracle_selection.csv", oracle_selection_path),
        ("oracle/summary.json", oracle_summary_path),
        ("oracle/validation_coverage.csv", coverage_path),
        ("direct/comparison.csv", direct_comparison_path),
        ("direct/summary.json", direct_summary_path),
        (
            "direct/source_summary.json",
            args.direct_source_root / "summary.json",
        ),
        (
            "direct/source_workload_results.csv",
            args.direct_source_root / "workload_results.csv",
        ),
        ("planner/comparison.csv", planner_comparison_path),
        (
            "planner/planner_candidates.csv",
            args.planner_root / "planner_candidates.csv",
        ),
        (
            "planner/planner_summary.csv",
            args.planner_root / "planner_summary.csv",
        ),
        ("planner/summary.json", planner_summary_path),
    ]
    snapshots: list[dict[str, Any]] = []
    for relative_text, source in sources:
        relative = Path("outputs") / relative_text
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(require_file(source), target)
        snapshots.append(
            artifact_record(source, relative)
        )

    external_artifacts: list[dict[str, Any]] = []
    for row in sorted(
        run_rows,
        key=lambda value: (
            int(value["split_seed"]),
            value["dataset_id"],
            value["model_id"],
            value["profile"],
            value["path"],
        ),
    ):
        identity = (
            f"seed{row['split_seed']}__{row['dataset_id']}__"
            f"{row['model_id']}__{row['candidate_id']}"
        )
        artifact_fields = ["stdout_log"]
        if row["status"] == "ok":
            artifact_fields.extend(["summary_path", "records_path"])
        for field in artifact_fields:
            external_artifacts.append(
                artifact_record(
                    Path(row[field]),
                    kind=field,
                    identity=identity,
                )
            )

    metrics_path = output / "outputs" / "planner" / "derived_metrics.json"
    metrics_path.write_text(
        json.dumps(derived_planner, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 1,
        "evidence_id": args.evidence_id,
        "evidence_type": (
            "strict_bounded_oracle_and_comparison_preliminary"
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
            "oracle": (
                "scripts/run_thesis_grade_tabular_validation_oracle.sh "
                "--full --resume --quiet-skips"
            ),
            "direct_comparison": (
                "python3 "
                "scripts/compare_direct_synthesis_to_catalog_oracle.py "
                "--force"
            ),
            "planner_comparison": (
                "scripts/run_thesis_grade_planner_oracle_comparison.sh "
                "--full"
            ),
        },
        "oracle_summary": oracle_summary,
        "direct_summary": direct_summary,
        "planner_summary": planner_summary,
        "derived_planner_metrics": derived_planner,
        "snapshots": snapshots,
        "external_run_artifacts": external_artifacts,
        "claim_boundary": (
            "The 1,100-run catalog is a bounded exhaustive oracle over "
            "the frozen 22-candidate matrix, not a global CKKS optimum. "
            "Direct/catalog timings were recorded in separate processes "
            "and remain UNPAIRED_DIAGNOSTIC. The planner is a candidate "
            "provider and its full MLP optimum recall is 36%, so it is "
            "not supported as a fastest-SAFE oracle substitute."
        ),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    all_metrics = derived_planner["all"]
    readme = f"""# Full Oracle Comparison Evidence: {args.evidence_id}

## Result

- Oracle candidate executions: `1,100/1,100`
- Successful executions: `1,050`
- Explicit execution failures: `50`
- Certificate rows: `5,500`
- Certificate states: `SAFE=3,750`, `REJECTED=1,500`, `FAILED=250`
- Oracle outcomes: `SELECTED=250`
- Direct outcomes at alpha 0.5: `SELECTED=50/50`
- Direct configuration trials / key runs: `70 / 210`
- Planner false NO_SAFE: `{all_metrics["false_no_safe"]}/250`
- Planner optimum recall: `{100 * all_metrics["optimum_recall"]:.2f}%`
- Planner mean pruning: `{100 * all_metrics["pruning_ratio"]:.2f}%`
- Planner mean bounded regret: `{100 * all_metrics["latency_regret_mean"]:.4f}%`

## Reproduce

```bash
scripts/run_thesis_grade_tabular_validation_oracle.sh --full --resume --quiet-skips
python3 scripts/compare_direct_synthesis_to_catalog_oracle.py --force
scripts/run_thesis_grade_planner_oracle_comparison.sh --full
```

Verify this snapshot:

```bash
python3 scripts/freeze_full_oracle_comparison_evidence.py \\
  --output-root docs/evidence/{args.evidence_id} \\
  --verify
```

The snapshot copies all aggregate oracle, direct-comparison, and
planner-comparison CSV/JSON outputs. To keep the repository compact,
individual candidate logs and raw records are not duplicated.
`manifest.json` binds all {len(external_artifacts)} external run artifacts by
path, byte size, and SHA-256.

## Claim Boundary

This is a bounded exhaustive oracle over the frozen 22-candidate catalog, not
a global CKKS optimum. Direct and catalog latencies were recorded in separate
processes and remain `UNPAIRED_DIAGNOSTIC`; the diagnostic ratio is not a paper
speedup claim. The planner retained at least one SAFE candidate in every
evaluated group, but its MLP optimum recall is 36%, so it is not a reliable
fastest-SAFE oracle substitute.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    checksum_paths = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(output)}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
    )
    print(
        "full_oracle_comparison_evidence=FROZEN_PRELIMINARY "
        f"files={len(checksum_paths)} "
        f"external_artifacts={len(external_artifacts)} "
        f"output={output}"
    )


def verify_checksums(root: Path) -> set[Path]:
    checksum_path = root / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{checksum_path}: checksum list is empty")
    declared: set[Path] = set()
    for line_number, line in enumerate(lines, start=1):
        digest, separator, relative_text = line.partition("  ")
        if len(digest) != 64 or not separator or not relative_text:
            raise ValueError(
                f"{checksum_path}: invalid line {line_number}"
            )
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(
                f"{checksum_path}: unsafe path {relative}"
            )
        path = root / relative
        require_file(path)
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
    return declared


def verify(root: Path) -> None:
    declared = verify_checksums(root)
    manifest = load_json(root / "manifest.json")
    snapshots = manifest.get("snapshots")
    external = manifest.get("external_run_artifacts")
    if not isinstance(snapshots, list) or len(snapshots) != 13:
        raise ValueError("snapshot manifest must contain 13 artifacts")
    if not isinstance(external, list) or len(external) != 3200:
        raise ValueError(
            "snapshot manifest must bind 3200 external artifacts"
        )
    for record in snapshots:
        if not isinstance(record, dict):
            raise ValueError("invalid snapshot artifact record")
        relative = Path(str(record["snapshot"]))
        path = root / relative
        if (
            "sha256:" + sha256_file(path) != record["sha256"]
            or path.stat().st_size != record["size_bytes"]
        ):
            raise ValueError(f"snapshot binding mismatch for {path}")

    oracle_root = root / "outputs" / "oracle"
    oracle_summary = load_json(oracle_root / "summary.json")
    run_rows = load_csv(oracle_root / "run_status.csv")
    certificate_rows = load_csv(
        oracle_root / "candidate_certificates.csv"
    )
    oracle_rows = load_csv(oracle_root / "oracle_selection.csv")
    coverage_rows = load_csv(
        oracle_root / "validation_coverage.csv"
    )
    validate_oracle(
        oracle_summary,
        run_rows,
        certificate_rows,
        oracle_rows,
        coverage_rows,
    )

    direct_root = root / "outputs" / "direct"
    validate_direct(
        load_json(direct_root / "summary.json"),
        load_csv(direct_root / "comparison.csv"),
    )
    planner_root = root / "outputs" / "planner"
    derived = validate_planner(
        load_json(planner_root / "summary.json"),
        load_csv(planner_root / "comparison.csv"),
    )
    frozen_derived = load_json(
        planner_root / "derived_metrics.json"
    )
    if derived != frozen_derived:
        raise ValueError("derived planner metrics do not match")
    if manifest.get("derived_planner_metrics") != derived:
        raise ValueError("manifest planner metrics do not match")
    print(
        "full_oracle_comparison_evidence=VERIFIED "
        f"files={len(declared)} external_artifacts={len(external)}"
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
