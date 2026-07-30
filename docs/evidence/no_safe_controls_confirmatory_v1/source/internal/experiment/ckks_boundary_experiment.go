package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksBoundaryOutputDir = "results/ckks_boundary"

// RunCKKSBoundary runs boundary-focused end-to-end CKKS decision evaluation.
func RunCKKSBoundary() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunFullLogRegBoundaryProbe()
	if err != nil {
		return fmt.Errorf("run CKKS boundary probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS boundary decision evaluation")
	fmt.Println("target: boundary-focused x1,x2,x3 -> z -> y -> decision")
	fmt.Println()

	flipCount := 0
	stableFlipCount := 0

	for i, result := range results {
		if result.Result.DecisionFlip {
			flipCount++
		}

		if result.Stable && result.Result.DecisionFlip {
			stableFlipCount++
		}

		fmt.Printf(
			"case=%d target_z=%.6f plain_z=%.10f ckks_z=%.10f plain_y=%.10f ckks_y=%.10f margin=%.10f stable=%t ambiguous=%t plain_decision=%t ckks_decision=%t flip=%t\n",
			i,
			result.Case.TargetZ,
			result.Result.PlainZ,
			result.Result.CKKSZ,
			result.Result.PlainY,
			result.Result.CKKSY,
			result.Margin,
			result.Stable,
			result.Ambiguous,
			result.Result.PlainDecision,
			result.Result.CKKSDecision,
			result.Result.DecisionFlip,
		)
	}

	if err := report.WriteCKKSBoundaryCSV(
		filepath.Join(ckksBoundaryOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS boundary CSV: %w", err)
	}

	fmt.Println()
	fmt.Printf("samples=%d flips=%d stable_flips=%d\n", len(results), flipCount, stableFlipCount)
	fmt.Printf("Exported CKKS boundary files to %s/\n", ckksBoundaryOutputDir)

	return nil
}
