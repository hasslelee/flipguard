#!/usr/bin/env python3
"""Replay deterministic non-tabular source extraction on a clean runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "flipguard_external_source_replay_v1"
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXPECTED_CHECKS = (
    "source_identity",
    "source_fetch",
    "mnist_export",
    "bsds500_sobel_export",
    "bsds500_harris_export",
    "static_graph_contracts",
    "git_diff_check",
    "final_clean_tree",
)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command_specs(fetch_manifest: Path) -> list[tuple[str, list[str]]]:
    python = sys.executable
    static_tests = (
        "^(TestBuildCNNLiteWorkloadContractAndSynthesize|"
        "TestCNNLiteAuditContractUsesOfficialTestRows|"
        "TestBuildHarrisWorkloadContractAndSynthesize)$"
    )
    return [
        ("source_identity", ["git", "rev-parse", "HEAD"]),
        (
            "source_fetch",
            [
                python,
                "scripts/fetch_external_source_inputs.py",
                "--verify",
                str(fetch_manifest),
            ],
        ),
        (
            "mnist_export",
            [
                python,
                "scripts/export_mnist_cnn_lite_holdout.py",
                "--verify",
            ],
        ),
        (
            "bsds500_sobel_export",
            [
                python,
                "scripts/export_bsds500_sobel_holdout.py",
                "--verify",
            ],
        ),
        (
            "bsds500_harris_export",
            [
                python,
                "scripts/export_bsds500_harris_holdout.py",
                "--verify",
            ],
        ),
        (
            "static_graph_contracts",
            [
                "go",
                "test",
                "./internal/ckksplanner",
                "-run",
                static_tests,
                "-count=1",
            ],
        ),
        ("git_diff_check", ["git", "diff", "--check"]),
        (
            "final_clean_tree",
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
        ),
    ]


def run_check(
    name: str,
    command: list[str],
    output: Path,
    expected_source_commit: str,
    env: dict[str, str],
) -> dict[str, Any]:
    started_at = utc_timestamp()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
    )
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
    elif name == "source_fetch":
        semantic_pass = (
            semantic_pass
            and b"external_source_fetch=VERIFIED"
            in completed.stdout
        )
    elif name in {
        "mnist_export",
        "bsds500_sobel_export",
        "bsds500_harris_export",
    }:
        expected_tokens = {
            "mnist_export": b"mnist_cnn_lite_source_replay=PASS",
            "bsds500_sobel_export": b"bsds500_sobel_holdout=PASS",
            "bsds500_harris_export": b"bsds500_harris_holdout=PASS",
        }
        semantic_pass = (
            semantic_pass
            and expected_tokens[name] in completed.stdout
        )
    elif name in {"git_diff_check", "final_clean_tree"}:
        semantic_pass = semantic_pass and not completed.stdout.strip()
    return {
        "name": name,
        "status": "PASS" if semantic_pass else "FAIL",
        "exit_code": completed.returncode,
        "command": command,
        "started_at": started_at,
        "ended_at": utc_timestamp(),
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


def write_checksums(output: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in output.iterdir()
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(f"{sha256_path(path)}  {path.name}\n")
    (output / "SHA256SUMS").write_text(
        "".join(lines),
        encoding="ascii",
    )


def run_replay(
    output: Path,
    source_commit: str,
    fetch_manifest: Path,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite source replay: {output}"
        )
    fetch_record = json.loads(fetch_manifest.read_text(encoding="ascii"))
    if fetch_record["source_commit"] != source_commit:
        raise ValueError(
            "source-fetch commit does not match replay source commit"
        )
    if fetch_record["status"] != "PASS":
        raise ValueError("source-fetch manifest is not PASS")
    output.mkdir(parents=True)
    started_at = utc_timestamp()
    env = dict(os.environ)
    env["PYTHONPYCACHEPREFIX"] = "/tmp/flipguard-external-source-pycache"
    checks = [
        run_check(
            name,
            command,
            output,
            source_commit,
            env,
        )
        for name, command in command_specs(fetch_manifest)
    ]
    status = (
        "PASS"
        if tuple(check["name"] for check in checks) == EXPECTED_CHECKS
        and all(check["status"] == "PASS" for check in checks)
        else "FAIL"
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "classification": "INDEPENDENT_EXTERNAL_SOURCE_REPLAY",
        "source_commit": source_commit,
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
        "source_fetch": {
            "path": "source_fetch_manifest.json",
            "sha256": sha256_path(fetch_manifest),
            "sources": fetch_record["sources"],
        },
        "checks": checks,
        "scope": {
            "source_datasets": ["MNIST", "BSDS500"],
            "deterministic_exporters": [
                "mnist_cnn_lite",
                "bsds500_sobel",
                "bsds500_harris",
            ],
            "static_graph_contracts": 3,
            "encrypted_smoke_test_executed": False,
            "ignored_execution_ledger_replay": "NOT_EVALUATED",
        },
        "policies": {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "policy_retuning": 0,
        },
        "encrypted_execution": {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "paper_claim_allowed": False,
    }
    (output / "source_fetch_manifest.json").write_bytes(
        fetch_manifest.read_bytes()
    )
    (output / "replay.json").write_bytes(canonical_json(record))
    write_checksums(output)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--fetch-manifest", type=Path, required=True)
    args = parser.parse_args()
    record = run_replay(
        args.output.resolve(),
        args.source_commit,
        args.fetch_manifest.resolve(),
    )
    print(
        f"external_source_replay={record['status']} "
        f"checks={len(record['checks'])} output={args.output.resolve()}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
