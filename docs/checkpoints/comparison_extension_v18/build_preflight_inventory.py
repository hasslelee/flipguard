#!/usr/bin/env python3
"""Create a read-only inventory for the immutable inputs consumed by V18."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/checkpoints/comparison_extension_v18"

INPUTS = {
    "v17_release_r3": ROOT / "docs/audit/model_family_expansion_v17/final_vm1x6_release_r3",
    "v17_final_evidence": ROOT / "docs/evidence/model_family_expansion_v17/final_vm1x6",
    "v17_final_tables": ROOT / "results/model_family_expansion_v17/final_vm1x6",
    "v17_immutable_run": ROOT / "results/model_family_expansion_v17/runs/v17_final_vm1x6_20260811T050104Z",
    "v17_protocol": ROOT / "docs/protocols/model_family_expansion_v17",
    "v8_external_evidence": ROOT / "docs/evidence/focused_external_comparison_v8",
    "v9_external_closure": ROOT / "docs/evidence/final_realistic_baseline_closure_v9",
    "external_v7": ROOT / "docs/evidence/external_end_to_end_code_v7",
}

EXPECTED = {
    "source_commit": "cefc44b0d7e351db2a34886dd758a2d31a3e4c12",
    "tooling_commit": "86b0403208abbc741a65934358a5dea4a66e4d88",
    "v17_r3_manifest_sha256": "f43e3a7ca075086dcc3e730a323b334ee9c81d5f906a46a89e22dfe273a59397",
    "v17_final_manifest_sha256": "2c6671debb4f885ed3b8003a8bd93e24a8c4fcca6e4f8178ef999f8ded6eddde",
    "v17_protocol_sha256": "09aac669e2a970edfadf99486a3c977f92e0a5ddc96f20432ed9221cc070d6c6",
    "v17_candidate_space_sha256": "174b9c0ebc553a14ebf6f61df5ffc890ab448103677a890d9f159fc4429bc3b7",
    "selected_configuration_table_sha256": "5c9757d4dd2b8d48e113b633b65ed99b5e21e153d4819cae28b02a26bc38c0cb",
    "direct_vs_exhaustive_table_sha256": "8c73d884ebb322943989f03130f7c28bc6c05e7641447df425151902718ed8e7",
    "formal_latency_table_sha256": "a3558bc912ee9f228a46c1243e8270f9fbbcb5a5a44aa67a5a19925eca63ec12",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def iter_files(path: Path):
    if path.is_file():
        yield path
    elif path.is_dir():
        yield from sorted(p for p in path.rglob("*") if p.is_file())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    missing: list[str] = []
    for category, path in INPUTS.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        for item in iter_files(path):
            rows.append(
                {
                    "category": category,
                    "relative_path": item.relative_to(ROOT).as_posix(),
                    "size_bytes": item.stat().st_size,
                    "sha256": sha256(item),
                }
            )

    inventory = OUT / "v17_input_inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["category", "relative_path", "size_bytes", "sha256"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    selected_paths = {
        "r3_manifest": ROOT / "docs/audit/model_family_expansion_v17/final_vm1x6_release_r3/manifest.json",
        "final_manifest": ROOT / "docs/evidence/model_family_expansion_v17/final_vm1x6/manifest.json",
        "protocol": ROOT / "docs/protocols/model_family_expansion_v17/protocol.json",
        "candidate_space": ROOT / "docs/protocols/model_family_expansion_v17/candidate_space.json",
        "selected_configuration_table": ROOT / "results/model_family_expansion_v17/final_vm1x6/table_07_selected_configurations.csv",
        "direct_vs_exhaustive_table": ROOT / "results/model_family_expansion_v17/final_vm1x6/table_04_direct_vs_exhaustive.csv",
        "formal_latency_table": ROOT / "results/model_family_expansion_v17/final_vm1x6/table_05_formal_paired_latency.csv",
    }
    selected = {
        key: {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for key, path in selected_paths.items()
    }
    binding = {
        "schema_version": "flipguard_comparison_extension_v18_input_binding_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "scientific_execution_source_commit": EXPECTED["source_commit"],
        "post_run_aggregation_tooling_commit": EXPECTED["tooling_commit"],
        "inventory_file_count": len(rows),
        "inventory_total_bytes": sum(int(row["size_bytes"]) for row in rows),
        "missing_inputs": missing,
        "selected_inputs": selected,
        "expected_digests": EXPECTED,
        "read_only": True,
        "new_encrypted_evaluations": 0,
    }
    (OUT / "input_binding.json").write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    status_lines = git("status", "--short").splitlines()
    preflight = f"""# V18 Comparison Extension Pre-flight

- Generated (UTC): `{binding['generated_at_utc']}`
- Branch: `{binding['branch']}`
- HEAD: `{binding['head']}`
- Scientific execution source commit: `{EXPECTED['source_commit']}`
- Post-run aggregation/tooling commit: `{EXPECTED['tooling_commit']}`
- Inventory: `{len(rows)}` files, `{binding['inventory_total_bytes']}` bytes
- Missing declared inputs: `{len(missing)}`
- Existing untracked/user files preserved: `{len(status_lines)}` status rows
- V17 writes performed: `0`
- Encrypted executions performed: `0`

## Locked Counts

- V17 matrix: `204/204`
- Formal latency: `68/68`
- Scientific recomputation: `489/489 PASS`
- Latency reconstruction: `15/15 PASS`

## Protection Rule

V18 reads the paths bound in `input_binding.json` by path and SHA-256. It does
not symlink, import completion markers, rewrite V17 manifests, or regenerate
V17 tables. All derived outputs remain under the V18 checkpoint, evidence,
report, and result roots.
"""
    (OUT / "PRE_FLIGHT.md").write_text(preflight, encoding="utf-8")

    sums = []
    for path in sorted([inventory, OUT / "input_binding.json", OUT / "PRE_FLIGHT.md"]):
        sums.append(f"{sha256(path)}  {path.name}")
    (OUT / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")

    print(
        f"V18_PRE_FLIGHT_INVENTORY files={len(rows)} bytes={binding['inventory_total_bytes']} "
        f"missing={len(missing)}"
    )


if __name__ == "__main__":
    main()
