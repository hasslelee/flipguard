package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksBoundarySweepOutputDir = "results/ckks_boundary_sweep"

// RunCKKSBoundarySweep runs dense boundary-focused CKKS decision evaluation.
func RunCKKSBoundarySweep() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	config := ckksbackend.DefaultFullLogRegBoundarySweepConfig()

	records, summary, err := ctx.RunFullLogRegBoundarySweepProbe(config)
	if err != nil {
		return fmt.Errorf("run CKKS boundary sweep probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS dense boundary sweep")
	fmt.Printf("points=%d repetitions=%d runs=%d\n", summary.Points, summary.Repetitions, summary.Runs)
	fmt.Println()

	fmt.Printf(
		"flips=%d stable_flips=%d ambiguous_flips=%d stable_runs=%d ambiguous_runs=%d max_z_error=%.10f max_y_error=%.10f\n",
		summary.Flips,
		summary.StableFlips,
		summary.AmbiguousFlips,
		summary.StableRuns,
		summary.AmbiguousRuns,
		summary.MaxZError,
		summary.MaxYError,
	)

	if err := report.WriteCKKSBoundarySweepSummaryCSV(
		filepath.Join(ckksBoundarySweepOutputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS boundary sweep summary CSV: %w", err)
	}

	if err := report.WriteCKKSBoundarySweepRecordsCSV(
		filepath.Join(ckksBoundarySweepOutputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS boundary sweep records CSV: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS boundary sweep files to %s/\n", ckksBoundarySweepOutputDir)

	return nil
}
