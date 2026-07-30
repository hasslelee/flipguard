#!/usr/bin/env python3
"""Collect an exact-security-estimator GitHub Actions run fail closed."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "hasslelee/flipguard"
EXPECTED_WORKFLOW = "Exact Security Estimator"
EXPECTED_ARTIFACTS = {
    "exact-security-estimator-guidelines-pinned-8f1ff7e",
    "exact-security-estimator-current-3e48ef4",
}


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
    payload = json.loads(completed.stdout)
    return payload["artifacts"]


def collection_classification(missing: set[str]) -> str:
    return (
        "PRE_ESTIMATOR_IMPLEMENTATION_RECOVERY"
        if missing
        else "COMPLETE_ARTIFACT_COLLECTION"
    )


def collect(
    run_id: int,
    output: Path,
    *,
    allow_incomplete: bool = False,
) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite CI collection: {output}")
    run = load_run(run_id)
    artifacts = list_artifacts(run_id)
    names = {artifact["name"] for artifact in artifacts}
    missing = EXPECTED_ARTIFACTS - names
    if missing and not allow_incomplete:
        raise ValueError(f"missing workflow artifacts: {sorted(missing)}")

    with tempfile.TemporaryDirectory(
        prefix="flipguard-exact-security-ci-",
        dir="/tmp",
    ) as temporary:
        staging = Path(temporary) / "collection"
        staging.mkdir()
        artifact_root = staging / "artifacts"
        artifact_root.mkdir()
        for name in sorted(EXPECTED_ARTIFACTS & names):
            destination = artifact_root / name
            destination.mkdir()
            run_command(
                [
                    "gh",
                    "run",
                    "download",
                    str(run_id),
                    "--repo",
                    REPOSITORY,
                    "--name",
                    name,
                    "--dir",
                    str(destination),
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

        artifact_records = []
        for artifact in sorted(artifacts, key=lambda item: item["name"]):
            if artifact["name"] not in EXPECTED_ARTIFACTS:
                continue
            root = artifact_root / artifact["name"]
            files = []
            for path in sorted(
                item for item in root.rglob("*") if item.is_file()
            ):
                files.append(
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256_path(path),
                        "bytes": path.stat().st_size,
                    }
                )
            artifact_records.append(
                {
                    "artifact_id": artifact["id"],
                    "name": artifact["name"],
                    "size_in_bytes": artifact["size_in_bytes"],
                    "digest": artifact.get("digest", ""),
                    "expired": artifact["expired"],
                    "created_at": artifact["created_at"],
                    "expires_at": artifact["expires_at"],
                    "files": files,
                }
            )
        manifest = {
            "schema_version": (
                "flipguard_exact_security_estimator_ci_collection_v1"
            ),
            "repository": REPOSITORY,
            "run_id": run_id,
            "run_url": run["url"],
            "head_sha": run["headSha"],
            "event": run["event"],
            "workflow_conclusion": run["conclusion"],
            "collection_classification": collection_classification(missing),
            "missing_expected_artifacts": sorted(missing),
            "job_conclusions": {
                job["name"]: job["conclusion"] for job in run["jobs"]
            },
            "artifacts": artifact_records,
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
        f"exact_security_estimator_ci=COLLECTED "
        f"run_id={args.run_id} output={output}"
    )


if __name__ == "__main__":
    main()
