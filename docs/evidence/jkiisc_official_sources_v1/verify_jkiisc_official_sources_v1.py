#!/usr/bin/env python3
"""Verify byte-identical KIISC official source files and extracted rules."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PACK = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((PACK / "source_manifest.json").read_text(encoding="utf-8"))
    requirements = json.loads((PACK / "requirements.json").read_text(encoding="utf-8"))
    assert manifest["official_domain"] == "kiisc.or.kr"
    assert manifest["source_files_modified"] is False
    assert len(manifest["sources"]) == 5
    for source in manifest["sources"]:
        path = PACK / source["file"]
        assert path.is_file(), path
        assert path.stat().st_size == source["file_size"], path
        assert digest(path) == source["sha256"], path
        assert source["url"].startswith("https://kiisc.or.kr/"), source["url"]
    assert (PACK / "files/submission_form.hwp").read_bytes().startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
    assert (PACK / "files/publication_form.hwp").read_bytes().startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
    assert (PACK / "files/submission_rules_2024-03-15.pdf").read_bytes().startswith(b"%PDF")
    assert requirements["author_information_in_initial_manuscript"] is False
    assert requirements["initial_submission_format"] == "authorless PDF"
    assert requirements["base_publication_pages"] == 6
    assert requirements["extra_page_fee_from_page"] == 7
    assert requirements["manuscript_hard_limit_a4_pages"] == 20
    assert requirements["abstract"]["korean_max_characters"] == 700
    assert requirements["abstract"]["english_max_words"] == 250
    assert requirements["abstract"]["keywords_max"] == 5
    assert requirements["two_column"] is True
    assert requirements["line_spacing_percent"] == 150
    for line in (PACK / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        assert digest(PACK / name) == expected, name
    print("jkiisc_official_sources_v1=VERIFIED files=5 revision=2024-03-15")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
