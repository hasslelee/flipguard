#!/usr/bin/env python3
"""Collect an independent-machine replay GitHub Actions run."""

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
EXPECTED_WORKFLOW = "Independent Artifact Replay"
EXPECTED_ARTIFACT = "flipguard-independent-machine-replay"
VERIFY_PATH = REPO_ROOT / "scripts/verify_independent_machine_replay.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_independent_machine_replay_for_collector",
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


def run_command(
    command: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=text,
    )


def load_run(run_id: int) -> dict[str, Any]:
    fields = (
        "status,conclusion,headSha,url,jobs,createdAt,updatedAt,"
        "workflowName,event,databaseId"
    )
    completed = run_command(
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
    )
    value = json.loads(completed.stdout)
    if value["workflowName"] != EXPECTED_WORKFLOW:
        raise ValueError(
            f"workflow={value['workflowName']!r}; "
            f"expected {EXPECTED_WORKFLOW!r}"
        )
    if value["status"] != "completed":
        raise ValueError(f"workflow status is {value['status']}, not completed")
    return value


def list_artifacts(run_id: int) -> list[dict[str, Any]]:
    completed = run_command(
        [
            "gh",
            "api",
            f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts",
            "--paginate",
        ]
    )
    return json.loads(completed.stdout)["artifacts"]


def collection_classification(
    missing_artifact: bool,
    workflow_conclusion: str,
) -> str:
    if workflow_conclusion == "success" and not missing_artifact:
        return "COMPLETE_INDEPENDENT_REPLAY"
    return "INDEPENDENT_REPLAY_RECOVERY"


def collect(
    run_id: int,
    output: Path,
    *,
    allow_recovery: bool = False,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite replay collection: {output}"
        )
    run = load_run(run_id)
    artifacts = list_artifacts(run_id)
    by_name = {artifact["name"]: artifact for artifact in artifacts}
    missing = EXPECTED_ARTIFACT not in by_name
    if (run["conclusion"] != "success" or missing) and not allow_recovery:
        raise ValueError(
            "run is not a complete success; use --allow-recovery "
            "to preserve it as recovery evidence"
        )

    with tempfile.TemporaryDirectory(
        prefix="flipguard-independent-replay-ci-",
        dir="/tmp",
    ) as temporary:
        staging = Path(temporary) / "collection"
        staging.mkdir()
        artifact_root = staging / "artifact"
        if not missing:
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
        (staging / "run_metadata.json").write_bytes(canonical_json(run))

        replay_record: dict[str, Any] | None = None
        if not missing:
            replay_path = artifact_root / "replay.json"
            if not replay_path.is_file():
                raise ValueError("artifact is missing replay.json")
            replay_record = json.loads(
                replay_path.read_text(encoding="utf-8")
            )
            if run["conclusion"] == "success":
                VERIFY.verify(artifact_root, run["headSha"])

        artifact_record = None
        if not missing:
            artifact = by_name[EXPECTED_ARTIFACT]
            files = [
                {
                    "path": path.relative_to(staging).as_posix(),
                    "sha256": sha256_path(path),
                    "bytes": path.stat().st_size,
                }
                for path in sorted(
                    item
                    for item in artifact_root.rglob("*")
                    if item.is_file()
                )
            ]
            artifact_record = {
                "artifact_id": artifact["id"],
                "name": artifact["name"],
                "digest": artifact.get("digest", ""),
                "size_in_bytes": artifact["size_in_bytes"],
                "expired": artifact["expired"],
                "created_at": artifact["created_at"],
                "expires_at": artifact["expires_at"],
                "files": files,
            }

        manifest = {
            "schema_version": (
                "flipguard_independent_machine_replay_ci_collection_v1"
            ),
            "repository": REPOSITORY,
            "run_id": run_id,
            "run_url": run["url"],
            "head_sha": run["headSha"],
            "event": run["event"],
            "workflow_conclusion": run["conclusion"],
            "collection_classification": collection_classification(
                missing,
                run["conclusion"],
            ),
            "missing_expected_artifact": missing,
            "job_conclusions": {
                job["name"]: job["conclusion"] for job in run["jobs"]
            },
            "artifact": artifact_record,
            "replay_status": (
                None if replay_record is None else replay_record["status"]
            ),
        }
        (staging / "collection_manifest.json").write_bytes(
            canonical_json(manifest)
        )
        checksum_lines = []
        for path in sorted(
            item
            for item in staging.rglob("*")
            if item.is_file() and item.name != "SHA256SUMS"
        ):
            checksum_lines.append(
                f"{sha256_path(path).removeprefix('sha256:')}  "
                f"{path.relative_to(staging).as_posix()}\n"
            )
        (staging / "SHA256SUMS").write_text(
            "".join(checksum_lines),
            encoding="ascii",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-recovery", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    collect(
        args.run_id,
        output,
        allow_recovery=args.allow_recovery,
    )
    print(
        "independent_machine_replay_ci=COLLECTED "
        f"run_id={args.run_id} output={output}"
    )


if __name__ == "__main__":
    main()
