package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSBoundaryCSV writes CKKS boundary decision evaluation results.
func WriteCKKSBoundaryCSV(path string, results []ckksbackend.FullLogRegBoundaryResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS boundary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"target_z",
		"x1",
		"x2",
		"x3",
		"threshold",
		"plain_z",
		"ckks_z",
		"z_error",
		"plain_y",
		"ckks_y",
		"y_error",
		"margin",
		"boundary",
		"ambiguous",
		"stable",
		"plain_decision",
		"ckks_decision",
		"decision_flip",
		"initial_level",
		"z_level",
		"z2_level",
		"z3_level",
		"y_level",
		"z_degree",
		"z2_degree",
		"z3_degree",
		"y_degree",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS boundary header: %w", err)
	}

	for i, result := range results {
		row := []string{
			strconv.Itoa(i),
			formatFloat(result.Case.TargetZ),
			formatFloat(result.Result.Input.X1),
			formatFloat(result.Result.Input.X2),
			formatFloat(result.Result.Input.X3),
			formatFloat(result.Result.Threshold),
			formatFloat(result.Result.PlainZ),
			formatFloat(result.Result.CKKSZ),
			formatFloat(result.Result.ZError),
			formatFloat(result.Result.PlainY),
			formatFloat(result.Result.CKKSY),
			formatFloat(result.Result.YError),
			formatFloat(result.Margin),
			strconv.FormatBool(result.Boundary),
			strconv.FormatBool(result.Ambiguous),
			strconv.FormatBool(result.Stable),
			strconv.FormatBool(result.Result.PlainDecision),
			strconv.FormatBool(result.Result.CKKSDecision),
			strconv.FormatBool(result.Result.DecisionFlip),
			strconv.Itoa(result.Result.InitialLevel),
			strconv.Itoa(result.Result.ZLevel),
			strconv.Itoa(result.Result.Z2Level),
			strconv.Itoa(result.Result.Z3Level),
			strconv.Itoa(result.Result.YLevel),
			strconv.Itoa(result.Result.ZDegree),
			strconv.Itoa(result.Result.Z2Degree),
			strconv.Itoa(result.Result.Z3Degree),
			strconv.Itoa(result.Result.YDegree),
			strconv.Itoa(result.Result.LogDefaultScale),
		}

		if err := w.Write(row); err != nil {
			return fmt.Errorf("write CKKS boundary row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS boundary csv: %w", err)
	}

	return nil
}
