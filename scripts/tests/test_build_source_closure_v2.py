import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/build_source_closure_v2.py"
SPEC = importlib.util.spec_from_file_location(
    "build_source_closure_v2",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceClosureV2Test(unittest.TestCase):
    def test_json_stream_decoder(self) -> None:
        self.assertEqual(
            MODULE.decode_json_stream('{"a":1}\n{"b":2}\n'),
            [{"a": 1}, {"b": 2}],
        )

    def test_build_closure_excludes_go_tests(self) -> None:
        files, packages = MODULE.go_build_closure(
            ("./cmd/flipguard-autotune",)
        )
        self.assertIn("cmd/flipguard-autotune/main.go", files)
        self.assertIn("go.mod", files)
        self.assertIn("go.sum", files)
        self.assertFalse(any(path.endswith("_test.go") for path in files))
        self.assertIn(
            "github.com/hasslelee/flipguard/internal/ckksplanner",
            packages,
        )

    def test_manifest_separates_execution_and_repository_tests(self) -> None:
        manifest = MODULE.build_manifest(
            entrypoints=("./cmd/flipguard-autotune",),
            orchestrators=(
                Path("scripts/build_resume_execution_provenance.py"),
            ),
            policy_inputs=(
                Path(
                    "docs/evidence/"
                    "security_v2_static_attestation_formal_v2/"
                    "direct_synthesis_policy_v2.json"
                ),
            ),
            comparison_sources=(
                Path("scripts/compare_direct_synthesis_to_catalog_oracle.py"),
            ),
            require_clean=False,
        )
        execution = manifest["execution_critical"]
        repository = manifest["repository_assurance"]
        self.assertFalse(
            any(
                path.endswith("_test.go")
                for path in execution["go_default_build_files"]
            )
        )
        self.assertGreater(
            len(repository["tracked_test_files"]),
            0,
        )
        self.assertTrue(manifest["semantics"]["non_retroactive"])
        self.assertFalse(
            manifest["semantics"]["historical_evidence_reinterpreted"]
        )

    def test_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-source-closure-v2-",
            dir="/tmp",
        ) as temporary:
            path = Path(temporary) / "manifest.json"
            MODULE.write_manifest(path, {"schema_version": "test"})
            with self.assertRaises(FileExistsError):
                MODULE.write_manifest(path, {"schema_version": "test"})


if __name__ == "__main__":
    unittest.main()
