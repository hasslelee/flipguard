#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 scripts/external_v7/record_provider_terminal_v7.py --provider halo --state OFFICIAL_PIPELINE_ONLY --reason "HALO implementation is integrated in the pinned post-publication HECATE repository without a distinct executable or paper tag; CoreLab V7 records the available shared pipeline separately." --source-url https://github.com/corelab-src/hecate-compiler --source-commit aedca73dac27b86044721781b9fca8d12e665876 --license MIT
