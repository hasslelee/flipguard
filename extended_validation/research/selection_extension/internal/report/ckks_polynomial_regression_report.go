package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSPolynomialRegressionCSV writes encrypted polynomial regression probe
// results.
func WriteCKKSPolynomialRegressionCSV(
	path string,
	results []ckksbackend.PolynomialRegressionProbeResult,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS polynomial regression csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"x",
		"threshold",
		"plain_y",
		"ckks_y",
		"abs_error",
		"plain_decision",
		"ckks_decision",
		"decision_flip",
		"x2_value",
		"x3_value",
		"x4_value",
		"x5_value",
		"initial_level",
		"x2_level",
		"x3_level",
		"x4_level",
		"x5_level",
		"y_level",
		"x_degree",
		"x2_degree",
		"x3_degree",
		"x4_degree",
		"x5_degree",
		"y_degree",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS polynomial regression header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.X),
			formatFloat(result.Threshold),
			formatFloat(result.PlainY),
			formatFloat(result.CKKSY),
			formatFloat(result.AbsError),
			strconv.FormatBool(result.PlainDecision),
			strconv.FormatBool(result.CKKSDecision),
			strconv.FormatBool(result.DecisionFlip),
			formatFloat(result.X2Value),
			formatFloat(result.X3Value),
			formatFloat(result.X4Value),
			formatFloat(result.X5Value),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.X2Level),
			strconv.Itoa(result.X3Level),
			strconv.Itoa(result.X4Level),
			strconv.Itoa(result.X5Level),
			strconv.Itoa(result.YLevel),
			strconv.Itoa(result.XDegree),
			strconv.Itoa(result.X2Degree),
			strconv.Itoa(result.X3Degree),
			strconv.Itoa(result.X4Degree),
			strconv.Itoa(result.X5Degree),
			strconv.Itoa(result.YDegree),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS polynomial regression row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS polynomial regression csv: %w", err)
	}

	return nil
}

// WriteCKKSPolynomialRegressionMarkdown writes encrypted polynomial regression
// probe results.
func WriteCKKSPolynomialRegressionMarkdown(
	path string,
	results []ckksbackend.PolynomialRegressionProbeResult,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS polynomial regression markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError, flips := ckksPolynomialRegressionAggregate(results)

	fmt.Fprintf(f, "# CKKS Polynomial Regression Probe\n\n")
	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes encrypted evaluation for the standalone polynomial regression benchmark.\n\n")
	fmt.Fprintf(f, "Target expression:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "y = 0.12 + 0.70*x - 0.25*x^2 + 0.11*x^3 - 0.035*x^4 + 0.006*x^5\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "The benchmark exposes explicit program points `x2`, `x3`, `x4`, and `x5`, making it useful for error accumulation and precision scheduling analysis.\n\n")

	fmt.Fprintf(f, "## Aggregate Results\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| decision_flips | %d |\n", flips)
	fmt.Fprintf(f, "| max_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n## Results\n\n")
	fmt.Fprintf(f, "| Index | x | Plain y | CKKS y | Error | Plain decision | CKKS decision | Flip | x2 | x3 | x4 | x5 | Initial Level | y Level | y Degree |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.10f | %.10f | %.10f | %t | %t | %t | %.10f | %.10f | %.10f | %.10f | %d | %d | %d |\n",
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

	return nil
}

func ckksPolynomialRegressionAggregate(
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
