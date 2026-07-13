#!/usr/bin/env python3

import csv
from pathlib import Path


PLANNER_MATCHES = Path("results/tuner_planner_demo/profile_matches.csv")
OUTPUT_DIR = Path("results/planner_guided_actual_execution/profile_lists")

WORKLOADS = [
    {
        "planner_workload": "linear_regression",
        "output_file": "linear_regression_profiles.txt",
    },
    {
        "planner_workload": "logreg_small",
        "output_file": "logreg_small_profiles.txt",
    },
    {
        "planner_workload": "polynomial_regression",
        "output_file": "polynomial_regression_profiles.txt",
    },
    {
        "planner_workload": "sobel_edge",
        "output_file": "sobel_edge_profiles.txt",
    },
]

ALLOWED_PLANNER_FAMILIES = {
    "reference",
    "planner_min_feasible",
    "planner_scale_guard",
    "planner_chain_guard",
    "planner_aggressive",
}


def main() -> None:
    if not PLANNER_MATCHES.exists():
        raise FileNotFoundError(f"missing planner matches: {PLANNER_MATCHES}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv(PLANNER_MATCHES)

    for workload in WORKLOADS:
        profiles = resolved_profiles_for_workload(
            rows,
            workload["planner_workload"],
        )

        if not profiles:
            raise ValueError(
                f"no resolved profiles found for workload {workload['planner_workload']}"
            )

        output_path = OUTPUT_DIR / workload["output_file"]
        output_path.write_text(",".join(sorted(profiles)) + "\n")

        print(f"{workload['planner_workload']}: {','.join(sorted(profiles))}")
        print(f"Wrote {output_path}")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def resolved_profiles_for_workload(rows: list[dict], workload_name: str) -> set[str]:
    profiles = set()

    for row in rows:
        if row.get("workload") != workload_name:
            continue

        family = row.get("planned_family", "").strip()
        if family not in ALLOWED_PLANNER_FAMILIES:
            continue

        profile_name = row.get("profile_name", "").strip()
        if profile_name:
            profiles.add(profile_name)

    return profiles


if __name__ == "__main__":
    main()