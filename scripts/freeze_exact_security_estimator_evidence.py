#!/usr/bin/env python3
"""Freeze exact-modulus estimator runs with Security V2 admission joins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_MODULE_PATH = (
    REPO_ROOT / "scripts/verify_exact_security_estimator.py"
)
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "verify_exact_security_estimator_for_freezer",
    VERIFY_MODULE_PATH,
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)

RAW_ROOT_DEFAULT = (
    REPO_ROOT
    / "results/thesis_grade_protocol/exact_security_estimator_v1"
)
COMPLETE_COLLECTION_NAME = "ci_run_30534465125"
RECOVERY_COLLECTION_NAMES = (
    "ci_run_30534037217_recovery",
    "ci_run_30534290032_recovery",
    "ci_run_30534465125_recovery",
    "ci_run_30535672009_recovery",
)
OUTPUT_DEFAULT = (
    REPO_ROOT / "docs/evidence/exact_security_estimator_v1"
)
SECURITY_PACK = (
    REPO_ROOT
    / "docs/evidence/security_v2_static_attestation_formal_v2"
)
INPUT_PATH = SECURITY_PACK / "lattice_estimator_inputs_v2.json"
INVENTORY_PATH = SECURITY_PACK / "parameter_inventory_v2.json"
EXPECTED_MODELS = {
    "guidelines-pinned-8f1ff7e": {
        "role": "GUIDELINE_PINNED_REPLAY",
        "commit": "8f1ff7e20a4d3391e3badff1d76825314db225bc",
    },
    "current-3e48ef4": {
        "role": "CURRENT_ESTIMATOR_SENSITIVITY",
        "commit": "3e48ef421ec256afddb3e7d2249a77eab6e9ba12",
    },
}


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_path(path).encode("ascii"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label}={actual!r}; expected {expected!r}"
        )


def verify_checksum_index(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    expected = set()
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file():
            raise ValueError(f"{root}: missing checksum target {relative}")
        require_equal(
            sha256_path(path),
            f"sha256:{digest}",
            f"{root}:{relative}",
        )
        expected.add(relative)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    require_equal(actual, expected, f"{root}: checksum file set")


def input_identities() -> dict[
    tuple[int, tuple[int, ...], tuple[int, ...]],
    str,
]:
    source = load_json(INPUT_PATH)
    identities = {}
    for entry in source["inputs"]:
        payload = VERIFY.signature_payload(entry)
        key = (
            payload["log_n"],
            tuple(payload["exact_q_primes"]),
            tuple(payload["exact_p_primes"]),
        )
        identifier = VERIFY.signature_id(payload)
        if key in identities:
            require_equal(
                identities[key],
                identifier,
                f"input identity {key}",
            )
        identities[key] = identifier
    require_equal(len(identities), 9, "input modulus identities")
    return identities


def static_admission_map() -> dict[str, dict[str, Any]]:
    identities = input_identities()
    inventory = load_json(INVENTORY_PATH)
    rows = inventory["direct_selected"] + inventory["catalog_profiles"]
    mapped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = (
            row["parameters"]["log_n"],
            tuple(row["actual_q_primes"]),
            tuple(row["actual_p_primes"]),
        )
        if key not in identities:
            continue
        identifier = identities[key]
        record = mapped.setdefault(
            identifier,
            {
                "signature_id": identifier,
                "log_n": key[0],
                "candidate_sources": set(),
                "candidate_ids": set(),
                "ciphertext_q_admission": set(),
                "evaluation_key_qp_admission": set(),
                "final_admission": set(),
            },
        )
        record["candidate_sources"].add(row["candidate_source"])
        record["candidate_ids"].add(row["candidate_id"])
        security = row["v2_security"]
        record["ciphertext_q_admission"].add(
            security["ciphertext_q_admission"]
        )
        record["evaluation_key_qp_admission"].add(
            security["evaluation_key_qp_admission"]
        )
        record["final_admission"].add(security["final_admission"])
    require_equal(set(mapped), set(identities.values()), "mapped identities")
    normalized = {}
    for identifier, record in mapped.items():
        for key in (
            "ciphertext_q_admission",
            "evaluation_key_qp_admission",
            "final_admission",
        ):
            require_equal(
                len(record[key]),
                1,
                f"{identifier} {key} consistency",
            )
        normalized[identifier] = {
            "signature_id": identifier,
            "log_n": record["log_n"],
            "candidate_sources": sorted(record["candidate_sources"]),
            "candidate_ids": sorted(record["candidate_ids"]),
            "ciphertext_q_admission": next(
                iter(record["ciphertext_q_admission"])
            ),
            "evaluation_key_qp_admission": next(
                iter(record["evaluation_key_qp_admission"])
            ),
            "final_admission": next(iter(record["final_admission"])),
        }
    return normalized


def result_paths(collection: Path) -> dict[str, Path]:
    paths = {}
    for model_id in EXPECTED_MODELS:
        path = (
            collection
            / "artifacts"
            / f"exact-security-estimator-{model_id}"
            / "results.json"
        )
        if not path.is_file():
            raise ValueError(f"missing estimator result: {path}")
        paths[model_id] = path
    return paths


def estimator_object_count(collection: Path) -> int:
    total = 0
    for model_id in EXPECTED_MODELS:
        path = (
            collection
            / "artifacts"
            / f"exact-security-estimator-{model_id}"
            / "results.json"
        )
        if path.is_file():
            total += len(load_json(path).get("objects", []))
    return total


def estimator_attack_failure_count(collection: Path) -> int:
    total = 0
    for model_id in EXPECTED_MODELS:
        path = (
            collection
            / "artifacts"
            / f"exact-security-estimator-{model_id}"
            / "results.json"
        )
        if path.is_file():
            total += int(
                load_json(path)["summary"]["attack_failures"]
            )
    return total


def verify_collection(
    collection: Path,
    *,
    complete: bool,
) -> dict[str, Any]:
    verify_checksum_index(collection)
    manifest = load_json(collection / "collection_manifest.json")
    if complete:
        require_equal(
            manifest["collection_classification"],
            "COMPLETE_ARTIFACT_COLLECTION",
            "complete collection classification",
        )
        require_equal(
            manifest["workflow_conclusion"],
            "success",
            "complete workflow conclusion",
        )
        require_equal(
            manifest["missing_expected_artifacts"],
            [],
            "complete missing artifacts",
        )
    else:
        classification = manifest["collection_classification"]
        if classification not in {
            "PRE_ESTIMATOR_IMPLEMENTATION_RECOVERY",
            "POST_ESTIMATOR_ARTIFACT_FINALIZATION_RECOVERY",
            "PARTIAL_ESTIMATOR_POSTPROCESSING_RECOVERY",
        }:
            raise ValueError(
                f"unsupported recovery classification: {classification}"
            )
        expected_conclusion = (
            "success"
            if classification
            == "PARTIAL_ESTIMATOR_POSTPROCESSING_RECOVERY"
            else "failure"
        )
        require_equal(
            manifest["workflow_conclusion"],
            expected_conclusion,
            "recovery workflow conclusion",
        )
        if classification == "PRE_ESTIMATOR_IMPLEMENTATION_RECOVERY":
            if not manifest["missing_expected_artifacts"]:
                raise ValueError(
                    "pre-estimator recovery must record missing artifacts"
                )
        else:
            require_equal(
                manifest["missing_expected_artifacts"],
                [],
                "post-estimator recovery artifacts",
            )
            for path in result_paths(collection).values():
                VERIFY.verify(path, INPUT_PATH)
            if estimator_attack_failure_count(collection) == 0:
                raise ValueError(
                    "post-estimator recovery has no attack failures"
                )
    return manifest


def static_object_admission(
    admission: dict[str, Any],
    object_type: str,
) -> str:
    if object_type == "CIPHERTEXT_Q":
        return admission["ciphertext_q_admission"]
    if object_type == "EVALUATION_KEY_QP":
        return admission["evaluation_key_qp_admission"]
    raise ValueError(f"unexpected object type: {object_type}")


def join_model(
    model_id: str,
    result: dict[str, Any],
    admissions: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = EXPECTED_MODELS[model_id]
    require_equal(result["model_id"], model_id, f"{model_id} ID")
    require_equal(
        result["model_role"],
        expected["role"],
        f"{model_id} role",
    )
    require_equal(
        result["estimator"]["git_commit"],
        expected["commit"],
        f"{model_id} estimator commit",
    )
    require_equal(
        result["input"]["sha256"],
        sha256_path(INPUT_PATH),
        f"{model_id} input digest",
    )
    rows = []
    cross_counts: dict[str, int] = {}
    admitted_failures = 0
    admitted_incomplete = 0
    for item in result["objects"]:
        admission = admissions[item["signature_id"]]
        static_status = static_object_admission(
            admission,
            item["object_type"],
        )
        estimator_status = item["status"]
        cross_key = f"{static_status}__{estimator_status}"
        cross_counts[cross_key] = cross_counts.get(cross_key, 0) + 1
        if static_status == "PASS":
            if estimator_status == "FAIL_ESTIMATOR_MODEL":
                admitted_failures += 1
            elif estimator_status == "INCOMPLETE_ATTACK_COVERAGE":
                admitted_incomplete += 1
        rows.append(
            {
                "model_id": model_id,
                "model_role": expected["role"],
                "signature_id": item["signature_id"],
                "log_n": item["log_n"],
                "object_type": item["object_type"],
                "exact_modulus_bit_length": item[
                    "exact_modulus_bit_length"
                ],
                "exact_log2_modulus": item["exact_log2_modulus"],
                "static_v2_object_admission": static_status,
                "static_v2_final_admission": admission[
                    "final_admission"
                ],
                "candidate_sources": admission["candidate_sources"],
                "candidate_ids": admission["candidate_ids"],
                "estimator_status": estimator_status,
                "minimum_log2_rop": item["minimum_log2_rop"],
                "attack_success_count": item["attack_success_count"],
                "attack_failure_count": item["attack_failure_count"],
            }
        )
    if admitted_failures:
        concordance = "FALSIFIED_FOR_STATIC_ADMITTED_OBJECT"
    elif admitted_incomplete:
        concordance = "INCOMPLETE_FOR_STATIC_ADMITTED_OBJECT"
    else:
        concordance = "SUPPORTED_FOR_STATIC_ADMITTED_OBJECTS"
    return rows, {
        "model_id": model_id,
        "model_role": expected["role"],
        "run_status": result["summary"]["run_status"],
        "objects": len(rows),
        "cross_classification_counts": cross_counts,
        "static_admitted_estimator_failures": admitted_failures,
        "static_admitted_estimator_incomplete": admitted_incomplete,
        "static_admission_concordance": concordance,
        "attack_failures": result["summary"]["attack_failures"],
    }


def overall_status(model_summaries: list[dict[str, Any]]) -> str:
    if any(
        summary["static_admitted_estimator_failures"]
        for summary in model_summaries
    ):
        return "FALSIFIED_FOR_STATIC_ADMITTED_OBJECT"
    if any(
        summary["static_admitted_estimator_incomplete"]
        for summary in model_summaries
    ):
        return "PARTIALLY_SUPPORTED"
    return "SUPPORTED_WITH_MODEL_CAVEATS"


def write_joined_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_id",
        "model_role",
        "signature_id",
        "log_n",
        "object_type",
        "exact_modulus_bit_length",
        "exact_log2_modulus",
        "static_v2_object_admission",
        "static_v2_final_admission",
        "candidate_sources",
        "candidate_ids",
        "estimator_status",
        "minimum_log2_rop",
        "attack_success_count",
        "attack_failure_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["candidate_sources"] = "|".join(
                row["candidate_sources"]
            )
            rendered["candidate_ids"] = "|".join(row["candidate_ids"])
            writer.writerow(rendered)


def write_checksums(output: Path) -> None:
    lines = []
    for path in sorted(
        item
        for item in output.rglob("*")
        if item.is_file() and item.name != "SHA256SUMS"
    ):
        lines.append(
            f"{sha256_path(path).removeprefix('sha256:')}  "
            f"{path.relative_to(output).as_posix()}\n"
        )
    (output / "SHA256SUMS").write_text(
        "".join(lines),
        encoding="ascii",
    )


def freeze(
    raw_root: Path,
    output: Path,
    freezer_commit: str,
) -> None:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite exact estimator evidence: {output}"
        )
    complete = raw_root / COMPLETE_COLLECTION_NAME
    complete_manifest = verify_collection(complete, complete=True)
    recovery_manifests = []
    for name in RECOVERY_COLLECTION_NAMES:
        recovery_manifests.append(
            verify_collection(raw_root / name, complete=False)
        )
    recovery_object_counts = [
        estimator_object_count(raw_root / name)
        for name in RECOVERY_COLLECTION_NAMES
    ]
    recovery_attack_failure_counts = [
        estimator_attack_failure_count(raw_root / name)
        for name in RECOVERY_COLLECTION_NAMES
    ]
    recovery_logs = [
        (raw_root / name / "workflow.log").read_text(encoding="utf-8")
        for name in RECOVERY_COLLECTION_NAMES
    ]
    if "git: command not found" not in recovery_logs[0]:
        raise ValueError("first recovery reason is not preserved")
    if "dubious ownership" not in recovery_logs[1]:
        raise ValueError("second recovery reason is not preserved")
    if "python3: command not found" not in recovery_logs[2]:
        raise ValueError("third recovery reason is not preserved")
    partial_results = [
        load_json(path)
        for path in result_paths(
            raw_root / RECOVERY_COLLECTION_NAMES[3]
        ).values()
    ]
    if not all(
        any(
            "use at most 53 bits"
            in attack.get("traceback", "")
            for row in result["objects"]
            for attack in row["attacks"]
            if attack["status"] == "FAILED"
        )
        for result in partial_results
    ):
        raise ValueError("fourth recovery reason is not preserved")

    paths = result_paths(complete)
    admissions = static_admission_map()
    all_rows = []
    model_summaries = []
    results = {}
    for model_id, path in sorted(paths.items()):
        VERIFY.verify(path, INPUT_PATH)
        result = load_json(path)
        results[model_id] = result
        rows, summary = join_model(model_id, result, admissions)
        all_rows.extend(rows)
        model_summaries.append(summary)

    status = overall_status(model_summaries)
    output.mkdir(parents=True)
    shutil.copytree(complete, output / "raw/complete")
    for index, name in enumerate(RECOVERY_COLLECTION_NAMES, start=1):
        shutil.copytree(
            raw_root / name,
            output / f"raw/recovery_{index}",
        )
    write_joined_csv(output / "joined_results.csv", all_rows)
    summary = {
        "schema_version": (
            "flipguard_exact_security_estimator_evidence_summary_v1"
        ),
        "status": status,
        "models": model_summaries,
        "source_signature_rows": 14,
        "unique_modulus_identities": 9,
        "objects_per_model": 18,
        "implementation_recoveries": len(RECOVERY_COLLECTION_NAMES),
        "estimator_objects_in_recoveries": sum(
            recovery_object_counts
        ),
        "attack_failures_in_recoveries": sum(
            recovery_attack_failure_counts
        ),
        "security_policy_modified": False,
        "security_claim": "PARTIALLY_SUPPORTED",
        "exact_distribution_claim_allowed": False,
        "paper_claim_allowed": False,
    }
    (output / "summary.json").write_bytes(canonical_json(summary))
    security_manifest = SECURITY_PACK / "manifest.json"
    manifest = {
        "schema_version": (
            "flipguard_exact_security_estimator_evidence_v1"
        ),
        "evidence_id": "exact_security_estimator_v1",
        "classification": "POST_SECURITY_V2_SENSITIVITY",
        "freezer_commit": freezer_commit,
        "execution_source_commit": complete_manifest["head_sha"],
        "workflow_run_id": complete_manifest["run_id"],
        "workflow_run_url": complete_manifest["run_url"],
        "workflow_conclusion": complete_manifest["workflow_conclusion"],
        "security_policy_id": (
            "security_guidelines_cic2025_table5_2_ternary_128_v2"
        ),
        "security_policy_modified": False,
        "security_v2_pack": {
            "path": SECURITY_PACK.relative_to(REPO_ROOT).as_posix(),
            "manifest_sha256": sha256_path(security_manifest),
            "tree_sha256": tree_digest(SECURITY_PACK),
        },
        "input_sha256": sha256_path(INPUT_PATH),
        "inventory_sha256": sha256_path(INVENTORY_PATH),
        "models": {
            model_id: {
                "role": EXPECTED_MODELS[model_id]["role"],
                "estimator_commit": EXPECTED_MODELS[model_id]["commit"],
                "results_sha256": sha256_path(paths[model_id]),
                "source_commit": results[model_id]["source_commit"],
                "container_image": results[model_id]["environment"][
                    "container_image"
                ],
                "sage_version": results[model_id]["environment"][
                    "sage_version"
                ],
            }
            for model_id in sorted(results)
        },
        "recovery_runs": [
            {
                "run_id": recovery["run_id"],
                "head_sha": recovery["head_sha"],
                "classification": recovery[
                    "collection_classification"
                ],
                "workflow_conclusion": recovery[
                    "workflow_conclusion"
                ],
                "estimator_objects": recovery_object_counts[index],
                "attack_failures": recovery_attack_failure_counts[index],
            }
            for index, recovery in enumerate(recovery_manifests)
        ],
        "summary_sha256": sha256_path(output / "summary.json"),
        "joined_results_sha256": sha256_path(
            output / "joined_results.csv"
        ),
        "status": status,
        "distribution_caveat": (
            "Xs is represented exactly per coefficient; Xe sigma matches "
            "but the Lattigo truncation bound is not modeled."
        ),
        "security_claim": "PARTIALLY_SUPPORTED",
        "paper_claim_allowed": False,
    }
    (output / "manifest.json").write_bytes(canonical_json(manifest))
    readme = """# Exact Security Estimator Evidence V1

This pack preserves two pre-estimator CI recoveries, one post-estimator
artifact-finalization recovery, one partial post-processing recovery, and the
complete guideline-pinned/current exact-modulus sensitivity run. Estimator
results are joined to Security V2 Q/QP object admission; excluded objects are
not reintroduced into the formal candidate set.

The error sigma is matched, but the estimator does not model Lattigo's
explicit Gaussian truncation bound. Security remains PARTIALLY_SUPPORTED and
Security Policy V2 is unchanged.

`paper_claim_allowed=false`.
"""
    (output / "README.md").write_text(readme, encoding="ascii")
    write_checksums(output)


def compare_trees(expected: Path, actual: Path) -> None:
    expected_files = sorted(
        path.relative_to(expected)
        for path in expected.rglob("*")
        if path.is_file()
    )
    actual_files = sorted(
        path.relative_to(actual)
        for path in actual.rglob("*")
        if path.is_file()
    )
    require_equal(actual_files, expected_files, "rebuilt file set")
    for relative in expected_files:
        require_equal(
            (actual / relative).read_bytes(),
            (expected / relative).read_bytes(),
            f"rebuilt file {relative.as_posix()}",
        )


def verify(output: Path, raw_root: Path) -> None:
    verify_checksum_index(output)
    manifest = load_json(output / "manifest.json")
    require_equal(
        manifest["paper_claim_allowed"],
        False,
        "paper claim gate",
    )
    require_equal(
        manifest["security_policy_modified"],
        False,
        "security policy modification",
    )
    with tempfile.TemporaryDirectory(
        prefix="flipguard-exact-security-freeze-",
        dir="/tmp",
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        freeze(raw_root, rebuilt, manifest["freezer_commit"])
        compare_trees(output, rebuilt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--freezer-commit")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    raw_root = (
        args.raw_root
        if args.raw_root.is_absolute()
        else REPO_ROOT / args.raw_root
    )
    output = (
        args.output
        if args.output.is_absolute()
        else REPO_ROOT / args.output
    )
    if args.verify:
        verify(output, raw_root)
        summary = load_json(output / "summary.json")
        print(
            "exact_security_estimator_evidence_v1=VERIFIED "
            f"status={summary['status']} models={len(summary['models'])} "
            "paper_claim_allowed=false"
        )
        return
    if not args.freezer_commit:
        raise ValueError("--freezer-commit is required when freezing")
    freeze(raw_root, output, args.freezer_commit)
    print(
        "exact_security_estimator_evidence_v1=FROZEN "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
