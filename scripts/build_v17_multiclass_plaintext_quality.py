#!/usr/bin/env python3
"""Build comprehensive plaintext-quality overlays for frozen V17 MNIST models."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/model_family_expansion_v17"
BINARY = RESULTS / "bin/flipguard-v17-plaintext-quality"
OUT = RESULTS / "plaintext/multiclass_quality"
SOURCE = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    models = [
        ("base_mlp100", ROOT / "datasets/journal_multiclass_extension_v1/mnist/mnist_mlp_square_784_100_10_v1.json"),
        ("base_lenet5_small", ROOT / "datasets/journal_multiclass_extension_v1/mnist/mnist_lenet5_small_square_v1.json"),
    ]
    for model in ("mlp100", "lenet5_small"):
        for seed in (0, 1, 2):
            models.append((f"{model}_seed_{seed}", RESULTS / f"plaintext/multiclass_training_seed/{model}/seed_{seed}/model.json"))
    records = []
    for identity, model in models:
        output = OUT / identity / "quality.json"
        if not output.is_file():
            subprocess.run([
                str(BINARY), "--model", str(model), "--source", str(SOURCE), "--output", str(output)
            ], cwd=ROOT, check=True)
        result = json.loads(output.read_text(encoding="ascii"))
        records.append({
            "identity": identity, "model_path": model.relative_to(ROOT).as_posix(),
            "model_sha256": sha(model), "quality_path": output.relative_to(ROOT).as_posix(),
            "quality_sha256": sha(output), "accuracy": result["accuracy"],
            "balanced_accuracy": result["balanced_accuracy"], "macro_f1": result["macro_f1"],
        })
    summary = {
        "schema_version": "flipguard_v17_multiclass_plaintext_quality_summary_v1",
        "binary_sha256": sha(BINARY), "source_sha256": sha(SOURCE), "records": records,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "models": len(records)}, sort_keys=True))


if __name__ == "__main__":
    main()
