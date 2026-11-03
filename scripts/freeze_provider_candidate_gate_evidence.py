#!/usr/bin/env python3
"""Freeze and verify provider-candidate interoperability evidence."""

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
DEFAULT_SUCCESSFUL_ROOT = Path(
    "results/thesis_grade_protocol/"
    "provider_candidate_gate_v1/run_707441b"
)
DEFAULT_FAILED_ROOT = Path(
    "results/thesis_grade_protocol/"
    "provider_candidate_gate_v1/run_f84ecff"
)
DEFAULT_CONTRACT = Path(
    "experiments/provider_candidate_gate_v1/contract.json"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/provider_candidate_gate_interoperability_v1"
)
SCHEMA_VERSION = (
    "flipguard_provider_candidate_gate_interoperability_evidence_v1"
)
SUCCESSFUL_EXECUTION_COMMIT = (
    "707441b724e48a7460ea264948562c9ad74d40e5"
)
FAILED_EXECUTION_COMMIT = (
    "f84ecff1ea98a505f5a895f5c352fcbc9101f7a8"
)
SUPERSEDED_CONTRACT_DIGEST = (
    "sha256:"
    "429dcf909626a4eaaa36e730b134b9d3be9ef71132de0f708e96897a888dd3a7"
)
CORRECTED_CONTRACT_DIGEST = (
    "sha256:"
    "7a16a835aad531e3517b212414236ac82f23958707db5d76e19dbebabc2c6482"
)
EXPECTED_ARMS = (
    "manual_literal",
    "bounded_catalog_literal",
    "external_autotuner_format_fixture",
    "direct_synthesizer_literal",
)

RUNNER_PATH = (
    REPO_ROOT / "scripts/run_provider_candidate_gate_interoperability.py"
)
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "run_provider_candidate_gate_for_freezer",
    RUNNER_PATH,
)
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
assert RUNNER_SPEC.loader is not None
RUNNER_SPEC.loader.exec_module(RUNNER)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--successful-root",
        type=Path,
        default=DEFAULT_SUCCESSFUL_ROOT,
    )
    parser.add_argument(
        "--failed-root",
        type=Path,
        default=DEFAULT_FAILED_ROOT,
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError(
            "provider evidence freezer requires a clean tree:\n" + status
        )
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(
            f"provider evidence freezer HEAD {head} != origin {origin}"
        )
    return head


def validate_successful_run(
    root: Path = DEFAULT_SUCCESSFUL_ROOT,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    root = absolute(root)
    contract_path = absolute(contract_path)
    summary = RUNNER.verify_output(contract_path, root)
    manifest = load_json(root / "run_manifest.json")
    state = load_json(root / "state.json")
    require(
        manifest["source_commit"] == SUCCESSFUL_EXECUTION_COMMIT and
        manifest["origin_commit"] == SUCCESSFUL_EXECUTION_COMMIT and
        manifest["contract_sha256"] == CORRECTED_CONTRACT_DIGEST and
        manifest["working_tree_clean"] is True and
        manifest["paper_claim_allowed"] is False,
        "successful provider run provenance changed",
    )
    require(
        state["stage"] == "PASS" and
        summary["status"] == "PASS" and
        summary["counts"] == {
            "arms": 4,
            "audit_key_runs": 12,
            "candidate_trials": 4,
            "implementation_failures": 0,
            "locked_audit_fail": 0,
            "locked_audit_pass": 4,
            "no_safe": 0,
            "retuning": 0,
            "scientific_negatives": 0,
            "selected": 4,
            "selection_key_runs": 12,
        },
        "successful provider run accounting changed",
    )
    require(
        tuple(row["arm_id"] for row in summary["arms"]) ==
        EXPECTED_ARMS,
        "successful provider arm order changed",
    )
    for row in summary["arms"]:
        require(
            row["selection_state"] == "SELECTED" and
            row["selection_status"] == "SAFE" and
            row["audit_state"] == "LOCKED_AUDIT_PASS" and
            row["audit_status"] == "SAFE" and
            row["selection_flips"] == 0 and
            row["selection_violations"] == 0 and
            row["audit_flips"] == 0 and
            row["audit_violations"] == 0 and
            row["retuning"] == 0 and
            row["selection_audit_candidate_identical"] is True,
            f"{row['arm_id']}: successful result changed",
        )
    return {
        "manifest": manifest,
        "state": state,
        "summary": summary,
    }


def validate_failed_run(
    root: Path = DEFAULT_FAILED_ROOT,
) -> dict[str, Any]:
    root = absolute(root)
    manifest = load_json(root / "run_manifest.json")
    state = load_json(root / "state.json")
    summary = load_json(root / "summary.json")
    incident = load_json(root / "incident_record.json")
    require(
        manifest["source_commit"] == FAILED_EXECUTION_COMMIT and
        manifest["origin_commit"] == FAILED_EXECUTION_COMMIT and
        manifest["contract_sha256"] == SUPERSEDED_CONTRACT_DIGEST and
        sha256_path(root / "contract_snapshot.json") ==
        SUPERSEDED_CONTRACT_DIGEST,
        "failed provider run provenance changed",
    )
    require(
        summary["counts"]["arms"] == 4 and
        summary["counts"]["selected"] == 4 and
        summary["counts"]["locked_audit_pass"] == 0 and
        summary["counts"]["implementation_failures"] == 4 and
        incident["reason_code"] ==
        "SELECTION_SPLIT_ID_MANIFEST_MISMATCH" and
        incident["locked_audit_results"][
            "encrypted_executions_started"
        ] == 0 and
        incident["disposition"] ==
        "HISTORICAL_FAILED_RUN_PRESERVED" and
        incident["paper_claim_allowed"] is False,
        "failed provider incident accounting changed",
    )
    for arm_id in EXPECTED_ARMS:
        selection = load_json(root / "selection" / f"{arm_id}.json")
        log = (
            root / "logs" / f"{arm_id}_audit.log"
        ).read_text(encoding="ascii")
        require(
            selection["outcome"] == "SELECTED" and
            selection["trial"]["status"] == "SAFE" and
            "split manifest seed implies \"split_seed_0\"" in log and
            "selection uses \"provider_gate_v1/split_seed_0\"" in log and
            not (root / "audit" / f"{arm_id}.json").exists(),
            f"{arm_id}: failed incident detail changed",
        )
    return {
        "manifest": manifest,
        "state": state,
        "summary": summary,
        "incident": incident,
    }


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_run_files(source_root: Path, destination_root: Path) -> None:
    names = (
        "run_manifest.json",
        "state.json",
        "stage_ledger.json",
        "summary.json",
        "contract_snapshot.json",
    )
    for name in names:
        copy_file(source_root / name, destination_root / name)
    for directory in ("selection", "audit", "logs"):
        source = source_root / directory
        if source.is_dir():
            shutil.copytree(source, destination_root / directory)


def write_sha256sums(root: Path) -> None:
    path = root / "SHA256SUMS"
    files = sorted(
        item for item in root.rglob("*")
        if item.is_file() and item != path
    )
    lines = [
        f"{sha256_path(item).removeprefix('sha256:')}  "
        f"{item.relative_to(root).as_posix()}"
        for item in files
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def verify_sha256sums(root: Path) -> None:
    for line in (
        root / "SHA256SUMS"
    ).read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        path = root / relative
        require(
            sha256_path(path) == "sha256:" + digest,
            f"provider evidence file changed: {relative}",
        )


def verify_pack(root: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    root = absolute(root)
    verify_sha256sums(root)
    manifest = load_json(root / "manifest.json")
    summary = load_json(root / "successful/summary.json")
    incident = load_json(root / "failed_v1/incident_record.json")
    require(
        manifest["schema_version"] == SCHEMA_VERSION and
        manifest["successful_execution_commit"] ==
        SUCCESSFUL_EXECUTION_COMMIT and
        manifest["failed_execution_commit"] ==
        FAILED_EXECUTION_COMMIT and
        manifest["corrected_contract_sha256"] ==
        CORRECTED_CONTRACT_DIGEST and
        manifest["superseded_contract_sha256"] ==
        SUPERSEDED_CONTRACT_DIGEST and
        manifest["counts"] == summary["counts"] and
        manifest["paper_claim_allowed"] is False,
        "provider evidence manifest changed",
    )
    require(
        incident["reason_code"] ==
        "SELECTION_SPLIT_ID_MANIFEST_MISMATCH" and
        incident["locked_audit_results"][
            "encrypted_executions_started"
        ] == 0,
        "provider evidence incident changed",
    )
    for row in summary["arms"]:
        arm_id = row["arm_id"]
        selection = load_json(
            root / "successful/selection" / f"{arm_id}.json"
        )
        audit = load_json(
            root / "successful/audit" / f"{arm_id}.json"
        )
        require(
            selection["outcome"] == "SELECTED" and
            selection["trial"]["status"] == "SAFE" and
            audit["outcome"] == "LOCKED_AUDIT_PASS" and
            audit["audit_trial"]["status"] == "SAFE" and
            audit["retuning_performed"] is False and
            audit["selected_candidate"]["id"] ==
            selection["bound_candidate"]["candidate"]["id"],
            f"{arm_id}: frozen provider evidence changed",
        )
    return manifest


def freeze(
    successful_root: Path,
    failed_root: Path,
    contract_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    successful_root = absolute(successful_root)
    failed_root = absolute(failed_root)
    contract_path = absolute(contract_path)
    output_root = absolute(output_root)
    successful = validate_successful_run(
        successful_root,
        contract_path,
    )
    failed = validate_failed_run(failed_root)
    freezer_commit = require_clean_origin()
    if output_root.exists():
        raise FileExistsError(
            f"refusing to overwrite provider evidence pack: {output_root}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=output_root.name + ".",
        dir=output_root.parent,
    ) as temporary:
        root = Path(temporary)
        copy_run_files(successful_root, root / "successful")
        copy_run_files(failed_root, root / "failed_v1")
        copy_file(
            failed_root / "incident_record.json",
            root / "failed_v1/incident_record.json",
        )
        copy_file(contract_path, root / "inputs/contract_v2.json")
        shutil.copytree(
            REPO_ROOT /
            "experiments/provider_candidate_gate_v1/candidates",
            root / "inputs/candidates",
        )
        copy_file(
            REPO_ROOT /
            "docs/research/"
            "step_7g1_provider_agnostic_candidate_gate_protocol.md",
            root / "protocol.md",
        )

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "freezer_commit": freezer_commit,
            "successful_execution_commit":
                SUCCESSFUL_EXECUTION_COMMIT,
            "failed_execution_commit": FAILED_EXECUTION_COMMIT,
            "successful_run_manifest_sha256": sha256_path(
                successful_root / "run_manifest.json"
            ),
            "successful_summary_sha256": sha256_path(
                successful_root / "summary.json"
            ),
            "failed_run_manifest_sha256": sha256_path(
                failed_root / "run_manifest.json"
            ),
            "failed_incident_sha256": sha256_path(
                failed_root / "incident_record.json"
            ),
            "corrected_contract_sha256":
                CORRECTED_CONTRACT_DIGEST,
            "superseded_contract_sha256":
                SUPERSEDED_CONTRACT_DIGEST,
            "security_policy_digest": successful["manifest"][
                "security_policy_digest"
            ],
            "direct_policy_digest": successful["manifest"][
                "direct_policy_digest"
            ],
            "execution_critical_source_digest": successful[
                "manifest"
            ]["execution_critical_source_digest"],
            "binary_digests": {
                name: record["sha256"]
                for name, record in successful["manifest"][
                    "binaries"
                ].items()
            },
            "counts": successful["summary"]["counts"],
            "claim_states": successful["summary"][
                "claim_states"
            ],
            "failed_run_disposition": failed["incident"][
                "disposition"
            ],
            "paper_claim_allowed": False,
            "block_reason": successful["summary"]["block_reason"],
        }
        (root / "manifest.json").write_bytes(canonical_json(manifest))
        (root / "README.md").write_text(
            "# Provider Candidate Gate Interoperability V1\n\n"
            "Development evidence for one seed-0 iris/linear workload. "
            "Four provider classes each supplied one exact literal; all "
            "four validation selections and locked audits were SAFE with "
            "zero retuning. The pack also preserves the superseded V1 "
            "split-ID mismatch and its fail-closed audit logs. The "
            "external arm is a schema fixture, not an evaluation of a "
            "third-party autotuner. `paper_claim_allowed=false`.\n",
            encoding="ascii",
        )
        write_sha256sums(root)
        verify_pack(root)
        shutil.move(str(root), output_root)
    return verify_pack(output_root)


def main() -> int:
    args = parse_args()
    if args.verify:
        manifest = verify_pack(args.output_root)
        print(
            "provider_candidate_gate_evidence=VERIFIED "
            f"selected={manifest['counts']['selected']} "
            f"audit_pass={manifest['counts']['locked_audit_pass']} "
            f"incident={manifest['failed_run_disposition']} "
            "paper_claim_allowed=false"
        )
        return 0
    manifest = freeze(
        args.successful_root,
        args.failed_root,
        args.contract,
        args.output_root,
    )
    print(
        "provider_candidate_gate_evidence=FROZEN "
        f"selected={manifest['counts']['selected']} "
        f"audit_pass={manifest['counts']['locked_audit_pass']} "
        "paper_claim_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
