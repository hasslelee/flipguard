#!/usr/bin/env python3
"""Verify the immutable V7 dependency and reusable provider tool bindings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "external/v8/manifests/v7_binding.json"
EXPECTED = {
    "eva": {
        "root": "external/v7/sources/eva",
        "commit": "4cd3254c9c51340ae30c451495ce5378135758c0",
        "required_clean": True,
        "files": {
            "external/v7/builds/eva/eva/python/eva/__init__.py": "a357073d2942babe81edf4ed87bb57c8a38c74875e250bbaf5a6d3e4f89cdf16"
        },
    },
    "heir": {
        "root": "external/v7/sources/heir",
        "commit": "cb7a7a30bb4d995b50e33bb5cd82ff7434db3656",
        "required_clean": False,
        "allowed_changes": [
            " M tests/Examples/lattigo/ckks/dot_product_8f/dot_product_8f_test.go",
            " M tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test.cpp"
        ],
        "files": {
            "external/v7/sources/heir/tests/Examples/lattigo/ckks/dot_product_8f/dot_product_8f_test.go": "5c0d39436d0920922a0d84d162f6a1343f8137be922d3b9ccf8e26b0562af0f7",
            "external/v7/sources/heir/tests/Examples/openfhe/ckks/dot_product_8f/dot_product_8f_test.cpp": "28f082b1e22931c63f29673180ec94ac54594df9bc03e180a24f3fb6246084da",
            "external/v7/builds/heir/b02fbecd7f06c73dabd4c72b0d38b345/execroot/_main/bazel-out/k8-fastbuild/bin/tools/heir-opt": "dccd5b66eaa7c1c2341d50b7245db44f8dcc551e3997cbc38e2d6e58b0aa35d7",
            "external/v7/builds/heir/b02fbecd7f06c73dabd4c72b0d38b345/execroot/_main/bazel-out/k8-fastbuild/bin/tools/heir-translate": "c57b257ce97f7d78b844be1a6818b077cec118f2142eb09a9f0a94cdebe6541d"
        },
    },
    "corelab": {
        "root": "external/v7/environments/elasm-runtime-r1",
        "commit": "3c37c11b29ca480525bb6681e0254bdf90029425",
        "required_clean": True,
        "files": {
            "external/v7/environments/elasm-runtime-r1/build/bin/hecate-opt": "176f51161fe3f2f3009f8541a8b278d37acfb5331d688abb492d82020f728aa1"
        },
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True).stdout.rstrip("\n")


def main() -> int:
    predecessor = ROOT / "docs/evidence/external_end_to_end_code_v7"
    verifier = subprocess.run(
        ["python3", str(predecessor / "verify_external_end_to_end_code_v7.py")],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if verifier.returncode != 0:
        raise RuntimeError(f"INTEGRITY_BLOCK: V7 verifier failed: {verifier.stderr}")
    manifest_digest = sha256(predecessor / "manifest.json")
    if manifest_digest != "09d6e25b64bfbfc7c8e6d3945049b4492709e28695e95813508e97181f7c12cd":
        raise RuntimeError("INTEGRITY_BLOCK: V7 manifest digest changed")

    providers: dict[str, object] = {}
    for provider, contract in EXPECTED.items():
        source_root = ROOT / str(contract["root"])
        commit = git(source_root, "rev-parse", "HEAD")
        status = git(source_root, "status", "--short").splitlines()
        if commit != contract["commit"]:
            raise RuntimeError(f"INTEGRITY_BLOCK: {provider} commit changed: {commit}")
        allowed = list(contract.get("allowed_changes", []))
        if contract["required_clean"] and status:
            raise RuntimeError(f"INTEGRITY_BLOCK: {provider} source is dirty: {status}")
        if not contract["required_clean"] and status != allowed:
            raise RuntimeError(f"INTEGRITY_BLOCK: {provider} compatibility patch changed: {status}")
        file_bindings = {}
        for relative, expected_digest in dict(contract["files"]).items():
            actual = sha256(ROOT / relative)
            if actual != expected_digest:
                raise RuntimeError(f"INTEGRITY_BLOCK: {relative} digest changed: {actual}")
            file_bindings[relative] = "sha256:" + actual
        providers[provider] = {
            "commit": commit,
            "status": status,
            "source_binding": "PASS",
            "binary_module_binding": "PASS",
            "files": file_bindings,
        }

    result = {
        "schema_version": "flipguard_focused_external_v8_v7_binding_v1",
        "status": "PASS",
        "v7_manifest_sha256": "sha256:" + manifest_digest,
        "providers": providers,
        "no_key_ciphertext_output_reuse": True,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text())
        if existing != result:
            raise RuntimeError("INTEGRITY_BLOCK: V7 binding result drift on resume")
    else:
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
