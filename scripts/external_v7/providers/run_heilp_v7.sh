#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 scripts/external_v7/record_provider_terminal_v7.py --provider heilp --state NO_EXECUTABLE_ARTIFACT --reason "No official executable artifact was verified in the frozen landscape audit."
