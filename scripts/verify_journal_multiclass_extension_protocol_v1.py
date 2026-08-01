#!/usr/bin/env python3
"""Fail-closed verifier for the frozen multiclass extension protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    return "sha256:" + value


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack",
        default="docs/evidence/journal_multiclass_extension_v1",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pack = root / args.pack
    manifest = load(pack / "protocol_manifest.json")
    require(manifest["schema_version"] == "flipguard_journal_multiclass_extension_protocol_v1", "schema")
    require(manifest["ready_for_encrypted_execution"] is True, "execution gate")
    require(manifest["new_encrypted_execution_before_freeze"] == 0, "pre-freeze run count")
    for name, binding in manifest["files"].items():
        require(digest(pack / name) == binding["sha256"], f"file digest {name}")
    checksum_lines = (pack / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in checksum_lines:
        expected, name = line.split("  ", 1)
        require(digest(pack / name) == "sha256:" + expected, f"SHA256SUMS {name}")
    policy = load(pack / "policy_binding.json")
    require(policy["security_policy_digest"] == "sha256:855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055", "security digest")
    require(policy["direct_policy_digest"] == "sha256:503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603", "direct digest")
    require(policy["policy_retuning"] == 0, "policy retuning")
    split = load(pack / "input_split_manifest.json")
    require(split["encrypted_scope"]["configuration_validation"] == 500, "validation size")
    require(split["encrypted_scope"]["locked_audit"] == 500, "audit size")
    require(split["validation_audit_overlap_count"] == 0, "split overlap")
    candidates = load(pack / "candidate_space.json")
    require(candidates["security_v2_bounded_catalog"]["denominator_per_model"] == 7, "catalog denominator")
    require(len(candidates["security_v2_bounded_catalog"]["profiles"]) == 7, "catalog profiles")
    contract = load(pack / "multiclass_contract.json")
    require(contract["uniform_bound_corollary"].startswith("2B < g"), "uniform corollary")
    require(contract["margin_utilization_cap"] == 0.5, "rho")
    for name, binding in manifest["inputs"]["models"].items():
        model = load(root / binding["path"])
        require(digest(root / binding["path"]) == binding["sha256"], f"model digest {name}")
        require(model["policy_binding"]["policy_retuning"] == 0, f"model policy {name}")
    for name, binding in manifest["inputs"]["preflights"].items():
        preflight = load(root / binding["path"])
        require(digest(root / binding["path"]) == binding["sha256"], f"preflight digest {name}")
        require(preflight["source_commit"] == manifest["source_commit"], f"preflight commit {name}")
        require(preflight["catalog_denominator"] == 7, f"preflight denominator {name}")
        require(preflight["policy_retuning"] == 0, f"preflight policy {name}")
    print("PASS: journal multiclass extension protocol v1")
    print("protocol_manifest=" + digest(pack / "protocol_manifest.json"))


if __name__ == "__main__":
    main()
