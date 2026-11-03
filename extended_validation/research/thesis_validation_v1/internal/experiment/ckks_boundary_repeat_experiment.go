package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksBoundaryRepeatOutputDir = "results/ckks_boundary_repeat"

// RunCKKSBoundaryRepeat runs repeated boundary-focused CKKS decision evaluation.
func RunCKKSBoundaryRepeat() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	config := CKKSBoundaryRepeatConfigFromRuntimeOptions()

	records, summary, err := ctx.RunFullLogRegBoundaryRepeatProbe(config)
	if err != nil {
		return fmt.Errorf("run CKKS boundary repeat probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS repeated boundary decision evaluation")
	fmt.Printf("cases=%d repetitions=%d runs=%d\n", summary.Cases, summary.Repetitions, summary.Runs)
	fmt.Println()

	fmt.Printf(
		"flips=%d stable_flips=%d ambiguous_runs=%d stable_runs=%d max_z_error=%.10f max_y_error=%.10f\n",
		summary.Flips,
		summary.StableFlips,
		summary.AmbiguousRuns,
		summary.StableRuns,
		summary.MaxZError,
		summary.MaxYError,
	)

	if err := report.WriteCKKSBoundaryRepeatSummaryCSV(
		filepath.Join(ckksBoundaryRepeatOutputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS boundary repeat summary CSV: %w", err)
	}

	if err := report.WriteCKKSBoundaryRepeatRecordsCSV(
		filepath.Join(ckksBoundaryRepeatOutputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS boundary repeat records CSV: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS boundary repeat files to %s/\n", ckksBoundaryRepeatOutputDir)

	return nil
}
