#!/usr/bin/env python3
"""Verify and optionally rebuild FlipGuard V3 publication inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def tree_files(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify(root: Path, repo_root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    publication = json.loads((root / "publication_status.json").read_text())
    if (
        manifest["artifact_id"] != "flipguard_paper_artifacts_v3"
        or manifest["publication_status"] != "FINAL_ADMISSIBLE"
        or manifest["paper_claim_allowed"] is not True
        or manifest["thesis_prose_generated"] is not False
        or manifest["formal_catalog_denominators"]
        != {"all": 700, "confirmatory": 560}
        or manifest["seed_roles_separated"] is not True
        or manifest["margin_theorem_policy_separated"] is not True
        or manifest["structural_negative_result_preserved"] is not True
        or re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]) is None
        or publication["generated_tables"] != 13
        or publication["generated_figures"] != 10
        or publication["provider_eva_role"] != "APPENDIX_ONLY"
    ):
        raise ValueError("V3 publication status changed")
    for relative, record in manifest["files"].items():
        path = root / relative
        if (
            not path.is_file()
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
        ):
            raise ValueError(f"{relative}: V3 artifact changed")
    for binding in manifest["input_bindings"].values():
        if sha256(repo_root / binding["path"]) != binding["sha256"]:
            raise ValueError(f"{binding['path']}: V3 input changed")

    tables = sorted((root / "tables").glob("*.md"))
    figures = sorted((root / "figures").glob("*.svg"))
    if len(tables) != 13 or len(figures) != 10:
        raise ValueError("V3 table/figure count changed")
    structural_table = (
        root / "tables/09_structural_polynomial_holdout.md"
    ).read_text()
    structural_figure = (
        root / "figures/figure_08_structural_scope_matrix.svg"
    ).read_text()
    if (
        "| 25 | 25 | 24 | 1 | 0 | 0 | 1 | 0 |" not in structural_table
        or 'data-structural-pass="24"' not in structural_figure
        or 'data-rejected="1"' not in structural_figure
    ):
        raise ValueError("structural negative result was omitted")
    theorem = (
        root / "publication_inputs/equation_list.md"
    ).read_text()
    if "e_c(x) < m(x)" not in theorem or "e_c(x) < rho*m(x)" not in theorem:
        raise ValueError("margin theorem and policy were conflated")
    headline = "\n".join(path.read_text() for path in tables + figures)
    for forbidden in ("1,100", "93.64%", "3,300", "global optimum"):
        if forbidden in headline:
            raise ValueError(f"forbidden V3 headline token: {forbidden}")
    if "Provider" in "\n".join(path.read_text() for path in tables):
        raise ValueError("provider evidence leaked into a main table")
    if publication["manuscript_claim_scan"]["headline_claims_inserted"]:
        raise ValueError("V3 builder wrote thesis prose")

    expected = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            expected.append(
                f"{sha256(path).removeprefix('sha256:')}  "
                f"{path.relative_to(root)}\n"
            )
    if (root / "SHA256SUMS").read_text() != "".join(expected):
        raise ValueError("V3 SHA256SUMS mismatch")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(
            "results/thesis_grade_protocol/paper_artifacts_v3/final"
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    repo_root = args.repo_root.resolve()
    manifest = verify(root, repo_root)
    if args.rebuild:
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "final"
            subprocess.run(
                [
                    "python3",
                    str(repo_root / "scripts/build_flipguard_v3_paper_artifacts.py"),
                    "--output",
                    str(rebuilt),
                    "--source-commit",
                    manifest["source_commit"],
                    "--skip-verify",
                ],
                cwd=repo_root,
                check=True,
            )
            if tree_files(root) != tree_files(rebuilt):
                raise ValueError("V3 deterministic rebuild mismatch")
    print(
        "paper_artifacts_v3=VERIFIED status=FINAL_ADMISSIBLE "
        f"tables=13 figures=10 rebuild={str(args.rebuild).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
