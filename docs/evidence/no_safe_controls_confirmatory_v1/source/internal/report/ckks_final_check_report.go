package report

import (
	"encoding/csv"
	"fmt"
	"os"
)

// CKKSFinalCheckRow records one final result consistency check.
type CKKSFinalCheckRow struct {
	Check    string
	Status   string
	Expected string
	Actual   string
	Notes    string
}

// WriteCKKSFinalCheckCSV writes final result consistency checks.
func WriteCKKSFinalCheckCSV(path string, rows []CKKSFinalCheckRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS final check csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"check",
		"status",
		"expected",
		"actual",
		"notes",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS final check header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.Check,
			row.Status,
			row.Expected,
			row.Actual,
			row.Notes,
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS final check row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS final check csv: %w", err)
	}

	return nil
}
