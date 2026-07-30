#!/usr/bin/env python3
"""Freeze and deterministically verify the BSDS500 Harris evidence pack."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "scripts/freeze_bsds500_sobel_evidence.py"
HELPER_SPEC = importlib.util.spec_from_file_location(
    "freeze_bsds500_sobel_evidence",
    HELPER_PATH,
)
HELPER = importlib.util.module_from_spec(HELPER_SPEC)
assert HELPER_SPEC.loader is not None
HELPER_SPEC.loader.exec_module(HELPER)

DEFAULT_RUN_ROOT = Path(
    "results/thesis_grade_protocol/non_tabular_harris_holdout_v1/run_a4ccd0b"
)
DEFAULT_OUTPUT = Path(
    "docs/evidence/non_tabular_harris_holdout_v1"
)
INPUT_ROOT = Path(
    "datasets/vision_suite/bsds500/harris_corner_response"
)
SOURCE_ARCHIVE = Path(
    "results/source_datasets/bsds500/BSR_bsds500.tgz"
)

SCHEMA_VERSION = "flipguard_non_tabular_harris_evidence_v1"
EXECUTION_COMMIT = "a4ccd0be562c4dac2ddac52b95bcaeb112e30d3b"
DIRECT_POLICY_DIGEST = (
    "sha256:"
    "503240fbf1f0bb1c43c8ed216ae6360771cc3b23ff4224efa84926f470646603"
)
SECURITY_POLICY_DIGEST = (
    "sha256:"
    "855d44820387879ea5cce97b945bbb7e14d869f1a1672cf4d4842713b743a055"
)
EXTRACTION_POLICY_DIGEST = (
    "sha256:"
    "90befad9bdf9c58b817a54664348b421233e5834995a2648793024892b5cb291"
)
EXECUTION_ADAPTER = "bsds500_harris_square_rescale_graph_adapter_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    return HELPER.sha256_path(path)


def canonical_json(value: Any) -> bytes:
    return HELPER.canonical_json(value)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_run(
    run_root: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    run_manifest = json.loads(
        (run_root / "run_manifest.json").read_text(encoding="ascii")
    )
    selection = json.loads(
        (run_root / "selection.json").read_text(encoding="ascii")
    )
    audit = json.loads(
        (run_root / "locked_audit.json").read_text(encoding="ascii")
    )
    if run_manifest["source_commit"] != EXECUTION_COMMIT or \
            run_manifest["origin_commit"] != EXECUTION_COMMIT or \
            not run_manifest["working_tree_clean"]:
        raise ValueError("execution source provenance changed")
    if run_manifest["execution_critical_source_digest"] != \
            canonical_digest(run_manifest["execution_source_files"]):
        raise ValueError("execution source closure digest changed")
    if run_manifest["direct_policy"]["digest"] != \
            DIRECT_POLICY_DIGEST or \
            run_manifest["security_policy"]["digest"] != \
            SECURITY_POLICY_DIGEST or \
            run_manifest["extraction_policy"]["digest"] != \
            EXTRACTION_POLICY_DIGEST:
        raise ValueError("run policy digest changed")
    if run_manifest["direct_policy"]["modified"]:
        raise ValueError("run claims Direct Policy modification")
    if run_manifest["graph_adapter"]["id"] != EXECUTION_ADAPTER:
        raise ValueError("run graph adapter changed")

    binary_paths = {
        "autotune": run_root / "bin/flipguard-harris-autotune",
        "audit": run_root / "bin/flipguard-harris-audit",
    }
    for name, path in binary_paths.items():
        if sha256_path(path) != run_manifest["binary_sha256"][name]:
            raise ValueError(f"{name} binary digest mismatch")
    input_paths = {
        "model": INPUT_ROOT / "model.json",
        "configuration_validation":
            INPUT_ROOT / "configuration_validation.csv",
        "locked_audit_test": INPUT_ROOT / "locked_audit_test.csv",
        "extraction_manifest": INPUT_ROOT / "extraction_manifest.json",
        "source_archive": SOURCE_ARCHIVE,
    }
    for name, path in input_paths.items():
        if sha256_path(path) != run_manifest["inputs"][name]:
            raise ValueError(f"{name} input digest mismatch")

    plan = selection["plan"]
    contract = plan["contract"]
    if selection["execution_adapter"] != EXECUTION_ADAPTER or \
            plan["direct_policy_digest"] != DIRECT_POLICY_DIGEST or \
            plan["security_policy_digest"] != SECURITY_POLICY_DIGEST:
        raise ValueError("selection policy or adapter changed")
    if contract["model_type"] != "harris_corner_response" or \
            contract["graph"]["multiplicative_depth"] != 2 or \
            contract["deployment"]["rescale_levels_consumed"] != 4 or \
            contract["deployment"]["required_q_primes"] != 6:
        raise ValueError("selection graph contract changed")
    if contract["decision"]["validation_samples"] != 200 or \
            contract["decision"]["certifiable_samples"] != 200 or \
            contract["decision"]["ambiguous_samples"] != 0:
        raise ValueError("selection decision contract changed")
    if contract["decision"]["safety_factor"] != 0.5 or \
            contract["decision"]["margin_floor"] != 0.001 or \
            contract["deployment"]["max_encrypted_trials"] != 4:
        raise ValueError("frozen decision/repair policy changed")
    if selection["outcome"] != "SELECTED" or \
            selection["trials_used"] != 1 or \
            selection["encrypted_key_runs"] != 3 or \
            selection["encrypted_sample_evaluations"] != 600:
        raise ValueError("selection aggregate changed")
    if len(selection["trials"]) != 1 or \
            selection["trials"][0]["status"] != "SAFE":
        raise ValueError("selection trial sequence changed")
    trial = selection["trials"][0]
    if selection["selected"] != trial["candidate"]:
        raise ValueError("selected candidate is not first SAFE trial")
    HELPER.validate_candidate_security(trial["candidate"])
    selection_ledger = HELPER.validate_ledger(
        trial,
        contract,
        "val",
    )
    if selection_ledger["decision_flips"] != 0 or \
            selection_ledger["error_violations"] != 0:
        raise ValueError("selection SAFE evidence changed")

    audit_trial = audit["audit_trial"]
    if audit["execution_adapter"] != EXECUTION_ADAPTER or \
            audit["outcome"] != "LOCKED_AUDIT_PASS" or \
            audit["retuning_performed"] or \
            audit["selected_candidate"] != selection["selected"] or \
            audit_trial["candidate"] != selection["selected"]:
        raise ValueError("locked audit candidate identity changed")
    audit_contract = audit["audit_contract"]
    if audit_contract["decision"]["validation_samples"] != 200 or \
            audit_contract["decision"]["certifiable_samples"] != 199 or \
            audit_contract["decision"]["ambiguous_samples"] != 1:
        raise ValueError("locked audit contract changed")
    audit_ledger = HELPER.validate_ledger(
        audit_trial,
        audit_contract,
        "test",
    )
    if audit_trial["status"] != "SAFE" or \
            audit_ledger["decision_flips"] != 0 or \
            audit_ledger["error_violations"] != 0:
        raise ValueError("locked audit SAFE evidence changed")

    validation_images = {
        row["image_id"] for row in trial["sample_ledger"]
    }
    audit_images = {
        row["image_id"] for row in audit_trial["sample_ledger"]
    }
    if validation_images & audit_images or \
            len(validation_images) != 50 or \
            len(audit_images) != 50:
        raise ValueError("validation/audit image clusters overlap")
    validation_rows = {
        int(row["row_id"]) for row in trial["sample_ledger"]
    }
    audit_rows = {
        int(row["row_id"]) for row in audit_trial["sample_ledger"]
    }
    if validation_rows & audit_rows or \
            len(validation_rows) != 200 or \
            len(audit_rows) != 200:
        raise ValueError("validation/audit row identities overlap")
    return run_manifest, selection, audit, {
        "selection_ledger": selection_ledger,
        "audit_ledger": audit_ledger,
    }


def write_ledger(
    path: Path,
    stage: str,
    trials: list[dict[str, Any]],
) -> None:
    HELPER.write_ledger(path, stage, trials)


def build(
    run_root: Path,
    output_root: Path,
    builder_commit: str,
    force: bool,
) -> None:
    run_manifest, selection, audit, derived = validate_run(run_root)
    if output_root.exists():
        if not force:
            raise FileExistsError(
                f"{output_root} exists; use --force"
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    raw = output_root / "raw"
    inputs = output_root / "inputs"
    raw.mkdir()
    inputs.mkdir()

    for name in (
        "run_manifest.json",
        "selection.json",
        "locked_audit.json",
    ):
        shutil.copyfile(run_root / name, raw / name)
    (raw / "execution_source_files.json").write_bytes(
        canonical_json(run_manifest["execution_source_files"])
    )
    for name in (
        "model.json",
        "configuration_validation.csv",
        "locked_audit_test.csv",
        "extraction_manifest.json",
        "SHA256SUMS",
    ):
        shutil.copyfile(INPUT_ROOT / name, inputs / name)

    write_ledger(
        output_root / "selection_sample_ledger.csv",
        "configuration_validation",
        selection["trials"],
    )
    write_ledger(
        output_root / "audit_sample_ledger.csv",
        "locked_audit",
        [audit["audit_trial"]],
    )

    trial = selection["trials"][0]
    audit_trial = audit["audit_trial"]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "SUPPORTED",
        "paper_claim_allowed": False,
        "block_reason": (
            "manual post-extension claim admission and paper review are pending"
        ),
        "scope": (
            "BSDS500 single-window Harris response threshold under "
            "scalar-replicated packing"
        ),
        "source": {
            "dataset": "BSDS500",
            "train_threshold_images": 100,
            "validation_images": 50,
            "audit_images": 50,
            "patches_per_image": 4,
            "validation_audit_image_overlap": 0,
        },
        "selection": {
            "outcome": selection["outcome"],
            "trials": selection["trials_used"],
            "repairs": 0,
            "fresh_key_runs": selection["encrypted_key_runs"],
            "encrypted_sample_evaluations":
                selection["encrypted_sample_evaluations"],
            "selected_candidate": trial["candidate"]["id"],
            "selected_flips": trial["decision_flips"],
            "selected_violations": trial["error_violations"],
            "selected_max_budget_usage":
                trial["max_error_budget_usage"],
            "security_headroom_bits":
                trial["candidate"]["security"]["headroom_bits"],
        },
        "locked_audit": {
            "outcome": audit["outcome"],
            "status": audit_trial["status"],
            "fresh_key_runs": audit_trial["key_repeats_completed"],
            "encrypted_sample_evaluations":
                audit_trial["encrypted_sample_evaluations"],
            "v_cert": audit_trial["v_cert"],
            "v_amb": audit_trial["v_amb"],
            "flips": audit_trial["decision_flips"],
            "violations": audit_trial["error_violations"],
            "max_budget_usage":
                audit_trial["max_error_budget_usage"],
            "retuning": int(audit["retuning_performed"]),
            "candidate_identity_equal":
                audit["selected_candidate"] ==
                audit_trial["candidate"],
        },
        "accounting": {
            "total_candidate_trials": 2,
            "total_fresh_key_runs": 6,
            "total_encrypted_sample_evaluations": 1200,
        },
        "claim_boundary": {
            "non_tabular_harris_holdout": "SUPPORTED",
            "multi_graph_vision_extension": "SUPPORTED",
            "structural_generalization": "PARTIALLY_SUPPORTED",
            "arbitrary_graph_generalization": "NOT_EVALUATED",
            "cnn_generalization": "NOT_EVALUATED",
            "full_image_corner_accuracy": "NOT_EVALUATED",
        },
    }
    (output_root / "summary.json").write_bytes(
        canonical_json(summary)
    )
    failure = {
        "schema_version": SCHEMA_VERSION,
        "scientific_negative_results": [],
        "execution_failures": [],
        "ambiguous_locked_audit_samples": [
            {
                "row_id": row["row_id"],
                "image_id": row["image_id"],
                "margin": row["margin"],
                "disposition": "excluded_from_Vcert_by_frozen_margin_floor",
            }
            for row in audit_trial["sample_ledger"]
            if row["key_run"] == 1 and not row["certifiable"]
        ],
    }
    (output_root / "failure_records.json").write_bytes(
        canonical_json(failure)
    )
    readme = """# Non-Tabular BSDS500 Harris Holdout Evidence V1

This pack freezes the predeclared BSDS500 Harris selection and no-retuning
locked audit. The first analysis-derived candidate was SAFE. The byte-identical
selected literal remained SAFE on 50 disjoint test-image clusters.

The raw JSON and flattened CSV ledgers retain every patch-by-key CKKS score.
`scripts/freeze_bsds500_harris_evidence.py --verify` rebuilds this pack and
recomputes all margins, decisions, errors, budgets, flips, violations, source
closure, and aggregate maxima.

Claim scope is one scalar-replicated 5x5 Harris response graph. This pack does
not support arbitrary graphs, packed full-image execution, corner-detection
accuracy, or CNN generalization. `paper_claim_allowed` remains false.
"""
    (output_root / "README.md").write_text(
        readme,
        encoding="ascii",
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": "non_tabular_harris_holdout_v1",
        "execution_commit": EXECUTION_COMMIT,
        "evidence_builder_commit": builder_commit,
        "execution_critical_source_digest":
            run_manifest["execution_critical_source_digest"],
        "binary_sha256": run_manifest["binary_sha256"],
        "policies": {
            "direct_policy_v2": DIRECT_POLICY_DIGEST,
            "security_policy_v2": SECURITY_POLICY_DIGEST,
            "extraction_policy": EXTRACTION_POLICY_DIGEST,
        },
        "raw_run": {
            "path": str(run_root),
            "run_manifest_sha256":
                sha256_path(run_root / "run_manifest.json"),
            "selection_sha256":
                sha256_path(run_root / "selection.json"),
            "locked_audit_sha256":
                sha256_path(run_root / "locked_audit.json"),
        },
        "summary": summary,
        "derived_validation": derived,
    }
    (output_root / "manifest.json").write_bytes(
        canonical_json(manifest)
    )
    checksum_names = sorted(
        str(path.relative_to(output_root))
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    checksums = "".join(
        f"{sha256_path(output_root / name).removeprefix('sha256:')}  {name}\n"
        for name in checksum_names
    )
    (output_root / "SHA256SUMS").write_text(
        checksums,
        encoding="ascii",
    )


def verify(run_root: Path, output_root: Path) -> None:
    manifest = json.loads(
        (output_root / "manifest.json").read_text(encoding="ascii")
    )
    builder_commit = manifest["evidence_builder_commit"]
    with tempfile.TemporaryDirectory(
        prefix="flipguard-harris-evidence-"
    ) as temporary:
        rebuilt = Path(temporary) / "pack"
        build(
            run_root,
            rebuilt,
            builder_commit=builder_commit,
            force=False,
        )
        expected_files = sorted(
            str(path.relative_to(output_root))
            for path in output_root.rglob("*")
            if path.is_file()
        )
        rebuilt_files = sorted(
            str(path.relative_to(rebuilt))
            for path in rebuilt.rglob("*")
            if path.is_file()
        )
        if expected_files != rebuilt_files:
            raise ValueError("evidence file set changed")
        for name in expected_files:
            if (output_root / name).read_bytes() != \
                    (rebuilt / name).read_bytes():
                raise ValueError(
                    f"evidence replay mismatch: {name}"
                )
    print(
        "bsds500_harris_evidence=PASS "
        f"manifest={sha256_path(output_root / 'manifest.json')} "
        "selection_observations=600 audit_observations=600 "
        "audit_status=SAFE retuning=0"
    )


def main() -> None:
    args = parse_args()
    run_root = (REPO_ROOT / args.run_root).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()
    if args.verify:
        verify(run_root, output_root)
        return
    builder_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    build(
        run_root,
        output_root,
        builder_commit=builder_commit,
        force=args.force,
    )
    print(
        "bsds500_harris_evidence=FROZEN "
        f"output={output_root} "
        f"manifest={sha256_path(output_root / 'manifest.json')}"
    )


if __name__ == "__main__":
    main()
