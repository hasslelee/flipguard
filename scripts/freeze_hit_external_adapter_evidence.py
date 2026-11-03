#!/usr/bin/env python3
"""Freeze and verify the AWS HIT source-replay development evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "experiments/hit_external_adapter_v1/contract.json"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/hit_external_adapter_replay_v1"
)
PROTOCOL = Path(
    "docs/research/step_7g3_aws_hit_external_parameter_selector_protocol.md"
)
SCHEMA_VERSION = "flipguard_hit_external_adapter_evidence_v1"

RUNNER_PATH = REPO_ROOT / "scripts/run_hit_external_adapter_replay.py"
SPEC = importlib.util.spec_from_file_location(
    "run_hit_adapter_for_freezer",
    RUNNER_PATH,
)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


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


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "HIT evidence freeze requires a clean tree:\n" + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(f"HEAD {head} does not match origin {origin}")
    return head


def selected_run_paths(run_root: Path) -> list[Path]:
    fixed = [
        "contract_snapshot.json",
        "source_manifest.json",
        "materialization.json",
        "candidate_request.json",
        "run_manifest.json",
        "completion_manifest.json",
        "state.json",
        "stage_ledger.json",
        "summary.json",
        "selection.json",
        "locked_audit.json",
    ]
    paths = [
        run_root / relative
        for relative in fixed
        if (run_root / relative).is_file()
    ]
    for directory in ("raw_sources", "logs"):
        root = run_root / directory
        if root.is_dir():
            paths.extend(
                path for path in root.rglob("*") if path.is_file()
            )
    return sorted(paths)


def copy_run(run_root: Path, destination: Path) -> None:
    for source in selected_run_paths(run_root):
        relative = source.relative_to(run_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


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
    expected: set[str] = set()
    for line in (root / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines():
        digest, relative = line.split("  ", 1)
        target = root / relative
        if not target.is_file() or sha256_path(target) != f"sha256:{digest}":
            raise ValueError(f"frozen HIT artifact changed: {relative}")
        expected.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != expected:
        raise ValueError("frozen HIT evidence file set changed")


def validate_frozen_run(
    root: Path,
    contract_path: Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    materialization = load_json(root / "materialization.json")
    RUNNER.validate_materialization(contract, materialization)
    if load_json(root / "candidate_request.json") != \
            RUNNER.candidate_request(materialization):
        raise ValueError("frozen HIT candidate request changed")
    source_manifest = load_json(root / "source_manifest.json")
    expected_sources = {
        source["source_id"]: source for source in contract["sources"]
    }
    for source in source_manifest["sources"]:
        expected = expected_sources.pop(source["source_id"])
        local = root / source["local_path"]
        if (
            source["sha256"] != expected["sha256"]
            or sha256_path(local) != expected["sha256"]
        ):
            raise ValueError("frozen HIT source replay changed")
    if expected_sources:
        raise ValueError("frozen HIT source replay is incomplete")

    summary = load_json(root / "summary.json")
    selection = (
        load_json(root / "selection.json")
        if (root / "selection.json").is_file()
        else None
    )
    audit = (
        load_json(root / "locked_audit.json")
        if (root / "locked_audit.json").is_file()
        else None
    )
    expected_summary = RUNNER.build_summary(
        root,
        selection,
        audit,
        summary["implementation_failure"],
    )
    if summary != expected_summary:
        raise ValueError("frozen HIT summary changed")
    if selection is None:
        raise ValueError("frozen HIT selection is missing")
    candidate = selection["bound_candidate"]["candidate"]
    if (
        selection["trials_used"] != 1
        or candidate["parameters"] !=
        RUNNER.candidate_request(materialization)["parameters"]
        or candidate["security"]["final_admission"] != "PASS"
        or candidate["security"]["log_qp"] != 242
    ):
        raise ValueError("frozen HIT candidate ledger changed")
    if selection["outcome"] == "SELECTED" and (
        audit is None
        or audit["retuning_performed"] is not False
        or audit["selected_candidate"] != candidate
    ):
        raise ValueError("frozen HIT locked replay changed")
    return summary


def freeze(
    run_root: Path,
    contract_path: Path,
    output_root: Path,
) -> None:
    run_root = absolute(run_root)
    contract_path = absolute(contract_path)
    output_root = absolute(output_root)
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite HIT evidence: {output_root}"
        )
    RUNNER.verify_output(contract_path, run_root)
    freezer_commit = require_clean_origin()
    run_manifest = load_json(run_root / "run_manifest.json")
    summary = load_json(run_root / "summary.json")
    with tempfile.TemporaryDirectory(
        prefix=output_root.name + ".",
        dir=output_root.parent,
    ) as temporary:
        root = Path(temporary)
        copy_run(run_root, root / "run")
        shutil.copy2(contract_path, root / "contract.json")
        shutil.copy2(REPO_ROOT / PROTOCOL, root / "protocol.md")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": "hit_external_adapter_replay_v1",
            "classification":
                "SOURCE_REPLAYED_PUBLIC_PARAMETER_SELECTOR",
            "freezer_commit": freezer_commit,
            "execution_commit": run_manifest["source_commit"],
            "run_manifest_sha256": sha256_path(
                root / "run/run_manifest.json"
            ),
            "summary_sha256": sha256_path(root / "run/summary.json"),
            "contract_sha256": sha256_path(root / "contract.json"),
            "execution_critical_source_digest": run_manifest[
                "execution_critical_source_digest"
            ],
            "binary_digests": {
                name: record["sha256"]
                for name, record in run_manifest["binaries"].items()
            },
            "selection": summary["selection"],
            "locked_audit": summary["locked_audit"],
            "claim_states": summary["claim_states"],
            "paper_claim_allowed": False,
            "block_reason": (
                "One seed-0 development candidate cannot establish general "
                "third-party autotuner integration or HIT candidate quality."
            ),
        }
        (root / "manifest.json").write_bytes(canonical_json(manifest))
        (root / "README.md").write_text(
            "# AWS HIT External Adapter Replay V1\n\n"
            "Development evidence for one source-replayed public HIT "
            "parameter-selector candidate on seed 0. Concrete Lattigo v2 "
            "Q/P primes were imported in order into Lattigo v6 and evaluated "
            "by the provider-neutral Security V2 and decision-integrity gates. "
            "The pack does not claim native HIT binary execution, general "
            "autotuner support, or parameter quality. "
            "`paper_claim_allowed=false`.\n",
            encoding="ascii",
        )
        write_checksums(root)
        verify(root)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root), output_root)


def verify(output_root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_root = absolute(output_root)
    verify_checksums(output_root)
    manifest = load_json(output_root / "manifest.json")
    if (
        manifest["schema_version"] != SCHEMA_VERSION
        or manifest["paper_claim_allowed"] is not False
    ):
        raise ValueError("HIT evidence claim gate changed")
    if manifest["contract_sha256"] != sha256_path(
        output_root / "contract.json"
    ):
        raise ValueError("HIT evidence contract binding changed")
    summary = validate_frozen_run(
        output_root / "run",
        output_root / "contract.json",
    )
    if (
        manifest["summary_sha256"] != sha256_path(
            output_root / "run/summary.json"
        )
        or manifest["claim_states"] != summary["claim_states"]
    ):
        raise ValueError("HIT evidence summary binding changed")
    return summary


def main() -> int:
    args = parse_args()
    if args.verify:
        summary = verify(args.output_root)
        print(
            "hit_external_adapter_evidence=VERIFIED "
            f"selection={summary['selection']['status']} "
            f"audit={summary['locked_audit']['status']} "
            "paper_claim_allowed=false"
        )
        return 0
    if args.run_root is None:
        raise ValueError("--run-root is required when freezing")
    freeze(args.run_root, args.contract, args.output_root)
    print(
        "hit_external_adapter_evidence=FROZEN "
        f"output={absolute(args.output_root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
