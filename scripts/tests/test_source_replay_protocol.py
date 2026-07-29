from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import summarize_direct_tabular_autotune as summary  # noqa: E402
import freeze_direct_locked_audit_evidence as freezer  # noqa: E402


def binding(path: Path) -> dict[str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "sha256": "sha256:" + digest,
    }


class SourceReplaySummaryTest(unittest.TestCase):
    def test_accepts_verified_model_input_materialization(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-source-replay-",
            dir="/tmp",
        ) as temporary:
            source = Path(temporary) / "source.csv"
            source.write_text(
                "row_id,label,x_0\n0,0,-1\n1,1,1\n",
                encoding="utf-8",
            )
            contract = {
                "source_data": binding(source),
                "input_materialization": {
                    "schema_version":
                        "flipguard_tabular_validation_v2",
                    "source_feature_space": "model_input",
                    "preprocessing_method":
                        "identity_model_input_v1",
                    "source_replay_verified": True,
                },
            }
            fields = summary.source_replay_fields(
                contract,
                Path("selection.json"),
                True,
            )

        self.assertTrue(fields["source_replay_verified"])
        self.assertEqual(
            fields["source_feature_space"],
            "model_input",
        )

    def test_rejects_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-source-mutation-",
            dir="/tmp",
        ) as temporary:
            source = Path(temporary) / "source.csv"
            source.write_text(
                "row_id,label,x_0\n0,0,-1\n",
                encoding="utf-8",
            )
            source_binding = binding(source)
            source.write_text(
                "row_id,label,x_0\n0,0,1\n",
                encoding="utf-8",
            )
            contract = {
                "source_data": source_binding,
                "input_materialization": {
                    "schema_version":
                        "flipguard_tabular_validation_v2",
                    "source_feature_space": "model_input",
                    "preprocessing_method":
                        "identity_model_input_v1",
                    "source_replay_verified": True,
                },
            }
            with self.assertRaisesRegex(
                ValueError,
                "source data binding changed",
            ):
                summary.source_replay_fields(
                    contract,
                    Path("selection.json"),
                    True,
                )

    def test_requires_source_binding_when_requested(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "source replay is required",
        ):
            summary.source_replay_fields(
                {},
                Path("selection.json"),
                True,
            )


class MatrixRunIDTest(unittest.TestCase):
    def test_materialized_input_has_distinct_run_id(self) -> None:
        completed = subprocess.run(
            [
                "bash",
                "scripts/run_direct_tabular_autotune_matrix.sh",
                "--smoke",
                "--run-label",
                "protocol_test",
                "--materialize-model-input",
                "--print-run-id",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.stdout.strip(),
            "smoke_protocol_test_inputmodel",
        )


class SelfContainedEvidenceTest(unittest.TestCase):
    def test_rejects_changed_model_binding(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-self-contained-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            model = root / "inputs/model.json"
            source_test = root / "inputs/source_test.csv"
            selection = root / "inputs/selection.json"
            split_manifest = root / "inputs/split_manifest.json"
            audit_result = root / "outputs/audit.json"
            for path in (
                model,
                source_test,
                selection,
                split_manifest,
                audit_result,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
            model.write_text('{"model":"linear"}\n', encoding="utf-8")
            source_test.write_text(
                "row_id,label,x_0\n0,0,-1\n",
                encoding="utf-8",
            )
            model_digest = binding(model)["sha256"]
            source_digest = binding(source_test)["sha256"]
            selection.write_text(
                json.dumps(
                    {
                        "plan": {
                            "contract": {
                                "model_artifact": {
                                    "sha256": model_digest,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            split_manifest.write_text(
                json.dumps(
                    {
                        "model_artifact_digest": model_digest,
                        "source_test_csv_digest": source_digest,
                    }
                ),
                encoding="utf-8",
            )
            audit_result.write_text(
                json.dumps(
                    {
                        "audit_contract": {
                            "model_artifact": {
                                "sha256": model_digest,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            row = {
                "selection_snapshot":
                    str(selection.relative_to(root)),
                "audit_result_snapshot":
                    str(audit_result.relative_to(root)),
                "model_artifact_snapshot":
                    str(model.relative_to(root)),
                "source_test_snapshot":
                    str(source_test.relative_to(root)),
                "split_manifest_snapshot":
                    str(split_manifest.relative_to(root)),
                "model_artifact_sha256": model_digest,
                "source_test_sha256": source_digest,
            }
            freezer.verify_self_contained_input(root, row)

            selection.write_text(
                json.dumps(
                    {
                        "plan": {
                            "contract": {
                                "model_artifact": {
                                    "sha256": "sha256:" + "0" * 64,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "upstream input binding changed",
            ):
                freezer.verify_self_contained_input(root, row)


if __name__ == "__main__":
    unittest.main()
