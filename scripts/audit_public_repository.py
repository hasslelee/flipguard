#!/usr/bin/env python3
"""Audit public-facing changes, sensitive patterns, and inherited exclusions."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "fd53d9f23040fd1490d9816a928dd04ec58eb473"
DEFAULT_OUTPUT = ROOT / "results/github_publication_preview/public_hygiene_report.json"

ALLOWED_CHANGED_PREFIXES = (
    ".github/",
    "docs/assets/",
    "results/github_publication_preview/",
    "scripts/tests/fixtures/public_readme/",
)
ALLOWED_CHANGED_FILES = {
    "README.md",
    "README_ko.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "requirements-ci.txt",
    "docs/ARCHITECTURE.md",
    "docs/CLAIM_SCOPE.md",
    "docs/DECISION_CONTRACTS.md",
    "docs/REPOSITORY_GUIDE.md",
    "docs/REPRODUCIBILITY.md",
    "docs/RESULTS.md",
    "docs/public-number-registry.json",
    "docs/research-history.md",
    "scripts/audit_public_repository.py",
    "scripts/build_github_publication_preview.py",
    "scripts/build_public_brand_assets.py",
    "scripts/lint_public_readme.py",
    "scripts/tests/test_lint_public_readme.py",
}
PUBLIC_SURFACES = {
    "README.md",
    "README_ko.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/ARCHITECTURE.md",
    "docs/CLAIM_SCOPE.md",
    "docs/DECISION_CONTRACTS.md",
    "docs/REPOSITORY_GUIDE.md",
    "docs/REPRODUCIBILITY.md",
    "docs/RESULTS.md",
}
SCANNER_DEFINITION_FILES = {
    ".github/workflows/ci.yml",
    "scripts/audit_public_repository.py",
    "scripts/lint_public_readme.py",
}

SECRET_PATTERNS = {
    "private_key_header": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_classic_token": re.compile(rb"\bghp_[A-Za-z0-9]{30,}\b"),
    "github_fine_grained_token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "slack_token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}


def run_git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, check=True, capture_output=True).stdout


def tracked_files() -> list[Path]:
    return [ROOT / line for line in run_git("ls-files").splitlines() if line]


def changed_files() -> list[str]:
    return sorted(line for line in run_git("diff", "--name-only", f"{BASE}...HEAD").splitlines() if line)


def is_allowed_change(path: str) -> bool:
    return path in ALLOWED_CHANGED_FILES or path.startswith(ALLOWED_CHANGED_PREFIXES)


def text_bytes(path: Path) -> bytes | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data


def build_report() -> dict[str, object]:
    tracked = tracked_files()
    changed = changed_files()
    secret_hits: list[dict[str, str]] = []
    absolute_paths: list[dict[str, object]] = []
    for path in tracked:
        data = text_bytes(path)
        if data is None:
            continue
        rel = str(path.relative_to(ROOT))
        if rel in SCANNER_DEFINITION_FILES:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                secret_hits.append({"path": rel, "pattern": name})
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), start=1):
            if re.search(r"/home/[^/\s]+/|file://|[A-Za-z]:\\Users\\", line):
                absolute_paths.append({"path": rel, "line": number})

    sensitive_names = sorted(
        str(path.relative_to(ROOT))
        for path in tracked
        if re.search(r"(^|/)(id_rsa|id_ed25519|credentials|\.env)$|\.(pem|key|p12)$", str(path.relative_to(ROOT)), flags=re.IGNORECASE)
    )
    official_forms = sorted(
        str(path.relative_to(ROOT))
        for path in tracked
        if path.suffix.lower() in {".hwp", ".hwpx"} or "jkiisc_official_sources_v1/files" in str(path)
    )
    anonymous_review_paths = sorted(
        str(path.relative_to(ROOT))
        for path in tracked
        if str(path.relative_to(ROOT)).startswith(("docs/journal/", "results/journal/"))
    )
    sizes = sorted(
        ({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size} for path in tracked if path.exists()),
        key=lambda item: (-int(item["bytes"]), str(item["path"])),
    )
    unexpected_changes = [path for path in changed if not is_allowed_change(path)]
    changed_absolute = [item for item in absolute_paths if item["path"] in set(changed)]
    changed_oversized = [item for item in sizes if item["path"] in set(changed) and int(item["bytes"]) > 2 * 1024 * 1024]
    public_absolute = [item for item in absolute_paths if item["path"] in PUBLIC_SURFACES]
    hard_failures = {
        "secret_pattern_hits": secret_hits,
        "sensitive_filenames": sensitive_names,
        "unexpected_change_paths": unexpected_changes,
        "changed_absolute_paths": changed_absolute,
        "public_surface_absolute_paths": public_absolute,
        "changed_files_over_2mib": changed_oversized,
    }
    failed = any(hard_failures.values())
    absolute_file_counts = Counter(str(item["path"]) for item in absolute_paths)
    absolute_group_counts: Counter[str] = Counter()
    for path, count in absolute_file_counts.items():
        parts = path.split("/")
        group = "/".join(parts[:3]) if path.startswith("docs/evidence/") else "/".join(parts[:2])
        absolute_group_counts[group] += count
    absolute_summary = {
        "occurrence_count": len(absolute_paths),
        "file_count": len(absolute_file_counts),
        "group_counts": [
            {"group": group, "occurrences": count}
            for group, count in sorted(absolute_group_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "non_evidence_paths": [
            {"path": path, "occurrences": count}
            for path, count in sorted(absolute_file_counts.items())
            if not path.startswith("docs/evidence/")
        ],
    }
    return {
        "schema_version": "flipguard_public_repository_audit_v1",
        "source_research_commit": BASE,
        "status": "FAIL" if failed else ("PASS_WITH_INHERITED_EXCLUSIONS" if official_forms or anonymous_review_paths or absolute_paths else "PASS"),
        "research_implementation_semantics_changed": bool(unexpected_changes),
        "frozen_evidence_changed": any(path.startswith(("docs/evidence/", "results/thesis_grade_protocol/", "results/journal/")) for path in changed),
        "hard_failures": hard_failures,
        "inherited_exclusions": {
            "absolute_local_paths": absolute_summary,
            "official_form_paths": official_forms,
            "anonymous_review_path_count": len(anonymous_review_paths),
            "anonymous_review_roots": ["docs/journal/", "results/journal/"] if anonymous_review_paths else [],
            "handling": "Excluded from curated public artifact export; frozen predecessor files are not rewritten by this documentation branch."
        },
        "largest_tracked_files": sizes[:20],
        "public_export_manifest_sha256": hashlib.sha256((ROOT / ".github/public-export-manifest.json").read_bytes()).hexdigest(),
    }


def write_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing audit report: {path}")
    with tempfile.TemporaryDirectory(prefix="flipguard-public-audit-") as directory:
        rebuilt = Path(directory) / "report.json"
        write_report(rebuilt)
        if rebuilt.read_bytes() != path.read_bytes():
            raise SystemExit("public repository audit deterministic rebuild mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["status"] == "FAIL":
        raise SystemExit("public repository audit contains hard failures")
    print(f"public repository audit: {payload['status']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(args.output)
    else:
        write_report(args.output)
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
