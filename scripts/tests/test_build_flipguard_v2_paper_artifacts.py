from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_flipguard_v2_paper_artifacts as paper  # noqa: E402


def direct_manifest(commit: str, workloads: int) -> dict:
    return {
        "source_code": {"git_commit": commit},
        "evidence_stage": "confirmatory",
        "evidence_type":
            "observed_no_retuning_locked_audit_confirmatory",
        "scope_policy": {"require_source_replay": True},
        "workloads": [
            {
                "source_replay_verified": True,
                "source_feature_space": "model_input",
                "preprocessing_method": "identity_model_input_v1",
                "audit_source_replay_verified": True,
                "audit_source_feature_space": "model_input",
                "audit_preprocessing_method":
                    "identity_model_input_v1",
            }
            for _ in range(workloads)
        ],
        "structural_summary": {
            "complete": True,
            "recorded_runs": workloads,
            "locked_audit_passes": workloads,
            "locked_audit_fails": 0,
            "retuned_runs": 0,
            "zero_flip_passes": workloads,
            "zero_violation_passes": workloads,
        },
    }


def valid_final_manifests(commit: str = "a" * 40) -> dict:
    return {
        "direct": direct_manifest(commit, 40),
        "structural": direct_manifest(commit, 25),
        "no_safe": {
            "schema_version": 2,
            "status": "CONFIRMATORY_DISJOINT_CONTROLS",
            "budget_source_commit": commit,
            "finite_audit_source_commit": commit,
            "finite_audit_control_result": "PASS",
            "counts": {
                "finite_audit_attempts": 300,
                "finite_audit_no_safe": 50,
            },
        },
        "paired": {
            "mode": "FINAL",
            "status": "FINAL_PAIRED_VERIFIED",
            "paper_latency_claim_allowed": True,
            "counts": {"decision_flips": 0},
            "source": {"commit": commit},
        },
        "security": {
            "artifact_id": "security_v2_static_attestation",
            "classification": "PRELIMINARY",
            "encrypted_execution_performed": False,
            "security_policy_id":
                "security_guidelines_cic2025_table5_2_ternary_128_v2",
            "source_commit": "d" * 40,
            "oracle_summary": {
                "allow_incomplete": False,
                "reference_candidate_v2_admission": "PASS",
            },
        },
    }


class FinalProfileGateTest(unittest.TestCase):
    def test_accepts_one_commit_and_all_semantic_gates(self) -> None:
        commit = "b" * 40
        self.assertEqual(
            paper.validate_final_profile(valid_final_manifests(commit)),
            commit,
        )

    def test_rejects_mixed_source_commits(self) -> None:
        manifests = valid_final_manifests()
        manifests["paired"]["source"]["commit"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "one source commit"):
            paper.validate_final_profile(manifests)

    def test_rejects_latency_pack_that_disallows_claim(self) -> None:
        manifests = valid_final_manifests()
        manifests["paired"]["paper_latency_claim_allowed"] = False
        with self.assertRaisesRegex(ValueError, "latency gates"):
            paper.validate_final_profile(manifests)

    def test_rejects_incomplete_locked_audit(self) -> None:
        manifests = valid_final_manifests()
        manifests["structural"]["structural_summary"][
            "locked_audit_passes"
        ] = 24
        with self.assertRaisesRegex(ValueError, "locked-audit"):
            paper.validate_final_profile(manifests)

    def test_rejects_direct_pack_without_source_replay(self) -> None:
        manifests = valid_final_manifests()
        manifests["direct"]["workloads"][0][
            "source_replay_verified"
        ] = False
        with self.assertRaisesRegex(ValueError, "source-replay"):
            paper.validate_final_profile(manifests)

    def test_rejects_direct_pack_without_audit_source_replay(
        self,
    ) -> None:
        manifests = valid_final_manifests()
        manifests["direct"]["workloads"][0][
            "audit_source_replay_verified"
        ] = False
        with self.assertRaisesRegex(ValueError, "source-replay"):
            paper.validate_final_profile(manifests)


class ConfirmatoryNoSafeReaderTest(unittest.TestCase):
    def test_reads_disjoint_locked_audit_schema(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-paper-nosafe-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            (root / "budget_confirm/summary").mkdir(parents=True)
            (
                root / "finite_domain_locked_audit/summary"
            ).mkdir(parents=True)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "budget_mode": "CONFIRM",
                    }
                ),
                encoding="utf-8",
            )
            (
                root / "budget_confirm/summary/summary.json"
            ).write_text(
                json.dumps(
                    {
                        "counts": {
                            "expected_workloads": 40,
                            "outcomes": {
                                "NO_SAFE": 20,
                                "SELECTED": 20,
                            },
                            "unsafe_selected": 0,
                        },
                        "control_result": "PASS",
                        "claim_boundary": "budget scoped",
                    }
                ),
                encoding="utf-8",
            )
            (
                root
                / "finite_domain_locked_audit/summary/summary.json"
            ).write_text(
                json.dumps(
                    {
                        "mode": "CONFIRM",
                        "metrics": {
                            "workloads": 50,
                            "restricted_no_safe": 50,
                            "restricted_selected": 0,
                            "candidate_rows": 100,
                            "attempts": 300,
                        },
                        "control_result": "PASS",
                        "claim_boundary": "finite domain scoped",
                    }
                ),
                encoding="utf-8",
            )

            rows, metrics = paper.no_safe_rows(root)

        self.assertEqual(rows[1][0], "finite_domain_disjoint_audit")
        self.assertEqual(rows[1][3:6], [50, 0, 0])
        self.assertEqual(metrics["finite_kind"], "DISJOINT_LOCKED_AUDIT")
        self.assertEqual(metrics["finite_attempts"], 300)


class DeterministicArtifactTest(unittest.TestCase):
    def test_compare_trees_rejects_content_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-paper-tree-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            expected = root / "expected"
            actual = root / "actual"
            expected.mkdir()
            actual.mkdir()
            (expected / "table.csv").write_text(
                "status,PASS\n",
                encoding="utf-8",
            )
            (actual / "table.csv").write_text(
                "status,FAIL\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "content changed"):
                paper.compare_trees(expected, actual)

    def test_generated_svg_is_well_formed(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-paper-svg-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            bar_path = root / "bar.svg"
            framework_path = root / "framework.svg"
            paper.bar_figure(
                bar_path,
                "Configuration Search Effort",
                "Preliminary evidence only",
                [
                    ("Catalog", 1100.0, "#64748b"),
                    ("Direct", 70.0, "#16a34a"),
                ],
            )
            paper.framework_figure(
                framework_path,
                "Preliminary evidence only",
            )
            bar_root = ElementTree.parse(bar_path).getroot()
            framework_root = ElementTree.parse(framework_path).getroot()
        self.assertTrue(bar_root.tag.endswith("svg"))
        self.assertTrue(framework_root.tag.endswith("svg"))


class CitationRegistryTest(unittest.TestCase):
    def test_manuscript_citations_are_defined_in_bibliography(self) -> None:
        manuscript = (
            REPO_ROOT
            / "docs/research/flipguard_v2_manuscript_draft_ko.md"
        ).read_text(encoding="utf-8")
        bibliography = (
            REPO_ROOT
            / "docs/research/flipguard_v2_references.bib"
        ).read_text(encoding="utf-8")
        used = set(re.findall(r"@([A-Za-z0-9_:-]+)", manuscript))
        defined = set(
            re.findall(r"@[A-Za-z]+\{([^,]+),", bibliography)
        )
        self.assertEqual(used - defined, set())
        self.assertEqual(
            len(defined),
            len(re.findall(r"@[A-Za-z]+\{([^,]+),", bibliography)),
        )
        self.assertEqual(bibliography.count("{"), bibliography.count("}"))


class ManuscriptPublicationGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manuscript = (
            REPO_ROOT
            / "docs/research/flipguard_v2_manuscript_draft_ko.md"
        ).read_text(encoding="utf-8")
        cls.artifact_root = (
            REPO_ROOT
            / "results/thesis_grade_protocol/paper_artifacts_v2/current"
        )
        cls.manifest = json.loads(
            (
                cls.artifact_root
                / "appendix/evidence_manifest.json"
            ).read_text(encoding="utf-8")
        )

    def section(self, heading: str) -> str:
        start = self.manuscript.index(heading) + len(heading)
        next_heading = self.manuscript.find("\n## ", start)
        if next_heading < 0:
            return self.manuscript[start:]
        return self.manuscript[start:next_heading]

    def test_preliminary_metrics_are_excluded_from_abstract_and_conclusion(
        self,
    ) -> None:
        abstract = self.section("## 초록")
        conclusion = self.section("## 10. 결론")
        forbidden_preliminary_metrics = (
            "70회",
            "210회",
            "1,100개",
            "93.64%",
            "150회",
            "1.9769",
            "50/50",
        )
        for metric in forbidden_preliminary_metrics:
            self.assertNotIn(metric, abstract)
            self.assertNotIn(metric, conclusion)

        status = self.manifest["publication_status"]
        if status == "NON_AUTHORITATIVE_SCAFFOLD":
            for name, (_, _, placeholder) in (
                paper.MANUSCRIPT_CLAIM_BLOCKS.items()
            ):
                self.assertEqual(
                    paper.manuscript_claim_block(
                        self.manuscript,
                        name,
                    ),
                    placeholder,
                )
        elif status == "FINAL_ADMISSIBLE":
            for name, (_, _, placeholder) in (
                paper.MANUSCRIPT_CLAIM_BLOCKS.items()
            ):
                self.assertNotEqual(
                    paper.manuscript_claim_block(
                        self.manuscript,
                        name,
                    ),
                    placeholder,
                )
        else:
            self.fail(f"unsupported publication status {status!r}")

    def test_manuscript_maps_every_generated_table_and_figure(
        self,
    ) -> None:
        for relative in paper.MANUSCRIPT_ARTIFACTS:
            self.assertIn(relative, self.manuscript)
            self.assertTrue(
                (self.artifact_root / relative).is_file(),
                relative,
            )

    def test_manuscript_declares_rq_gates_and_reproducibility(self) -> None:
        for expected in (
            "## 8. 논의",
            "### 8.2 연구 질문별 현재 상태",
            "## 9. 재현성 및 artifact",
            "## 10. 결론",
            "scripts/run_thesis_final_confirmatory_suite.sh --resume",
            "source_replay_verified",
            "`PILOT_ONLY`",
        ):
            self.assertIn(expected, self.manuscript)

    def test_builder_enforces_preliminary_and_final_markers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="flipguard-manuscript-gate-",
            dir="/tmp",
        ) as temporary:
            root = Path(temporary)
            output = root / "output"
            for relative in paper.MANUSCRIPT_ARTIFACTS:
                path = output / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")

            preliminary_path = root / "preliminary.md"
            changed_preliminary = (
                paper.replace_manuscript_claim_block(
                    self.manuscript,
                    "result",
                    "REMOVED_RESULT_PLACEHOLDER",
                )
            )
            preliminary_path.write_text(
                changed_preliminary,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "preliminary manuscript claim block changed",
            ):
                paper.validate_manuscript_publication_gate(
                    "NON_AUTHORITATIVE_SCAFFOLD",
                    output,
                    preliminary_path,
                )

            claims = {
                "result": "FINAL RESULT FIXTURE",
                "conclusion": "FINAL CONCLUSION FIXTURE",
            }
            with self.assertRaisesRegex(
                ValueError,
                "does not match generated evidence",
            ):
                paper.validate_manuscript_publication_gate(
                    "FINAL_ADMISSIBLE",
                    output,
                    REPO_ROOT
                    / "docs/research/flipguard_v2_manuscript_draft_ko.md",
                    claims,
                )

            final_path = root / "final.md"
            final_document = self.manuscript
            for name, content in claims.items():
                final_document = paper.replace_manuscript_claim_block(
                    final_document,
                    name,
                    content,
                )
            final_path.write_text(final_document, encoding="utf-8")
            gate = paper.validate_manuscript_publication_gate(
                "FINAL_ADMISSIBLE",
                output,
                final_path,
                claims,
            )
            self.assertEqual(
                gate["publication_status"],
                "FINAL_ADMISSIBLE",
            )

    def test_final_claim_renderer_is_evidence_conditioned(self) -> None:
        direct = {
            "workloads": 40,
            "configuration_trials": 56,
            "selection_key_runs": 168,
            "locked_audit_key_runs": 120,
            "locked_audit_passes": 40,
            "decision_flips": 0,
            "error_violations": 0,
            "selection_source_replay_workloads": 40,
            "audit_source_replay_workloads": 40,
        }
        oracle = {
            "catalog_executions": 560,
            "execution_reduction_pct": 90.0,
        }
        no_safe = {
            "finite_no_safe": 50,
            "finite_workloads": 50,
            "finite_selected": 0,
            "budget_unsafe_selected": 0,
        }
        paired = {
            "claim_allowed": True,
            "numerator": "catalog",
            "denominator": "direct",
            "ratio": 1.9,
            "ci_low": 1.8,
            "ci_high": 2.0,
        }
        claims = paper.render_final_manuscript_claims(
            direct,
            oracle,
            no_safe,
            paired,
        )
        self.assertIn("560회의 bounded-catalog", claims["result"])
        self.assertIn("90.00%", claims["result"])
        self.assertIn("catalog/direct", claims["result"])
        self.assertIn("50/50 workload", claims["result"])

        paired["claim_allowed"] = False
        with self.assertRaisesRegex(ValueError, "claimable paired"):
            paper.render_final_manuscript_claims(
                direct,
                oracle,
                no_safe,
                paired,
            )


if __name__ == "__main__":
    unittest.main()
