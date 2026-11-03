package report

import (
	"encoding/csv"
	"fmt"
	"os"
)

// CKKSPolicyComparisonRow records one policy comparison row.
type CKKSPolicyComparisonRow struct {
	Source           string
	Method           string
	Role             string
	Samples          string
	StableRuns       string
	StableFlips      string
	StableViolations string
	Certification    string
	Certified        string
	BudgetUsage      string
	MaxError         string
	EstimatedError   string
	AvgBits          string
	SavingVsU12      string
	SavingVsU16      string
	Notes            string
}

// WriteCKKSPolicyComparisonCSV writes the combined CKKS and simulation comparison table.
func WriteCKKSPolicyComparisonCSV(path string, rows []CKKSPolicyComparisonRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS policy comparison csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"source",
		"method",
		"role",
		"samples",
		"stable_runs",
		"stable_flips",
		"stable_violations",
		"certification",
		"certified",
		"budget_usage",
		"max_error",
		"estimated_error",
		"avg_bits",
		"saving_vs_u12",
		"saving_vs_u16",
		"notes",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS policy comparison header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Source,
			row.Method,
			row.Role,
			row.Samples,
			row.StableRuns,
			row.StableFlips,
			row.StableViolations,
			row.Certification,
			row.Certified,
			row.BudgetUsage,
			row.MaxError,
			row.EstimatedError,
			row.AvgBits,
			row.SavingVsU12,
			row.SavingVsU16,
			row.Notes,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS policy comparison row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS policy comparison csv: %w", err)
	}

	return nil
}
