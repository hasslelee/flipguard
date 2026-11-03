#!/usr/bin/env python3
"""Collect an External Source Replay GitHub Actions run fail closed."""

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
REPOSITORY = "hasslelee/flipguard"
EXPECTED_WORKFLOW = "External Source Replay"
EXPECTED_ARTIFACT = "flipguard-external-source-replay"
VERIFY_PATH = REPO_ROOT / "scripts/verify_external_source_replay.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_external_source_replay_for_collector",
    VERIFY_PATH,
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


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


def run_command(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def load_run(run_id: int) -> dict[str, Any]:
    fields = (
        "status,conclusion,headSha,url,jobs,createdAt,updatedAt,"
        "workflowName,event,databaseId"
    )
    value = json.loads(
        run_command(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                REPOSITORY,
                "--json",
                fields,
            ]
        ).stdout
    )
    if value["workflowName"] != EXPECTED_WORKFLOW:
        raise ValueError(
            f"workflow={value['workflowName']!r}; "
            f"expected {EXPECTED_WORKFLOW!r}"
        )
    if value["status"] != "completed":
        raise ValueError("workflow run is not completed")
    return value


def list_artifacts(run_id: int) -> list[dict[str, Any]]:
    value = json.loads(
        run_command(
            [
                "gh",
                "api",
                f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts",
                "--paginate",
            ]
        ).stdout
    )
    return value["artifacts"]


def classification(
    workflow_conclusion: str,
    replay_status: str,
) -> str:
    if workflow_conclusion == "success" and replay_status == "PASS":
        return "COMPLETE_EXTERNAL_SOURCE_REPLAY"
    return "RECOVERABLE_SOURCE_REPLAY_IMPLEMENTATION_FAILURE"


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
    (root / "SHA256SUMS").write_text(
        "".join(lines),
        encoding="ascii",
    )


def collect(
    run_id: int,
    output: Path,
    *,
    allow_incomplete: bool,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite source replay collection: {output}"
        )
    run = load_run(run_id)
    artifacts = list_artifacts(run_id)
    matching = [
        artifact
        for artifact in artifacts
        if artifact["name"] == EXPECTED_ARTIFACT
    ]
    if len(matching) != 1:
        raise ValueError(
            f"expected one {EXPECTED_ARTIFACT} artifact; got {len(matching)}"
        )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-external-source-collection-",
        dir="/tmp",
    ) as temporary:
        staging = Path(temporary) / "collection"
        staging.mkdir()
        artifact_root = staging / "artifact"
        artifact_root.mkdir()
        run_command(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "--repo",
                REPOSITORY,
                "--name",
                EXPECTED_ARTIFACT,
                "--dir",
                str(artifact_root),
            ]
        )
        VERIFY.verify_checksums(artifact_root)
        replay = json.loads(
            (artifact_root / "replay.json").read_text(encoding="ascii")
        )
        if replay["source_commit"] != run["headSha"]:
            raise ValueError("source replay commit mismatch")
        replay_status = replay["status"]
        collection_classification = classification(
            run["conclusion"],
            replay_status,
        )
        if not allow_incomplete:
            if collection_classification != (
                "COMPLETE_EXTERNAL_SOURCE_REPLAY"
            ):
                raise ValueError(
                    "source replay is incomplete; use --allow-incomplete "
                    "to preserve recovery"
                )
            VERIFY.verify(artifact_root, run["headSha"])
        elif collection_classification == (
            "COMPLETE_EXTERNAL_SOURCE_REPLAY"
        ):
            VERIFY.verify(artifact_root, run["headSha"])

        log = run_command(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                REPOSITORY,
                "--log",
            ]
        ).stdout
        (staging / "workflow.log").write_text(log, encoding="utf-8")
        (staging / "run_metadata.json").write_bytes(
            canonical_json(run)
        )
        failed_checks = [
            check["name"]
            for check in replay["checks"]
            if check["status"] != "PASS"
        ]
        artifact = matching[0]
        manifest = {
            "schema_version": (
                "flipguard_external_source_replay_ci_collection_v1"
            ),
            "repository": REPOSITORY,
            "run_id": run_id,
            "run_url": run["url"],
            "head_sha": run["headSha"],
            "workflow_conclusion": run["conclusion"],
            "replay_status": replay_status,
            "collection_classification": collection_classification,
            "failed_checks": failed_checks,
            "job_conclusions": {
                job["name"]: job["conclusion"]
                for job in run["jobs"]
            },
            "artifact": {
                "artifact_id": artifact["id"],
                "name": artifact["name"],
                "size_in_bytes": artifact["size_in_bytes"],
                "digest": artifact.get("digest", ""),
                "created_at": artifact["created_at"],
                "expires_at": artifact["expires_at"],
                "tree_sha256": tree_digest(artifact_root),
            },
        }
        (staging / "collection_manifest.json").write_bytes(
            canonical_json(manifest)
        )
        write_checksums(staging)
        shutil.copytree(staging, output)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_path(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    collect(
        args.run_id,
        output,
        allow_incomplete=args.allow_incomplete,
    )
    print(
        "external_source_replay_ci=COLLECTED "
        f"run_id={args.run_id} output={output}"
    )


if __name__ == "__main__":
    main()
