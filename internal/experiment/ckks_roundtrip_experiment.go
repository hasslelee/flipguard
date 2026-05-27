package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksRoundTripOutputDir = "results/ckks_roundtrip"

// RunCKKSRoundTrip runs a minimal Lattigo CKKS roundtrip experiment.
func RunCKKSRoundTrip() error {
	result, err := ckksbackend.RunRoundTripProbe()
	if err != nil {
		return fmt.Errorf("run CKKS roundtrip probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS roundtrip probe")
	fmt.Printf("want=%.10f got=%.10f abs_error=%.10f\n", result.Want, result.Got, result.AbsError)
	fmt.Printf("max_slots=%d max_level=%d log_default_scale=%d\n",
		result.MaxSlots,
		result.MaxLevel,
		result.LogDefaultScale,
	)

	if err := report.WriteCKKSRoundTripSummaryCSV(
		filepath.Join(ckksRoundTripOutputDir, "summary.csv"),
		result,
	); err != nil {
		return fmt.Errorf("write CKKS roundtrip summary CSV: %w", err)
	}

	if err := report.WriteCKKSRoundTripMarkdown(
		filepath.Join(ckksRoundTripOutputDir, "report.md"),
		result,
	); err != nil {
		return fmt.Errorf("write CKKS roundtrip Markdown report: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS roundtrip files to %s/\n", ckksRoundTripOutputDir)

	return nil
}
