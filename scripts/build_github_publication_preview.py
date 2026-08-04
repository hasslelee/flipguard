#!/usr/bin/env python3
"""Build deterministic local HTML previews for FlipGuard public documentation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

from audit_public_repository import build_report as build_hygiene_report
from lint_public_readme import ROOT, collect_link_report


OUTPUT = ROOT / "results/github_publication_preview"
SOURCES = [ROOT / "README.md", ROOT / "README_ko.md"]


CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#24292f;--muted:#57606a;--border:#d0d7de;--code:#f6f8fa;--link:#0969da}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#f0f6fc;--muted:#b6c2cf;--border:#30363d;--code:#161b22;--link:#58a6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:40px 28px 80px}a{color:var(--link)}img{max-width:100%;height:auto}h1,h2{border-bottom:1px solid var(--border);padding-bottom:.35em}h2{margin-top:2em}code{background:var(--code);padding:.15em .35em;border-radius:4px}pre{overflow:auto;background:var(--code);padding:16px;border-radius:6px}pre code{padding:0}table{display:block;overflow-x:auto;border-collapse:collapse;width:max-content;max-width:100%}th,td{border:1px solid var(--border);padding:8px 12px}blockquote{margin-left:0;padding-left:16px;border-left:4px solid var(--border);color:var(--muted)}
@media(max-width:640px){main{padding:24px 16px 56px;font-size:15px}h1{font-size:1.75rem}h2{font-size:1.35rem}table{font-size:13px}}
""".strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_relative_assets(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attr, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#", "data:", "../../")):
            return match.group(0)
        return f'{attr}="../../{target}"'
    return re.sub(r'(href|src|srcset)="([^"#][^"]*)"', replace, html)


def render_markdown(path: Path, language: str) -> str:
    renderer = MarkdownIt("commonmark", {"html": True}).enable("table")
    body = rewrite_relative_assets(renderer.render(path.read_text(encoding="utf-8")))
    title = "FlipGuard public README preview"
    return f"""<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head>
<body><main>{body}</main></body></html>
"""


def brand_gallery() -> str:
    assets = [
        "flipguard-mark.svg",
        "flipguard-mark-dark.svg",
        "flipguard-mark-mono.svg",
        "flipguard-wordmark.svg",
        "flipguard-wordmark-dark.svg",
        "flipguard-social-preview.png",
        "flipguard-mark-128.png",
        "flipguard-mark-512.png",
    ]
    rows = []
    for name in assets:
        theme = " dark" if "dark" in name or "social" in name else ""
        rows.append(f'<figure class="tile{theme}"><img src="../../docs/assets/brand/{name}" alt="{name}"><figcaption>{name}</figcaption></figure>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlipGuard brand gallery</title><style>{CSS}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}.tile{{margin:0;padding:20px;border:1px solid var(--border);background:#fff;color:#24292f;min-height:180px;display:flex;flex-direction:column;justify-content:center}}.tile.dark{{background:#0d1117;color:#f0f6fc}}figcaption{{margin-top:14px;font:13px ui-monospace,monospace}}</style></head>
<body><main><h1>FlipGuard brand gallery</h1><div class="grid">{''.join(rows)}</div></main></body></html>
"""


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "README_en.html").write_text(render_markdown(ROOT / "README.md", "en"), encoding="utf-8")
    (output / "README_ko.html").write_text(render_markdown(ROOT / "README_ko.md", "ko"), encoding="utf-8")
    (output / "brand_gallery.html").write_text(brand_gallery(), encoding="utf-8")

    links = collect_link_report(
        [
            ROOT / "README.md",
            ROOT / "README_ko.md",
            ROOT / "docs/ARCHITECTURE.md",
            ROOT / "docs/DECISION_CONTRACTS.md",
            ROOT / "docs/RESULTS.md",
            ROOT / "docs/REPRODUCIBILITY.md",
            ROOT / "docs/CLAIM_SCOPE.md",
            ROOT / "docs/REPOSITORY_GUIDE.md",
        ]
    )
    (output / "link_report.json").write_text(
        json.dumps({"schema_version": "flipguard_public_link_report_v1", "all_relative_links_valid": all(item["inside_root"] and item["exists"] for item in links), "links": links}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "public_hygiene_report.json").write_text(
        json.dumps(build_hygiene_report(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "flipguard_github_publication_preview_v1",
        "source_research_commit": "fd53d9f23040fd1490d9816a928dd04ec58eb473",
        "source_digests": {str(path.relative_to(ROOT)): digest(path) for path in SOURCES},
        "outputs": {path.name: digest(path) for path in sorted(output.iterdir()) if path.name != "manifest.json"},
        "status": "PUBLICATION_PREVIEW",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify() -> None:
    if not OUTPUT.exists():
        raise SystemExit("preview output is missing")
    with tempfile.TemporaryDirectory(prefix="flipguard-public-preview-") as directory:
        rebuilt = Path(directory) / "preview"
        build(rebuilt)
        expected = {path.name: path.read_bytes() for path in sorted(OUTPUT.iterdir()) if path.is_file()}
        actual = {path.name: path.read_bytes() for path in sorted(rebuilt.iterdir()) if path.is_file()}
        if expected != actual:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            changed = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
            raise SystemExit(f"preview rebuild mismatch: missing={missing}, extra={extra}, changed={changed}")
    print("GitHub publication preview deterministic rebuild: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        if args.output.exists() and args.output != OUTPUT:
            shutil.rmtree(args.output)
        build(args.output)
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
