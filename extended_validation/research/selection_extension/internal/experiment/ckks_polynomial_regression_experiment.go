package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksPolynomialRegressionOutputDir = "results/ckks_polynomial_regression"

// RunCKKSPolynomialRegression runs the CKKS encrypted polynomial regression
// probe.
func RunCKKSPolynomialRegression() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	results, err := ctx.RunPolynomialRegressionProbe()
	if err != nil {
		return fmt.Errorf("run CKKS polynomial regression probe: %w", err)
	}

	maxError, meanError, flips := summarizePolynomialRegressionProbe(results)

	fmt.Println("FlipGuard CKKS polynomial regression probe")
	fmt.Println("target: y = 0.12 + 0.70*x - 0.25*x^2 + 0.11*x^3 - 0.035*x^4 + 0.006*x^5")
	fmt.Printf("samples=%d decision_flips=%d max_abs_error=%.10f mean_abs_error=%.10f\n",
		len(results),
		flips,
		maxError,
		meanError,
	)
	fmt.Println()

	for i, result := range results {
		fmt.Printf(
			"case=%d x=%.6f plain_y=%.10f ckks_y=%.10f abs_error=%.10f plain_decision=%t ckks_decision=%t flip=%t x2=%.10f x3=%.10f x4=%.10f x5=%.10f initial_level=%d y_level=%d y_degree=%d\n",
			i,
			result.X,
			result.PlainY,
			result.CKKSY,
			result.AbsError,
			result.PlainDecision,
			result.CKKSDecision,
			result.DecisionFlip,
			result.X2Value,
			result.X3Value,
			result.X4Value,
			result.X5Value,
			result.InitialLevel,
			result.YLevel,
			result.YDegree,
		)
	}

	if err := report.WriteCKKSPolynomialRegressionCSV(
		filepath.Join(ckksPolynomialRegressionOutputDir, "summary.csv"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS polynomial regression CSV: %w", err)
	}

	if err := report.WriteCKKSPolynomialRegressionMarkdown(
		filepath.Join(ckksPolynomialRegressionOutputDir, "report.md"),
		results,
	); err != nil {
		return fmt.Errorf("write CKKS polynomial regression Markdown: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS polynomial regression files to %s/\n", ckksPolynomialRegressionOutputDir)

	return nil
}

func summarizePolynomialRegressionProbe(
	results []ckksbackend.PolynomialRegressionProbeResult,
) (maxError float64, meanError float64, flips int) {
	if len(results) == 0 {
		return 0, 0, 0
	}

	sumError := 0.0

	for _, result := range results {
		sumError += result.AbsError
		if result.AbsError > maxError {
			maxError = result.AbsError
		}
		if result.DecisionFlip {
			flips++
		}
	}

	return maxError, sumError / float64(len(results)), flips
}
