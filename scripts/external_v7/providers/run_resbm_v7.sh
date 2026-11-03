#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 scripts/external_v7/record_provider_terminal_v7.py --provider resbm --state LICENSE_BLOCKED --reason "Implementation is integrated into the ANT-ACE repository after the pinned CGO artifact, which declares no software license." --source-url https://github.com/ant-research/ace-compiler --source-commit 929e9b621f11bebbaa9ec1e215f4a52e3d07109b --license NO_LICENSE_DECLARED
