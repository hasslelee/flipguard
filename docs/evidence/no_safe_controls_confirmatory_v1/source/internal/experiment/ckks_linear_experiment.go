package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksLinearOutputDir = "results/ckks_linear"

// RunCKKSLinear runs encrypted CKKS evaluation for the linear part of logreg_small.
func RunCKKSLinear() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	inputs := []ckksbackend.LogRegSmallInput{
		{
			X1: 0.8,
			X2: -0.3,
			X3: 0.1,
		},
		{
			X1: 0.0,
			X2: 0.0,
			X3: 0.0,
		},
		{
			X1: 1.0,
			X2: 0.5,
			X3: -0.25,
		},
		{
			X1: -0.7,
			X2: 0.25,
			X3: 0.9,
		},
	}

	results := make([]ckksbackend.LinearLogRegResult, 0, len(inputs))

	fmt.Println("FlipGuard CKKS linear logreg_small evaluation")
	fmt.Println("target: z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3")
	fmt.Println()

	for i, input := range inputs {
		result, err := ctx.EvalLogRegSmallLinearEncrypted(input)
		if err != nil {
			return fmt.Errorf("evaluate encrypted linear sample %d: %w", i, err)
		}

		results = append(results, result)

		fmt.Printf(
			"sample=%d x1=%.6f x2=%.6f x3=%.6f plain_z=%.10f ckks_z=%.10f abs_error=%.10f initial_level=%d final_level=%d\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.AbsError,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	if err := report.WriteCKKSLinearSummaryCSV(
		filepath.Join(ckksLinearOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS linear summary CSV: %w", err)
	}

	if err := report.WriteCKKSLinearMarkdown(
		filepath.Join(ckksLinearOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS linear Markdown report: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS linear files to %s/\n", ckksLinearOutputDir)

	return nil
}
