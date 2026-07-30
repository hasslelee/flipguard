package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSBoundarySweepSummaryCSV writes aggregate dense boundary sweep results.
func WriteCKKSBoundarySweepSummaryCSV(path string, summary ckksbackend.FullLogRegBoundarySweepSummary) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS boundary sweep summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"points",
		"repetitions",
		"runs",
		"flips",
		"stable_flips",
		"ambiguous_flips",
		"boundary_runs",
		"stable_runs",
		"ambiguous_runs",
		"min_margin",
		"max_margin",
		"max_z_error",
		"mean_z_error",
		"max_y_error",
		"mean_y_error",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS boundary sweep summary header: %w", err)
	}

	row := []string{
		strconv.Itoa(summary.Points),
		strconv.Itoa(summary.Repetitions),
		strconv.Itoa(summary.Runs),
		strconv.Itoa(summary.Flips),
		strconv.Itoa(summary.StableFlips),
		strconv.Itoa(summary.AmbiguousFlips),
		strconv.Itoa(summary.BoundaryRuns),
		strconv.Itoa(summary.StableRuns),
		strconv.Itoa(summary.AmbiguousRuns),
		formatFloat(summary.MinMargin),
		formatFloat(summary.MaxMargin),
		formatFloat(summary.MaxZError),
		formatFloat(summary.MeanZError),
		formatFloat(summary.MaxYError),
		formatFloat(summary.MeanYError),
	}

	if err := w.Write(row); err != nil {
		return fmt.Errorf("write CKKS boundary sweep summary row: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS boundary sweep summary csv: %w", err)
	}

	return nil
}

// WriteCKKSBoundarySweepRecordsCSV writes per-run dense boundary sweep results.
func WriteCKKSBoundarySweepRecordsCSV(path string, records []ckksbackend.FullLogRegBoundarySweepRecord) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS boundary sweep records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"case_index",
		"repetition",
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
		return fmt.Errorf("write CKKS boundary sweep records header: %w", err)
	}

	for _, record := range records {
		boundary := record.BoundaryResult
		result := boundary.Result

		row := []string{
			strconv.Itoa(record.CaseIndex),
			strconv.Itoa(record.Repetition),
			formatFloat(boundary.Case.TargetZ),
			formatFloat(result.Input.X1),
			formatFloat(result.Input.X2),
			formatFloat(result.Input.X3),
			formatFloat(result.Threshold),
			formatFloat(result.PlainZ),
			formatFloat(result.CKKSZ),
			formatFloat(result.ZError),
			formatFloat(result.PlainY),
			formatFloat(result.CKKSY),
			formatFloat(result.YError),
			formatFloat(boundary.Margin),
			strconv.FormatBool(boundary.Boundary),
			strconv.FormatBool(boundary.Ambiguous),
			strconv.FormatBool(boundary.Stable),
			strconv.FormatBool(result.PlainDecision),
			strconv.FormatBool(result.CKKSDecision),
			strconv.FormatBool(result.DecisionFlip),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.ZLevel),
			strconv.Itoa(result.Z2Level),
			strconv.Itoa(result.Z3Level),
			strconv.Itoa(result.YLevel),
			strconv.Itoa(result.ZDegree),
			strconv.Itoa(result.Z2Degree),
			strconv.Itoa(result.Z3Degree),
			strconv.Itoa(result.YDegree),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(row); err != nil {
			return fmt.Errorf(
				"write CKKS boundary sweep record case %d repetition %d: %w",
				record.CaseIndex,
				record.Repetition,
				err,
			)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS boundary sweep records csv: %w", err)
	}

	return nil
}
