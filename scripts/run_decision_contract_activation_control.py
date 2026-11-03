#!/usr/bin/env python3
"""Run the predeclared finite-domain decision-contract activation control."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DIRECT_POLICY_DIGEST = (
    "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXECUTION_PATHS = (
    "go.mod",
    "go.sum",
    "cmd/flipguard-autotune",
    "cmd/flipguard-audit",
    "internal",
    "research/decisionactivation",
)
ARMS = (
    ("narrow_margin", 9101, "decision_contract"),
    ("narrow_margin", 9101, "graph_fixed_tolerance"),
    ("wide_margin", 9102, "decision_contract"),
    ("wide_margin", 9102, "graph_fixed_tolerance"),
)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


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


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def require_clean_origin() -> str:
    status = git("status", "--short")
    if status:
        raise ValueError(f"INTEGRITY_BLOCK: working tree is dirty:\n{status}")
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if not branch:
        raise ValueError("INTEGRITY_BLOCK: detached HEAD")
    origin = git("rev-parse", f"origin/{branch}")
    if head != origin:
        raise ValueError(
            f"INTEGRITY_BLOCK: HEAD {head} != origin/{branch} {origin}"
        )
    return head


def tracked_files(commit: str) -> list[str]:
    output = git(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        *EXECUTION_PATHS,
    )
    return [line for line in output.splitlines() if line]


def commit_source_digest(commit: str) -> str:
    files = tracked_files(commit)
    if not files:
        raise ValueError(f"no execution files at commit {commit}")
    digest = hashlib.sha256()
    for relative in files:
        content = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        digest.update(relative.encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def current_source_digest(reference_commit: str) -> str:
    files = tracked_files(reference_commit)
    current_files = [
        line
        for line in git("ls-files", "--", *EXECUTION_PATHS).splitlines()
        if line
    ]
    if files != current_files:
        raise ValueError(
            "INTEGRITY_BLOCK: execution-critical file set changed"
        )
    digest = hashlib.sha256()
    for relative in files:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise ValueError(
                f"INTEGRITY_BLOCK: missing execution source {relative}"
            )
        digest.update(relative.encode("ascii"))
        digest.update(b"\0")
        digest.update(
            hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii")
        )
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def validate_input_root(input_root: Path) -> dict[str, Any]:
    static_path = input_root / "static_analysis.json"
    static = load_json(static_path)
    expected = {
        "schema_version": (
            "flipguard_decision_contract_activation_control_v1"
        ),
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
        if static.get(key) != value:
            raise ValueError(
                f"INTEGRITY_BLOCK: static {key}={static.get(key)!r}; "
                f"expected {value!r}"
            )
    if len(static.get("regimes", [])) != 2:
        raise ValueError("INTEGRITY_BLOCK: expected two static regimes")
    model = input_root / "model.json"
    if sha256_path(model) != static["model"]["sha256"]:
        raise ValueError("INTEGRITY_BLOCK: model digest changed")
    for regime in static["regimes"]:
        name = regime["id"]
        expected_paths = {
            "validation": input_root / f"{name}_validation.csv",
            "locked_audit": input_root / f"{name}_locked_audit.csv",
            "split_manifest": (
                input_root / f"{name}_split_manifest.json"
            ),
        }
        for key, path in expected_paths.items():
            if sha256_path(path) != regime[key]["sha256"]:
                raise ValueError(
                    f"INTEGRITY_BLOCK: {name} {key} digest changed"
                )
        if regime["aggregate_sensitivity"] != 120.803:
            raise ValueError(
                f"INTEGRITY_BLOCK: {name} sensitivity changed"
            )
        if regime["graph_fixed"]["security"]["final_admission"] != "PASS":
            raise ValueError(
                f"INTEGRITY_BLOCK: {name} graph candidate is inadmissible"
            )
        if (
            regime["decision_contract"]["security"]["final_admission"]
            != "PASS"
        ):
            raise ValueError(
                f"INTEGRITY_BLOCK: {name} direct candidate is inadmissible"
            )
    return static


def save_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=path.name + ".",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_binary(package: str, output: Path) -> None:
    subprocess.run(
        [
            "go",
            "build",
            "-buildvcs=false",
            "-trimpath",
            "-o",
            str(output),
            package,
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def initialize_state(
    run_root: Path,
    input_root: Path,
    static: dict[str, Any],
    runner_commit: str,
    execution_digest: str,
) -> dict[str, Any]:
    if run_root.exists():
        raise FileExistsError(
            f"refusing to overwrite control run root: {run_root}"
        )
    (run_root / "bin").mkdir(parents=True)
    (run_root / "logs").mkdir()
    (run_root / "results").mkdir()
    autotune = run_root / "bin/flipguard-autotune"
    audit = run_root / "bin/flipguard-audit"
    build_binary("./cmd/flipguard-autotune", autotune)
    build_binary("./cmd/flipguard-audit", audit)
    state = {
        "schema_version": "flipguard_decision_contract_activation_run_v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "runner_commit": runner_commit,
        "execution_source_commit": static["source_commit"],
        "execution_critical_source_digest": execution_digest,
        "input_root": str(input_root.relative_to(REPO_ROOT)),
        "input_static_analysis_sha256": sha256_path(
            input_root / "static_analysis.json"
        ),
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "binaries": {
            "autotune": {
                "path": str(autotune.relative_to(REPO_ROOT)),
                "sha256": sha256_path(autotune),
            },
            "audit": {
                "path": str(audit.relative_to(REPO_ROOT)),
                "sha256": sha256_path(audit),
            },
        },
        "retry_limit": 3,
        "paper_claim_allowed": False,
        "arms": {
            f"{regime}__{arm}": {
                "regime": regime,
                "split_seed": seed,
                "arm": arm,
                "selection_status": "PENDING",
                "audit_status": "PENDING",
                "selection_attempts": 0,
                "audit_attempts": 0,
            }
            for regime, seed, arm in ARMS
        },
    }
    save_atomic(run_root / "state.json", state)
    return state


def validate_resume_state(
    run_root: Path,
    input_root: Path,
    static: dict[str, Any],
    runner_commit: str,
    execution_digest: str,
) -> dict[str, Any]:
    state = load_json(run_root / "state.json")
    checks = {
        "runner_commit": runner_commit,
        "execution_source_commit": static["source_commit"],
        "execution_critical_source_digest": execution_digest,
        "input_root": str(input_root.relative_to(REPO_ROOT)),
        "input_static_analysis_sha256": sha256_path(
            input_root / "static_analysis.json"
        ),
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
    }
    for key, expected in checks.items():
        if state.get(key) != expected:
            raise ValueError(
                f"INTEGRITY_BLOCK: resume {key} changed"
            )
    for name, record in state["binaries"].items():
        path = REPO_ROOT / record["path"]
        if sha256_path(path) != record["sha256"]:
            raise ValueError(
                f"INTEGRITY_BLOCK: {name} binary digest changed"
            )
    return state


def run_with_retries(
    command: list[str],
    log_prefix: Path,
    output_path: Path,
    prior_attempts: int,
) -> tuple[bool, int, str]:
    if output_path.exists():
        load_json(output_path)
        return True, prior_attempts, "RECOVERED_EXISTING_RESULT"
    attempts = prior_attempts
    last_detail = ""
    while attempts < 3:
        attempts += 1
        command_path = log_prefix.with_suffix(
            f".attempt{attempts}.command.txt"
        )
        log_path = log_prefix.with_suffix(
            f".attempt{attempts}.log"
        )
        command_path.write_text(
            "\n".join(command) + "\n",
            encoding="ascii",
        )
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_path.write_text(result.stdout, encoding="utf-8")
        if result.returncode == 0:
            if not output_path.is_file():
                raise ValueError(
                    "INTEGRITY_BLOCK: successful command has no result"
                )
            load_json(output_path)
            return True, attempts, "PASS"
        if output_path.exists():
            raise ValueError(
                "INTEGRITY_BLOCK: failed command left an output artifact"
            )
        last_detail = (
            f"returncode={result.returncode} log={log_path}"
        )
    return False, attempts, last_detail


def expected_static_candidate(
    static: dict[str, Any],
    regime: str,
    arm: str,
) -> dict[str, Any]:
    record = next(
        item for item in static["regimes"] if item["id"] == regime
    )
    key = (
        "decision_contract"
        if arm == "decision_contract"
        else "graph_fixed"
    )
    return record[key]


def validate_selection(
    selection: dict[str, Any],
    static: dict[str, Any],
    regime: str,
    arm: str,
) -> None:
    if selection["plan"]["direct_policy_digest"] != DIRECT_POLICY_DIGEST:
        raise ValueError("INTEGRITY_BLOCK: selection direct policy changed")
    if selection["plan"]["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError("INTEGRITY_BLOCK: selection security policy changed")
    first = selection["trials"][0]["candidate"]
    expected = expected_static_candidate(static, regime, arm)
    if first["id"] != expected["id"]:
        raise ValueError(
            f"INTEGRITY_BLOCK: {regime}/{arm} initial identity changed"
        )
    if first["parameters"] != expected["parameters"]:
        raise ValueError(
            f"INTEGRITY_BLOCK: {regime}/{arm} initial literal changed"
        )
    for trial in selection["trials"]:
        if trial["candidate"]["security"]["final_admission"] != "PASS":
            raise ValueError(
                f"INTEGRITY_BLOCK: {regime}/{arm} executed inadmissible candidate"
            )


def run_arm(
    run_root: Path,
    input_root: Path,
    static: dict[str, Any],
    state: dict[str, Any],
    regime: str,
    seed: int,
    arm: str,
) -> None:
    tag = f"{regime}__{arm}"
    record = state["arms"][tag]
    selection_path = run_root / "results" / f"{tag}__selection.json"
    audit_path = run_root / "results" / f"{tag}__audit.json"
    autotune = REPO_ROOT / state["binaries"]["autotune"]["path"]
    audit = REPO_ROOT / state["binaries"]["audit"]["path"]

    if record["selection_status"] == "PENDING":
        command = [
            str(autotune),
            "--model",
            str((input_root / "model.json").relative_to(REPO_ROOT)),
            "--validation",
            str(
                (
                    input_root / f"{regime}_validation.csv"
                ).relative_to(REPO_ROOT)
            ),
            "--split-id",
            f"split_seed_{seed}",
            "--margin-floor",
            "0.001",
            "--safety-factor",
            "0.5",
            "--key-repeats",
            "3",
            "--max-encrypted-trials",
            "4",
            "--synthesis-budget-mode",
            arm,
        ]
        if arm == "graph_fixed_tolerance":
            command += [
                "--fixed-output-error-budget",
                "0.001",
            ]
        command += [
            "--out",
            str(selection_path.relative_to(REPO_ROOT)),
        ]
        success, attempts, detail = run_with_retries(
            command,
            run_root / "logs" / f"{tag}__selection",
            selection_path,
            record["selection_attempts"],
        )
        record["selection_attempts"] = attempts
        if not success:
            record["selection_status"] = (
                "RECOVERABLE_IMPLEMENTATION_FAILURE"
            )
            record["selection_detail"] = detail
            record["audit_status"] = "SKIPPED_SELECTION_FAILURE"
            save_atomic(run_root / "state.json", state)
            return
        selection = load_json(selection_path)
        validate_selection(selection, static, regime, arm)
        record["selection_status"] = selection["outcome"]
        record["selection_sha256"] = sha256_path(selection_path)
        record["selection_detail"] = detail
        save_atomic(run_root / "state.json", state)

    selection = load_json(selection_path)
    if selection["outcome"] != "SELECTED":
        record["audit_status"] = "NOT_APPLICABLE_NO_SAFE"
        save_atomic(run_root / "state.json", state)
        return
    if record["audit_status"] != "PENDING":
        return

    command = [
        str(audit),
        "--selection",
        str(selection_path.relative_to(REPO_ROOT)),
        "--audit",
        str(
            (
                input_root / f"{regime}_locked_audit.csv"
            ).relative_to(REPO_ROOT)
        ),
        "--manifest",
        str(
            (
                input_root / f"{regime}_split_manifest.json"
            ).relative_to(REPO_ROOT)
        ),
        "--key-repeats",
        "3",
        "--out",
        str(audit_path.relative_to(REPO_ROOT)),
    ]
    success, attempts, detail = run_with_retries(
        command,
        run_root / "logs" / f"{tag}__audit",
        audit_path,
        record["audit_attempts"],
    )
    record["audit_attempts"] = attempts
    if not success:
        record["audit_status"] = "RECOVERABLE_IMPLEMENTATION_FAILURE"
        record["audit_detail"] = detail
        save_atomic(run_root / "state.json", state)
        return
    audit_result = load_json(audit_path)
    if audit_result["retuning_performed"] is not False:
        raise ValueError("INTEGRITY_BLOCK: locked audit retuned")
    if (
        audit_result["selected_candidate"]
        != selection["selected"]
    ):
        raise ValueError(
            "INTEGRITY_BLOCK: locked audit candidate identity changed"
        )
    record["audit_status"] = audit_result["outcome"]
    record["audit_sha256"] = sha256_path(audit_path)
    record["audit_detail"] = detail
    save_atomic(run_root / "state.json", state)


def build_summary(
    run_root: Path,
    static: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for regime, _, arm in ARMS:
        tag = f"{regime}__{arm}"
        record = state["arms"][tag]
        selection_path = run_root / "results" / f"{tag}__selection.json"
        if not selection_path.is_file():
            rows.append(
                {
                    "regime": regime,
                    "arm": arm,
                    "selection_outcome": record["selection_status"],
                    "audit_outcome": record["audit_status"],
                }
            )
            continue
        selection = load_json(selection_path)
        trials = selection["trials"]
        row: dict[str, Any] = {
            "regime": regime,
            "arm": arm,
            "selection_outcome": selection["outcome"],
            "trials": selection["trials_used"],
            "repairs": max(0, selection["trials_used"] - 1),
            "key_runs": selection["encrypted_key_runs"],
            "encrypted_sample_evaluations": (
                selection["encrypted_key_runs"] * 32
            ),
            "initial_candidate": trials[0]["candidate"]["id"],
            "initial_scale": trials[0]["candidate"]["parameters"][
                "log_default_scale"
            ],
            "initial_status": trials[0]["status"],
            "selected_candidate": (
                selection["selected"]["id"]
                if selection.get("selected")
                else ""
            ),
            "selected_scale": (
                selection["selected"]["parameters"][
                    "log_default_scale"
                ]
                if selection.get("selected")
                else None
            ),
            "validation_flips": sum(
                trial["decision_flips"] for trial in trials
            ),
            "validation_violations": sum(
                trial["error_violations"] for trial in trials
            ),
            "audit_outcome": record["audit_status"],
        }
        audit_path = run_root / "results" / f"{tag}__audit.json"
        if audit_path.is_file():
            audit = load_json(audit_path)
            row.update(
                {
                    "audit_status": audit["audit_trial"]["status"],
                    "audit_flips": audit["audit_trial"][
                        "decision_flips"
                    ],
                    "audit_violations": audit["audit_trial"][
                        "error_violations"
                    ],
                    "audit_key_runs": audit["audit_trial"][
                        "key_repeats_completed"
                    ],
                    "audit_encrypted_sample_evaluations": (
                        audit["audit_trial"]["key_repeats_completed"] * 32
                    ),
                    "audit_retuning": int(
                        audit["retuning_performed"]
                    ),
                }
            )
        rows.append(row)

    all_complete = all(
        row["selection_outcome"] in {"SELECTED", "NO_SAFE"}
        and row["audit_outcome"]
        in {
            "LOCKED_AUDIT_PASS",
            "LOCKED_AUDIT_FAIL",
            "NOT_APPLICABLE_NO_SAFE",
        }
        for row in rows
    )
    encrypted_rows = sum(
        1 for row in rows if int(row.get("key_runs", 0) or 0) > 0
    )
    failed_before_encryption = sum(
        1
        for row in rows
        if row.get("initial_status") == "FAILED"
        and int(row.get("key_runs", 0) or 0) == 0
    )
    if encrypted_rows == len(rows) and all_complete:
        encrypted_control_state = "SUPPORTED"
        stage_status = "PASS"
    elif encrypted_rows == 0 and failed_before_encryption == len(rows):
        encrypted_control_state = "BLOCKED"
        stage_status = "RECOVERABLE_IMPLEMENTATION_FAILURE"
    else:
        encrypted_control_state = "PARTIALLY_SUPPORTED"
        stage_status = "PARTIAL_SCIENTIFIC_RESULT"
    summary = {
        "schema_version": (
            "flipguard_decision_contract_activation_summary_v1"
        ),
        "execution_source_commit": state["execution_source_commit"],
        "runner_commit": state["runner_commit"],
        "execution_critical_source_digest": state[
            "execution_critical_source_digest"
        ],
        "direct_policy_digest": DIRECT_POLICY_DIGEST,
        "security_policy_digest": SECURITY_POLICY_DIGEST,
        "static_analysis_sha256": state[
            "input_static_analysis_sha256"
        ],
        "static_claim_state": static["static_claim_state"],
        "natural_data_decision_contract_synthesis_effect": "BLOCKED",
        "finite_domain_decision_contract_synthesis_effect":
            static["static_claim_state"],
        "finite_domain_encrypted_control": encrypted_control_state,
        "encrypted_rows": encrypted_rows,
        "failed_before_encryption": failed_before_encryption,
        "stage_status": stage_status,
        "policy_modifications": 0,
        "paper_claim_allowed": False,
        "rows": rows,
    }
    return summary


def write_summary_files(run_root: Path, summary: dict[str, Any]) -> None:
    (run_root / "summary.json").write_bytes(canonical_json(summary))
    fieldnames = sorted(
        {
            key
            for row in summary["rows"]
            for key in row
        }
    )
    with (run_root / "summary.csv").open(
        "w",
        newline="",
        encoding="ascii",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(summary["rows"])
    files = [
        path
        for path in run_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (run_root / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(run_root).as_posix()}\n"
            for path in sorted(files)
        ),
        encoding="ascii",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    input_root = (
        args.input_root
        if args.input_root.is_absolute()
        else REPO_ROOT / args.input_root
    ).resolve()
    run_root = (
        args.run_root
        if args.run_root.is_absolute()
        else REPO_ROOT / args.run_root
    ).resolve()
    runner_commit = require_clean_origin()
    static = validate_input_root(input_root)
    source_commit = static["source_commit"]
    frozen_digest = commit_source_digest(source_commit)
    current_digest = current_source_digest(source_commit)
    if frozen_digest != current_digest:
        raise ValueError(
            "INTEGRITY_BLOCK: execution-critical source changed since "
            f"{source_commit}: frozen={frozen_digest} current={current_digest}"
        )
    if args.resume:
        state = validate_resume_state(
            run_root,
            input_root,
            static,
            runner_commit,
            current_digest,
        )
    else:
        state = initialize_state(
            run_root,
            input_root,
            static,
            runner_commit,
            current_digest,
        )
    for regime, seed, arm in ARMS:
        run_arm(
            run_root,
            input_root,
            static,
            state,
            regime,
            seed,
            arm,
        )
    summary = build_summary(run_root, static, state)
    write_summary_files(run_root, summary)
    print(
        "decision_contract_activation_run="
        f"{summary['stage_status']} "
        "static_effect="
        f"{summary['finite_domain_decision_contract_synthesis_effect']} "
        "encrypted_control="
        f"{summary['finite_domain_encrypted_control']} "
        f"output={run_root}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        FileExistsError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(f"decision activation runner: {error}", file=sys.stderr)
        raise SystemExit(1)
