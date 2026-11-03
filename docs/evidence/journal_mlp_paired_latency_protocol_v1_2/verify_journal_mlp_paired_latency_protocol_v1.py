#!/usr/bin/env python3
"""Verify the frozen focused MLP-100 paired-latency protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


SCHEMA = "flipguard_journal_mlp_paired_latency_protocol_v1"
RANK_DOMAIN = "journal_mlp100_paired_latency_subset_v1"
CRITICAL_PATHS = [
    "cmd/flipguard-journal-mlp-paired-latency/main.go",
    "internal/ckksbackend/journal_mlp_paired_latency.go",
    "internal/ckksbackend/journal_mnist_multiclass.go",
    "internal/ckksbackend/ckks_timing_benchmark.go",
    "internal/ckksbackend/context.go",
    "internal/ckksbackend/profile.go",
    "internal/certify/multiclass_decision_contract.go",
    "internal/ckksplanner/synthesis.go",
    "internal/ckksplanner/security_policy.go",
    "internal/ckksplanner/concrete_security.go",
    "internal/journalmnist/artifact.go",
    "internal/journalmnist/dataset.go",
    "internal/journalmnist/execution_accessors.go",
    "internal/journalmnist/mlp.go",
    "go.mod",
    "go.sum",
]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def critical_digest(repo: Path) -> str:
    payload = "".join(f"{path}\0{sha(repo / path)}\n" for path in CRITICAL_PATHS)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_rank(label: int, source_index: int) -> str:
    payload = f"{RANK_DOMAIN}\0{label}\0{source_index}".encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def expected_rows(audit_path: Path) -> list[dict]:
    with audit_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_class: dict[int, list[dict]] = {label: [] for label in range(10)}
    for row in rows:
        label = int(row["label"])
        by_class[label].append(
            {
                "row_id": int(row["row_id"]),
                "sample_id": row["sample_id"],
                "source_index": int(row["source_index"]),
                "label": label,
                "sha256_rank": row_rank(label, int(row["source_index"])),
            }
        )
    output: list[dict] = []
    for label in range(10):
        ranked = sorted(by_class[label], key=lambda item: (item["sha256_rank"], item["source_index"]))[:10]
        for ordinal, item in enumerate(ranked, 1):
            output.append({"rank": ordinal, **item})
    return output


def verify(pack: Path, repo: Path) -> dict:
    pack = pack.resolve()
    repo = repo.resolve()
    manifest = load(pack / "manifest.json")
    protocol = load(pack / "execution_protocol.json")
    require(manifest["schema_version"] == SCHEMA, "manifest schema")
    require(protocol["schema_version"] == SCHEMA, "protocol schema")
    require(
        protocol["protocol_id"] in {
            "journal_mlp100_paired_latency_amendment_v1",
            "journal_mlp100_paired_latency_amendment_v1_1",
            "journal_mlp100_paired_latency_amendment_v1_2",
        },
        "protocol ID",
    )
    require(protocol["fresh_keysets"] == 3, "fresh keysets")
    require(protocol["warmup_runs"] == 1 and protocol["measurement_runs"] == 6, "passes")
    require(protocol["concurrent_ckks_processes"] == 0, "concurrency")
    require(protocol["outlier_removal"] is False, "outlier policy")
    require(len(protocol["arms"]) == 3, "arm count")
    require([arm["id"] for arm in protocol["arms"]] == ["gap_aware", "graph_only", "catalog"], "arm order")
    require(protocol["expected_measurement_records"] == 5400, "record count")
    require(protocol["execution_critical_source_digest"] == critical_digest(repo), "execution source digest")

    for item in [
        protocol["model"], protocol["locked_audit"], protocol["security_reconciliation"],
        *[arm["source"] for arm in protocol["arms"]],
    ]:
        require(sha(repo / item["path"]) == item["sha256"], f"binding {item['path']}")

    rows = expected_rows(repo / protocol["locked_audit"]["path"])
    require(protocol["selected_rows"] == rows, "SHA-ranked latency subset")
    require(len(rows) == 100, "selected image count")
    for label in range(10):
        require(sum(row["label"] == label for row in rows) == 10, f"class {label} count")

    binary = repo / manifest["frozen_binary"]["path"]
    if binary.exists():
        require(sha(binary) == protocol["frozen_binary_sha256"], "frozen binary digest")
    require(manifest["execution_protocol_sha256"] == sha(pack / "execution_protocol.json"), "protocol digest")
    require(manifest["latency_subset_manifest_sha256"] == sha(pack / "latency_subset_manifest.json"), "subset digest")

    sums = {}
    for line in (pack / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            relative = str(path.relative_to(pack))
            require(relative in sums, f"missing checksum {relative}")
            require(sha(path).removeprefix("sha256:") == sums[relative], f"checksum {relative}")
    return protocol


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default_pack = Path(__file__).resolve().parent
    if default_pack.name == "scripts":
        default_pack = Path("docs/evidence/journal_mlp_paired_latency_protocol_v1_2")
    parser.add_argument("--pack", type=Path, default=default_pack)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    protocol = verify(args.pack, args.repo)
    print(
        "journal_mlp_paired_latency_protocol=VERIFIED "
        f"rows={len(protocol['selected_rows'])} records={protocol['expected_measurement_records']}"
    )
