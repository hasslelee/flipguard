#!/usr/bin/env python3
"""Run the pinned Orion MLP official-test path on ten ordered MNIST inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "external/v7/sources/orion"
OUTPUT = ROOT / "external/v9/orion/orion_preflight_10.json"
INPUT_MANIFEST = ROOT / "external/v9/orion/preflight_input_manifest.json"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def model_digest(model: torch.nn.Module) -> str:
    value = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value.update(name.encode("utf-8"))
        array = tensor.detach().cpu().contiguous().numpy()
        value.update(str(array.dtype).encode("ascii"))
        value.update(str(tuple(array.shape)).encode("ascii"))
        value.update(array.tobytes())
    return "sha256:" + value.hexdigest()


def vector(value: torch.Tensor) -> list[float]:
    return [float(item) for item in value.detach().cpu().reshape(-1).tolist()]


def main() -> int:
    if OUTPUT.exists():
        json.loads(OUTPUT.read_text(encoding="utf-8"))
        print("PASS: existing Orion preflight output is valid JSON")
        return 0
    declared = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    if declared["ordered_test_indices"] != list(range(10)):
        raise RuntimeError("INTEGRITY_BLOCK: Orion preflight input declaration drift")

    import orion
    import orion.models as models
    from orion.core.utils import get_mnist_datasets, mae

    source_commit = subprocess.run(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if source_commit != "be8a827350a147d610fe3bb998b5bea8de814ff8":
        raise RuntimeError("INTEGRITY_BLOCK: Orion source commit drift")
    source_status = subprocess.run(
        ["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if source_status:
        raise RuntimeError("INTEGRITY_BLOCK: tracked Orion source is dirty")

    torch.manual_seed(42)
    config = SOURCE / "configs/mlp.yml"
    binary = SOURCE / "orion/backend/lattigo/lattigo-linux.so"
    model_source = SOURCE / "orion/models/mlp.py"
    data_root = ROOT / "external/v9/orion/data"
    data_root.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    orion.init_scheme(str(config))
    scheme_ms = (time.perf_counter() - start) * 1000
    trainloader, testloader = get_mnist_datasets(
        data_dir=str(data_root), batch_size=1, seed=42
    )
    net = models.MLP()
    weights_digest = model_digest(net)
    net.eval()

    inputs: list[torch.Tensor] = []
    labels: list[int] = []
    plain_logits: list[torch.Tensor] = []
    iterator = iter(testloader)
    for expected_index in declared["ordered_test_indices"]:
        inp, label = next(iterator)
        inputs.append(inp)
        labels.append(int(label.item()))
        with torch.no_grad():
            plain_logits.append(net(inp).detach().clone())

    start = time.perf_counter()
    orion.fit(net, trainloader)
    fit_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    input_level = int(orion.compile(net))
    compile_ms = (time.perf_counter() - start) * 1000
    net.he()

    records = []
    for index, (inp, label, clear) in enumerate(zip(inputs, labels, plain_logits)):
        start = time.perf_counter()
        encoded = orion.encode(inp, input_level)
        ciphertext = orion.encrypt(encoded)
        encrypt_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        encrypted_output = net(ciphertext)
        evaluate_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        decrypted = encrypted_output.decrypt().decode()
        decrypt_ms = (time.perf_counter() - start) * 1000
        clear_values = vector(clear)
        decrypted_values = vector(decrypted)
        if len(clear_values) != 10 or len(decrypted_values) != 10:
            raise RuntimeError("Orion MLP did not expose ten logits")
        errors = [abs(a - b) for a, b in zip(clear_values, decrypted_values)]
        plain_argmax = max(range(10), key=clear_values.__getitem__)
        encrypted_argmax = max(range(10), key=decrypted_values.__getitem__)
        records.append({
            "ordered_input_index": index,
            "official_test_index": declared["ordered_test_indices"][index],
            "label": label,
            "plaintext_logits": clear_values,
            "decrypted_logits": decrypted_values,
            "plaintext_argmax": plain_argmax,
            "encrypted_argmax": encrypted_argmax,
            "argmax_flip": plain_argmax != encrypted_argmax,
            "mae": float(mae(clear, decrypted)),
            "max_absolute_error": max(errors),
            "encrypt_ms": encrypt_ms,
            "evaluate_ms": evaluate_ms,
            "decrypt_ms": decrypt_ms,
            "total_ms": encrypt_ms + evaluate_ms + decrypt_ms,
        })

    raw_files = {}
    for path in sorted((data_root / "MNIST/raw").glob("*")):
        if path.is_file():
            raw_files[path.name] = {"size": path.stat().st_size, "sha256": sha256(path)}
    payload = {
        "schema_version": "flipguard_orion_v9_preflight_v1",
        "status": "PASS",
        "evidence_role": "OFFICIAL_SELF_TEST_ONLY_UNTRAINED_DETERMINISTIC_WEIGHTS",
        "source_repository": "https://github.com/baahl-nyu/orion",
        "source_commit": source_commit,
        "tracked_source_clean": True,
        "model": "official Orion MLP",
        "model_architecture_source": "external/v7/sources/orion/orion/models/mlp.py",
        "model_architecture_sha256": sha256(model_source),
        "weight_provenance": "torch.manual_seed(42) deterministic initialization from official test_mlp.py; no trained MLP weights are distributed at the pinned commit",
        "model_state_sha256": weights_digest,
        "config": "external/v7/sources/orion/configs/mlp.yml",
        "config_sha256": sha256(config),
        "binary": "external/v7/sources/orion/orion/backend/lattigo/lattigo-linux.so",
        "binary_sha256": sha256(binary),
        "actual_keygen_encrypt_evaluate_decrypt": True,
        "input_level": input_level,
        "unique_inputs": len(records),
        "ordered_input_ids": declared["ordered_test_indices"],
        "input_manifest_sha256": sha256(INPUT_MANIFEST),
        "dataset_raw_files": raw_files,
        "scheme_init_and_keygen_ms": scheme_ms,
        "fit_ms": fit_ms,
        "compile_ms": compile_ms,
        "argmax_flips": sum(record["argmax_flip"] for record in records),
        "all_logits_extractable": all(len(record["decrypted_logits"]) == 10 for record in records),
        "records": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    partial = OUTPUT.with_suffix(".json.partial")
    partial.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    partial.replace(OUTPUT)
    print(json.dumps({key: payload[key] for key in ("status", "unique_inputs", "argmax_flips", "fit_ms", "compile_ms")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
