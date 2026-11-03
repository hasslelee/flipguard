#!/usr/bin/env python3
"""Build seed 0/1/2 CNN-lite artifacts without changing the frozen source pack."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = ROOT / "scripts/export_mnist_cnn_lite_holdout.py"
SOURCE = ROOT / "results/source_datasets/mnist/mnist_784.arff.gz"
OUT = ROOT / "results/model_family_expansion_v17/plaintext/packed_cnn_training_seed"


def load_module():
    spec = importlib.util.spec_from_file_location("v17_cnn_source", SOURCE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_module()
    records = []
    for seed in (0, 1, 2):
        output = OUT / f"seed_{seed}"
        if output.exists():
            raise FileExistsError(output)
        output.mkdir(parents=True)
        module.MODEL_SEED = seed
        module.LOGICAL_OUTPUT = output.relative_to(ROOT)
        module.build_artifacts(SOURCE, output)
        model = json.loads((output / "model.json").read_text(encoding="ascii"))
        records.append({"seed": seed, "model": (output / "model.json").relative_to(ROOT).as_posix(), "plaintext_metrics": model["training"]["model_development_metrics"]})
    (OUT / "summary.json").write_text(json.dumps({"schema_version": "flipguard_v17_packed_cnn_training_seeds_v1", "seeds": [0, 1, 2], "records": records}, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": "PASS", "models": len(records)}, sort_keys=True))


if __name__ == "__main__":
    main()
