package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksFullLogRegOutputDir = "results/ckks_full_logreg"

// RunCKKSFullLogReg runs the end-to-end CKKS logreg_small evaluation.
func RunCKKSFullLogReg() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunFullLogRegProbe()
	if err != nil {
		return fmt.Errorf("run CKKS full logreg probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS full logreg_small evaluation")
	fmt.Println("target: x1,x2,x3 -> z -> y -> decision")
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d x1=%.6f x2=%.6f x3=%.6f plain_z=%.10f ckks_z=%.10f z_error=%.10f plain_y=%.10f ckks_y=%.10f y_error=%.10f plain_decision=%t ckks_decision=%t flip=%t\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.ZError,
			result.PlainY,
			result.CKKSY,
			result.YError,
			result.PlainDecision,
			result.CKKSDecision,
			result.DecisionFlip,
		)
	}

	if err := report.WriteCKKSFullLogRegCSV(
		filepath.Join(ckksFullLogRegOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS full logreg CSV: %w", err)
	}

	if err := report.WriteCKKSFullLogRegMarkdown(
		filepath.Join(ckksFullLogRegOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS full logreg Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS full logreg files to %s/\n", ckksFullLogRegOutputDir)

	return nil
}
