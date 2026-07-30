import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "scripts/verify_external_provider_research_boundary_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_external_provider_research_boundary_v2", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExternalProviderResearchBoundaryV2Test(unittest.TestCase):
    def test_repository_boundary_matches_frozen_evidence(self) -> None:
        MODULE.verify()

    def test_stale_no_safe_statement_fails_closed(self) -> None:
        documents = {
            name: path.read_text(encoding="utf-8")
            for name, path in MODULE.DOCUMENT_PATHS.items()
        }
        documents["provider_boundary"] += (
            "\nno native third-party compiler or selector has produced "
            "a SAFE candidate\n"
        )
        with self.assertRaisesRegex(ValueError, "stale or overclaimed"):
            MODULE.validate_documents(documents)

    def test_cross_runtime_overclaim_fails_closed(self) -> None:
        documents = {
            name: path.read_text(encoding="utf-8")
            for name, path in MODULE.DOCUMENT_PATHS.items()
        }
        documents["cross_runtime_boundary"] += (
            "\ncross_runtime_numerical_equivalence=SUPPORTED\n"
        )
        with self.assertRaisesRegex(ValueError, "stale or overclaimed"):
            MODULE.validate_documents(documents)


if __name__ == "__main__":
    unittest.main()
