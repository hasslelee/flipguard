package experiment

import (
	"fmt"
	"math"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/report"
)

const ckksOutputAccuracyOutputDir = "results/ckks_output_accuracy"

// RunCKKSOutputAccuracy validates task-level output accuracy from CKKS audit records.
func RunCKKSOutputAccuracy() error {
	options := GetRuntimeOptions()

	inputPath := CKKSResultPath(ckksCertificateAuditOutputDir, "records.csv")
	outputDir := CKKSResultDir(ckksOutputAccuracyOutputDir)

	inputRecords, err := readCSVRecordsByHeader(inputPath)
	if err != nil {
		return fmt.Errorf("read CKKS audit records: %w", err)
	}

	records, summary, err := evaluateCKKSOutputAccuracy(inputRecords, options)
	if err != nil {
		return fmt.Errorf("evaluate CKKS output accuracy: %w", err)
	}

	if err := report.WriteCKKSOutputAccuracySummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS output accuracy summary CSV: %w", err)
	}

	if err := report.WriteCKKSOutputAccuracyRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS output accuracy records CSV: %w", err)
	}

	fmt.Println("FlipGuard CKKS output accuracy guard")
	fmt.Printf("input_records=%s\n", inputPath)
	fmt.Printf("runs=%d stable_runs=%d ambiguous_runs=%d\n", summary.Runs, summary.StableRuns, summary.AmbiguousRuns)
	fmt.Printf("score_abs_error_cap=%.10f score_rel_error_cap=%.10f\n", summary.ScoreAbsErrorCap, summary.ScoreRelErrorCap)
	fmt.Println()
	fmt.Printf(
		"score_certified_runs=%d score_error_violations=%d all_score_error_violations=%d max_score_error_usage=%.10f max_y_error=%.10f\n",
		summary.ScoreCertifiedRuns,
		summary.ScoreErrorViolations,
		summary.AllScoreErrorViolations,
		summary.MaxScoreErrorUsage,
		summary.MaxYError,
	)

	fmt.Println()
	fmt.Printf("Exported CKKS output accuracy files to %s/\n", outputDir)

	return nil
}

func evaluateCKKSOutputAccuracy(
	inputRecords []map[string]string,
	options RuntimeOptions,
) ([]report.CKKSOutputAccuracyRecord, report.CKKSOutputAccuracySummary, error) {
	if options.CKKSScoreAbsErrorCap <= 0 && options.CKKSScoreRelErrorCap <= 0 {
		return nil, report.CKKSOutputAccuracySummary{}, fmt.Errorf("at least one score error cap must be positive")
	}

	records := make([]report.CKKSOutputAccuracyRecord, 0, len(inputRecords))

	summary := report.CKKSOutputAccuracySummary{
		Runs:                len(inputRecords),
		ScoreAbsErrorCap:    options.CKKSScoreAbsErrorCap,
		ScoreRelErrorCap:    options.CKKSScoreRelErrorCap,
		MinScoreErrorBudget: math.Inf(1),
		MaxScoreErrorBudget: 0,
		MaxScoreErrorUsage:  0,
		MeanScoreErrorUsage: 0,
		MaxYError:           0,
		MaxStableYError:     0,
	}

	stableUsageSum := 0.0

	for i, inputRecord := range inputRecords {
		plainY, err := outputAccuracyFloatField(inputRecord, "plain_y", "plain_output", "plain_score", "expected_y")
		if err != nil {
			return nil, report.CKKSOutputAccuracySummary{}, fmt.Errorf("record %d plain y: %w", i, err)
		}

		yError, err := outputAccuracyFloatField(inputRecord, "y_error", "output_error", "score_error", "abs_error")
		if err != nil {
			return nil, report.CKKSOutputAccuracySummary{}, fmt.Errorf("record %d y error: %w", i, err)
		}

		stable := outputAccuracyStable(inputRecord)
		scoreErrorBudget, err := outputAccuracyBudget(
			plainY,
			options.CKKSScoreAbsErrorCap,
			options.CKKSScoreRelErrorCap,
		)
		if err != nil {
			return nil, report.CKKSOutputAccuracySummary{}, fmt.Errorf("record %d score error budget: %w", i, err)
		}

		scoreErrorUsage := 0.0
		if scoreErrorBudget > 0 {
			scoreErrorUsage = yError / scoreErrorBudget
		}

		scoreErrorViolation := yError > scoreErrorBudget
		scoreCertified := stable && !scoreErrorViolation

		if stable {
			summary.StableRuns++
			stableUsageSum += scoreErrorUsage

			if yError > summary.MaxStableYError {
				summary.MaxStableYError = yError
			}

			if scoreErrorViolation {
				summary.ScoreErrorViolations++
			} else {
				summary.ScoreCertifiedRuns++
			}

			if scoreErrorUsage > summary.MaxScoreErrorUsage {
				summary.MaxScoreErrorUsage = scoreErrorUsage
			}

			if scoreErrorBudget < summary.MinScoreErrorBudget {
				summary.MinScoreErrorBudget = scoreErrorBudget
			}

			if scoreErrorBudget > summary.MaxScoreErrorBudget {
				summary.MaxScoreErrorBudget = scoreErrorBudget
			}
		} else {
			summary.AmbiguousRuns++
		}

		if scoreErrorViolation {
			summary.AllScoreErrorViolations++
		}

		if yError > summary.MaxYError {
			summary.MaxYError = yError
		}

		record := report.CKKSOutputAccuracyRecord{
			CaseIndex:           firstNonEmpty(inputRecord["case_index"], inputRecord["case"], inputRecord["index"]),
			Repetition:          firstNonEmpty(inputRecord["repetition"], inputRecord["repeat"], inputRecord["run"]),
			TargetZ:             firstNonEmpty(inputRecord["target_z"], inputRecord["z"], inputRecord["plain_z"]),
			Stable:              stable,
			PlainY:              plainY,
			YError:              yError,
			ScoreErrorBudget:    scoreErrorBudget,
			ScoreErrorUsage:     scoreErrorUsage,
			ScoreErrorViolation: scoreErrorViolation,
			ScoreCertified:      scoreCertified,
		}

		records = append(records, record)
	}

	if summary.StableRuns > 0 {
		summary.MeanScoreErrorUsage = stableUsageSum / float64(summary.StableRuns)
	} else {
		summary.MinScoreErrorBudget = 0
	}

	if math.IsInf(summary.MinScoreErrorBudget, 1) {
		summary.MinScoreErrorBudget = 0
	}

	return records, summary, nil
}

func outputAccuracyFloatField(record map[string]string, names ...string) (float64, error) {
	for _, name := range names {
		value, ok := record[name]
		if !ok {
			continue
		}

		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}

		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return 0, fmt.Errorf("parse field %s=%q: %w", name, value, err)
		}

		return parsed, nil
	}

	return 0, fmt.Errorf("missing fields %s", strings.Join(names, ","))
}

func outputAccuracyStable(record map[string]string) bool {
	stable := strings.TrimSpace(firstNonEmpty(
		record["stable"],
		record["is_stable"],
		record["stable_sample"],
	))

	if stable != "" {
		return parseBoolLike(stable)
	}

	ambiguous := strings.TrimSpace(firstNonEmpty(
		record["ambiguous"],
		record["is_ambiguous"],
		record["ambiguous_sample"],
	))

	if ambiguous != "" {
		return !parseBoolLike(ambiguous)
	}

	classification := strings.ToLower(strings.TrimSpace(firstNonEmpty(
		record["classification"],
		record["sample_class"],
		record["margin_class"],
		record["status"],
	)))

	if strings.Contains(classification, "ambiguous") {
		return false
	}

	if strings.Contains(classification, "stable") {
		return true
	}

	return true
}

func outputAccuracyBudget(plainY float64, absCap float64, relCap float64) (float64, error) {
	budgets := make([]float64, 0, 2)

	if absCap > 0 {
		budgets = append(budgets, absCap)
	}

	if relCap > 0 {
		denominator := math.Max(math.Abs(plainY), 1e-12)
		budgets = append(budgets, relCap*denominator)
	}

	if len(budgets) == 0 {
		return 0, fmt.Errorf("no positive score error cap")
	}

	budget := budgets[0]
	for _, candidate := range budgets[1:] {
		if candidate < budget {
			budget = candidate
		}
	}

	if budget <= 0 {
		return 0, fmt.Errorf("non-positive score error budget %.10f", budget)
	}

	return budget, nil
}
