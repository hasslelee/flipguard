package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSPolynomialCSV writes encrypted polynomial probe results.
func WriteCKKSPolynomialCSV(path string, results []ckksbackend.PolynomialProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS polynomial csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"z",
		"plain_y",
		"ckks_y",
		"abs_error",
		"z3_value",
		"initial_level",
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
		return fmt.Errorf("write CKKS polynomial header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.Z),
			formatFloat(result.PlainY),
			formatFloat(result.CKKSY),
			formatFloat(result.AbsError),
			formatFloat(result.Z3Value),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.Z2Level),
			strconv.Itoa(result.Z3Level),
			strconv.Itoa(result.YLevel),
			strconv.Itoa(result.ZDegree),
			strconv.Itoa(result.Z2Degree),
			strconv.Itoa(result.Z3Degree),
			strconv.Itoa(result.YDegree),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS polynomial row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS polynomial csv: %w", err)
	}

	return nil
}

// WriteCKKSPolynomialMarkdown writes encrypted polynomial probe results.
func WriteCKKSPolynomialMarkdown(path string, results []ckksbackend.PolynomialProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS polynomial markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError := ckksPolynomialErrors(results)

	fmt.Fprintf(f, "# CKKS Polynomial logreg_small Probe\n\n")
	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes encrypted polynomial evaluation for the current `logreg_small` polynomial approximation.\n\n")
	fmt.Fprintf(f, "Target expression:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "y = 0.5 + 0.197*z - 0.004*z^3\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "The current path uses relinearization after ciphertext-ciphertext multiplication and plaintext bias addition for the constant term.\n\n")

	fmt.Fprintf(f, "## Aggregate Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n## Results\n\n")
	fmt.Fprintf(f, "| Index | z | Plain y | CKKS y | Error | z3 | z Degree | z2 Degree | z3 Degree | y Degree | Initial Level | y Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.10f | %.10f | %.10f | %.10f | %d | %d | %d | %d | %d | %d |\n",
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

	return nil
}

func ckksPolynomialErrors(results []ckksbackend.PolynomialProbeResult) (float64, float64) {
	if len(results) == 0 {
		return 0, 0
	}

	maxError := 0.0
	sumError := 0.0

	for _, result := range results {
		sumError += result.AbsError
		if result.AbsError > maxError {
			maxError = result.AbsError
		}
	}

	return maxError, sumError / float64(len(results))
}
