#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 scripts/external_v7/record_provider_terminal_v7.py --provider fhecrafter --state NO_EXECUTABLE_ARTIFACT --reason "Only official DOI metadata was verified; no executable artifact is available."
