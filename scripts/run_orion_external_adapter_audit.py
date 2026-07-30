#!/usr/bin/env python3
"""Run the source-pinned, non-encrypted Orion adapter audit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/orion_external_adapter_v1/contract.json"
)
RESULTS_PARENT = Path(
    "results/thesis_grade_protocol/orion_external_adapter_v1"
)
RUN_SCHEMA = "flipguard_orion_external_adapter_run_v1"

VERIFIER_PATH = (
    REPO_ROOT / "scripts/verify_orion_external_adapter_contract.py"
)
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "verify_orion_contract_for_runner",
    VERIFIER_PATH,
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> tuple[str, str]:
    status = git("status", "--short")
    if status:
        raise ValueError("Orion adapter audit requires a clean tree:\n" + status)
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(f"HEAD {head} does not match origin {origin}")
    return head, origin


def source_url(
    contract: dict[str, Any],
    source: dict[str, Any],
) -> str:
    upstream = contract["upstream"]
    repository = source["repository"]
    if repository == "orion":
        owner_repo = "baahl-nyu/orion"
        commit = upstream["commit"]
    elif repository == "orion_lattigo":
        owner_repo = "baahl-nyu/lattigo"
        commit = upstream["backend_commit"]
    elif repository == "comparison_lattigo":
        owner_repo = "tuneinsight/lattigo"
        commit = upstream["comparison_backend_commit"]
    else:
        raise ValueError(f"unsupported source repository: {repository}")
    return (
        f"https://raw.githubusercontent.com/{owner_repo}/"
        f"{commit}/{source['path']}"
    )


def fetch_bytes(url: str, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "FlipGuard-Orion-Audit/1"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as error:  # network failures are retried and logged
            last_error = error
            if attempt < attempts:
                time.sleep(attempt)
    raise RuntimeError(
        f"failed to fetch {url} after {attempts} attempts: {last_error}"
    )


def write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    (root / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def verify_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file():
            raise ValueError(f"missing audited artifact: {relative}")
        if sha256_path(target) != f"sha256:{digest}":
            raise ValueError(f"audited artifact digest changed: {relative}")


def validate_reports(
    contract: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    expected = {
        config["config_id"]: config
        for config in contract["configurations"]
    }
    if set(reports) != set(expected):
        raise ValueError("Orion adapter report set changed")
    rows = []
    for config_id, prediction in expected.items():
        report = reports[config_id]
        actual_reasons = set(report["block_reasons"])
        if report["status"] != prediction["predicted_status"]:
            raise ValueError(f"{config_id}: adapter status changed")
        if actual_reasons != set(prediction["predicted_reasons"]):
            raise ValueError(f"{config_id}: block reasons changed")
        if (
            report["encrypted_execution"] is not False
            or report["candidate_request_emitted"] is not False
            or report["policy_modification_count"] != 0
        ):
            raise ValueError(f"{config_id}: fail-closed gate was bypassed")
        security = report.get("security_assessment")
        rows.append(
            {
                "config_id": config_id,
                "status": report["status"],
                "block_reasons": sorted(actual_reasons),
                "log_n": report["parsed_parameters"]["log_n"],
                "log_qp": (
                    None if security is None else security["log_qp"]
                ),
                "security_admission": (
                    "UNSUPPORTED_LOGN"
                    if security is None
                    else security["final_admission"]
                ),
                "encrypted_execution": False,
                "candidate_request_emitted": False,
            }
        )
    return {
        "schema_version": RUN_SCHEMA,
        "status": "PASS",
        "classification": "STATIC_FAIL_CLOSED_INTEROPERABILITY_AUDIT",
        "counts": {
            "actual_public_configurations": len(rows),
            "importable_exact": 0,
            "blocked_semantic_mismatch": len(rows),
            "candidate_requests_emitted": 0,
            "encrypted_executions": 0,
            "policy_modifications": 0,
        },
        "configurations": rows,
        "claim_states": {
            "actual_public_orion_source_provenance": "SUPPORTED",
            "orion_schema_translation": "PARTIALLY_SUPPORTED",
            "lossless_orion_candidate_import": "BLOCKED",
            "third_party_compiler_configuration_integration": "BLOCKED",
            "third_party_autotuner_integration": "NOT_EVALUATED",
            "encrypted_external_candidate_certification": "NOT_EVALUATED",
        },
        "paper_claim_allowed": False,
    }


def run_audit(
    contract_path: Path,
    output_root: Path | None,
) -> Path:
    contract_path = (
        contract_path
        if contract_path.is_absolute()
        else REPO_ROOT / contract_path
    )
    VERIFIER.validate_contract(contract_path)
    contract = load_json(contract_path)
    head, origin = require_clean_origin()
    if output_root is None:
        output_root = REPO_ROOT / RESULTS_PARENT / f"run_{head[:7]}"
    elif not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite Orion adapter run: {output_root}"
        )
    output_root.mkdir(parents=True)
    raw_root = output_root / "raw_sources"
    report_root = output_root / "reports"
    log_root = output_root / "logs"
    raw_root.mkdir()
    report_root.mkdir()
    log_root.mkdir()
    started = dt.datetime.now(dt.timezone.utc)

    fetched: dict[str, dict[str, Any]] = {}
    for source in contract["sources"]:
        url = source_url(contract, source)
        data = fetch_bytes(url)
        actual = "sha256:" + hashlib.sha256(data).hexdigest()
        if actual != source["sha256"]:
            raise ValueError(
                f"{source['source_id']}: source digest mismatch "
                f"{actual} != {source['sha256']}"
            )
        local = (
            raw_root / source["source_id"] / Path(source["path"]).name
        )
        local.parent.mkdir()
        local.write_bytes(data)
        fetched[source["source_id"]] = {
            **source,
            "url": url,
            "local_path": local.relative_to(output_root).as_posix(),
            "fetch_attempt_limit": 3,
        }

    binary_path = Path(tempfile.gettempdir()) / (
        f"flipguard-audit-orion-candidate-{os.getpid()}"
    )
    try:
        subprocess.run(
            [
                "go",
                "build",
                "-trimpath",
                "-o",
                str(binary_path),
                "./cmd/flipguard-audit-orion-candidate",
            ],
            cwd=REPO_ROOT,
            check=True,
        )
        binary_digest = sha256_path(binary_path)
        reports: dict[str, dict[str, Any]] = {}
        upstream = contract["upstream"]
        for config in contract["configurations"]:
            source = fetched[config["source_id"]]
            source_path = output_root / source["local_path"]
            report_path = report_root / f"{config['config_id']}.json"
            completed = subprocess.run(
                [
                    str(binary_path),
                    "--config",
                    str(source_path),
                    "--repository-url",
                    upstream["repository_url"],
                    "--commit",
                    upstream["commit"],
                    "--upstream-path",
                    source["path"],
                    "--source-sha256",
                    source["sha256"],
                    "--backend-module",
                    upstream["backend_module"],
                    "--backend-version",
                    upstream["backend_version"],
                    "--backend-commit",
                    upstream["backend_commit"],
                    "--out",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            (log_root / f"{config['config_id']}.stdout.log").write_text(
                completed.stdout,
                encoding="ascii",
            )
            (log_root / f"{config['config_id']}.stderr.log").write_text(
                completed.stderr,
                encoding="ascii",
            )
            reports[config["config_id"]] = load_json(report_path)
    finally:
        binary_path.unlink(missing_ok=True)

    summary = validate_reports(contract, reports)
    ended = dt.datetime.now(dt.timezone.utc)
    source_manifest = {
        "schema_version": "flipguard_orion_upstream_source_manifest_v1",
        "upstream_commit": contract["upstream"]["commit"],
        "sources": list(fetched.values()),
    }
    (output_root / "source_manifest.json").write_bytes(
        canonical_json(source_manifest)
    )
    (output_root / "contract_snapshot.json").write_bytes(
        contract_path.read_bytes()
    )
    (output_root / "summary.json").write_bytes(canonical_json(summary))
    manifest = {
        "schema_version": RUN_SCHEMA,
        "source_commit": head,
        "origin_commit": origin,
        "working_tree_clean": True,
        "contract_sha256": sha256_path(contract_path),
        "binary_sha256": binary_digest,
        "adapter_id": contract["adapter_id"],
        "security_policy_digest": contract["frozen_policies"][
            "security_policy_digest"
        ],
        "direct_policy_digest": contract["frozen_policies"][
            "direct_policy_digest"
        ],
        "orion_commit": contract["upstream"]["commit"],
        "orion_backend_commit": contract["upstream"]["backend_commit"],
        "start_timestamp": started.isoformat(),
        "end_timestamp": ended.isoformat(),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "go_version": subprocess.run(
            ["go", "version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "encrypted_executions": 0,
        "paper_claim_allowed": False,
    }
    (output_root / "run_manifest.json").write_bytes(
        canonical_json(manifest)
    )
    write_checksums(output_root)
    verify_output(contract_path, output_root)
    return output_root


def verify_output(contract_path: Path, output_root: Path) -> dict[str, Any]:
    contract_path = (
        contract_path
        if contract_path.is_absolute()
        else REPO_ROOT / contract_path
    )
    output_root = (
        output_root
        if output_root.is_absolute()
        else REPO_ROOT / output_root
    )
    verify_checksums(output_root)
    contract = load_json(contract_path)
    if sha256_path(output_root / "contract_snapshot.json") != sha256_path(
        contract_path
    ):
        raise ValueError("Orion adapter contract snapshot changed")
    source_manifest = load_json(output_root / "source_manifest.json")
    source_by_id = {
        source["source_id"]: source
        for source in source_manifest["sources"]
    }
    for expected in contract["sources"]:
        actual = source_by_id[expected["source_id"]]
        if actual["sha256"] != expected["sha256"]:
            raise ValueError(
                f"{expected['source_id']}: source manifest changed"
            )
        if sha256_path(output_root / actual["local_path"]) != expected[
            "sha256"
        ]:
            raise ValueError(
                f"{expected['source_id']}: raw source changed"
            )
    reports = {
        config["config_id"]: load_json(
            output_root / "reports" / f"{config['config_id']}.json"
        )
        for config in contract["configurations"]
    }
    expected_summary = validate_reports(contract, reports)
    summary = load_json(output_root / "summary.json")
    if summary != expected_summary:
        raise ValueError("Orion adapter summary changed")
    manifest = load_json(output_root / "run_manifest.json")
    if (
        manifest["encrypted_executions"] != 0
        or manifest["paper_claim_allowed"] is not False
        or manifest["contract_sha256"] != sha256_path(contract_path)
    ):
        raise ValueError("Orion adapter run gate changed")
    return summary


def main() -> int:
    args = parse_args()
    output = run_audit(args.contract, args.output_root)
    summary = load_json(output / "summary.json")
    print(
        "orion_external_adapter_audit=PASS "
        f"configs={summary['counts']['actual_public_configurations']} "
        f"blocked={summary['counts']['blocked_semantic_mismatch']} "
        "encrypted_executions=0 "
        f"output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
