#!/usr/bin/env python3
"""Bind exact predecessor key runs for the duplicate V17 B3 base arms."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/model_family_expansion_v17"
SOURCE = ROOT / "results/journal_multiclass_extension_v1/encrypted"

MODELS = {
    "mnist_mlp_square_784_100_10_v1": (
        "synth_analysis_minimum_rescale_N13_Q5_S29_cd07c4b74140",
        "sha256:cd07c4b74140f146445a4d03a3edab35927c8c5b9d02f01d7b3c5f5411a7838a",
    ),
    "mnist_lenet5_small_square_v1": (
        "synth_analysis_minimum_rescale_N15_Q18_S44_3d9a3ac648cc",
        "sha256:3d9a3ac648cc1be8d04ca533115b1e128a4b4a105dfc6122e975b60a1926c0ba",
    ),
}


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = []
    for model_id, (candidate_id, expected_contract) in MODELS.items():
        source_root = SOURCE / model_id / f"trial_01_{candidate_id}"
        destination_root = RESULTS / "exhaustive" / model_id / f"candidate_01_{candidate_id}"
        destination_root.mkdir(parents=True, exist_ok=True)
        for key_run in range(1, 4):
            source = source_root / f"key_run_{key_run:02d}.json"
            destination = destination_root / source.name
            item = json.loads(source.read_text(encoding="utf-8"))
            if item.get("candidate_id") != candidate_id or item.get("key_run") != key_run:
                raise RuntimeError(f"predecessor identity mismatch: {source}")
            if item.get("contract_digest") != expected_contract:
                raise RuntimeError(f"predecessor contract mismatch: {source}")
            if destination.exists():
                if sha(destination) != sha(source):
                    raise RuntimeError(f"refusing to overwrite non-identical reuse destination: {destination}")
            else:
                shutil.copyfile(source, destination)
            records.append({
                "model_id": model_id,
                "candidate_id": candidate_id,
                "key_run": key_run,
                "source": source.relative_to(ROOT).as_posix(),
                "destination": destination.relative_to(ROOT).as_posix(),
                "sha256": sha(source),
                "contract_digest": item["contract_digest"],
                "reuse_class": "BYTE_IDENTICAL_PREDECESSOR_KEY_RUN",
            })
    manifest = {
        "schema_version": "flipguard_v17_multiclass_predecessor_reuse_v1",
        "purpose": "avoid duplicate encryption for the byte-identical B3 base candidate",
        "new_encrypted_key_runs": 0,
        "records": records,
    }
    path = RESULTS / "multiclass_predecessor_reuse.json"
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="ascii") != encoded:
        raise RuntimeError(f"reuse manifest drift: {path}")
    path.write_text(encoded, encoding="ascii")
    print(json.dumps({"status": "PASS", "reused_key_runs": len(records), "manifest_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
