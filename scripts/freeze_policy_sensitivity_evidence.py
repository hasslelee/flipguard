#!/usr/bin/env python3
"""Freeze and independently verify the static policy-sensitivity study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_ROOT = Path(
    "results/thesis_grade_protocol/policy_sensitivity_v1/full"
)
DEFAULT_OUTPUT_ROOT = Path(
    "docs/evidence/policy_sensitivity_v1"
)
RESULT_FILES = (
    Path("summary.json"),
    Path("synthesis_plans.csv"),
    Path("synthesis_aggregate.csv"),
    Path("alpha_certificate_sensitivity.csv"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def artifact(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(base)),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing source file {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def validate_study(root: Path) -> dict[str, Any]:
    summary = load_json(root / "summary.json")
    if (
        summary.get("schema_version") != 1
        or summary.get("status") != "COMPLETE"
    ):
        raise ValueError("policy study is not schema-v1 COMPLETE")

    plans = read_csv(root / "synthesis_plans.csv")
    aggregates = read_csv(root / "synthesis_aggregate.csv")
    alpha_rows = read_csv(root / "alpha_certificate_sensitivity.csv")
    counts = summary["counts"]
    if (
        len(plans) != 4500
        or len(aggregates) != 90
        or len(alpha_rows) != 5
        or counts
        != {
            "plan_rows": 4500,
            "plan_ok": 4485,
            "infeasible": 15,
            "no_certifiable_sample": 15,
            "unexpected_failures": 0,
            "aggregate_rows": 90,
        }
    ):
        raise ValueError("policy study row or outcome counts changed")

    expected_grid = {
        (
            partition,
            str(seed),
            dataset,
            model,
            format(alpha, ".12g"),
            format(floor, ".12g"),
        )
        for partition in (
            "configuration_validation",
            "locked_audit_test",
        )
        for seed in range(5)
        for dataset in (
            "banknote",
            "digits_binary",
            "iris_binary",
            "mnist_pool16",
            "wdbc",
        )
        for model in (
            "linear_poly3",
            "mlp_square_linear_score",
        )
        for alpha in (0.1, 0.25, 0.5, 0.75, 0.9)
        for floor in (
            0.0,
            1e-5,
            1e-4,
            5e-4,
            1e-3,
            2e-3,
            5e-3,
            1e-2,
            5e-2,
        )
    }
    observed_grid = {
        (
            row["partition"],
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
            row["alpha"],
            row["margin_floor"],
        )
        for row in plans
    }
    if observed_grid != expected_grid:
        raise ValueError("policy study grid changed")

    statuses = Counter(row["status"] for row in plans)
    failures = Counter(
        row["failure_class"]
        for row in plans
        if row["failure_class"]
    )
    if (
        statuses != {"PLAN_OK": 4485, "INFEASIBLE": 15}
        or failures != {"NO_CERTIFIABLE_SAMPLE": 15}
    ):
        raise ValueError("policy study failure semantics changed")

    expected_alpha = {
        "candidate_rows": "1100",
        "safe": "750",
        "rejected": "300",
        "failed": "50",
        "oracle_rows": "50",
        "oracle_selected": "50",
        "oracle_no_safe": "0",
    }
    for row in alpha_rows:
        if any(row[key] != value for key, value in expected_alpha.items()):
            raise ValueError("alpha certificate counts changed")
    diagnostics = summary["alpha_certificate_diagnostics"]
    if (
        not diagnostics["status_invariant_across_grid"]
        or not diagnostics["oracle_invariant_across_grid"]
        or diagnostics["candidate_state_changes_across_alpha"] != 0
        or diagnostics["oracle_candidate_changes_across_alpha"] != 0
    ):
        raise ValueError("alpha invariance diagnostics failed")

    by_policy = {
        (
            row["partition"],
            row["alpha"],
            row["margin_floor"],
        ): row
        for row in aggregates
    }
    expected = {
        ("configuration_validation", "0.5", "0.0005"):
            (50, 8142, 8230),
        ("configuration_validation", "0.5", "0.001"):
            (50, 8043, 8230),
        ("locked_audit_test", "0.5", "0.0005"):
            (50, 8203, 8300),
        ("locked_audit_test", "0.5", "0.001"):
            (50, 8122, 8300),
    }
    expected_signature = '{"N13_Q6_S20":25,"N13_Q7_S20":25}'
    for key, (plan_ok, v_cert, samples) in expected.items():
        row = by_policy[key]
        if (
            int(row["plan_ok"]) != plan_ok
            or int(row["total_v_cert"]) != v_cert
            or int(row["total_samples_in_plan_ok"]) != samples
            or row["candidate_signatures"] != expected_signature
            or not math.isclose(
                float(row["aggregate_coverage"]),
                v_cert / samples,
                rel_tol=0,
                abs_tol=1e-15,
            )
        ):
            raise ValueError(f"policy checkpoint changed: {key}")

    for name, item in summary["outputs"].items():
        source = root / Path(item["path"]).name
        if sha256_path(source) != item["sha256"]:
            raise ValueError(f"{name}: summary output digest mismatch")
    return summary


def write_readme(path: Path) -> None:
    path.write_text(
        """# FlipGuard Policy-Sensitivity Evidence

This pack freezes the complete static policy grid used in Step 7B.6.

- Static synthesis plans: `4,500`
- Successful plans: `4,485`
- Expected no-certifiable-sample outcomes: `15`
- Unexpected failures: `0`
- Aggregate policy cells: `90`
- Alpha certificate rows: `5`

At alpha `0.5`, lowering the margin floor from `0.001` to `0.0005`
increases certifiable validation rows from `8,043` to `8,142` and audit rows
from `8,122` to `8,203`, while retaining the same 50 static parameter
signatures. This is static challenger evidence, not encrypted recertification.

Verify all copied files, external bindings, grid completeness, outcome
semantics, alpha invariance, and the default/challenger checkpoints with:

```bash
python3 scripts/freeze_policy_sensitivity_evidence.py --verify
```
""",
        encoding="utf-8",
    )


def generate(input_root: Path, output_root: Path, force: bool) -> None:
    summary = validate_study(input_root)
    if output_root.exists():
        if not force:
            raise ValueError(f"{output_root} exists; use --force")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    for relative in RESULT_FILES:
        copy_file(
            input_root / relative,
            output_root / "results" / relative,
        )
    for relative, expected in summary["source"]["files"].items():
        source = REPO_ROOT / relative
        if (
            source.stat().st_size != expected["bytes"]
            or sha256_path(source) != expected["sha256"]
        ):
            raise ValueError(f"{source}: source snapshot changed")
        copy_file(source, output_root / "source" / relative)
    copy_file(
        REPO_ROOT / "scripts/freeze_policy_sensitivity_evidence.py",
        output_root
        / "source/scripts/freeze_policy_sensitivity_evidence.py",
    )
    write_readme(output_root / "README.md")

    copied = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    external = []
    for item in summary["inputs"].values():
        source = REPO_ROOT / item["path"]
        if sha256_path(source) != item["sha256"]:
            raise ValueError(f"{source}: external input changed")
        external.append(artifact(source, REPO_ROOT))
    manifest = {
        "schema_version": 1,
        "evidence_id": "policy_sensitivity_v1",
        "status": "STATIC_GRID_COMPLETE",
        "claim_boundary": summary["claim_boundary"],
        "source_commit": summary["source"]["commit"],
        "source_digest": summary["source"]["digest"],
        "counts": {
            **summary["counts"],
            "internal_files": len(copied),
            "external_artifacts": len(external),
        },
        "files": {
            str(path.relative_to(output_root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256_path(path),
            }
            for path in copied
        },
        "external_artifacts": sorted(
            external,
            key=lambda item: item["path"],
        ),
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify(output_root: Path) -> None:
    manifest = load_json(output_root / "manifest.json")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("evidence_id") != "policy_sensitivity_v1"
    ):
        raise ValueError("unsupported policy evidence manifest")

    expected_files = set(manifest["files"])
    actual_files = {
        str(path.relative_to(output_root))
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_files != expected_files:
        raise ValueError(
            "policy evidence file set changed: "
            f"missing={sorted(expected_files - actual_files)} "
            f"unexpected={sorted(actual_files - expected_files)}"
        )
    for relative, expected in manifest["files"].items():
        path = output_root / relative
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: evidence digest changed")
    for expected in manifest["external_artifacts"]:
        path = REPO_ROOT / expected["path"]
        if (
            path.stat().st_size != expected["bytes"]
            or sha256_path(path) != expected["sha256"]
        ):
            raise ValueError(f"{path}: external digest changed")

    summary = validate_study(output_root / "results")
    for relative, expected in summary["source"]["files"].items():
        source = output_root / "source" / relative
        if (
            source.stat().st_size != expected["bytes"]
            or sha256_path(source) != expected["sha256"]
        ):
            raise ValueError(f"{source}: frozen source mismatch")
    print(
        "policy_sensitivity_evidence=VERIFIED "
        f"files={len(expected_files)} "
        f"external={len(manifest['external_artifacts'])} "
        "plans=4500"
    )


def main() -> int:
    args = parse_args()
    input_root = (REPO_ROOT / args.input_root).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output_root)
    else:
        generate(input_root, output_root, args.force)
        verify(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
