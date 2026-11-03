#!/usr/bin/env python3
"""Summarise `govulncheck -format json` output and decide whether CI fails.

Only findings whose trace reaches a function (the code appears to call the
vulnerable symbol) are counted.

- A called vulnerability in a required module (go.mod) fails the job: the fix
  is a dependency bump inside this repository.
- A called vulnerability in the Go standard library is reported with a
  warning. The Go toolchain version is part of the reproduction environment
  lock (go.mod, release/environment_requirements_v1.json), so moving it is a
  deliberate decision, not an automatic one.

Usage: govulncheck_gate.py <govulncheck.json> <summary.md>
Exit status: 1 if a required module has a called vulnerability, else 0.
"""

import json
import sys


def read_stream(path):
    """govulncheck JSON is a stream of concatenated JSON objects."""
    text = open(path, encoding="utf-8").read()
    decoder = json.JSONDecoder()
    pos, out = 0, []
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return out
        obj, pos = decoder.raw_decode(text, pos)
        out.append(obj)


def main(json_path, summary_path):
    messages = read_stream(json_path)
    summaries = {}
    called = {}  # osv id -> (module, found version, fixed version)
    for msg in messages:
        if "osv" in msg:
            osv = msg["osv"]
            summaries[osv["id"]] = osv.get("summary", "").replace("|", "\\|")
        finding = msg.get("finding")
        if not finding:
            continue
        trace = finding.get("trace") or []
        if not trace or not trace[0].get("function"):
            continue  # imported or required, but not called
        top = trace[0]
        called[finding["osv"]] = (
            top.get("module", ""),
            top.get("version", ""),
            finding.get("fixed_version", ""),
        )

    stdlib = {k: v for k, v in called.items() if v[0] == "stdlib"}
    modules = {k: v for k, v in called.items() if v[0] != "stdlib"}

    lines = ["### govulncheck", ""]
    if not called:
        lines.append("No called vulnerabilities.")
    else:
        lines += [
            "| Advisory | Where | Found | Fixed in | Summary | Blocks? |",
            "|---|---|---|---|---|---|",
        ]
        for osv_id, (module, found, fixed) in sorted(
            called.items(), key=lambda kv: (kv[1][0] == "stdlib", kv[0])
        ):
            blocks = "no (toolchain pin)" if module == "stdlib" else "**yes**"
            lines.append(
                f"| [{osv_id}](https://pkg.go.dev/vuln/{osv_id}) | {module} | "
                f"{found} | {fixed or '-'} | {summaries.get(osv_id, '')} | {blocks} |"
            )
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    if stdlib:
        fixed = sorted({v[2] for v in stdlib.values() if v[2]})
        print(
            f"::warning title=Go standard library advisories::"
            f"{len(stdlib)} called advisories in the pinned Go toolchain "
            f"(fixed in {', '.join(fixed) or 'n/a'}). Reported, not blocking: the "
            f"toolchain is part of the reproduction environment lock."
        )
    if modules:
        print(
            f"::error title=Go module advisories::{len(modules)} called advisories "
            f"in required modules: {', '.join(sorted(modules))}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
