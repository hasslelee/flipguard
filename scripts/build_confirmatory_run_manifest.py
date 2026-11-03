#!/usr/bin/env python3
"""Freeze or verify the immutable pre-execution confirmatory run manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(
    "results/thesis_grade_protocol/final_confirmatory_suite_v1/run_manifest"
)
APPROVED_CHECKPOINT = "41056ad768a133b1e4ba799ada89dd9490001be8"
SECURITY_ROOT = Path(
    "results/thesis_grade_protocol/security_v2_static_attestation"
)
PRIMARY_SPLIT = Path(
    "results/thesis_grade_protocol/tabular_splits_v1/summary.json"
)
STRUCTURAL_SPLIT = Path(
    "results/thesis_grade_protocol/structural_extension_splits_v1/summary.json"
)
BINARIES = {
    "flipguard_autotune": "./cmd/flipguard-autotune",
    "flipguard_audit": "./cmd/flipguard-audit",
    "flipguard_paired_latency": "./cmd/flipguard-paired-latency",
}
SOURCE_PATHS = ("cmd", "internal", "scripts", "go.mod", "go.sum")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--approved-checkpoint-source-commit",
        default=APPROVED_CHECKPOINT,
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--expected-execution-source-commit",
        help=(
            "verify a preserved encrypted-execution commit while later "
            "analysis code is checked out"
        ),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def command(*args: str) -> str:
    return subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def source_status() -> str:
    return command(
        "git",
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *SOURCE_PATHS,
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def host_metadata() -> dict[str, Any]:
    cpu_model = ""
    for line in read_text(Path("/proc/cpuinfo")).splitlines():
        if line.lower().startswith("model name"):
            cpu_model = line.split(":", 1)[-1].strip()
            break
    meminfo = {}
    for line in read_text(Path("/proc/meminfo")).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meminfo[key] = value.strip()
    return {
        "platform": platform.platform(),
        "uname": " ".join(platform.uname()),
        "os_release": read_text(Path("/etc/os-release")),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "logical_cpu": os.cpu_count(),
        "memory_total": meminfo.get("MemTotal", ""),
        "memory_available_at_freeze": meminfo.get("MemAvailable", ""),
        "vm_vendor": read_text(Path("/sys/class/dmi/id/sys_vendor")),
        "vm_product": read_text(Path("/sys/class/dmi/id/product_name")),
        "process_cpu_affinity": (
            sorted(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity")
            else []
        ),
    }


def build_binaries(output: Path) -> dict[str, Any]:
    binary_root = output / "binaries"
    binary_root.mkdir(parents=True, exist_ok=True)
    result = {}
    environment = dict(os.environ)
    environment["GOCACHE"] = "/tmp/flipguard-confirmatory-manifest-gocache"
    for name, package in BINARIES.items():
        path = binary_root / name.replace("_", "-")
        subprocess.run(
            ["go", "build", "-o", str(path), package],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
        )
        result[name] = {
            "package": package,
            "path": str(path.relative_to(REPO_ROOT)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def generate(output: Path, approved_commit: str) -> None:
    if source_status():
        raise ValueError("confirmatory run manifest requires clean source")
    if output.exists():
        raise ValueError(f"{output} exists; use --force")
    output.mkdir(parents=True)
    security_manifest = load_json(REPO_ROOT / SECURITY_ROOT / "manifest.json")
    oracle = load_json(
        REPO_ROOT
        / SECURITY_ROOT
        / "bounded_oracle_security_v2/summary.json"
    )
    for path in (PRIMARY_SPLIT, STRUCTURAL_SPLIT):
        if not (REPO_ROOT / path).is_file():
            raise ValueError(f"missing split summary {path}")
    manifest = {
        "schema_version": 1,
        "manifest_id": "flipguard_final_confirmatory_run_v1",
        "approved_checkpoint_source_commit": approved_commit,
        "execution_source_commit": command("git", "rev-parse", "HEAD"),
        "clean_tree_status_at_freeze": "CLEAN",
        "source_paths": list(SOURCE_PATHS),
        "versions": {
            "go": command("go", "version"),
            "python": platform.python_version(),
            "lattigo_module": "github.com/tuneinsight/lattigo/v6",
            "lattigo_version": command(
                "go",
                "list",
                "-m",
                "-f",
                "{{.Version}}",
                "github.com/tuneinsight/lattigo/v6",
            ),
        },
        "host": host_metadata(),
        "security_policy": {
            "id": security_manifest["security_policy_id"],
            "digest": security_manifest["security_policy_digest"],
        },
        "direct_policy": {
            "id": security_manifest["direct_policy_id"],
            "digest": security_manifest["direct_policy_digest"],
        },
        "splits": {
            "primary": {
                "path": str(PRIMARY_SPLIT),
                "sha256": sha256(REPO_ROOT / PRIMARY_SPLIT),
            },
            "structural_holdout": {
                "identity": "mlp_square_poly3_25_workload_partitions",
                "path": str(STRUCTURAL_SPLIT),
                "sha256": sha256(REPO_ROOT / STRUCTURAL_SPLIT),
            },
        },
        "evaluation_policy": {
            "primary_alpha": 0.5,
            "primary_margin_floor": 0.001,
            "development_seed": 0,
            "confirmatory_seeds": [1, 2, 3, 4],
            "no_retuning": (
                "locked audit replays the byte-identical selected literal; "
                "synthesis and repair are forbidden"
            ),
        },
        "catalog": {
            "raw_catalog_executions": 1100,
            "security_admitted_catalog_candidates": 700,
            "security_excluded_catalog_candidates": 400,
            "admitted_profiles": oracle["admitted_profiles"],
            "excluded_profiles": oracle["excluded_profiles"],
            "paths": ["baseline_non_rescale", "rescale_aware"],
        },
        "fixed_reference": {
            "candidate_id": oracle["reference_candidate_v2"],
            "security_admission": oracle[
                "reference_candidate_v2_admission"
            ],
            "decision_status_evaluated_per_workload": True,
        },
        "paired_latency_policy": {
            "execution_order":
                "balanced_cyclic_and_reverse_row_rotated_v1",
            "warmup_runs": 1,
            "measurement_passes": 6,
            "outlier_removal": "none",
            "concurrent_ckks_processes": 0,
        },
        "start_timestamp": datetime.now().astimezone().isoformat(),
        "binaries": build_binaries(output),
    }
    manifest_path = output / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "run_manifest.sha256").write_text(
        sha256(manifest_path) + "  run_manifest.json\n",
        encoding="utf-8",
    )


def verify(
    output: Path,
    expected_execution_source_commit: str | None = None,
) -> None:
    manifest_path = output / "run_manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("manifest_id") != "flipguard_final_confirmatory_run_v1":
        raise ValueError("unexpected confirmatory run manifest")
    expected_commit = (
        expected_execution_source_commit
        or command("git", "rev-parse", "HEAD")
    )
    if manifest["execution_source_commit"] != expected_commit:
        raise ValueError("run manifest execution source commit changed")
    if source_status():
        raise ValueError("confirmatory execution source is dirty")
    for item in manifest["splits"].values():
        path = REPO_ROOT / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"{path}: split digest changed")
    for item in manifest["binaries"].values():
        path = REPO_ROOT / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError(f"{path}: binary digest changed")
    recorded = (output / "run_manifest.sha256").read_text(
        encoding="utf-8"
    ).split()[0]
    if recorded != sha256(manifest_path):
        raise ValueError("run manifest digest changed")
    print(
        "confirmatory_run_manifest=VERIFIED "
        f"source_commit={manifest['execution_source_commit']} "
        f"digest={recorded}"
    )


def main() -> int:
    args = parse_args()
    output = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        if args.force:
            raise ValueError("--verify and --force are mutually exclusive")
        verify(output, args.expected_execution_source_commit)
        return 0
    if output.exists() and args.force:
        shutil.rmtree(output)
    generate(output, args.approved_checkpoint_source_commit)
    verify(output, args.expected_execution_source_commit)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
