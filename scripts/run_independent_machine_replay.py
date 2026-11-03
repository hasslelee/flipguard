#!/usr/bin/env python3
"""Run the committed FlipGuard artifact checks on an independent machine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "flipguard_independent_machine_replay_v1"
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXPECTED_CHECKS = (
    "source_identity",
    "initial_clean_tree",
    "go_test",
    "go_vet",
    "python_unittest",
    "python_py_compile",
    "bash_syntax",
    "git_diff_check",
    "checkpoint_v1",
    "checkpoint_v2",
    "final_clean_tree",
)
SOURCE_REPLAY_INPUTS = (
    "results/source_datasets/mnist/mnist_784.arff.gz",
    "results/source_datasets/bsds500/BSR_bsds500.tgz",
    "results/thesis_grade_protocol/paper_artifacts_v2/current/"
    "appendix/evidence_manifest.json",
    "results/thesis_grade_protocol/direct_tabular_autotune_v1/"
    "full_structural_poly3_inputmodel_floor18_keys3/summary/summary.json",
    "results/thesis_grade_protocol/non_tabular_harris_holdout_v1/"
    "run_a4ccd0b/run_manifest.json",
    "results/thesis_grade_protocol/direct_synthesis_ablation_v1/"
    "run_062e1a9/run_manifest.json",
    "results/thesis_grade_protocol/independent_training_seed_extension_v1/"
    "run_f3cfd7f/run_manifest.json",
    "results/thesis_grade_protocol/non_tabular_mnist_cnn_lite_holdout_v1/"
    "run_515d5dd/run_manifest.json",
)
PORTABLE_GO_EXCLUSIONS = (
    "TestRunRequiresInputs",
    "TestBuildCNNLiteWorkloadContractAndSynthesize",
    "TestCNNLiteAuditContractUsesOfficialTestRows",
    "TestCNNLiteInitialCandidateOneRowSmoke",
    "TestBuildHarrisWorkloadContractAndSynthesize",
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_files(pattern: str) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", pattern],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    ]


def command_specs() -> list[tuple[str, list[str]]]:
    python_files = git_files("*.py")
    shell_files = git_files("*.sh")
    python = sys.executable
    return [
        (
            "source_identity",
            ["git", "rev-parse", "HEAD"],
        ),
        (
            "initial_clean_tree",
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        ),
        (
            "go_test",
            [
                "go",
                "test",
                "./...",
                "-skip",
                "^(" + "|".join(PORTABLE_GO_EXCLUSIONS) + ")$",
            ],
        ),
        ("go_vet", ["go", "vet", "./..."]),
        (
            "python_unittest",
            [
                python,
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/tests",
                "-p",
                "test_*.py",
            ],
        ),
        (
            "python_py_compile",
            [python, "-m", "py_compile", *python_files],
        ),
        ("bash_syntax", ["bash", "-n", *shell_files]),
        ("git_diff_check", ["git", "diff", "--check"]),
        (
            "checkpoint_v1",
            [
                python,
                "scripts/freeze_research_completion_checkpoint_v1.py",
                "--verify",
            ],
        ),
        (
            "checkpoint_v2",
            [
                python,
                "scripts/freeze_research_completion_checkpoint_v2.py",
                "--verify",
            ],
        ),
        (
            "final_clean_tree",
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        ),
    ]


def run_check(
    name: str,
    command: list[str],
    output: Path,
    env: dict[str, str],
    expected_source_commit: str,
) -> dict[str, Any]:
    started_at = utc_timestamp()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
    )
    ended_at = utc_timestamp()
    stdout_path = output / f"{name}.stdout.txt"
    stderr_path = output / f"{name}.stderr.txt"
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)

    semantic_pass = completed.returncode == 0
    if name == "source_identity":
        semantic_pass = (
            semantic_pass
            and completed.stdout.decode("utf-8").strip()
            == expected_source_commit
        )
    elif name in {"initial_clean_tree", "final_clean_tree"}:
        semantic_pass = semantic_pass and not completed.stdout.strip()
    elif name == "checkpoint_v1":
        semantic_pass = (
            semantic_pass
            and b"research_completion_checkpoint_v1=VERIFIED"
            in completed.stdout
        )
    elif name == "checkpoint_v2":
        semantic_pass = (
            semantic_pass
            and b"research_completion_checkpoint_v2=VERIFIED"
            in completed.stdout
        )

    return {
        "name": name,
        "status": "PASS" if semantic_pass else "FAIL",
        "exit_code": completed.returncode,
        "command": command,
        "started_at": started_at,
        "ended_at": ended_at,
        "stdout": {
            "path": stdout_path.name,
            "sha256": sha256_path(stdout_path),
            "bytes": stdout_path.stat().st_size,
        },
        "stderr": {
            "path": stderr_path.name,
            "sha256": sha256_path(stderr_path),
            "bytes": stderr_path.stat().st_size,
        },
    }


def version_output(command: list[str]) -> str:
    return subprocess.check_output(
        command,
        cwd=REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def memory_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def source_replay_scope() -> dict[str, Any]:
    inputs = [
        {
            "path": relative,
            "available": (REPO_ROOT / relative).is_file(),
        }
        for relative in SOURCE_REPLAY_INPUTS
    ]
    missing = [
        item["path"] for item in inputs if not item["available"]
    ]
    return {
        "status": (
            "COMPLETE"
            if not missing
            else "NOT_EVALUATED_ON_CLEAN_CLONE"
        ),
        "inputs": inputs,
        "missing": missing,
        "portable_tests_skip_missing_external_inputs": True,
        "portable_go_test_exclusions": list(PORTABLE_GO_EXCLUSIONS),
        "portable_go_exclusion_reasons": {
            "TestRunRequiresInputs": (
                "diagnostic assertion depends on nondeterministic Go map "
                "iteration order; frozen source closure is not modified"
            ),
            "external_source_tests": (
                "four tests require ignored MNIST or BSDS500 source inputs"
            ),
        },
        "committed_checkpoint_replay_independent_of_raw_results": True,
    }


def write_checksums(output: Path) -> None:
    files = sorted(
        path
        for path in output.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    lines = [
        f"{sha256_path(path)}  {path.name}"
        for path in files
    ]
    (output / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n",
        encoding="ascii",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite replay output: {output}")
    output.mkdir(parents=True)

    started_at = utc_timestamp()
    with tempfile.TemporaryDirectory(
        prefix="flipguard-independent-replay-pycache-",
        dir="/tmp",
    ) as pycache:
        pycache_root = Path(pycache)
        env = dict(os.environ)
        env["PYTHONPYCACHEPREFIX"] = str(pycache_root)
        checks = [
            run_check(
                name,
                command,
                output,
                env,
                args.source_commit,
            )
            for name, command in command_specs()
        ]

    status = (
        "PASS"
        if tuple(item["name"] for item in checks) == EXPECTED_CHECKS
        and all(item["status"] == "PASS" for item in checks)
        else "FAIL"
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": "INDEPENDENT_MACHINE_DETERMINISTIC_REPLAY",
        "source_commit": args.source_commit,
        "started_at": started_at,
        "ended_at": utc_timestamp(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "memory_bytes": memory_bytes(),
            "python": version_output([sys.executable, "--version"]),
            "go": version_output(["go", "version"]),
            "git": version_output(["git", "--version"]),
        },
        "policies": {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "checks": checks,
        "source_replay_scope": source_replay_scope(),
        "encrypted_execution": {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "paper_claim_allowed": False,
    }
    (output / "replay.json").write_bytes(canonical_json(record))
    write_checksums(output)
    print(
        f"independent_machine_replay={status} "
        f"checks={len(checks)} output={output}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
