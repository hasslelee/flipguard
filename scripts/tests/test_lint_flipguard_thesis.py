#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/lint_flipguard_thesis.py"
SPEC = importlib.util.spec_from_file_location("lint_flipguard_thesis", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ThesisLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        claims = json.loads(
            (ROOT / "docs/evidence/paper_claim_admission_v1/claims.json").read_text(encoding="utf-8")
        )["claims"]
        cls.claims = claims

    def fixture(self, name: str) -> str:
        return (ROOT / "scripts/tests/fixtures" / name).read_text(encoding="utf-8")

    def test_positive_fixture_allows_scoped_negation(self) -> None:
        findings = MODULE.prohibited_occurrences(
            self.fixture("thesis_lint_positive.md"), self.claims
        )
        self.assertEqual(findings, [])

    def test_negative_fixture_rejects_overclaim(self) -> None:
        findings = MODULE.prohibited_occurrences(
            self.fixture("thesis_lint_negative.md"), self.claims
        )
        self.assertTrue(any(item["claim_id"] == "scoped_direct_synthesis" for item in findings))

    def test_canonical_firstness_sentence_fails_closed(self) -> None:
        registry = (
            ROOT / "docs/evidence/paper_claim_admission_v1/prohibited_sentences.md"
        ).read_text(encoding="utf-8")
        findings = MODULE.registry_prohibited_sentence_occurrences(
            "FlipGuard is the first CKKS autotuner.", registry
        )
        self.assertEqual(findings, ["FlipGuard is the first CKKS autotuner."])

    def test_canonical_prohibited_sentence_is_allowed_when_explicitly_denied(self) -> None:
        registry = (
            ROOT / "docs/evidence/paper_claim_admission_v1/prohibited_sentences.md"
        ).read_text(encoding="utf-8")
        findings = MODULE.registry_prohibited_sentence_occurrences(
            "We do not claim that FlipGuard is the first CKKS autotuner.", registry
        )
        self.assertEqual(findings, [])

    def test_reviewer_question_may_name_an_overclaim_but_answer_may_not_assert_it(self) -> None:
        question = "Is this production speedup?"
        self.assertEqual(
            MODULE.prohibited_occurrences(question, self.claims, context_mode="line"), []
        )
        assertion = "This is production speedup."
        findings = MODULE.prohibited_occurrences(
            assertion, self.claims, context_mode="line"
        )
        self.assertTrue(any(item["claim_id"] == "paired_latency" for item in findings))

    def test_authoritative_source_passes(self) -> None:
        result = MODULE.lint_source(ROOT, Path("docs/thesis"))
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(result["metrics"]["abstract_claim_markers"], 7)
        self.assertEqual(
            result["metrics"]["claim_markers"],
            result["metrics"]["chapter_claim_markers"] + 7,
        )

    def test_number_registry_is_fully_reconstructed_from_evidence(self) -> None:
        registry = json.loads(
            (ROOT / "docs/thesis/number_registry.json").read_text(encoding="utf-8")
        )
        reconstructed = MODULE.extract_authoritative_numbers(ROOT)
        self.assertGreaterEqual(len(reconstructed), 50)
        for key, value in reconstructed.items():
            self.assertIn(key, registry)
            self.assertEqual(registry[key], value, key)

    def test_number_registry_mutation_fails_closed(self) -> None:
        registry = json.loads(
            (ROOT / "docs/thesis/number_registry.json").read_text(encoding="utf-8")
        )
        registry["formal_catalog_all"] = 1100
        errors: list[str] = []
        MODULE.validate_registry(ROOT, registry, errors)
        self.assertTrue(any("formal_catalog_all" in error for error in errors))

    def lint_mutated_source(self, mutate) -> dict:
        with tempfile.TemporaryDirectory(prefix="thesis-lint-fixture-", dir=ROOT) as directory:
            source = Path(directory) / "thesis"
            shutil.copytree(ROOT / "docs/thesis", source)
            mutate(source)
            return MODULE.lint_source(ROOT, source.relative_to(ROOT))

    def test_unverified_citation_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "citation_audit.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(",true,02_background", ",false,02_background", 1), encoding="utf-8")

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("primary-source verification" in error for error in result["errors"]))

    def test_citation_title_mismatch_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "citation_audit.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace(
                    "Homomorphic Encryption for Arithmetic of Approximate Numbers",
                    "A Different Paper Title",
                    1,
                ),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("title differs from BibTeX" in error for error in result["errors"]))

    def test_related_work_comparison_row_requires_citation(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "03_related_work.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("HECO [@viand2023heco]", "HECO", 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("comparison row" in error for error in result["errors"]))

    def test_stale_figure_reference_line_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "figure_table_map.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(",05_flipguard_design,7,", ",05_flipguard_design,999,"), encoding="utf-8")

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("stale first-reference line" in error for error in result["errors"]))

    def test_number_marker_rendering_and_unknown_key(self) -> None:
        registry = {"count": 7, "ratio": 0.9}
        rendered = MODULE.render_number_markers(
            "{{N:count}} candidates, {{N:ratio|.0%}} reduction", registry
        )
        self.assertEqual(rendered, "7 candidates, 90% reduction")
        with self.assertRaisesRegex(ValueError, "unknown thesis number key"):
            MODULE.render_number_markers("{{N:not_registered}}", registry)

    def test_unknown_number_marker_in_defense_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "advisor_defense_qa.md"
            path.write_text(
                path.read_text(encoding="utf-8") + "\n{{N:not_registered}}\n",
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("not_registered" in error for error in result["errors"]))

    def test_missing_defense_evidence_path_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "advisor_defense_qa.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace(
                    "`docs/evidence/margin_utilization_interpretation_v1/`",
                    "`docs/evidence/not-a-real-pack/`",
                    1,
                ),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("missing evidence path" in error for error in result["errors"]))

    def test_unknown_defense_claim_id_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "advisor_defense_qa.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("`finite_scope_decision_integrity`", "`not_a_claim`", 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("unknown claim ID" in error for error in result["errors"]))

    def test_claim_traceability_dependency_mismatch_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "claim_traceability.csv"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("direct_confirmatory;", "not_the_frozen_pack;", 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("evidence dependency mismatch" in error for error in result["errors"]))

    def test_stale_release_digest_in_thesis_chapter_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "10_reproducibility_security.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace(MODULE.EXPECTED_DIGESTS["rc2_archive_sha256"], "0" * 64, 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("release binding token" in error for error in result["errors"]))

    def test_missing_reserve_policy_interpretation_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "02_background.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("**reserved margin fraction**", "**unused margin**", 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("reserve-policy interpretation" in error for error in result["errors"]))

    def test_incomplete_qa_report_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "qa_report_v1.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("- Status: `PASS`", "- Status: `FAIL`", 1), encoding="utf-8")

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("eight PASS states" in error for error in result["errors"]))

    def test_missing_limitation_topic_fails_closed(self) -> None:
        def mutate(source: Path) -> None:
            path = source / "09_discussion_limitations.md"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                text.replace("Dataset별 lookup table은 사용하지 않지만", "Adapter implementation은 남아 있지만", 1),
                encoding="utf-8",
            )

        result = self.lint_mutated_source(mutate)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("graph-adapter hardcoding" in error for error in result["errors"]))

    def test_release_qa_ledger_is_counted_and_fails_closed(self) -> None:
        lines = [
            "qa_soak_start=2026-07-31T19:45:18+09:00",
            "cycle=1 status=PASS deep=not_due",
            "cycle=2 status=PASS deep=clean_clone_pass",
            "qa_soak_end=2026-08-01T17:37:26+09:00 status=PASS cycles=2",
        ]
        self.assertEqual(MODULE.extract_release_qa_counts(lines), (2, 1))
        with self.assertRaisesRegex(ValueError, "incomplete or contains a failed cycle"):
            MODULE.extract_release_qa_counts(lines[:-1])
        failed = [*lines]
        failed[1] = "cycle=1 status=FAIL deep=not_due"
        with self.assertRaisesRegex(ValueError, "incomplete or contains a failed cycle"):
            MODULE.extract_release_qa_counts(failed)

    def test_release_qa_summary_matches_local_ledger(self) -> None:
        self.assertEqual(MODULE.release_qa_counts(ROOT), (258, 21))

    def test_release_qa_summary_supports_clean_clone_without_ignored_ledger(self) -> None:
        with tempfile.TemporaryDirectory(prefix="release-qa-summary-") as directory:
            root = Path(directory)
            target = root / "docs/thesis"
            target.mkdir(parents=True)
            shutil.copy2(ROOT / "docs/thesis/release_qa_summary.json", target)
            self.assertEqual(MODULE.release_qa_counts(root), (258, 21))

    def test_release_qa_summary_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="release-qa-summary-") as directory:
            root = Path(directory)
            target = root / "docs/thesis"
            target.mkdir(parents=True)
            summary = json.loads(
                (ROOT / "docs/thesis/release_qa_summary.json").read_text(encoding="utf-8")
            )
            summary["soak_cycles"] = 257
            (target / "release_qa_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "release QA summary mismatch"):
                MODULE.release_qa_counts(root)


if __name__ == "__main__":
    unittest.main()
