#!/usr/bin/env python3
"""Build and verify static plans for the deeper tabular graph extension."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SPLIT_ROOT = Path(
    "results/thesis_grade_protocol/structural_extension_splits_v1"
)
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/"
    "structural_extension_v1/static_plans"
)
DATASETS = (
    "banknote",
    "digits_binary",
    "iris_binary",
    "mnist_pool16",
    "wdbc",
)
MODEL_ID = "mlp_square_poly3"
PARTITIONS = (
    "configuration_validation",
    "locked_audit_test",
)
SOURCE_FILES = (
    Path("cmd/flipguard-synthesize/main.go"),
    Path("internal/ckksplanner/contract.go"),
    Path("internal/ckksplanner/synthesis.go"),
    Path("internal/ckksplanner/tabular_contract.go"),
    Path("scripts/analyze_structural_extension_plans.py"),
    Path("go.mod"),
    Path("go.sum"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT,
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_files() -> dict[str, dict[str, Any]]:
    return {
        str(path): {
            "bytes": (REPO_ROOT / path).stat().st_size,
            "sha256": sha256_path(REPO_ROOT / path),
        }
        for path in SOURCE_FILES
    }


def source_digest(files: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for path, item in sorted(files.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def build_binary(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["GOCACHE"] = (
        "/tmp/flipguard-structural-extension-gocache"
    )
    subprocess.run(
        [
            "go",
            "build",
            "-o",
            str(path),
            "./cmd/flipguard-synthesize",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def run_plan(
    binary: Path,
    partition: str,
    seed: int,
    dataset: str,
) -> dict[str, Any]:
    model_path = (
        Path("datasets/tabular_suite")
        / dataset
        / MODEL_ID
        / "model.json"
    )
    validation_path = (
        SPLIT_ROOT
        / f"split_seed_{seed}"
        / dataset
        / MODEL_ID
        / f"{partition}.csv"
    )
    command = [
        str(binary),
        "--model",
        str(model_path),
        "--validation",
        str(validation_path),
        "--split-id",
        f"split_seed_{seed}/structural_extension/{partition}",
        "--margin-floor",
        "0.001",
        "--safety-factor",
        "0.5",
        "--max-encrypted-trials",
        "4",
        "--key-repeats",
        "3",
        "--min-scale-bits",
        "18",
        "--min-prime-bits",
        "18",
        "--special-prime-bits",
        "30",
        "--precision-slack-mode",
        "none",
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    base = {
        "partition": partition,
        "split_seed": seed,
        "dataset_id": dataset,
        "model_id": MODEL_ID,
        "status": "",
        "failure": "",
        "validation_samples": "",
        "v_cert": "",
        "v_amb": "",
        "coverage": "",
        "protected_margin": "",
        "output_error_budget": "",
        "multiplicative_depth": "",
        "rescale_ops": "",
        "required_q_primes": "",
        "candidate_id": "",
        "log_n": "",
        "q_prime_count": "",
        "p_prime_count": "",
        "log_default_scale": "",
        "declared_log_qp": "",
        "security_headroom_bits": "",
    }
    if completed.returncode != 0:
        base["status"] = "INFEASIBLE"
        base["failure"] = completed.stderr.strip()
        return base

    plan = json.loads(completed.stdout)
    contract = plan["contract"]
    decision = contract["decision"]
    deployment = contract["deployment"]
    graph = contract["graph"]
    candidate = plan["initial_candidates"][0]
    parameters = candidate["parameters"]
    security = candidate["security"]
    validation_samples = int(decision["validation_samples"])
    v_cert = int(decision["certifiable_samples"])
    base.update(
        {
            "status": "PLAN_OK",
            "validation_samples": validation_samples,
            "v_cert": v_cert,
            "v_amb": int(decision["ambiguous_samples"]),
            "coverage": v_cert / validation_samples,
            "protected_margin": decision["protected_margin"],
            "output_error_budget": decision[
                "output_error_budget"
            ],
            "multiplicative_depth": graph[
                "multiplicative_depth"
            ],
            "rescale_ops": graph["rescale_ops"],
            "required_q_primes": deployment[
                "required_q_primes"
            ],
            "candidate_id": candidate["id"],
            "log_n": parameters["log_n"],
            "q_prime_count": len(parameters["log_q"]),
            "p_prime_count": len(parameters["log_p"]),
            "log_default_scale": parameters[
                "log_default_scale"
            ],
            "declared_log_qp": security["declared_log_qp"],
            "security_headroom_bits": security[
                "headroom_bits"
            ],
        }
    )
    return base


def validate_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    if len(rows) != 50:
        raise ValueError("structural plan matrix must have 50 rows")
    identities = {
        (
            row["partition"],
            row["split_seed"],
            row["dataset_id"],
            row["model_id"],
        )
        for row in rows
    }
    if len(identities) != 50:
        raise ValueError("structural plan identities are not unique")
    statuses = Counter(row["status"] for row in rows)
    graph_shapes = Counter(
        (
            row["multiplicative_depth"],
            row["rescale_ops"],
            row["required_q_primes"],
        )
        for row in rows
        if row["status"] == "PLAN_OK"
    )
    signatures = Counter(
        (
            row["log_n"],
            row["q_prime_count"],
            row["log_default_scale"],
        )
        for row in rows
        if row["status"] == "PLAN_OK"
    )
    return {
        "statuses": dict(sorted(statuses.items())),
        "graph_shapes": {
            f"depth{key[0]}_rescale{key[1]}_q{key[2]}": count
            for key, count in sorted(graph_shapes.items())
        },
        "candidate_signatures": {
            f"N{key[0]}_Q{key[1]}_S{key[2]}": count
            for key, count in sorted(signatures.items())
        },
        "total_v_cert": sum(
            int(row["v_cert"])
            for row in rows
            if row["status"] == "PLAN_OK"
        ),
        "total_v_amb": sum(
            int(row["v_amb"])
            for row in rows
            if row["status"] == "PLAN_OK"
        ),
    }


def verify(output_root: Path) -> None:
    summary = json.loads(
        (output_root / "summary.json").read_text(encoding="utf-8")
    )
    rows = read_csv(output_root / "plans.csv")
    diagnostics = validate_rows(rows)
    if diagnostics != summary["diagnostics"]:
        raise ValueError("structural diagnostics changed")
    for item in summary["inputs"].values():
        path = REPO_ROOT / item["path"]
        if sha256_path(path) != item["sha256"]:
            raise ValueError(f"{path}: input digest changed")
    for relative, item in summary["source"]["files"].items():
        path = REPO_ROOT / relative
        if (
            path.stat().st_size != item["bytes"]
            or sha256_path(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: source digest changed")
    output = summary["outputs"]["plans"]
    if sha256_path(output_root / "plans.csv") != output["sha256"]:
        raise ValueError("structural plans digest changed")
    print(
        "structural_extension_plans=VERIFIED "
        f"plans={len(rows)} "
        f"statuses={diagnostics['statuses']} "
        f"shapes={diagnostics['graph_shapes']} "
        f"signatures={diagnostics['candidate_signatures']}"
    )


def main() -> int:
    args = parse_args()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(output_root)
        return 0
    if output_root.exists() and not args.force:
        raise ValueError(f"{output_root} exists; use --force")
    output_root.mkdir(parents=True, exist_ok=True)
    binary = output_root / "bin/flipguard-synthesize"
    build_binary(binary)
    rows = [
        run_plan(binary, partition, seed, dataset)
        for partition in PARTITIONS
        for seed in range(5)
        for dataset in DATASETS
    ]
    rows.sort(
        key=lambda row: (
            row["partition"],
            int(row["split_seed"]),
            row["dataset_id"],
        )
    )
    plans_path = output_root / "plans.csv"
    write_csv(plans_path, rows)
    files = source_files()
    split_summary = REPO_ROOT / SPLIT_ROOT / "summary.json"
    summary = {
        "schema_version": 1,
        "status": "STATIC_PLAN_COMPLETE",
        "claim_boundary": (
            "Static feasibility for the five-dataset mlp_square_poly3 "
            "extension does not establish encrypted safety."
        ),
        "protocol": {
            "split_seeds": list(range(5)),
            "datasets": list(DATASETS),
            "model_id": MODEL_ID,
            "partitions": list(PARTITIONS),
            "margin_floor": 0.001,
            "safety_factor": 0.5,
            "key_repeats_contract": 3,
            "max_encrypted_trials": 4,
        },
        "diagnostics": validate_rows(
            [
                {
                    key: str(value)
                    for key, value in row.items()
                }
                for row in rows
            ]
        ),
        "inputs": {
            "split_summary": {
                "path": str(split_summary.relative_to(REPO_ROOT)),
                "sha256": sha256_path(split_summary),
            }
        },
        "source": {
            "commit": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
            "digest": source_digest(files),
            "files": files,
        },
        "outputs": {
            "plans": {
                "path": str(plans_path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(plans_path),
            }
        },
    }
    write_json(output_root / "summary.json", summary)
    verify(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
