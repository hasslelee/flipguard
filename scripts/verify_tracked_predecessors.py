#!/usr/bin/env python3
"""Verify frozen V3/V10 from a tracked-only source-commit archive."""

from __future__ import annotations

import io
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "98e5e4105c0b0597d6fb245b5718a00eb4828349"


def run(path: Path, script: str) -> str:
    proc = subprocess.run(
        ["python3", script], cwd=path, text=True, capture_output=True,
        env={"PATH": str(Path("/usr/bin")) + ":/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode:
        raise SystemExit(
            f"tracked_predecessor=FAILED script={script}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc.stdout.strip()


def main() -> int:
    archive = subprocess.check_output(["git", "archive", "--format=tar", SOURCE_COMMIT], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="flipguard-tracked-predecessors-") as temp:
        checkout = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(checkout, filter="data")
        v3 = run(checkout, "results/thesis_grade_protocol/paper_artifacts_v3/final/verify_flipguard_v3_paper_artifacts.py")
        v10 = run(checkout, "docs/evidence/research_completion_checkpoint_v10/verify_research_completion_checkpoint_v10.py")
    print("tracked_predecessors=VERIFIED")
    print(v3)
    print(v10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
