package experiment

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/report"
)

const ckksFinalCheckOutputDir = "results/ckks_final_check"

// RunCKKSFinalCheck validates consistency across CKKS result artifacts.
func RunCKKSFinalCheck() error {
	options := GetRuntimeOptions()

	auditPath := CKKSResultPath(ckksCertificateAuditOutputDir, "summary.csv")
	comparisonPath := CKKSResultPath(ckksPolicyComparisonOutputDir, "comparison.csv")
	paperTablePath := CKKSResultPath(ckksPaperTableOutputDir, "table.csv")
	outputAccuracyPath := CKKSResultPath(ckksOutputAccuracyOutputDir, "summary.csv")
	profileModeSummaryPath := resultPathForExplicitTag(ckksProfileModeComparisonOutputDir, options.CKKSProfileModeComparisonTag, "summary.csv")
	profileModeTablePath := resultPathForExplicitTag(ckksProfileModeComparisonOutputDir, options.CKKSProfileModeComparisonTag, "table.tex")

	rows := make([]report.CKKSFinalCheckRow, 0, 96)

	rows = append(rows, fileExistsCheck("audit_summary_exists", auditPath))
	rows = append(rows, fileExistsCheck("policy_comparison_exists", comparisonPath))
	rows = append(rows, fileExistsCheck("paper_table_exists", paperTablePath))
	rows = append(rows, fileExistsCheck("output_accuracy_summary_exists", outputAccuracyPath))
	rows = append(rows, fileExistsCheck("profile_mode_summary_exists", profileModeSummaryPath))
	rows = append(rows, fileExistsCheck("profile_mode_table_exists", profileModeTablePath))

	auditRecord, err := loadSingleRecordForFinalCheck(auditPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_audit_summary", "one readable record", err.Error(), auditPath))
		return finishCKKSFinalCheck(rows)
	}

	comparisonRecords, err := readFinalCheckCSVRecordsByHeader(comparisonPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_policy_comparison", "readable csv", err.Error(), comparisonPath))
		return finishCKKSFinalCheck(rows)
	}

	paperRecords, err := readFinalCheckCSVRecordsByHeader(paperTablePath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_paper_table", "readable csv", err.Error(), paperTablePath))
		return finishCKKSFinalCheck(rows)
	}

	outputAccuracyRecord, err := loadSingleRecordForFinalCheck(outputAccuracyPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_output_accuracy_summary", "one readable record", err.Error(), outputAccuracyPath))
		return finishCKKSFinalCheck(rows)
	}

	profileModeRecords, err := readFinalCheckCSVRecordsByHeader(profileModeSummaryPath)
	if err != nil {
		rows = append(rows, failedFinalCheck("load_profile_mode_summary", "readable csv", err.Error(), profileModeSummaryPath))
		return finishCKKSFinalCheck(rows)
	}

	rows = append(rows, validateCertificateAndAccuracyFinalArtifacts(
		auditRecord,
		outputAccuracyRecord,
		comparisonRecords,
		paperRecords,
		auditPath,
		outputAccuracyPath,
		comparisonPath,
		paperTablePath,
	)...)

	rows = append(rows, validateProfileModeComparisonFinalArtifacts(
		profileModeRecords,
		profileModeSummaryPath,
		profileModeTablePath,
	)...)

	return finishCKKSFinalCheck(rows)
}

func validateCertificateAndAccuracyFinalArtifacts(
	auditRecord map[string]string,
	outputAccuracyRecord map[string]string,
	comparisonRecords []map[string]string,
	paperRecords []map[string]string,
	auditPath string,
	outputAccuracyPath string,
	comparisonPath string,
	paperTablePath string,
) []report.CKKSFinalCheckRow {
	rows := make([]report.CKKSFinalCheckRow, 0, 64)

	_, ckksComparisonOK := findFinalCheckRecordByField(comparisonRecords, "method", "ckks_observed_certificate")
	_, ckksPaperOK := findFinalCheckRecordByField(paperRecords, "method", "ckks_observed_certificate")
	_, flipguardP5OK := findFinalCheckRecordByField(paperRecords, "method", "flipguard_p5_m12")
	_, flipguardP1OK := findFinalCheckRecordByField(paperRecords, "method", "flipguard_p1_m16")

	rows = append(rows, boolFinalCheck(
		"comparison_ckks_row_exists",
		ckksComparisonOK,
		"present",
		formatPresentMissing(ckksComparisonOK),
		comparisonPath,
	))

	rows = append(rows, boolFinalCheck(
		"paper_ckks_row_exists",
		ckksPaperOK,
		"present",
		formatPresentMissing(ckksPaperOK),
		paperTablePath,
	))

	rows = append(rows, boolFinalCheck(
		"paper_flipguard_p5_row_exists",
		flipguardP5OK,
		"present",
		formatPresentMissing(flipguardP5OK),
		paperTablePath,
	))

	rows = append(rows, boolFinalCheck(
		"paper_flipguard_p1_row_exists",
		flipguardP1OK,
		"present",
		formatPresentMissing(flipguardP1OK),
		paperTablePath,
	))

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
	outputAccuracyMaxYError, outputAccuracyMaxYErrorErr := parseFinalCheckFloat(outputAccuracyRecord["max_y_error"])

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
	rows = append(rows, parseStatusCheck("output_accuracy_max_y_error_parse", outputAccuracyMaxYErrorErr))

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
		outputAccuracyMaxYErrorErr,
	) {
		return rows
	}

	rows = append(rows, boolFinalCheck(
		"audit_runs_match_points_times_repetitions",
		runs == points*repetitions,
		fmt.Sprintf("%d", points*repetitions),
		fmt.Sprintf("%d", runs),
		auditPath,
	))

	rows = append(rows, boolFinalCheck(
		"audit_boundary_runs_match_runs",
		boundaryRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", boundaryRuns),
		auditPath,
	))

	rows = append(rows, boolFinalCheck(
		"audit_stable_plus_ambiguous_match_runs",
		stableRuns+ambiguousRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", stableRuns+ambiguousRuns),
		auditPath,
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
		auditPath,
	))

	rows = append(rows, boolFinalCheck(
		"audit_max_stable_usage_positive",
		maxStableUsage > 0,
		">0",
		formatFinalCheckFloat(maxStableUsage),
		auditPath,
	))

	rows = append(rows, boolFinalCheck(
		"audit_max_y_error_positive",
		maxYError > 0,
		">0",
		formatFinalCheckFloat(maxYError),
		auditPath,
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_runs_match_audit_runs",
		outputAccuracyRuns == runs,
		fmt.Sprintf("%d", runs),
		fmt.Sprintf("%d", outputAccuracyRuns),
		outputAccuracyPath,
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_stable_runs_match_audit",
		outputAccuracyStableRuns == stableRuns,
		fmt.Sprintf("%d", stableRuns),
		fmt.Sprintf("%d", outputAccuracyStableRuns),
		outputAccuracyPath,
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_ambiguous_runs_match_audit",
		outputAccuracyAmbiguousRuns == ambiguousRuns,
		fmt.Sprintf("%d", ambiguousRuns),
		fmt.Sprintf("%d", outputAccuracyAmbiguousRuns),
		outputAccuracyPath,
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_score_certified_runs_match_stable_runs",
		scoreCertifiedRuns == stableRuns,
		fmt.Sprintf("%d", stableRuns),
		fmt.Sprintf("%d", scoreCertifiedRuns),
		outputAccuracyPath,
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
		outputAccuracyPath,
	))

	rows = append(rows, boolFinalCheck(
		"output_accuracy_max_y_error_match_audit",
		math.Abs(outputAccuracyMaxYError-maxYError) <= 1e-10,
		formatFinalCheckFloat(maxYError),
		formatFinalCheckFloat(outputAccuracyMaxYError),
		outputAccuracyPath,
	))

	return rows
}

func validateProfileModeComparisonFinalArtifacts(
	records []map[string]string,
	summaryPath string,
	tablePath string,
) []report.CKKSFinalCheckRow {
	rows := make([]report.CKKSFinalCheckRow, 0, 32)

	defaultNaive, defaultNaiveOK := findProfileModeRecord(records, "default", "naive")
	defaultRescale, defaultRescaleOK := findProfileModeRecord(records, "default", "rescale")

	selectedRecords := findFinalCheckRecordsByField(records, "selected_fastest_accepted", "true")
	rejectedShortChainCount := 0
	shortChainCount := 0

	for _, record := range records {
		if strings.HasPrefix(record["profile"], "short_chain") {
			shortChainCount++
			if strings.EqualFold(record["profile_accepted"], "false") {
				rejectedShortChainCount++
			}
		}
	}

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_naive_baseline_exists",
		defaultNaiveOK,
		"present",
		formatPresentMissing(defaultNaiveOK),
		summaryPath,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_rescale_exists",
		defaultRescaleOK,
		"present",
		formatPresentMissing(defaultRescaleOK),
		summaryPath,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_fastest_exists_once",
		len(selectedRecords) == 1,
		"1",
		fmt.Sprintf("%d", len(selectedRecords)),
		summaryPath,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_short_chain_rows_exist",
		shortChainCount > 0,
		">0",
		fmt.Sprintf("%d", shortChainCount),
		summaryPath,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_rejected_short_chain_rows_exist",
		rejectedShortChainCount > 0,
		">0",
		fmt.Sprintf("%d", rejectedShortChainCount),
		summaryPath,
	))

	if defaultNaiveOK {
		rows = append(rows, validateDefaultNaiveProfileModeRow(defaultNaive, summaryPath)...)
	}

	if defaultRescaleOK {
		rows = append(rows, validateDefaultRescaleProfileModeRow(defaultRescale, summaryPath)...)
	}

	if len(selectedRecords) == 1 {
		rows = append(rows, validateSelectedProfileModeRow(selectedRecords[0], summaryPath)...)
	}

	rows = append(rows, boolFinalCheck(
		"profile_mode_latex_table_exists",
		fileExists(tablePath),
		"present",
		formatPresentMissing(fileExists(tablePath)),
		tablePath,
	))

	return rows
}

func validateDefaultNaiveProfileModeRow(
	record map[string]string,
	path string,
) []report.CKKSFinalCheckRow {
	rows := make([]report.CKKSFinalCheckRow, 0, 8)

	accepted, acceptedErr := strconv.ParseBool(record["profile_accepted"])
	speedupEval, speedupEvalErr := parseFinalCheckFloat(record["speedup_vs_default_naive_eval_only"])
	speedupTotal, speedupTotalErr := parseFinalCheckFloat(record["speedup_vs_default_naive_total"])
	flips, flipsErr := parseFinalCheckInt(record["decision_flips"])

	rows = append(rows, parseStatusCheck("profile_mode_default_naive_accepted_parse", acceptedErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_naive_speedup_eval_parse", speedupEvalErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_naive_speedup_total_parse", speedupTotalErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_naive_flips_parse", flipsErr))

	if anyError(acceptedErr, speedupEvalErr, speedupTotalErr, flipsErr) {
		return rows
	}

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_naive_accepted",
		accepted,
		"true",
		fmt.Sprintf("%t", accepted),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_naive_speedup_eval_is_one",
		math.Abs(speedupEval-1.0) <= 1e-9,
		"1.0000000000",
		formatFinalCheckFloat(speedupEval),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_naive_speedup_total_is_one",
		math.Abs(speedupTotal-1.0) <= 1e-9,
		"1.0000000000",
		formatFinalCheckFloat(speedupTotal),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_naive_flips_zero",
		flips == 0,
		"0",
		fmt.Sprintf("%d", flips),
		path,
	))

	return rows
}

func validateDefaultRescaleProfileModeRow(
	record map[string]string,
	path string,
) []report.CKKSFinalCheckRow {
	rows := make([]report.CKKSFinalCheckRow, 0, 8)

	accepted, acceptedErr := strconv.ParseBool(record["profile_accepted"])
	speedupEval, speedupEvalErr := parseFinalCheckFloat(record["speedup_vs_default_naive_eval_only"])
	flips, flipsErr := parseFinalCheckInt(record["decision_flips"])
	scoreViolation, scoreViolationErr := strconv.ParseBool(record["score_error_violation"])

	rows = append(rows, parseStatusCheck("profile_mode_default_rescale_accepted_parse", acceptedErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_rescale_speedup_eval_parse", speedupEvalErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_rescale_flips_parse", flipsErr))
	rows = append(rows, parseStatusCheck("profile_mode_default_rescale_score_violation_parse", scoreViolationErr))

	if anyError(acceptedErr, speedupEvalErr, flipsErr, scoreViolationErr) {
		return rows
	}

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_rescale_accepted",
		accepted,
		"true",
		fmt.Sprintf("%t", accepted),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_rescale_speedup_eval_above_one",
		speedupEval > 1.0,
		">1.0",
		formatFinalCheckFloat(speedupEval),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_rescale_flips_zero",
		flips == 0,
		"0",
		fmt.Sprintf("%d", flips),
		path,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_default_rescale_score_violation_false",
		!scoreViolation,
		"false",
		fmt.Sprintf("%t", scoreViolation),
		path,
	))

	return rows
}

func validateSelectedProfileModeRow(
	record map[string]string,
	path string,
) []report.CKKSFinalCheckRow {
	rows := make([]report.CKKSFinalCheckRow, 0, 12)

	accepted, acceptedErr := strconv.ParseBool(record["profile_accepted"])
	decisionSafe, decisionSafeErr := strconv.ParseBool(record["decision_safe"])
	scoreViolation, scoreViolationErr := strconv.ParseBool(record["score_error_violation"])
	speedupEval, speedupEvalErr := parseFinalCheckFloat(record["speedup_vs_default_naive_eval_only"])
	flips, flipsErr := parseFinalCheckInt(record["decision_flips"])

	rows = append(rows, parseStatusCheck("profile_mode_selected_accepted_parse", acceptedErr))
	rows = append(rows, parseStatusCheck("profile_mode_selected_decision_safe_parse", decisionSafeErr))
	rows = append(rows, parseStatusCheck("profile_mode_selected_score_violation_parse", scoreViolationErr))
	rows = append(rows, parseStatusCheck("profile_mode_selected_speedup_eval_parse", speedupEvalErr))
	rows = append(rows, parseStatusCheck("profile_mode_selected_flips_parse", flipsErr))

	if anyError(acceptedErr, decisionSafeErr, scoreViolationErr, speedupEvalErr, flipsErr) {
		return rows
	}

	selectedName := record["profile"] + "+" + record["evaluation_mode"]

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_profile_accepted",
		accepted,
		"true",
		fmt.Sprintf("%t", accepted),
		selectedName,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_decision_safe",
		decisionSafe,
		"true",
		fmt.Sprintf("%t", decisionSafe),
		selectedName,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_score_error_violation_false",
		!scoreViolation,
		"false",
		fmt.Sprintf("%t", scoreViolation),
		selectedName,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_flips_zero",
		flips == 0,
		"0",
		fmt.Sprintf("%d", flips),
		selectedName,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_speedup_eval_above_one",
		speedupEval > 1.0,
		">1.0",
		formatFinalCheckFloat(speedupEval),
		selectedName,
	))

	rows = append(rows, boolFinalCheck(
		"profile_mode_selected_is_default_rescale",
		record["profile"] == "default" && record["evaluation_mode"] == "rescale",
		"default+rescale",
		selectedName,
		path,
	))

	return rows
}

func finishCKKSFinalCheck(rows []report.CKKSFinalCheckRow) error {
	outputPath := CKKSResultPath(ckksFinalCheckOutputDir, "check.csv")

	if err := report.WriteCKKSFinalCheckCSV(outputPath, rows); err != nil {
		return fmt.Errorf("write CKKS final check CSV: %w", err)
	}

	failures := 0
	for _, row := range rows {
		if row.Status != "pass" {
			failures++
		}
	}

	fmt.Println("FlipGuard CKKS final check")
	fmt.Printf("checks=%d failures=%d\n", len(rows), failures)
	fmt.Printf("Exported CKKS final check to %s\n", outputPath)

	if failures > 0 {
		return fmt.Errorf("CKKS final check failed: %d/%d checks failed", failures, len(rows))
	}

	return nil
}

func resultPathForExplicitTag(base string, tag string, name string) string {
	tag = sanitizeOutputTag(tag)
	if tag == "" {
		return filepath.Join(base, name)
	}

	return filepath.Join(base, tag, name)
}

func fileExistsCheck(check string, path string) report.CKKSFinalCheckRow {
	return boolFinalCheck(
		check,
		fileExists(path),
		"present",
		formatPresentMissing(fileExists(path)),
		path,
	)
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func formatPresentMissing(present bool) string {
	if present {
		return "present"
	}

	return "missing"
}

func loadSingleRecordForFinalCheck(path string) (map[string]string, error) {
	records, err := readFinalCheckCSVRecordsByHeader(path)
	if err != nil {
		return nil, err
	}

	if len(records) != 1 {
		return nil, fmt.Errorf("expected exactly one data row, got %d", len(records))
	}

	return records[0], nil
}

func readFinalCheckCSVRecordsByHeader(path string) ([]map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open csv: %w", err)
	}
	defer f.Close()

	reader := csv.NewReader(f)

	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read csv: %w", err)
	}

	if len(records) == 0 {
		return nil, fmt.Errorf("csv has no header")
	}

	header := records[0]
	out := make([]map[string]string, 0, len(records)-1)

	for _, record := range records[1:] {
		row := make(map[string]string, len(header))
		for i, name := range header {
			if i < len(record) {
				row[name] = record[i]
			} else {
				row[name] = ""
			}
		}

		out = append(out, row)
	}

	return out, nil
}

func findFinalCheckRecordByField(records []map[string]string, field string, value string) (map[string]string, bool) {
	for _, record := range records {
		if record[field] == value {
			return record, true
		}
	}

	return nil, false
}

func findFinalCheckRecordsByField(records []map[string]string, field string, value string) []map[string]string {
	out := make([]map[string]string, 0)

	for _, record := range records {
		if record[field] == value {
			out = append(out, record)
		}
	}

	return out
}

func findProfileModeRecord(records []map[string]string, profile string, mode string) (map[string]string, bool) {
	for _, record := range records {
		if record["profile"] == profile && record["evaluation_mode"] == mode {
			return record, true
		}
	}

	return nil, false
}

func parseFinalCheckInt(value string) (int, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0, fmt.Errorf("empty integer")
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parse integer %q: %w", value, err)
	}

	return parsed, nil
}

func parseFinalCheckFloat(value string) (float64, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0, fmt.Errorf("empty float")
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf("parse float %q: %w", value, err)
	}

	return parsed, nil
}

func parseStatusCheck(check string, err error) report.CKKSFinalCheckRow {
	if err == nil {
		return report.CKKSFinalCheckRow{
			Check:    check,
			Status:   "pass",
			Expected: "parse ok",
			Actual:   "parse ok",
			Notes:    "",
		}
	}

	return failedFinalCheck(check, "parse ok", err.Error(), "")
}

func boolFinalCheck(check string, ok bool, expected string, actual string, notes string) report.CKKSFinalCheckRow {
	status := "fail"
	if ok {
		status = "pass"
	}

	return report.CKKSFinalCheckRow{
		Check:    check,
		Status:   status,
		Expected: expected,
		Actual:   actual,
		Notes:    notes,
	}
}

func failedFinalCheck(check string, expected string, actual string, notes string) report.CKKSFinalCheckRow {
	return report.CKKSFinalCheckRow{
		Check:    check,
		Status:   "fail",
		Expected: expected,
		Actual:   actual,
		Notes:    notes,
	}
}

func anyError(errs ...error) bool {
	for _, err := range errs {
		if err != nil {
			return true
		}
	}

	return false
}

func formatFinalCheckFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
