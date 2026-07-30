#!/usr/bin/env python3
"""Freeze and verify the decision-contract activation control evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DEFAULT = REPO_ROOT / (
    "results/thesis_grade_protocol/decision_contract_activation_v1/"
    "input_8bd51a3"
)
RUN_DEFAULT = REPO_ROOT / (
    "results/thesis_grade_protocol/decision_contract_activation_v1/"
    "run_8bd51a3"
)
OUTPUT_DEFAULT = REPO_ROOT / (
    "docs/evidence/decision_contract_activation_control_v1"
)
RECOVERY_DEFAULTS = (
    (
        REPO_ROOT
        / (
            "results/thesis_grade_protocol/"
            "decision_contract_activation_v1/run_bbc7856"
        ),
        "NON_NUMERIC_ROW_ID",
    ),
    (
        REPO_ROOT
        / (
            "results/thesis_grade_protocol/"
            "decision_contract_activation_v1/run_87f68f7"
        ),
        "INCOMPLETE_CANONICAL_CSV_SCHEMA",
    ),
)
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXECUTION_SOURCE_COMMIT = (
    "8bd51a353c26dd9ce848e4509bbadc7539ffc8ce"
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
    return "sha256:" + digest.hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_path(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label}={actual!r}; expected {expected!r}"
        )


def validate_input(input_root: Path) -> dict[str, Any]:
    static = load_json(input_root / "static_analysis.json")
    expected = {
        "schema_version": (
            "flipguard_decision_contract_activation_control_v1"
        ),
        "source_commit": EXECUTION_SOURCE_COMMIT,
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "primary_alpha": 0.5,
        "primary_margin_floor": 0.001,
        "fixed_tolerance": 0.001,
        "encrypted_executions": 0,
        "policy_modifications": 0,
        "static_claim_state": "SUPPORTED",
        "paper_claim_allowed": False,
    }
    for key, value in expected.items():
        require_equal(static.get(key), value, f"static {key}")
    require_equal(len(static["regimes"]), 2, "static regimes")
    require_equal(
        [row["aggregate_sensitivity"] for row in static["regimes"]],
        [120.803, 120.803],
        "static aggregate sensitivities",
    )
    require_equal(
        [
            row["graph_fixed"]["parameters"]["log_default_scale"]
            for row in static["regimes"]
        ],
        [20, 20],
        "graph-fixed initial scales",
    )
    require_equal(
        [
            row["decision_contract"]["parameters"][
                "log_default_scale"
            ]
            for row in static["regimes"]
        ],
        [21, 20],
        "decision-contract initial scales",
    )
    for regime in static["regimes"]:
        for arm in ("graph_fixed", "decision_contract"):
            require_equal(
                regime[arm]["security"]["final_admission"],
                "PASS",
                f"{regime['id']} {arm} security admission",
            )
        for key in ("validation", "locked_audit", "split_manifest"):
            path = input_root / Path(regime[key]["path"]).name
            require_equal(
                sha256_path(path),
                regime[key]["sha256"],
                f"{regime['id']} {key} digest",
            )
    require_equal(
        sha256_path(input_root / "model.json"),
        static["model"]["sha256"],
        "model digest",
    )
    return static


def validate_success_summary(
    summary: dict[str, Any],
) -> dict[str, int]:
    expected = {
        "execution_source_commit": EXECUTION_SOURCE_COMMIT,
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "static_claim_state": "SUPPORTED",
        "natural_data_decision_contract_synthesis_effect": "BLOCKED",
        "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
        "finite_domain_encrypted_control": "SUPPORTED",
        "encrypted_rows": 4,
        "failed_before_encryption": 0,
        "stage_status": "PASS",
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    for key, value in expected.items():
        require_equal(summary.get(key), value, f"summary {key}")
    rows = summary.get("rows", [])
    require_equal(len(rows), 4, "successful arm rows")
    by_key = {(row["regime"], row["arm"]): row for row in rows}
    expected_scales = {
        ("narrow_margin", "decision_contract"): (21, 33, 4),
        ("narrow_margin", "graph_fixed_tolerance"): (20, 32, 4),
        ("wide_margin", "decision_contract"): (20, 28, 3),
        ("wide_margin", "graph_fixed_tolerance"): (20, 28, 3),
    }
    for key, (initial_scale, selected_scale, trials) in (
        expected_scales.items()
    ):
        row = by_key[key]
        require_equal(row["selection_outcome"], "SELECTED", f"{key} outcome")
        require_equal(row["initial_scale"], initial_scale, f"{key} initial")
        require_equal(row["selected_scale"], selected_scale, f"{key} selected")
        require_equal(row["trials"], trials, f"{key} trials")
        require_equal(
            row["audit_outcome"],
            "LOCKED_AUDIT_PASS",
            f"{key} audit outcome",
        )
        require_equal(row["audit_status"], "SAFE", f"{key} audit status")
        require_equal(row["audit_flips"], 0, f"{key} audit flips")
        require_equal(
            row["audit_violations"],
            0,
            f"{key} audit violations",
        )
        require_equal(row["audit_retuning"], 0, f"{key} audit retuning")
    accounting = {
        "arms": 4,
        "selection_trials": sum(row["trials"] for row in rows),
        "selection_repairs": sum(row["repairs"] for row in rows),
        "selection_key_runs": sum(row["key_runs"] for row in rows),
        "selection_encrypted_sample_evaluations": sum(
            row["encrypted_sample_evaluations"] for row in rows
        ),
        "audit_key_runs": sum(row["audit_key_runs"] for row in rows),
        "audit_encrypted_sample_evaluations": sum(
            row["audit_encrypted_sample_evaluations"]
            for row in rows
        ),
        "locked_audit_pass": sum(
            row["audit_outcome"] == "LOCKED_AUDIT_PASS"
            for row in rows
        ),
    }
    require_equal(
        accounting,
        {
            "arms": 4,
            "selection_trials": 14,
            "selection_repairs": 10,
            "selection_key_runs": 42,
            "selection_encrypted_sample_evaluations": 1344,
            "audit_key_runs": 12,
            "audit_encrypted_sample_evaluations": 384,
            "locked_audit_pass": 4,
        },
        "successful accounting",
    )
    return accounting


def validate_success_run(
    run_root: Path,
    require_binaries: bool,
) -> tuple[dict[str, Any], dict[str, int]]:
    summary = load_json(run_root / "summary.json")
    accounting = validate_success_summary(summary)
    state = load_json(run_root / "state.json")
    require_equal(
        state["execution_source_commit"],
        EXECUTION_SOURCE_COMMIT,
        "run execution source commit",
    )
    require_equal(
        state["direct_policy_digest"],
        DIRECT_POLICY_DIGEST,
        "run direct policy",
    )
    require_equal(
        state["security_policy_digest"],
        SECURITY_POLICY_DIGEST,
        "run security policy",
    )
    if require_binaries:
        for name, record in state["binaries"].items():
            path = REPO_ROOT / record["path"]
            require_equal(
                sha256_path(path),
                record["sha256"],
                f"{name} binary digest",
            )

    for row in summary["rows"]:
        tag = f"{row['regime']}__{row['arm']}"
        selection = load_json(
            run_root / "results" / f"{tag}__selection.json"
        )
        audit = load_json(
            run_root / "results" / f"{tag}__audit.json"
        )
        require_equal(
            selection["outcome"],
            "SELECTED",
            f"{tag} raw selection",
        )
        require_equal(
            selection["trials"][-1]["status"],
            "SAFE",
            f"{tag} final validation status",
        )
        require_equal(
            selection["trials"][-1]["decision_flips"],
            0,
            f"{tag} final validation flips",
        )
        require_equal(
            selection["trials"][-1]["error_violations"],
            0,
            f"{tag} final validation violations",
        )
        for trial in selection["trials"]:
            require_equal(
                trial["candidate"]["security"]["final_admission"],
                "PASS",
                f"{tag} trial security",
            )
        require_equal(
            audit["selected_candidate"],
            selection["selected"],
            f"{tag} audit candidate identity",
        )
        require_equal(
            audit["retuning_performed"],
            False,
            f"{tag} audit retuning",
        )
    return summary, accounting


def validate_recovery(
    recovery_root: Path,
    reason_code: str,
) -> dict[str, Any]:
    expected_fragment = {
        "NON_NUMERIC_ROW_ID": 'parse int "',
        "INCOMPLETE_CANONICAL_CSV_SCHEMA": "missing field label",
    }[reason_code]
    selection_paths = sorted(
        (recovery_root / "results").glob("*__selection.json")
    )
    require_equal(len(selection_paths), 4, f"{reason_code} selections")
    for path in selection_paths:
        selection = load_json(path)
        require_equal(selection["outcome"], "NO_SAFE", f"{path} outcome")
        require_equal(
            selection["encrypted_key_runs"],
            0,
            f"{path} encrypted key runs",
        )
        require_equal(
            selection["trials"][0]["status"],
            "FAILED",
            f"{path} first status",
        )
        if expected_fragment not in selection["trials"][0]["failure"]:
            raise ValueError(
                f"{path}: recovery reason does not match {reason_code}"
            )
    return {
        "classification": "SUPERSEDED_IMPLEMENTATION_RECOVERY",
        "reason_code": reason_code,
        "selection_attempts": 4,
        "encrypted_key_runs": 0,
        "encrypted_rerun_justified": True,
    }


def copy_run_without_binaries(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for name in ("state.json", "summary.json", "summary.csv"):
        path = source / name
        if path.is_file():
            shutil.copy2(path, destination / name)
    for directory in ("logs", "results"):
        source_directory = source / directory
        if source_directory.is_dir():
            shutil.copytree(
                source_directory,
                destination / directory,
            )


def write_checksums(output: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output).as_posix()}\n"
        )
    (output / "SHA256SUMS").write_text(
        "".join(lines),
        encoding="ascii",
    )


def freeze(
    input_root: Path,
    run_root: Path,
    recoveries: tuple[tuple[Path, str], ...],
    output: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite activation evidence: {output}"
        )
    static = validate_input(input_root)
    summary, accounting = validate_success_run(
        run_root,
        require_binaries=True,
    )
    recovery_records = [
        {
            **validate_recovery(path, reason),
            "source_path": path.relative_to(REPO_ROOT).as_posix(),
            "source_tree_sha256": tree_digest(path),
        }
        for path, reason in recoveries
    ]

    (output / "raw").mkdir(parents=True)
    shutil.copytree(input_root, output / "raw/input")
    copy_run_without_binaries(run_root, output / "raw/run")
    for index, (path, _) in enumerate(recoveries, start=1):
        copy_run_without_binaries(
            path,
            output / "recovery" / f"attempt_{index}",
        )

    result_summary = {
        "schema_version": (
            "flipguard_decision_contract_activation_evidence_summary_v1"
        ),
        "status": "SUPPORTED",
        "natural_data_decision_contract_synthesis_effect": "BLOCKED",
        "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
        "finite_domain_encrypted_control": "SUPPORTED",
        "accounting": accounting,
        "initial_scales": {
            "narrow_decision_contract": 21,
            "narrow_graph_fixed": 20,
            "wide_decision_contract": 20,
            "wide_graph_fixed": 20,
        },
        "selected_scales": {
            "narrow_decision_contract": 33,
            "narrow_graph_fixed": 32,
            "wide_decision_contract": 28,
            "wide_graph_fixed": 28,
        },
        "locked_audit_flips": 0,
        "locked_audit_violations": 0,
        "locked_audit_retuning": 0,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
    }
    (output / "summary.json").write_bytes(
        canonical_json(result_summary)
    )
    manifest = {
        "schema_version": (
            "flipguard_decision_contract_activation_evidence_v1"
        ),
        "evidence_id": "decision_contract_activation_control_v1",
        "classification": "FINITE_DOMAIN_DEVELOPMENT_CONTROL",
        "freezer_commit": freezer_commit,
        "execution_source_commit": EXECUTION_SOURCE_COMMIT,
        "runner_commit": summary["runner_commit"],
        "execution_critical_source_digest": summary[
            "execution_critical_source_digest"
        ],
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "input_source_tree_sha256": tree_digest(input_root),
        "run_source_tree_sha256": tree_digest(run_root),
        "binary_sha256": load_json(run_root / "state.json")["binaries"],
        "claims": {
            "natural_data_decision_contract_synthesis_effect": "BLOCKED",
            "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
            "finite_domain_encrypted_control": "SUPPORTED",
            "paper_claim_allowed": False,
        },
        "accounting": accounting,
        "recoveries": recovery_records,
        "static_analysis_sha256": sha256_path(
            input_root / "static_analysis.json"
        ),
        "raw_summary_sha256": sha256_path(
            run_root / "summary.json"
        ),
        "evidence_summary_sha256": sha256_path(
            output / "summary.json"
        ),
        "frozen_evidence_modified": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# Decision-Contract Activation Control V1

This finite-domain development control holds graph, interval calibration,
aggregate sensitivity, and frozen policies constant while changing the
minimum certifiable decision margin.

- Static synthesis effect: `SUPPORTED`.
- Encrypted control: `SUPPORTED`.
- Natural-data synthesis effect: `BLOCKED`.
- Selection: 4/4 SELECTED.
- No-retuning locked audit: 4/4 PASS.
- Audit flips/violations: 0/0.

Two pre-encryption CSV-schema failures are preserved under `recovery/` as
superseded implementation-recovery evidence. They completed zero key runs and
did not inform a policy change.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)
    del static


def verify_checksums(output: Path) -> None:
    lines = (output / "SHA256SUMS").read_text(
        encoding="ascii"
    ).splitlines()
    expected_paths: set[str] = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        path = output / relative
        if not path.is_file():
            raise ValueError(f"missing frozen file: {relative}")
        require_equal(
            sha256_path(path),
            f"sha256:{digest}",
            f"checksum {relative}",
        )
        expected_paths.add(relative)
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(actual_paths, expected_paths, "frozen file set")


def verify(output: Path) -> None:
    verify_checksums(output)
    validate_input(output / "raw/input")
    _, accounting = validate_success_run(
        output / "raw/run",
        require_binaries=False,
    )
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["accounting"],
        accounting,
        "manifest accounting",
    )
    require_equal(
        manifest["claims"],
        {
            "natural_data_decision_contract_synthesis_effect": "BLOCKED",
            "finite_domain_decision_contract_synthesis_effect": "SUPPORTED",
            "finite_domain_encrypted_control": "SUPPORTED",
            "paper_claim_allowed": False,
        },
        "manifest claims",
    )
    for index, record in enumerate(
        manifest["recoveries"],
        start=1,
    ):
        validate_recovery(
            output / "recovery" / f"attempt_{index}",
            record["reason_code"],
        )
    summary = load_json(output / "summary.json")
    require_equal(summary["paper_claim_allowed"], False, "paper gate")
    require_equal(
        sha256_path(output / "summary.json"),
        manifest["evidence_summary_sha256"],
        "evidence summary binding",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--run-root", type=Path, default=RUN_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--freezer-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    input_root = (
        args.input_root
        if args.input_root.is_absolute()
        else REPO_ROOT / args.input_root
    )
    run_root = (
        args.run_root
        if args.run_root.is_absolute()
        else REPO_ROOT / args.run_root
    )
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        verify(output)
        print(
            "decision_contract_activation_evidence_v1=VERIFIED "
            "arms=4 audits=4 recoveries=2 paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(
        input_root,
        run_root,
        RECOVERY_DEFAULTS,
        output,
        args.freezer_commit,
    )
    print(
        "decision_contract_activation_evidence_v1=FROZEN "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
