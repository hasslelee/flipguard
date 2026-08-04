#!/usr/bin/env python3
"""Build the deterministic authorless JKIISC template-ready content pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from lint_flipguard_jkiisc_v1 import audit_manuscript


OUTPUT = Path("results/journal/flipguard_jkiisc_v1")
SCHEMA = "flipguard_jkiisc_content_pack_v1"


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def source_commit(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def collect(root: Path, commit: str) -> dict[str, bytes]:
    manuscript = (root / "docs/journal/01_manuscript_ko.md").read_text(encoding="utf-8")
    abstracts = (root / "docs/journal/abstract_ko_en.md").read_text(encoding="utf-8")
    with (root / "docs/journal/figure_table_map.csv").open(newline="", encoding="utf-8") as handle:
        map_rows = list(csv.DictReader(handle))
    figure_rows = sorted(
        (row for row in map_rows if row["type"] == "Figure"),
        key=lambda row: int(row["number"]),
    )
    figure_names = {
        int(row["number"]): f"figures/figure_{int(row['number']):02d}.svg"
        for row in figure_rows
    }
    rendered = manuscript.replace("{{ABSTRACTS}}", abstracts.strip())
    for number, name in figure_names.items():
        rendered = rendered.replace(f"{{{{FIGURE_{number:02d}}}}}", f"![Fig. {number}]({name})")
    lint = audit_manuscript(root, rendered, rendered=True)
    if lint["status"] != "PASS":
        raise RuntimeError("rendered manuscript lint failed: " + repr(lint["findings"]))

    files: dict[str, bytes] = {
        "manuscript_ko.md": rendered.encode("utf-8"),
        "abstract_ko_en.md": abstracts.encode("utf-8"),
        "authorless_submission_metadata.json": (root / "docs/journal/authorless_submission_metadata.json").read_bytes(),
        "claim_traceability.csv": (root / "docs/journal/claim_traceability.csv").read_bytes(),
        "figure_table_map.csv": (root / "docs/journal/figure_table_map.csv").read_bytes(),
        "number_registry.json": (root / "docs/journal/number_registry.json").read_bytes(),
        "page_budget.md": (root / "docs/journal/page_budget.md").read_bytes(),
        "reference_map.csv": (root / "docs/journal/reference_map.csv").read_bytes(),
        "references.bib": (root / "docs/thesis/references.bib").read_bytes(),
        "lint_report.json": canonical(lint).encode("utf-8"),
    }
    for row in figure_rows:
        files[figure_names[int(row["number"])]] = (root / row["source_path"]).read_bytes()

    manuscript_text = rendered
    build_report = {
        "artifact_status": "TEMPLATE_READY_AUTHORLESS_CONTENT_PACK",
        "author_information_present": False,
        "citations": lint["citations"],
        "content_source_commit": commit,
        "figures": lint["figures"],
        "hwp_conversion": "NOT_PERFORMED",
        "line_count": len(manuscript_text.splitlines()),
        "manuscript_characters": len(manuscript_text),
        "manuscript_words_whitespace": len(manuscript_text.split()),
        "official_page_hard_limit": 20,
        "page_budget_estimate": "9-11 after official HWP layout",
        "schema_version": SCHEMA,
        "tables": lint["tables"],
    }
    files["build_report.json"] = canonical(build_report).encode("utf-8")
    return files


def input_bindings(root: Path) -> list[dict]:
    paths = [
        "docs/journal/00_jkiisc_contract.md",
        "docs/journal/01_manuscript_ko.md",
        "docs/journal/abstract_ko_en.md",
        "docs/journal/authorless_submission_metadata.json",
        "docs/journal/claim_traceability.csv",
        "docs/journal/figure_table_map.csv",
        "docs/journal/number_registry.json",
        "docs/journal/page_budget.md",
        "docs/journal/reference_map.csv",
        "docs/evidence/jkiisc_official_sources_v1/source_manifest.json",
        "docs/evidence/journal_multiclass_extension_final_v1/manifest.json",
        "docs/evidence/journal_multiclass_claim_admission_v2/manifest.json",
        "docs/evidence/paper_claim_admission_v1/manifest.json",
        "results/thesis_grade_protocol/paper_artifacts_v3/final/manifest.json",
    ]
    return [{"path": path, "sha256": digest(root / path)} for path in paths]


def build_manifest(root: Path, commit: str, files: dict[str, bytes]) -> dict:
    return {
        "artifact_id": "flipguard_jkiisc_v1",
        "artifact_status": "TEMPLATE_READY_AUTHORLESS_CONTENT_PACK",
        "content_source_commit": commit,
        "core_artifacts_modified": False,
        "generated_files": {
            name: {"sha256": digest_bytes(content), "size": len(content)}
            for name, content in sorted(files.items())
        },
        "inputs": input_bindings(root),
        "new_dataset_or_model": 0,
        "policy_retuning": 0,
        "schema_version": SCHEMA,
    }


def write_pack(root: Path, output: Path, commit: str, *, force: bool) -> None:
    if output.exists():
        if not force:
            raise RuntimeError(f"output exists: {output}; use --force for deterministic rebuild")
        shutil.rmtree(output)
    files = collect(root, commit)
    manifest = build_manifest(root, commit, files)
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    checksums = []
    for path in sorted(candidate for candidate in output.rglob("*") if candidate.is_file()):
        name = str(path.relative_to(output))
        checksums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}")
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(OUTPUT))
    parser.add_argument("--source-commit")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    commit = args.source_commit or source_commit(root)
    write_pack(root, root / args.output, commit, force=args.force)
    print(f"jkiisc_content_pack=BUILT output={args.output} source_commit={commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
