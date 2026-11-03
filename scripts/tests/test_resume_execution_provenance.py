from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "build_resume_execution_provenance.py"
SPEC = importlib.util.spec_from_file_location(
    "build_resume_execution_provenance",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
PROVENANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROVENANCE)


class ResumeExecutionProvenanceTests(unittest.TestCase):
    def test_analysis_build_tag_is_excluded_from_default_build(self) -> None:
        source = (
            b"//go:build validationidentity\n\n"
            b"package ckksplanner\n"
        )
        self.assertTrue(
            PROVENANCE.excluded_from_default_build(
                "internal/ckksplanner/validation_identity.go",
                source,
            )
        )

    def test_ordinary_runtime_source_remains_in_default_build(self) -> None:
        self.assertFalse(
            PROVENANCE.excluded_from_default_build(
                "internal/ckksplanner/executor.go",
                b"package ckksplanner\n",
            )
        )

    def test_test_file_is_excluded(self) -> None:
        self.assertTrue(
            PROVENANCE.excluded_from_default_build(
                "internal/ckksplanner/executor_test.go",
                b"package ckksplanner\n",
            )
        )


if __name__ == "__main__":
    unittest.main()
