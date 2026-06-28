#!/usr/bin/env python3

import csv
from pathlib import Path
from typing import Dict, List


PROFILE_SUMMARY = Path("results/ckks_tabular_profile_sweep_summary/current/profile_summary.csv")
OUTPUT_ROOT = Path("results/ckks_profile_parameter_analysis/current")


PROFILE_METADATA = {
    "default": {
        "log_n": 14,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "log_default_scale": 45,
        "profile_class": "default_chain",
    },
    "scale42": {
        "log_n": 14,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "log_default_scale": 42,
        "profile_class": "scale_reduced_default_chain",
    },
    "scale40": {
        "log_n": 14,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "log_default_scale": 40,
        "profile_class": "scale_reduced_default_chain",
    },
    "scale38": {
        "log_n": 14,
        "q_prime_count": 7,
        "p_prime_count": 1,
        "log_default_scale": 38,
        "profile_class": "scale_reduced_default_chain",
    },
    "deep_chain_8_scale45": {
        "log_n": 15,
        "q_prime_count": 8,
        "p_prime_count": 1,
        "log_default_scale": 45,
        "profile_class": "deep_chain",
    },
    "deep_chain_9_scale45": {
        "log_n": 15,
        "q_prime_count": 9,
        "p_prime_count": 1,
        "log_default_scale": 45,
        "profile_class": "deep_chain",
    },
    "short_chain_6_scale42": {
        "log_n": 14,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "log_default_scale": 42,
        "profile_class": "short_chain",
    },
    "short_chain_6_scale40": {
        "log_n": 14,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "log_default_scale": 40,
        "profile_class": "short_chain",
    },
    "short_chain_6_scale38": {
        "log_n": 14,
        "q_prime_count": 6,
        "p_prime_count": 1,
        "log_default_scale": 38,
        "profile_class": "short_chain",
    },
    "short_chain_5": {
        "log_n": 14,
        "q_prime_count": 5,
        "p_prime_count": 1,
        "log_default_scale": 40,
        "profile_class": "short_chain",
    },
    "short_chain_3": {
        "log_n": 14,
        "q_prime_count": 3,
        "p_prime_count": 1,
        "log_default_scale": 35,
        "profile_class": "short_chain",
    },
}


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        raise ValueError(f"no rows to write: {path}")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def to_int(value: str) -> int:
    if value == "":
        return 0
    return int(float(value))


def to_float(value: str) -> float:
    if value == "":
        return 0.0
    return float(value)


def summarize_profile_safety(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}

    for row in rows:
        grouped.setdefault(row["profile"], []).append(row)

    out = []

    for profile, profile_rows in sorted(grouped.items()):
        metadata = PROFILE_METADATA.get(profile, {})

        candidate_count = len(profile_rows)
        strict_safe_count = sum(1 for row in profile_rows if row["strict_safe"] == "true")
        failed_candidate_count = sum(1 for row in profile_rows if to_int(row["failed_runs"]) > 0)
        rejected_candidate_count = candidate_count - strict_safe_count

        total_failed_runs = sum(to_int(row["failed_runs"]) for row in profile_rows)
        total_decision_flips = sum(to_int(row["sum_decision_flips"]) for row in profile_rows)
        total_score_violations = sum(to_int(row["sum_score_error_violations"]) for row in profile_rows)

        completed_latencies = [
            to_float(row["mean_total_ms"])
            for row in profile_rows
            if row["mean_total_ms"] != ""
        ]
        mean_total_ms = sum(completed_latencies) / len(completed_latencies) if completed_latencies else 0.0

        out.append({
            "profile": profile,
            "profile_class": str(metadata.get("profile_class", "")),
            "log_n": str(metadata.get("log_n", "")),
            "slots": str(2 ** (int(metadata["log_n"]) - 1)) if "log_n" in metadata else "",
            "q_prime_count": str(metadata.get("q_prime_count", "")),
            "p_prime_count": str(metadata.get("p_prime_count", "")),
            "log_default_scale": str(metadata.get("log_default_scale", "")),
            "candidate_count": str(candidate_count),
            "strict_safe_candidate_count": str(strict_safe_count),
            "rejected_candidate_count": str(rejected_candidate_count),
            "failed_candidate_count": str(failed_candidate_count),
            "total_failed_runs": str(total_failed_runs),
            "total_decision_flips": str(total_decision_flips),
            "total_score_error_violations": str(total_score_violations),
            "mean_total_ms_completed_candidates": f"{mean_total_ms:.10f}",
        })

    return out


def write_latex(rows: List[Dict[str, str]]) -> None:
    lines = []
    lines.append(r"\begin{tabular}{lrrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Profile & $\log N$ & Slots & $|Q|$ & Scale & Safe & Failed & Flips \\")
    lines.append(r"\midrule")

    for row in rows:
        profile = row["profile"].replace("_", r"\_")
        lines.append(
            f"{profile} & {row['log_n']} & {row['slots']} & {row['q_prime_count']} & "
            f"{row['log_default_scale']} & {row['strict_safe_candidate_count']} & "
            f"{row['total_failed_runs']} & {row['total_decision_flips']} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    (OUTPUT_ROOT / "profile_parameter_safety_table.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_readme(rows: List[Dict[str, str]]) -> None:
    safest = max(rows, key=lambda row: int(row["strict_safe_candidate_count"]))
    fastest_risky = min(
        rows,
        key=lambda row: float(row["mean_total_ms_completed_candidates"]),
    )

    text = f"""FlipGuard CKKS profile parameter and safety analysis

This analysis summarizes CKKS profile metadata and observed safety outcomes across the repeated tabular profile sweep.

Key observations:
- profile with the largest number of strict safe candidates: {safest["profile"]} ({safest["strict_safe_candidate_count"]})
- profile with the lowest mean latency among completed candidates: {fastest_risky["profile"]} ({fastest_risky["mean_total_ms_completed_candidates"]} ms)
- short-chain profiles can reduce latency but may increase decision flips, output error violations, or level-exhaustion failures.
- deep-chain profiles provide more capacity, but they are not automatically fastest.

Scope:
- Security level is not independently estimated in this script.
- The table reports parameter-shape metadata used by FlipGuard experiments.
- A formal security estimate should be added separately with an LWE/RLWE estimator or library-provided security metadata.
"""

    (OUTPUT_ROOT / "README.txt").write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    rows = read_rows(PROFILE_SUMMARY)
    summary = summarize_profile_safety(rows)

    write_rows(OUTPUT_ROOT / "profile_parameter_safety.csv", summary)
    write_latex(summary)
    write_readme(summary)

    print(f"wrote {OUTPUT_ROOT / 'profile_parameter_safety.csv'}")
    print(f"wrote {OUTPUT_ROOT / 'profile_parameter_safety_table.tex'}")
    print(f"wrote {OUTPUT_ROOT / 'README.txt'}")


if __name__ == "__main__":
    main()
