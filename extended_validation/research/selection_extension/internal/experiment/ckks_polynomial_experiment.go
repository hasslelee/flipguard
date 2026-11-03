package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksPolynomialOutputDir = "results/ckks_polynomial"

// RunCKKSPolynomial runs the CKKS encrypted polynomial probe.
func RunCKKSPolynomial() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunPolynomialProbe()
	if err != nil {
		return fmt.Errorf("run CKKS polynomial probe: %w", err)
	}

	fmt.Println("FlipGuard CKKS polynomial logreg_small probe")
	fmt.Println("target: y = 0.5 + 0.197*z - 0.004*z^3")
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d z=%.6f plain_y=%.10f ckks_y=%.10f abs_error=%.10f z3=%.10f z_degree=%d z2_degree=%d z3_degree=%d y_degree=%d initial_level=%d y_level=%d\n",
			i,
			result.Z,
			result.PlainY,
			result.CKKSY,
			result.AbsError,
			result.Z3Value,
			result.ZDegree,
			result.Z2Degree,
			result.Z3Degree,
			result.YDegree,
			result.InitialLevel,
			result.YLevel,
		)
	}

	if err := report.WriteCKKSPolynomialCSV(
		filepath.Join(ckksPolynomialOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS polynomial CSV: %w", err)
	}

	if err := report.WriteCKKSPolynomialMarkdown(
		filepath.Join(ckksPolynomialOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS polynomial Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS polynomial files to %s/\n", ckksPolynomialOutputDir)

	return nil
}
