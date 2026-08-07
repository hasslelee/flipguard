#!/usr/bin/env python3
"""Build final-window-only V7 tables and figures from normalized records."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "external/v7/status"
TABLE_SOURCES = {
    "table_01_artifact_execution_levels.csv": "artifact_execution_levels.csv",
    "table_02_clean_build_status.csv": "clean_build_matrix.csv",
    "table_03_official_pipeline_status.csv": "official_pipeline_matrix.csv",
    "table_04_native_execution_results.csv": "native_execution_records.csv",
    "table_05_provider_gate_results.csv": "provider_gate_records.csv",
    "table_06_execution_accounting.csv": "execution_accounting.csv",
    "table_07_security_qualification.csv": "security_summary.csv",
    "table_08_failure_taxonomy.csv": "failure_summary.csv",
}


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def numeric(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def bar_svg(title: str, items: list[tuple[str, float]], note: str) -> str:
    width, height = 1200, 720
    maximum = max((value for _, value in items), default=1.0) or 1.0
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        f"<desc>{html.escape(note)}</desc>",
        '<rect width="1200" height="720" fill="#ffffff"/>',
        f'<text x="60" y="70" font-family="sans-serif" font-size="32" font-weight="700" fill="#0d2a52">{html.escape(title)}</text>',
    ]
    top = 125
    row_height = min(62, 440 // max(1, len(items)))
    for index, (label, value) in enumerate(items):
        y = top + index * row_height
        bar_width = 650 * value / maximum
        lines.extend(
            [
                f'<text x="60" y="{y + 24}" font-family="sans-serif" font-size="18" fill="#24292f">{html.escape(label)}</text>',
                f'<rect x="400" y="{y + 4}" width="{bar_width:.2f}" height="26" rx="3" fill="#1f6feb"/>',
                f'<text x="{410 + bar_width:.2f}" y="{y + 24}" font-family="monospace" font-size="17" fill="#24292f">{value:g}</text>',
            ]
        )
    lines.extend(
        [
            f'<text x="60" y="675" font-family="sans-serif" font-size="16" fill="#57606a">{html.escape(note)}</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines) + "\n"


def publication_figures(root: Path) -> dict[str, str]:
    levels = rows(root / "artifact_execution_levels.csv")
    builds = rows(root / "clean_build_matrix.csv")
    pipelines = rows(root / "official_pipeline_matrix.csv")
    gates = rows(root / "provider_gate_records.csv")
    accounting = rows(root / "execution_accounting.csv")
    latency = rows(root / "latency_summary.csv")
    security = rows(root / "security_summary.csv")
    failures = rows(root / "failure_summary.csv")
    state_counts: dict[str, int] = {}
    for row in gates:
        state_counts[row["final_flipguard_state"]] = state_counts.get(row["final_flipguard_state"], 0) + 1
    level_items = [(row["system"], numeric(row["evidence_level"])) for row in levels]
    run_items = [
        (row["system"], numeric(row["encrypted_candidate_runs"]))
        for row in accounting if numeric(row["encrypted_candidate_runs"]) > 0
    ]
    latency_items = [
        (f"{row['provider']} / {row['workload']}", numeric(row["mean_total_ms"]))
        for row in latency if numeric(row["mean_total_ms"]) > 0
    ]
    failure_counts: dict[str, int] = {}
    for row in failures:
        failure_counts[row["reason_code"]] = failure_counts.get(row["reason_code"], 0) + 1
    return {
        "figure_01_evidence_funnel.svg": bar_svg(
            "V7 evidence funnel",
            [
                ("systems classified", len(levels)),
                ("clean-build PASS rows", sum(row["state"] == "PASS" for row in builds)),
                ("pipeline PASS rows", sum(row["state"] == "PASS" for row in pipelines)),
                ("encrypted E2E systems", sum(int(row["evidence_level"]) >= 3 for row in levels)),
                ("decision-bearing providers", 1),
                ("locked-audit providers", 1),
            ],
            "Counts are V7 records, not claims of universal tool coverage.",
        ),
        "figure_02_native_evidence_levels.svg": bar_svg(
            "Official artifact execution levels", level_items,
            "Evidence levels range from 0 (blocked/source only) to 6 (locked audit).",
        ),
        "figure_03_native_total_latency.svg": bar_svg(
            "Native total latency by provider workload", latency_items,
            "Unlike native timing boundaries; no cross-runtime algorithm-only speedup is admitted.",
        ),
        "figure_04_provider_gate_states.svg": bar_svg(
            "Provider candidate decision-gate states", sorted(state_counts.items()),
            "Only EVA shared-polynomial candidates exposed a frozen decision rule.",
        ),
        "figure_05_encrypted_run_accounting.svg": bar_svg(
            "Encrypted candidate runs by system", run_items,
            "Counts separate candidate executions from inputs, contexts, and timing passes.",
        ),
        "figure_06_common_executor_coverage.svg": bar_svg(
            "Common-executor portability", [("PORTABLE_EXACT", 0), ("GRAPH_EQUIVALENT", 0), ("NATIVE_ONLY systems", 4)],
            "No valid common-executor paired arm was established in V7.",
        ),
        "figure_07_security_headline_eligibility.svg": bar_svg(
            "Security qualification", [
                ("security rows", len(security)),
                ("headline eligible", sum(row["headline_eligible"] == "True" for row in security)),
            ],
            "External runtime distributions and exact-prime material were not universally aligned.",
        ),
        "figure_08_failure_taxonomy.svg": bar_svg(
            "Recorded blocker and failure taxonomy", sorted(failure_counts.items()),
            "Build, hardware, credential, and semantic blockers remain explicit rather than zero-filled.",
        ),
    }


def build(root: Path) -> dict[str, object]:
    pause = dt.datetime.fromisoformat((STATUS / "hard_pause_timestamp.txt").read_text().strip())
    if dt.datetime.now().astimezone() < pause - dt.timedelta(minutes=30):
        raise RuntimeError("V7 publication inputs are blocked until the final 30-minute window")
    tables = root / "tables"
    figures = root / "figures"
    manifest_path = root / "publication_inputs_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest["files"]:
            path = root / item["path"]
            if not path.is_file() or sha256(path) != item["sha256"]:
                raise RuntimeError(f"V7 publication input drift: {item['path']}")
        return manifest
    if tables.exists() or figures.exists():
        raise RuntimeError("refusing partial V7 publication-input overwrite")
    tables.mkdir()
    figures.mkdir()
    for target, source in TABLE_SOURCES.items():
        shutil.copy2(root / source, tables / target)
    for name, content in publication_figures(root).items():
        (figures / name).write_text(content, encoding="utf-8")
    files = [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256(path), "size_bytes": path.stat().st_size}
        for path in sorted([*tables.glob("*.csv"), *figures.glob("*.svg")])
    ]
    manifest = {
        "schema_version": "flipguard_external_v7_publication_inputs_v1",
        "table_count": 8,
        "figure_count": 8,
        "files": files,
        "actual_v7_records_only": True,
        "cross_runtime_algorithm_speedup_admitted": False,
        "portable_exact_count": 0,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.root.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
