package report

import (
	"encoding/csv"
	"fmt"
	"os"
)

// CKKSOutputAccuracySummary stores output accuracy guard summary results.
type CKKSOutputAccuracySummary struct {
	Runs                    int
	StableRuns              int
	AmbiguousRuns           int
	ScoreAbsErrorCap        float64
	ScoreRelErrorCap        float64
	ScoreCertifiedRuns      int
	ScoreErrorViolations    int
	AllScoreErrorViolations int
	MaxYError               float64
	MaxStableYError         float64
	MinScoreErrorBudget     float64
	MaxScoreErrorBudget     float64
	MaxScoreErrorUsage      float64
	MeanScoreErrorUsage     float64
}

// CKKSOutputAccuracyRecord stores one output accuracy guard record.
type CKKSOutputAccuracyRecord struct {
	CaseIndex           string
	Repetition          string
	TargetZ             string
	Stable              bool
	PlainY              float64
	YError              float64
	ScoreErrorBudget    float64
	ScoreErrorUsage     float64
	ScoreErrorViolation bool
	ScoreCertified      bool
}

// WriteCKKSOutputAccuracySummaryCSV writes output accuracy guard summary.
func WriteCKKSOutputAccuracySummaryCSV(path string, summary CKKSOutputAccuracySummary) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS output accuracy summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"runs",
		"stable_runs",
		"ambiguous_runs",
		"score_abs_error_cap",
		"score_rel_error_cap",
		"score_certified_runs",
		"score_error_violations",
		"all_score_error_violations",
		"max_y_error",
		"max_stable_y_error",
		"min_score_error_budget",
		"max_score_error_budget",
		"max_score_error_usage",
		"mean_score_error_usage",
	}

	record := []string{
		fmt.Sprintf("%d", summary.Runs),
		fmt.Sprintf("%d", summary.StableRuns),
		fmt.Sprintf("%d", summary.AmbiguousRuns),
		formatCKKSOutputAccuracyFloat(summary.ScoreAbsErrorCap),
		formatCKKSOutputAccuracyFloat(summary.ScoreRelErrorCap),
		fmt.Sprintf("%d", summary.ScoreCertifiedRuns),
		fmt.Sprintf("%d", summary.ScoreErrorViolations),
		fmt.Sprintf("%d", summary.AllScoreErrorViolations),
		formatCKKSOutputAccuracyFloat(summary.MaxYError),
		formatCKKSOutputAccuracyFloat(summary.MaxStableYError),
		formatCKKSOutputAccuracyFloat(summary.MinScoreErrorBudget),
		formatCKKSOutputAccuracyFloat(summary.MaxScoreErrorBudget),
		formatCKKSOutputAccuracyFloat(summary.MaxScoreErrorUsage),
		formatCKKSOutputAccuracyFloat(summary.MeanScoreErrorUsage),
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS output accuracy summary header: %w", err)
	}

	if err := w.Write(record); err != nil {
		return fmt.Errorf("write CKKS output accuracy summary record: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS output accuracy summary csv: %w", err)
	}

	return nil
}

// WriteCKKSOutputAccuracyRecordsCSV writes output accuracy guard records.
func WriteCKKSOutputAccuracyRecordsCSV(path string, records []CKKSOutputAccuracyRecord) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS output accuracy records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"case_index",
		"repetition",
		"target_z",
		"stable",
		"plain_y",
		"y_error",
		"score_error_budget",
		"score_error_usage",
		"score_error_violation",
		"score_certified",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS output accuracy records header: %w", err)
	}

	for i, record := range records {
		row := []string{
			record.CaseIndex,
			record.Repetition,
			record.TargetZ,
			fmt.Sprintf("%t", record.Stable),
			formatCKKSOutputAccuracyFloat(record.PlainY),
			formatCKKSOutputAccuracyFloat(record.YError),
			formatCKKSOutputAccuracyFloat(record.ScoreErrorBudget),
			formatCKKSOutputAccuracyFloat(record.ScoreErrorUsage),
			fmt.Sprintf("%t", record.ScoreErrorViolation),
			fmt.Sprintf("%t", record.ScoreCertified),
		}

		if err := w.Write(row); err != nil {
			return fmt.Errorf("write CKKS output accuracy record %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS output accuracy records csv: %w", err)
	}

	return nil
}

func formatCKKSOutputAccuracyFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
