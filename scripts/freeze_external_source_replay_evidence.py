#!/usr/bin/env python3
"""Freeze and deterministically verify external-source replay evidence."""

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
    REPO_ROOT / "results/thesis_grade_protocol/external_source_replay_v1"
)
COMPLETE_COLLECTION_NAME = "ci_run_30539143968"
RECOVERY_COLLECTION_NAME = "ci_run_30538909521_recovery"
OUTPUT_DEFAULT = REPO_ROOT / "docs/evidence/external_source_replay_v1"
VERIFY_PATH = REPO_ROOT / "scripts/verify_external_source_replay.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_external_source_replay_for_freezer",
    VERIFY_PATH,
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)

EXPECTED_SOURCE_DIGESTS = {
    "openml_mnist_784_arff_gzip_v1": (
        15_469_256,
        "fe4410d8dbb50f6db6482b187557c5cb8bccfbcec74eeb6abc47c858f4ffab78",
    ),
    "berkeley_bsds500_archive_v1": (
        70_763_455,
        "97e49d31764f3912f0c4122707d53062ac9e783ba0f095e447a4d53c1a41af8e",
    ),
}


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
        if not separator or len(digest) != 64:
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


def failed_checks(replay: dict[str, Any]) -> list[str]:
    return [
        row["name"]
        for row in replay["checks"]
        if row["status"] != "PASS"
    ]


def verify_sources(replay: dict[str, Any]) -> None:
    sources = {
        source["source_id"]: (source["bytes"], source["sha256"])
        for source in replay["source_fetch"]["sources"]
    }
    require_equal(sources, EXPECTED_SOURCE_DIGESTS, "official source bytes")


def verify_collection(
    root: Path,
    *,
    complete: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_checksum_index(root)
    manifest = load_json(root / "collection_manifest.json")
    require_equal(
        manifest["schema_version"],
        "flipguard_external_source_replay_ci_collection_v1",
        "collection schema",
    )
    replay = load_json(root / "artifact/replay.json")
    verify_sources(replay)
    if complete:
        require_equal(
            manifest["collection_classification"],
            "COMPLETE_EXTERNAL_SOURCE_REPLAY",
            "complete classification",
        )
        require_equal(
            manifest["workflow_conclusion"],
            "success",
            "complete workflow conclusion",
        )
        require_equal(failed_checks(replay), [], "complete failed checks")
        VERIFY.verify(root / "artifact", manifest["head_sha"])
    else:
        require_equal(
            manifest["collection_classification"],
            "RECOVERABLE_SOURCE_REPLAY_IMPLEMENTATION_FAILURE",
            "recovery classification",
        )
        require_equal(
            manifest["workflow_conclusion"],
            "failure",
            "recovery workflow conclusion",
        )
        require_equal(
            failed_checks(replay),
            [
                "mnist_export",
                "bsds500_sobel_export",
                "bsds500_harris_export",
            ],
            "recovery failed checks",
        )
    return manifest, replay


def verify_recovery_reason(root: Path) -> None:
    mnist_output = (
        root / "artifact/mnist_export.stdout.txt"
    ).read_text(encoding="utf-8")
    sobel_error = (
        root / "artifact/bsds500_sobel_export.stderr.txt"
    ).read_text(encoding="utf-8")
    harris_error = (
        root / "artifact/bsds500_harris_export.stderr.txt"
    ).read_text(encoding="utf-8")
    if (
        "mnist_cnn_lite_source_replay=PASS" not in mnist_output
        or "partition train has 0 images" not in sobel_error
        or "partition train has 0 images" not in harris_error
    ):
        raise ValueError("external-source replay recovery reason is not preserved")


def derive_summary(
    complete: dict[str, Any],
    recovery: dict[str, Any],
) -> dict[str, Any]:
    require_equal(len(complete["checks"]), 8, "complete check count")
    require_equal(failed_checks(complete), [], "complete check failures")
    require_equal(
        complete["scope"]["ignored_execution_ledger_replay"],
        "NOT_EVALUATED",
        "ignored-ledger replay status",
    )
    require_equal(
        complete["encrypted_execution"],
        {
            "candidate_trials": 0,
            "key_runs": 0,
            "sample_evaluations": 0,
        },
        "encrypted accounting",
    )
    return {
        "schema_version": (
            "flipguard_external_source_replay_evidence_summary_v1"
        ),
        "status": "SUPPORTED_WITH_SCOPE_LIMIT",
        "official_source_byte_replay": "SUPPORTED",
        "deterministic_exporter_replay": "SUPPORTED",
        "static_graph_contract_replay": "SUPPORTED",
        "encrypted_execution_ledger_replay": "NOT_EVALUATED",
        "source_datasets": 2,
        "deterministic_exporters": 3,
        "static_graph_contracts": complete["scope"]["static_graph_contracts"],
        "checks_passed": len(complete["checks"]),
        "checks_failed": 0,
        "recovery_runs": 1,
        "recovery_failed_checks": failed_checks(recovery),
        "encrypted_candidate_trials": 0,
        "encrypted_key_runs": 0,
        "encrypted_sample_evaluations": 0,
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
    (output / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def build(
    output: Path,
    complete_root: Path,
    recovery_root: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite external replay evidence: {output}"
        )
    complete_manifest, complete = verify_collection(
        complete_root,
        complete=True,
    )
    recovery_manifest, recovery = verify_collection(
        recovery_root,
        complete=False,
    )
    verify_recovery_reason(recovery_root)

    output.mkdir(parents=True)
    shutil.copytree(complete_root, output / "raw/complete")
    shutil.copytree(recovery_root, output / "raw/recovery_1")
    summary = derive_summary(complete, recovery)
    (output / "summary.json").write_bytes(canonical_json(summary))
    manifest = {
        "schema_version": "flipguard_external_source_replay_evidence_v1",
        "evidence_id": "external_source_replay_v1",
        "classification": "POST_CONFIRMATORY_ARTIFACT_ASSURANCE",
        "freezer_commit": freezer_commit,
        "execution_source_commit": complete_manifest["head_sha"],
        "workflow_run_id": complete_manifest["run_id"],
        "workflow_run_url": complete_manifest["run_url"],
        "workflow_conclusion": complete_manifest["workflow_conclusion"],
        "replay_sha256": sha256_path(
            complete_root / "artifact/replay.json"
        ),
        "official_source_digests": {
            source_id: {
                "bytes": metadata[0],
                "sha256": metadata[1],
            }
            for source_id, metadata in EXPECTED_SOURCE_DIGESTS.items()
        },
        "policies": complete["policies"],
        "policy_retuning": 0,
        "encrypted_execution": complete["encrypted_execution"],
        "recovery_run": {
            "run_id": recovery_manifest["run_id"],
            "head_sha": recovery_manifest["head_sha"],
            "workflow_conclusion": recovery_manifest[
                "workflow_conclusion"
            ],
            "failed_checks": failed_checks(recovery),
            "reason_codes": [
                "EXPORTER_PASS_TOKEN_MISMATCH",
                "VERIFIED_ARCHIVE_NOT_EXTRACTED",
            ],
        },
        "scope_limit": (
            "Official source bytes, deterministic exporters, and static "
            "graph contracts only; encrypted execution-ledger replay was "
            "not evaluated."
        ),
        "summary_sha256": sha256_path(output / "summary.json"),
        "status": summary["status"],
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# External Source Replay Evidence V1

This pack preserves one failed clean-runner recovery and one successful
replay from byte-pinned official MNIST and BSDS500 sources. The successful
run reproduces the CNN-lite, Sobel, and Harris deterministic exporters and
three static graph contracts from a clean GitHub runner.

The recovery is retained: MNIST export succeeded but the replay driver
matched the wrong success token, while the verified BSDS500 archive had not
been extracted before the Sobel and Harris exporters ran.

This evidence does not replay ignored encrypted execution ledgers and does
not perform CKKS trials, key runs, sample evaluations, or policy retuning.
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
        raw_root / RECOVERY_COLLECTION_NAME,
        freezer_commit,
    )


def verify(output: Path) -> None:
    verify_checksum_index(output)
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["schema_version"],
        "flipguard_external_source_replay_evidence_v1",
        "evidence schema",
    )
    require_equal(
        manifest["paper_claim_allowed"],
        False,
        "paper claim gate",
    )
    complete_root = output / "raw/complete"
    recovery_root = output / "raw/recovery_1"
    complete_manifest, complete = verify_collection(
        complete_root,
        complete=True,
    )
    _, recovery = verify_collection(recovery_root, complete=False)
    verify_recovery_reason(recovery_root)
    require_equal(
        derive_summary(complete, recovery),
        load_json(output / "summary.json"),
        "summary replay",
    )
    require_equal(
        manifest["execution_source_commit"],
        complete_manifest["head_sha"],
        "execution source commit",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-external-source-evidence-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        build(
            rebuilt,
            complete_root,
            recovery_root,
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
            "external_source_replay_evidence_v1=VERIFIED "
            "paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(raw_root, output, args.freezer_commit)
    print(f"external_source_replay_evidence_v1=FROZEN output={output}")


if __name__ == "__main__":
    main()
