#!/usr/bin/env python3
"""Run the final static audit in a disposable clean clone.

This script does not run research experiments. The immutable manuscript input
bundle is copied in only for deterministic report regeneration and removed
before the clean-tree assertion.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "98e5e4105c0b0597d6fb245b5718a00eb4828349"
INPUT_DIR = ROOT / "docs/manuscript_review_input"
INPUT_ZIP = ROOT / "docs/FlipGuard_정보보호학회논문지_석사학위논문_전체편집원본_v10_평면구조.zip"
EXTERNAL_DATASETS = {
    Path("results/source_datasets/mnist/mnist_784.arff.gz"): "fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78",
    Path("results/source_datasets/bsds500/BSR_bsds500.tgz"): "97e49d31764f3912f0c4122707d53062ac9e783ba0f095e447a4d53c1a41af8e",
}
BOUND_RUNTIME_INPUTS = {
    Path(
        "results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/"
        "iris_binary/linear_poly3/configuration_validation.csv"
    ): "29cf99a47cd25520a15aa36d8e7fdf58328fc3a91ad54067266d443b4c04e5ea",
    Path(
        "results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/"
        "iris_binary/linear_poly3/locked_audit_test.csv"
    ): "72a182968acd60e8c0bd5acc830627d698a9f1d2e1760dd492dbb07129a26327",
    Path(
        "results/thesis_grade_protocol/tabular_splits_v1/split_seed_0/"
        "iris_binary/linear_poly3/split_manifest.json"
    ): "c76e7b0478fffbbac4d24ff41a86fa7694cf3f5719e462270eb780b2531760d1",
    Path(
        "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
        "full_final_baseline_inputmodel_floor18_keys3/results/"
        "directv1_full_final_baseline_inputmodel_floor18_keys3_seed0_"
        "iris_binary_linear_poly3.json"
    ): "df20396b04f3fae71c518e75a26ad9e18cd0007fd64d3d32175ed6a8561d9842",
    Path(
        "results/thesis_grade_protocol/security_v2_static_attestation/"
        "bounded_oracle_security_v2/oracle_selection_security_v2.csv"
    ): "dc08523ec449d123d0b7aab2df8449bb450dc97236d70ad5f122bd0f99a333c6",
}
BOUND_RUNTIME_TREES = {
    Path(
        "results/thesis_grade_protocol/provider_candidate_gate_v1/"
        "run_707441b"
    ): {
        "sha256": "d1ecd65e0380d0bb4b654dec850f1549f5ff0ac99dfada146ad9145247b998af",
        "file_count": 24,
        "size_bytes": 22392926,
    },
    Path(
        "results/thesis_grade_protocol/provider_candidate_gate_v1/"
        "run_f84ecff"
    ): {
        "sha256": "8447dd6a5a11035954e35f187bf5eff0afbb96d5acd515d4860ab99104013a16",
        "file_count": 21,
        "size_bytes": 22364768,
    },
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tree_binding(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    file_count = 0
    size_bytes = 0
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        file_digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                file_digest.update(chunk)
        digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.digest())
        digest.update(b"\n")
        file_count += 1
        size_bytes += file_path.stat().st_size
    return {
        "sha256": digest.hexdigest(),
        "file_count": file_count,
        "size_bytes": size_bytes,
    }


def run(command: list[str], cwd: Path, env: dict[str, str], timeout: int = 7200) -> dict[str, object]:
    started = dt.datetime.now(dt.timezone.utc)
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
    ended = dt.datetime.now(dt.timezone.utc)
    combined = proc.stdout + ("\n" if proc.stdout and proc.stderr else "") + proc.stderr
    record = {
        "command": command,
        "returncode": proc.returncode,
        "elapsed_seconds": (ended - started).total_seconds(),
        "output_sha256": sha256_text(combined),
        "output_tail": "\n".join(combined.splitlines()[-30:]),
    }
    if proc.returncode:
        raise RuntimeError(json.dumps(record, ensure_ascii=False, indent=2))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", default=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip())
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/final_manuscript_audit_v1/clean_clone_audit.json")
    args = parser.parse_args()
    if not INPUT_DIR.is_dir() or not INPUT_ZIP.is_file():
        raise SystemExit("clean_clone_audit=FAILED immutable_manuscript_input_missing")
    temporary_test_inputs = EXTERNAL_DATASETS | BOUND_RUNTIME_INPUTS
    for relative_path, expected in temporary_test_inputs.items():
        source = ROOT / relative_path
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"clean_clone_audit=FAILED test_input_digest:{relative_path}")
    for relative_path, expected in BOUND_RUNTIME_TREES.items():
        source = ROOT / relative_path
        if not source.is_dir() or tree_binding(source) != expected:
            raise SystemExit(f"clean_clone_audit=FAILED test_input_tree:{relative_path}")

    start = dt.datetime.now(dt.timezone.utc)
    checks: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="flipguard-final-audit-clean-") as temp:
        clone = Path(temp) / "repo"
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPYCACHEPREFIX"] = str(Path(temp) / "pycache")
        checks.append(run(["git", "clone", "--no-local", "--no-hardlinks", str(ROOT), str(clone)], Path(temp), env))
        checks.append(run(["git", "checkout", "--detach", args.commit], clone, env))
        actual_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=clone, text=True).strip()
        if actual_commit != args.commit:
            raise SystemExit("clean_clone_audit=FAILED commit_mismatch")
        checks.append(run(["git", "merge-base", "--is-ancestor", SOURCE_COMMIT, args.commit], clone, env))

        external_dir = clone / "docs/manuscript_review_input"
        external_zip = clone / INPUT_ZIP.relative_to(ROOT)
        shutil.copytree(INPUT_DIR, external_dir)
        external_zip.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INPUT_ZIP, external_zip)
        for relative_path in temporary_test_inputs:
            destination = clone / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative_path, destination)
        for relative_path in BOUND_RUNTIME_TREES:
            shutil.copytree(ROOT / relative_path, clone / relative_path)

        commands = [
            ["go", "test", "./..."],
            ["go", "vet", "./..."],
            ["python3", "-m", "unittest", "discover", "-s", "scripts/tests", "-p", "test_*.py"],
            ["python3", "scripts/verify_tracked_predecessors.py"],
            ["bash", "scripts/verify_frozen_evidence.sh"],
            ["python3", "scripts/build_final_manuscript_audit_v1.py"],
            ["python3", "scripts/verify_manuscript_numbers.py"],
            ["python3", "scripts/verify_claim_sentence_traceability.py"],
            ["python3", "docs/evidence/final_manuscript_audit_v1/verify_final_manuscript_audit_v1.py", "--allow-clean-clone-pending"],
            ["bash", "scripts/reproduce_quick_demo.sh"],
            ["git", "diff", "--exit-code"],
        ]
        for command in commands:
            checks.append(run(command, clone, env))

        tracked_python = subprocess.check_output(["git", "ls-files", "*.py"], cwd=clone, text=True).splitlines()
        checks.append(run(["python3", "-m", "py_compile", *tracked_python], clone, env))
        tracked_shell = subprocess.check_output(["git", "ls-files", "*.sh"], cwd=clone, text=True).splitlines()
        if tracked_shell:
            checks.append(run(["bash", "-n", *tracked_shell], clone, env))

        shutil.rmtree(external_dir)
        external_zip.unlink()
        for relative_path in temporary_test_inputs:
            (clone / relative_path).unlink()
        for relative_path in BOUND_RUNTIME_TREES:
            shutil.rmtree(clone / relative_path)
        final_status = subprocess.check_output(["git", "status", "--short"], cwd=clone, text=True)
        if final_status:
            raise SystemExit(f"clean_clone_audit=FAILED dirty_tree:{final_status}")

    end = dt.datetime.now(dt.timezone.utc)
    output = {
        "schema_version": "flipguard_final_manuscript_audit_v1_clean_clone",
        "source_commit": SOURCE_COMMIT,
        "audit_commit": args.commit,
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "elapsed_seconds": (end - start).total_seconds(),
        "status": "PASS",
        "checks": checks,
        "check_count": len(checks),
        "final_git_status_short": "",
        "external_manuscript_inputs": {
            "directory_sha_binding": "docs/evidence/final_manuscript_audit_v1/dependency_manifest.json",
            "flat_zip_sha256": hashlib.sha256(INPUT_ZIP.read_bytes()).hexdigest(),
            "copied_for_rebuild": True,
            "removed_before_clean_status_check": True,
        },
        "external_dataset_inputs": [
            {"path": path.as_posix(), "sha256": digest, "copied_for_tests": True, "removed_before_clean_status_check": True}
            for path, digest in EXTERNAL_DATASETS.items()
        ],
        "bound_runtime_test_inputs": [
            {
                "path": path.as_posix(),
                "sha256": digest,
                "copied_for_tests": True,
                "removed_before_clean_status_check": True,
            }
            for path, digest in BOUND_RUNTIME_INPUTS.items()
        ],
        "bound_runtime_test_trees": [
            {
                "path": path.as_posix(),
                **binding,
                "copied_for_tests": True,
                "removed_before_clean_status_check": True,
            }
            for path, binding in BOUND_RUNTIME_TREES.items()
        ],
        "recovery_attempts": [
            {
                "attempt": 1,
                "classification": "RUNNER_INPUT_ERROR",
                "failure": "incorrect manually supplied full audit commit caused checkout failure before verification",
                "resolution": "read exact git rev-parse HEAD and retry",
            },
            {
                "attempt": 2,
                "classification": "RECOVERABLE_REPRODUCIBILITY_FAILURE",
                "failure": "go test lacked ignored MNIST and BSDS500 source archives in the clean clone",
                "resolution": "verify and temporarily restore the two existing digest-bound source archives",
            },
            {
                "attempt": 3,
                "classification": "RECOVERABLE_REPRODUCIBILITY_FAILURE",
                "failure": "Python tests lacked five ignored contract-bound split, selection, and bounded-oracle artifacts",
                "resolution": "verify and temporarily restore only the five files named by frozen contracts, then remove them before the clean-tree check",
            },
            {
                "attempt": 4,
                "classification": "RUNNER_INPUT_ERROR_REPEAT",
                "failure": "a second manually transcribed audit commit was rejected before verification",
                "resolution": "obtain the full commit only from git rev-parse HEAD and retry without transcription",
            },
            {
                "attempt": 5,
                "classification": "RECOVERABLE_REPRODUCIBILITY_FAILURE",
                "failure": "three provider evidence-freezer tests lacked two ignored provider-gate run trees",
                "resolution": "bind both trees by relative-path and per-file SHA-256 aggregation, restore them temporarily, and remove them before the clean-tree check",
            },
        ],
        "new_scientific_execution_count": 0,
        "long_experiments_run": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"clean_clone_audit=PASS checks={len(checks)} elapsed_seconds={output['elapsed_seconds']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
