#!/usr/bin/env python3
"""Freeze and verify independent-machine replay evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT_DEFAULT = (
    REPO_ROOT
    / "results/thesis_grade_protocol/independent_machine_replay_v1"
)
COMPLETE_COLLECTION_NAME = "ci_run_30535993621"
RECOVERY_COLLECTION_NAMES = (
    "ci_run_30535123758_recovery",
    "ci_run_30535672062_recovery",
)
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/independent_machine_replay_v1"
)
VERIFY_PATH = REPO_ROOT / "scripts/verify_independent_machine_replay.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_independent_machine_replay_for_freezer",
    VERIFY_PATH,
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
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
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def verify_checksum_index(root: Path) -> None:
    index = root / "SHA256SUMS"
    if not index.is_file():
        raise ValueError(f"{root}: missing SHA256SUMS")
    indexed = set()
    for line in index.read_text(encoding="ascii").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise ValueError(f"{root}: malformed checksum line")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"{root}: missing checksum target {relative}")
        require_equal(
            sha256_path(path),
            f"sha256:{digest}",
            f"{root}:{relative}",
        )
        indexed.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(actual, indexed, f"{root}: checksum coverage")


def verify_collection(
    root: Path,
    *,
    complete: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_checksum_index(root)
    manifest = load_json(root / "collection_manifest.json")
    require_equal(
        manifest["schema_version"],
        "flipguard_independent_machine_replay_ci_collection_v1",
        "collection schema",
    )
    replay = load_json(root / "artifact/replay.json")
    if complete:
        require_equal(
            manifest["collection_classification"],
            "COMPLETE_INDEPENDENT_REPLAY",
            "complete classification",
        )
        require_equal(
            manifest["workflow_conclusion"],
            "success",
            "complete workflow conclusion",
        )
        require_equal(replay["status"], "PASS", "complete replay status")
        VERIFY.verify(root / "artifact", manifest["head_sha"])
    else:
        require_equal(
            manifest["collection_classification"],
            "INDEPENDENT_REPLAY_RECOVERY",
            "recovery classification",
        )
        require_equal(
            manifest["workflow_conclusion"],
            "failure",
            "recovery workflow conclusion",
        )
        require_equal(replay["status"], "FAIL", "recovery replay status")
    return manifest, replay


def failed_checks(replay: dict[str, Any]) -> list[str]:
    return [
        row["name"]
        for row in replay["checks"]
        if row["status"] != "PASS"
    ]


def derive_summary(
    complete: dict[str, Any],
    recoveries: list[dict[str, Any]],
) -> dict[str, Any]:
    require_equal(
        len(complete["checks"]),
        len(VERIFY.EXPECTED_CHECKS),
        "complete check count",
    )
    require_equal(failed_checks(complete), [], "complete failed checks")
    require_equal(
        [failed_checks(replay) for replay in recoveries],
        [["go_test", "python_unittest"], ["go_test"]],
        "recovery failed checks",
    )
    scope = complete["source_replay_scope"]
    require_equal(
        scope["status"],
        "NOT_EVALUATED_ON_CLEAN_CLONE",
        "external source replay status",
    )
    require_equal(len(scope["missing"]), 8, "missing external inputs")
    require_equal(
        len(scope["portable_go_test_exclusions"]),
        5,
        "portable Go exclusions",
    )
    return {
        "schema_version": (
            "flipguard_independent_machine_replay_evidence_summary_v1"
        ),
        "status": "SUPPORTED_WITH_DECLARED_EXTERNAL_INPUT_BOUNDARY",
        "portable_replay": "SUPPORTED",
        "committed_checkpoint_replay": "SUPPORTED",
        "external_source_replay": "NOT_EVALUATED_ON_CLEAN_CLONE",
        "checks_passed": len(complete["checks"]),
        "checks_failed": 0,
        "missing_external_inputs": len(scope["missing"]),
        "portable_go_test_exclusions": len(
            scope["portable_go_test_exclusions"]
        ),
        "recovery_runs": len(recoveries),
        "recovery_failed_checks": [
            failed_checks(replay) for replay in recoveries
        ],
        "encrypted_candidate_trials": 0,
        "encrypted_key_runs": 0,
        "paper_claim_allowed": False,
    }


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


def build(
    output: Path,
    complete_root: Path,
    recovery_roots: list[Path],
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite replay evidence: {output}"
        )
    complete_manifest, complete = verify_collection(
        complete_root,
        complete=True,
    )
    recovery_pairs = [
        verify_collection(root, complete=False)
        for root in recovery_roots
    ]
    recovery_manifests = [pair[0] for pair in recovery_pairs]
    recoveries = [pair[1] for pair in recovery_pairs]
    first_python_error = (
        recovery_roots[0]
        / "artifact/python_unittest.stderr.txt"
    ).read_text(encoding="utf-8")
    first_go_output = (
        recovery_roots[0] / "artifact/go_test.stdout.txt"
    ).read_text(encoding="utf-8")
    if (
        "No module named 'PIL'" not in first_python_error
        or "mnist_784.arff.gz" not in first_go_output
    ):
        raise ValueError("first replay recovery reason is not preserved")
    second_go_output = (
        recovery_roots[1] / "artifact/go_test.stdout.txt"
    ).read_text(encoding="utf-8")
    if (
        "expected missing model error, got --data is required"
        not in second_go_output
    ):
        raise ValueError("second replay recovery reason is not preserved")

    output.mkdir(parents=True)
    shutil.copytree(complete_root, output / "raw/complete")
    for index, root in enumerate(recovery_roots, start=1):
        shutil.copytree(root, output / f"raw/recovery_{index}")
    summary = derive_summary(complete, recoveries)
    (output / "summary.json").write_bytes(canonical_json(summary))
    manifest = {
        "schema_version": (
            "flipguard_independent_machine_replay_evidence_v1"
        ),
        "evidence_id": "independent_machine_replay_v1",
        "classification": "POST_CONFIRMATORY_ARTIFACT_ASSURANCE",
        "freezer_commit": freezer_commit,
        "execution_source_commit": complete_manifest["head_sha"],
        "workflow_run_id": complete_manifest["run_id"],
        "workflow_run_url": complete_manifest["run_url"],
        "workflow_conclusion": complete_manifest[
            "workflow_conclusion"
        ],
        "replay_sha256": sha256_path(
            complete_root / "artifact/replay.json"
        ),
        "source_replay_scope": complete["source_replay_scope"],
        "policies": complete["policies"],
        "policy_retuning": 0,
        "encrypted_execution": complete["encrypted_execution"],
        "recovery_runs": [
            {
                "run_id": record["run_id"],
                "head_sha": record["head_sha"],
                "workflow_conclusion": record["workflow_conclusion"],
                "failed_checks": failed_checks(replay),
                "reason_code": reason,
            }
            for record, replay, reason in zip(
                recovery_manifests,
                recoveries,
                (
                    "NON_HERMETIC_EXTERNAL_SOURCE_TEST_BOUNDARY",
                    "NONDETERMINISTIC_REQUIRED_FLAG_ASSERTION",
                ),
                strict=True,
            )
        ],
        "summary_sha256": sha256_path(output / "summary.json"),
        "status": summary["status"],
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# Independent Machine Replay Evidence V1

This pack preserves two fail-closed clean-runner recoveries and one successful
portable replay. The successful run verifies Go/Python checks, shell syntax,
clean-tree invariants, and committed completion checkpoints V1/V2.

Raw dataset and ignored execution-ledger replay is explicitly
NOT_EVALUATED_ON_CLEAN_CLONE. Five Go tests are excluded with recorded reasons:
four require external source datasets and one asserts nondeterministic missing
flag order in a source file bound by frozen evidence.

No CKKS experiment or policy retuning was performed.
`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = {
        path.relative_to(expected).as_posix(): sha256_path(path)
        for path in expected.rglob("*")
        if path.is_file()
    }
    actual_files = {
        path.relative_to(actual).as_posix(): sha256_path(path)
        for path in actual.rglob("*")
        if path.is_file()
    }
    require_equal(actual_files, expected_files, "rebuilt evidence tree")


def freeze(raw_root: Path, output: Path, freezer_commit: str) -> None:
    build(
        output,
        raw_root / COMPLETE_COLLECTION_NAME,
        [raw_root / name for name in RECOVERY_COLLECTION_NAMES],
        freezer_commit,
    )


def verify(output: Path) -> None:
    verify_checksum_index(output)
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["schema_version"],
        "flipguard_independent_machine_replay_evidence_v1",
        "evidence schema",
    )
    require_equal(
        manifest["paper_claim_allowed"],
        False,
        "paper claim gate",
    )
    complete_root = output / "raw/complete"
    recovery_roots = [
        output / f"raw/recovery_{index}"
        for index in range(1, len(RECOVERY_COLLECTION_NAMES) + 1)
    ]
    complete_manifest, complete = verify_collection(
        complete_root,
        complete=True,
    )
    recovery_pairs = [
        verify_collection(root, complete=False)
        for root in recovery_roots
    ]
    require_equal(
        derive_summary(
            complete,
            [pair[1] for pair in recovery_pairs],
        ),
        load_json(output / "summary.json"),
        "summary replay",
    )
    require_equal(
        manifest["execution_source_commit"],
        complete_manifest["head_sha"],
        "execution source commit",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-independent-replay-evidence-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        build(
            rebuilt,
            complete_root,
            recovery_roots,
            manifest["freezer_commit"],
        )
        compare_trees(output, rebuilt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--freezer-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    raw_root = (
        args.raw_root
        if args.raw_root.is_absolute()
        else REPO_ROOT / args.raw_root
    )
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        verify(output)
        print(
            "independent_machine_replay_evidence_v1=VERIFIED "
            "paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(raw_root, output, args.freezer_commit)
    print(
        "independent_machine_replay_evidence_v1=FROZEN "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
