#!/usr/bin/env python3
"""Verify the V9 final realistic baseline closure."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parent
RESULTS = ROOT / "results/thesis_grade_protocol/final_realistic_baseline_closure_v9"
V8 = ROOT / "docs/evidence/focused_external_comparison_v8"
REQUIRED = (
    "manifest.json", "predecessor_v8.json", "environment.json", "literature_baseline_practice.csv",
    "baseline_practice_audit.md", "pairwise_latency_claim_admission.json", "hecate_feasibility.json",
    "orion_preflight.json", "orion_input_manifest.json", "final_baseline_matrix.csv",
    "nonexecution_justification.csv", "execution_accounting.csv", "final_claim_admission.json",
    "manuscript_change_map.md", "fairness_limitations.md", "CHECKPOINT_REPORT.md", "SHA256SUMS",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    missing = [name for name in REQUIRED if not (PACK / name).is_file()]
    if missing:
        raise RuntimeError(f"missing V9 files: {missing}")
    checksums = {}
    for line in (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1); checksums[name] = expected
    for name, expected in checksums.items():
        if digest(PACK / name) != expected:
            raise RuntimeError(f"checksum mismatch: {name}")
    if digest(V8 / "manifest.json") != "a3c345aaf95b29753d5a62c80cd86d8fdae158bc5bbe38f1f83bbd363c92f867":
        raise RuntimeError("V8 predecessor manifest drift")
    subprocess.run(["python3", str(V8 / "verify_focused_external_comparison_v8.py")], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["python3", str(PACK / "direct_repeat_flip_forensics/verify_direct_repeat_flip_forensics.py")], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

    literature = rows(PACK / "literature_baseline_practice.csv")
    if len(literature) != 8 or {row["paper"] for row in literature} != {"HECATE", "ELASM", "DaCapo", "Orion", "HECO", "AutoFHE", "LOHEN", "SLOTHE"}:
        raise RuntimeError("literature audit population drift")
    if any(not row["exact_locator"] or not row["official_url"].startswith("https://") for row in literature):
        raise RuntimeError("literature source locator incomplete")

    pairwise = json.loads((PACK / "pairwise_latency_claim_admission.json").read_text())
    claims = {row["pair_id"]: row for row in pairwise["claims"]}
    if {key: value["state"] for key, value in claims.items()} != {"P1": "BLOCKED_UNSTABLE_ARM", "P2": "BLOCKED_UNSTABLE_ARM", "P3": "PAPER_ADMITTED"}:
        raise RuntimeError("pairwise claim states drift")
    if claims["P3"]["measurement_repeat_flips"] != {"bounded_catalog": 0, "heir_generated": 0} or claims["P3"]["raw_pairs"] != 1800:
        raise RuntimeError("P3 completeness or stability drift")
    if not math.isclose(claims["P3"]["geometric_mean_total_ratio"], 6.393517225744701, rel_tol=1e-12):
        raise RuntimeError("P3 ratio drift")
    common = rows(V8 / "common_executor_records.csv")
    for arm in ("bounded_catalog", "heir_generated"):
        selected = [row for row in common if row["arm"] == arm]
        if len(selected) != 1800 or any(row["decision_flip"] == "True" for row in selected):
            raise RuntimeError(f"P3 arm incomplete or unstable: {arm}")

    hecate = json.loads((PACK / "hecate_feasibility.json").read_text())
    if hecate["final_status"] != "HECATE_PAPER_BASELINE_ONLY" or hecate["plans_attempted"] != 0 or hecate["paper_derived_reimplementation_performed"]:
        raise RuntimeError("HECATE official-mode boundary drift")
    orion = json.loads((PACK / "orion_preflight.json").read_text())
    if orion["preflight_status"] != "PASS" or orion["preflight"]["unique_inputs"] != 10 or orion["preflight"]["argmax_flips"] != 0:
        raise RuntimeError("Orion preflight drift")
    if orion["full_run_performed"] or orion["full_extension_accounting"]["audit_argmax_flips"] != "NOT_EVALUATED":
        raise RuntimeError("Orion missing value was converted to a false result")
    if orion["source"]["official_trained_mlp_weight_artifacts"]:
        raise RuntimeError("Orion blocker contradicts a distributed trained MLP weight")
    if len(orion["preflight"]["records"]) != 10 or any(len(row["decrypted_logits"]) != 10 for row in orion["preflight"]["records"]):
        raise RuntimeError("Orion encrypted logits incomplete")

    matrix = rows(PACK / "final_baseline_matrix.csv")
    measured = {row["system"] for row in matrix if row["evidence_tier"].startswith("EXTERNAL_DECISION_BEARING")}
    if measured != {"Microsoft EVA", "Google HEIR Lattigo", "Google HEIR OpenFHE"}:
        raise RuntimeError("final external measured-provider set drift")
    for system in ("HECATE", "Orion"):
        row = next(row for row in matrix if row["system"] == system)
        if row["evidence_tier"].startswith("EXTERNAL_DECISION_BEARING"):
            raise RuntimeError(f"non-reproduced provider promoted: {system}")
    if len(rows(PACK / "nonexecution_justification.csv")) != 11:
        raise RuntimeError("nonexecution population drift")

    direct = rows(PACK / "tables/table_07_internal_direct_trial_distribution.csv")
    if len(direct) != 1 or (direct[0]["instances"], direct[0]["candidate_trials"], direct[0]["one_trial_instances"], direct[0]["two_trial_instances"]) != ("50", "70", "30", "20"):
        raise RuntimeError("direct trial distribution drift")
    publication = json.loads((RESULTS / "publication_inputs_manifest.json").read_text())
    if publication["table_count"] != 7 or publication["figure_count"] != 5 or publication["docx_hwp_created"]:
        raise RuntimeError("publication input count or format drift")
    for entry in publication["tables"] + publication["figures"]:
        path = ROOT / entry["path"]
        if not path.is_file() or "sha256:" + digest(path) != entry["sha256"]:
            raise RuntimeError(f"publication checksum mismatch: {entry['path']}")
        if path.suffix == ".svg":
            ET.parse(path)
    claims_v9 = json.loads((PACK / "final_claim_admission.json").read_text())
    if not claims_v9["external_comparison_manuscript_ready"] or claims_v9["repository_wide_paper_claim_allowed_unchanged"]:
        raise RuntimeError("claim gate semantics drift")
    manifest = json.loads((PACK / "manifest.json").read_text())
    if manifest["completion_state"] != "FINAL_BASELINE_V8_SUFFICIENT_OPTIONALS_BLOCKED" or not manifest["external_comparison_manuscript_ready"]:
        raise RuntimeError("V9 completion state drift")
    publication_text = [
        PACK / "CHECKPOINT_REPORT.md", PACK / "manuscript_change_map.md",
        PACK / "fairness_limitations.md", PACK / "final_baseline_matrix.csv",
    ] + sorted((PACK / "tables").glob("*.csv"))
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in publication_text)
    for phrase in ("all state-of-the-art autotuners were compared", "comprehensive execution of every ckks compiler", "direct synthesis always wins", "heir is globally optimal"):
        if phrase in corpus.lower():
            raise RuntimeError(f"prohibited overclaim: {phrase}")
    print(json.dumps({"status": "PASS", "completion_state": manifest["completion_state"], "checksums": len(checksums), "tables": publication["table_count"], "figures": publication["figure_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
