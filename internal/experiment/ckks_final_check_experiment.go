package experiment

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/report"
)

const ckksFinalCheckOutputDir = "results/ckks_final_check"

// RunCKKSFinalCheck validates consistency across tagged CKKS result artifacts.
func RunCKKSFinalCheck() error {
	auditPath := CKKSResultPath(ckksCertificateAuditOutputDir, "summary.csv")
	comparisonPath := CKKSResultPath(ckksPolicyComparisonOutputDir, "comparison.csv")
	paperTablePath := CKKSResultPath(ckksPaperTableOutputDir, "table.csv")
	outputAccuracyPath := CKKSResultPath(ckksOutputAccuracyOutputDir, "summary.csv")

	rows := make([]report.CKKSFinalCheckRow, 0, 48)

	rows = append(rows, fileExistsCheck("audit_summary_exists", auditPath))
	rows = append(rows, fileExistsCheck("policy_comparison_exists", comparisonPath))
	rows = append(rows, fileExistsCheck("paper_table_exists", paperTablePath))
	rows = append(rows, fileExistsCheck("output_accuracy_summary_exists", outputAccuracyPath))

	auditRecord, err := loadSingleRecordForFinalCheck(auditPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_audit_summary", "one readable record", err.Error(), auditPath))
		return finishCKKSFinalCheck(rows)
	}

	comparisonRecords, err := readCSVRecordsByHeader(comparisonPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_policy_comparison", "readable csv", err.Error(), comparisonPath))
		return finishCKKSFinalCheck(rows)
	}

	paperRecords, err := readCSVRecordsByHeader(paperTablePath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_paper_table", "readable csv", err.Error(), paperTablePath))
		return finishCKKSFinalCheck(rows)
	}

	outputAccuracyRecord, err := loadSingleRecordForFinalCheck(outputAccuracyPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_output_accuracy_summary", "one readable record", err.Error(), outputAccuracyPath))
		return finishCKKSFinalCheck(rows)
	}

	ckksComparisonRow, ok := findRecordByField(comparisonRecords, "method", "ckks_observed_certificate")
	if !ok {
		rows = append(rows, failedFinalCheck("comparison_ckks_row_exists", "present", "missing", comparisonPath))
		return finishCKKSFinalCheck(rows)
	}

	ckksPaperRow, ok := findRecordByField(paperRecords, "method", "ckks_observed_certificate")
	if !ok {
		rows = append(rows, failedFinalCheck("paper_ckks_row_exists", "present", "missing", paperTablePath))
		return finishCKKSFinalCheck(rows)
	}

	flipguardP5Row, p5OK := findRecordByField(paperRecords, "method", "flipguard_p5_m12")
	flipguardP1Row, p1OK := findRecordByField(paperRecords, "method", "flipguard_p1_m16")

	points, pointsErr := parseFinalCheckInt(auditRecord["points"])
	repetitions, repetitionsErr := parseFinalCheckInt(auditRecord["repetitions"])
	runs, runsErr := parseFinalCheckInt(auditRecord["runs"])
	stableRuns, stableRunsErr := parseFinalCheckInt(auditRecord["stable_runs"])
	ambiguousRuns, ambiguousRunsErr := parseFinalCheckInt(auditRecord["ambiguous_runs"])
	boundaryRuns, boundaryRunsErr := parseFinalCheckInt(auditRecord["boundary_runs"])
	stableFlips, stableFlipsErr := parseFinalCheckInt(auditRecord["stable_flips"])
	stableViolations, stableViolationsErr := parseFinalCheckInt(auditRecord["stable_violations"])
	stableCertifiedRuns, stableCertifiedRunsErr := parseFinalCheckInt(auditRecord["stable_certified_runs"])
	maxStableUsage, maxStableUsageErr := parseFinalCheckFloat(auditRecord["max_stable_usage"])
	maxYError, maxYErrorErr := parseFinalCheckFloat(auditRecord["max_y_error"])

	outputAccuracyRuns, outputAccuracyRunsErr := parseFinalCheckInt(outputAccuracyRecord["runs"])
	outputAccuracyStableRuns, outputAccuracyStableRunsErr := parseFinalCheckInt(outputAccuracyRecord["stable_runs"])
	outputAccuracyAmbiguousRuns, outputAccuracyAmbiguousRunsErr := parseFinalCheckInt(outputAccuracyRecord["ambiguous_runs"])
	scoreCertifiedRuns, scoreCertifiedRunsErr := parseFinalCheckInt(outputAccuracyRecord["score_certified_runs"])
	scoreErrorViolations, scoreErrorViolationsErr := parseFinalCheckInt(outputAccuracyRecord["score_error_violations"])
	allScoreErrorViolations, allScoreErrorViolationsErr := parseFinalCheckInt(outputAccuracyRecord["all_score_error_violations"])
	maxScoreErrorUsage, maxScoreErrorUsageErr := parseFinalCheckFloat(outputAccuracyRecord["max_score_error_usage"])
	_, maxOutputAccuracyYErrorErr := parseFinalCheckFloat(outputAccuracyRecord["max_y_error"])

	rows = append(rows, parseStatusCheck("audit_points_parse", pointsErr))
	rows = append(rows, parseStatusCheck("audit_repetitions_parse", repetitionsErr))
	rows = append(rows, parseStatusCheck("audit_runs_parse", runsErr))
	rows = append(rows, parseStatusCheck("audit_stable_runs_parse", stableRunsErr))
	rows = append(rows, parseStatusCheck("audit_ambiguous_runs_parse", ambiguousRunsErr))
	rows = append(rows, parseStatusCheck("audit_boundary_runs_parse", boundaryRunsErr))
	rows = append(rows, parseStatusCheck("audit_stable_flips_parse", stableFlipsErr))
	rows = append(rows, parseStatusCheck("audit_stable_violations_parse", stableViolationsErr))
	rows = append(rows, parseStatusCheck("audit_stable_certified_runs_parse", stableCertifiedRunsErr))
	rows = append(rows, parseStatusCheck("audit_max_stable_usage_parse", maxStableUsageErr))
	rows = append(rows, parseStatusCheck("audit_max_y_error_parse", maxYErrorErr))

	rows = append(rows, parseStatusCheck("output_accuracy_runs_parse", outputAccuracyRunsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_stable_runs_parse", outputAccuracyStableRunsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_ambiguous_runs_parse", outputAccuracyAmbiguousRunsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_score_certified_runs_parse", scoreCertifiedRunsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_score_error_violations_parse", scoreErrorViolationsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_all_score_error_violations_parse", allScoreErrorViolationsErr))
	rows = append(rows, parseStatusCheck("output_accuracy_max_score_error_usage_parse", maxScoreErrorUsageErr))
	rows = append(rows, parseStatusCheck("output_accuracy_max_y_error_parse", maxOutputAccuracyYErrorErr))

	if anyError(
		pointsErr,
		repetitionsErr,
		runsErr,
		stableRunsErr,
		ambiguousRunsErr,
		boundaryRunsErr,
		stableFlipsErr,
		stableViolationsErr,
		stableCertifiedRunsErr,
		maxStableUsageErr,
		maxYErrorErr,
		outputAccuracyRunsErr,
		outputAccuracyStableRunsErr,
		outputAccuracyAmbiguousRunsErr,
		scoreCertifiedRunsErr,
		scoreErrorViolationsErr,
		allScoreErrorViolationsErr,
		maxScoreErrorUsageErr,
		maxOutputAccuracyYErrorErr,
	) {
		return finishCKKSFinalCheck(rows)
	}

	rows = append(rows, boolFinalCheck(
		"audit_runs_match_points_times_repetitions",
		runs == points*repetitions,
		fmt.Sprintf("%d", points*repetitions),
		fmt.Sprintf("%d", runs),
		"audit summary internal consistency",
	))

	rows = append(rows, boolFinalCheck(
		"audit_boundary_runs_match_runs",
		boundaryRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", boundaryRuns),
		"all generated sweep samples should be boundary samples",
	))

	rows = append(rows, boolFinalCheck(
		"audit_stable_plus_ambiguous_match_runs",
		stableRuns+ambiguousRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", stableRuns+ambiguousRuns),
		"stable and ambiguous samples should partition boundary runs",
	))

	rows = append(rows, boolFinalCheck(
		"audit_stable_flips_zero",
		stableFlips == 0,
		"0",
		fmt.Sprintf("%d", stableFlips),
		"main decision-stability claim",
	))

	rows = append(rows, boolFinalCheck(
		"audit_stable_violations_zero",
		stableViolations == 0,
		"0",
		fmt.Sprintf("%d", stableViolations),
		"main margin-safety certificate claim",
	))

	rows = append(rows, boolFinalCheck(
		"audit_stable_certified_runs_match_stable_runs",
		stableCertifiedRuns == stableRuns,
		fmt.Sprintf("%d", stableRuns),
		fmt.Sprintf("%d", stableCertifiedRuns),
		"all stable samples should satisfy the observed-error certificate",
	))

	rows = append(rows, boolFinalCheck(
		"audit_max_stable_usage_positive",
		maxStableUsage > 0,
		">0",
		formatFinalCheckFloat(maxStableUsage),
		"usage should preserve a nonzero observed CKKS error ratio",
	))

	rows = append(rows, boolFinalCheck(
		"audit_max_y_error_positive",
		maxYError > 0,
		">0",
		formatFinalCheckFloat(maxYError),
		"observed CKKS error should be explicitly represented",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_runs_match_audit_runs",
		outputAccuracyRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", outputAccuracyRuns),
		"output accuracy summary should reuse the same audit records",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_stable_runs_match_audit",
		outputAccuracyStableRuns == stableRuns,
		fmt.Sprintf("%d", stableRuns),
		fmt.Sprintf("%d", outputAccuracyStableRuns),
		"output accuracy stable run count should match audit stable run count",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_ambiguous_runs_match_audit",
		outputAccuracyAmbiguousRuns == ambiguousRuns,
		fmt.Sprintf("%d", ambiguousRuns),
		fmt.Sprintf("%d", outputAccuracyAmbiguousRuns),
		"output accuracy ambiguous run count should match audit ambiguous run count",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_score_certified_runs_match_stable_runs",
		scoreCertifiedRuns == stableRuns,
		fmt.Sprintf("%d", stableRuns),
		fmt.Sprintf("%d", scoreCertifiedRuns),
		"all stable samples should satisfy the output accuracy guard",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_score_error_violations_zero",
		scoreErrorViolations == 0,
		"0",
		fmt.Sprintf("%d", scoreErrorViolations),
		"stable samples should not violate the output accuracy guard",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_all_score_error_violations_zero",
		allScoreErrorViolations == 0,
		"0",
		fmt.Sprintf("%d", allScoreErrorViolations),
		"all samples should satisfy the task-level output accuracy guard",
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_max_score_error_usage_positive",
		maxScoreErrorUsage > 0,
		">0",
		formatFinalCheckFloat(maxScoreErrorUsage),
		"score error usage should preserve a nonzero observed ratio",
	))

	rows = append(rows, floatFieldCheck(
		"output_accuracy_max_y_error_match_audit",
		maxYError,
		outputAccuracyRecord["max_y_error"],
		1e-10,
		"output accuracy max error should match audit max_y_error",
	))

	rows = append(rows, stringFieldCheck(
		"comparison_samples_match_audit_runs",
		fmt.Sprintf("%d", runs),
		ckksComparisonRow["samples"],
		"comparison CKKS row should reuse audit summary",
	))

	rows = append(rows, stringFieldCheck(
		"comparison_stable_runs_match_audit",
		fmt.Sprintf("%d", stableRuns),
		ckksComparisonRow["stable_runs"],
		"comparison CKKS row should reuse audit summary",
	))

	rows = append(rows, stringFieldCheck(
		"comparison_stable_flips_match_audit",
		fmt.Sprintf("%d", stableFlips),
		ckksComparisonRow["stable_flips"],
		"comparison CKKS row should reuse audit summary",
	))

	rows = append(rows, stringFieldCheck(
		"comparison_stable_violations_match_audit",
		fmt.Sprintf("%d", stableViolations),
		ckksComparisonRow["stable_violations"],
		"comparison CKKS row should reuse audit summary",
	))

	rows = append(rows, floatFieldCheck(
		"comparison_budget_usage_match_audit",
		maxStableUsage,
		ckksComparisonRow["budget_usage"],
		1e-10,
		"comparison CKKS budget usage should match audit max_stable_usage",
	))

	rows = append(rows, floatFieldCheck(
		"comparison_max_error_match_audit",
		maxYError,
		ckksComparisonRow["max_error"],
		1e-10,
		"comparison CKKS max error should match audit max_y_error",
	))

	rows = append(rows, stringFieldCheck(
		"paper_ckks_stable_flips_match",
		fmt.Sprintf("%d", stableFlips),
		ckksPaperRow["stable_flips"],
		"paper table should reflect CKKS stable flips",
	))

	rows = append(rows, stringFieldCheck(
		"paper_ckks_margin_violations_match",
		fmt.Sprintf("%d", stableViolations),
		ckksPaperRow["margin_violations"],
		"paper table should reflect CKKS margin-safety violations",
	))

	rows = append(rows, stringFieldCheck(
		"paper_ckks_score_violations_match",
		fmt.Sprintf("%d", scoreErrorViolations),
		ckksPaperRow["score_violations"],
		"paper table should reflect CKKS output accuracy violations",
	))

	rows = append(rows, paperUsageCheck(ckksPaperRow["usage"]))

	rows = append(rows, boolFinalCheck(
		"paper_flipguard_p5_row_exists",
		p5OK,
		"present",
		boolToPresentMissing(p5OK),
		"paper table should include FlipGuard p5 row",
	))

	rows = append(rows, boolFinalCheck(
		"paper_flipguard_p1_row_exists",
		p1OK,
		"present",
		boolToPresentMissing(p1OK),
		"paper table should include FlipGuard p1 row",
	))

	if p5OK {
		rows = append(rows, savingCheck("paper_flipguard_p5_saving_positive", flipguardP5Row["saving"]))
	}

	if p1OK {
		rows = append(rows, savingCheck("paper_flipguard_p1_saving_positive", flipguardP1Row["saving"]))
	}

	return finishCKKSFinalCheck(rows)
}

func loadSingleRecordForFinalCheck(path string) (map[string]string, error) {
	records, err := readCSVRecordsByHeader(path)
	if err != nil {
		return nil, err
	}

	if len(records) != 1 {
		return nil, fmt.Errorf("expected exactly one record, got %d", len(records))
	}

	return records[0], nil
}

func finishCKKSFinalCheck(rows []report.CKKSFinalCheckRow) error {
	outputDir := CKKSResultDir(ckksFinalCheckOutputDir)
	outputPath := filepath.Join(outputDir, "check.csv")

	if err := report.WriteCKKSFinalCheckCSV(outputPath, rows); err != nil {
		return fmt.Errorf("write CKKS final check CSV: %w", err)
	}

	failures := 0
	for _, row := range rows {
		if row.Status != "pass" {
			failures++
		}
	}

	fmt.Println("FlipGuard CKKS final tagged result check")
	fmt.Printf("checks=%d failures=%d\n", len(rows), failures)
	fmt.Println()

	for _, row := range rows {
		fmt.Printf(
			"check=%s status=%s expected=%s actual=%s\n",
			row.Check,
			row.Status,
			row.Expected,
			row.Actual,
		)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS final check file to %s\n", outputPath)

	if failures > 0 {
		return fmt.Errorf("CKKS final check failed with %d failures", failures)
	}

	return nil
}

func fileExistsCheck(check string, path string) report.CKKSFinalCheckRow {
	_, err := os.Stat(path)
	if err != nil {
		return failedFinalCheck(check, "exists", path, err.Error())
	}

	return passedFinalCheck(check, "exists", path, "")
}

func parseStatusCheck(check string, err error) report.CKKSFinalCheckRow {
	if err != nil {
		return failedFinalCheck(check, "parse ok", err.Error(), "")
	}

	return passedFinalCheck(check, "parse ok", "parse ok", "")
}

func boolFinalCheck(
	check string,
	passed bool,
	expected string,
	actual string,
	notes string,
) report.CKKSFinalCheckRow {
	if passed {
		return passedFinalCheck(check, expected, actual, notes)
	}

	return failedFinalCheck(check, expected, actual, notes)
}

func stringFieldCheck(
	check string,
	expected string,
	actual string,
	notes string,
) report.CKKSFinalCheckRow {
	return boolFinalCheck(check, expected == actual, expected, actual, notes)
}

func floatFieldCheck(
	check string,
	expected float64,
	actualValue string,
	tolerance float64,
	notes string,
) report.CKKSFinalCheckRow {
	actual, err := parseFinalCheckFloat(actualValue)
	if err != nil {
		return failedFinalCheck(check, formatFinalCheckFloat(expected), actualValue, err.Error())
	}

	return boolFinalCheck(
		check,
		almostEqual(expected, actual, tolerance),
		formatFinalCheckFloat(expected),
		formatFinalCheckFloat(actual),
		notes,
	)
}

func paperUsageCheck(value string) report.CKKSFinalCheckRow {
	parsed, err := parseFinalCheckFloat(value)
	if err != nil {
		return failedFinalCheck("paper_ckks_usage_parse", ">0", value, err.Error())
	}

	return boolFinalCheck(
		"paper_ckks_usage_positive_and_nonzero_display",
		parsed > 0 && strings.TrimSpace(value) != "0.0000",
		">0 and not 0.0000",
		value,
		"paper usage should not hide small CKKS error as zero",
	)
}

func savingCheck(check string, value string) report.CKKSFinalCheckRow {
	normalized := strings.TrimSuffix(strings.TrimSpace(value), "%")
	parsed, err := strconv.ParseFloat(normalized, 64)
	if err != nil {
		return failedFinalCheck(check, ">0%", value, err.Error())
	}

	return boolFinalCheck(check, parsed > 0, ">0%", value, "FlipGuard saving should be positive")
}

func passedFinalCheck(
	check string,
	expected string,
	actual string,
	notes string,
) report.CKKSFinalCheckRow {
	return report.CKKSFinalCheckRow{
		Check:    check,
		Status:   "pass",
		Expected: expected,
		Actual:   actual,
		Notes:    notes,
	}
}

func failedFinalCheck(
	check string,
	expected string,
	actual string,
	notes string,
) report.CKKSFinalCheckRow {
	return report.CKKSFinalCheckRow{
		Check:    check,
		Status:   "fail",
		Expected: expected,
		Actual:   actual,
		Notes:    notes,
	}
}

func findRecordByField(records []map[string]string, field string, value string) (map[string]string, bool) {
	for _, record := range records {
		if record[field] == value {
			return record, true
		}
	}

	return nil, false
}

func parseFinalCheckInt(value string) (int, error) {
	parsed, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil {
		return 0, fmt.Errorf("parse int %q: %w", value, err)
	}

	return parsed, nil
}

func parseFinalCheckFloat(value string) (float64, error) {
	parsed, err := strconv.ParseFloat(strings.TrimSpace(value), 64)
	if err != nil {
		return 0, fmt.Errorf("parse float %q: %w", value, err)
	}

	return parsed, nil
}

func formatFinalCheckFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}

func anyError(errors ...error) bool {
	for _, err := range errors {
		if err != nil {
			return true
		}
	}

	return false
}

func boolToPresentMissing(value bool) string {
	if value {
		return "present"
	}

	return "missing"
}
