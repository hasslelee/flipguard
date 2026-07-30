package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSFullLogRegCSV writes end-to-end encrypted logreg_small results.
func WriteCKKSFullLogRegCSV(path string, results []ckksbackend.FullLogRegProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS full logreg csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"x1",
		"x2",
		"x3",
		"threshold",
		"plain_z",
		"ckks_z",
		"z_error",
		"plain_y",
		"ckks_y",
		"y_error",
		"plain_decision",
		"ckks_decision",
		"decision_flip",
		"initial_level",
		"z_level",
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
		return fmt.Errorf("write CKKS full logreg header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.Input.X1),
			formatFloat(result.Input.X2),
			formatFloat(result.Input.X3),
			formatFloat(result.Threshold),
			formatFloat(result.PlainZ),
			formatFloat(result.CKKSZ),
			formatFloat(result.ZError),
			formatFloat(result.PlainY),
			formatFloat(result.CKKSY),
			formatFloat(result.YError),
			strconv.FormatBool(result.PlainDecision),
			strconv.FormatBool(result.CKKSDecision),
			strconv.FormatBool(result.DecisionFlip),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.ZLevel),
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
			return fmt.Errorf("write CKKS full logreg row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS full logreg csv: %w", err)
	}

	return nil
}

// WriteCKKSFullLogRegMarkdown writes end-to-end encrypted logreg_small results.
func WriteCKKSFullLogRegMarkdown(path string, results []ckksbackend.FullLogRegProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS full logreg markdown: %w", err)
	}
	defer f.Close()

	maxZError, meanZError, maxYError, meanYError, flips := ckksFullLogRegStats(results)

	fmt.Fprintf(f, "# CKKS Full logreg_small Evaluation\n\n")
	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes end-to-end encrypted CKKS evaluation for the current `logreg_small` benchmark.\n\n")
	fmt.Fprintf(f, "Evaluation flow:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "x1, x2, x3 -> z -> y -> decision\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "Target expressions:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3\n")
	fmt.Fprintf(f, "y = 0.5 + 0.197*z - 0.004*z^3\n")
	fmt.Fprintf(f, "decision = y >= 0.5\n")
	fmt.Fprintf(f, "```\n\n")

	fmt.Fprintf(f, "## Aggregate Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| decision_flips | %d |\n", flips)
	fmt.Fprintf(f, "| max_z_error | %.10f |\n", maxZError)
	fmt.Fprintf(f, "| mean_z_error | %.10f |\n", meanZError)
	fmt.Fprintf(f, "| max_y_error | %.10f |\n", maxYError)
	fmt.Fprintf(f, "| mean_y_error | %.10f |\n", meanYError)

	fmt.Fprintf(f, "\n## Results\n\n")
	fmt.Fprintf(f, "| Index | x1 | x2 | x3 | Plain z | CKKS z | Plain y | CKKS y | y Error | Plain Decision | CKKS Decision | Flip |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.10f | %.10f | %.10f | %.10f | %t | %t | %t |\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.PlainY,
			result.CKKSY,
			result.YError,
			result.PlainDecision,
			result.CKKSDecision,
			result.DecisionFlip,
		)
	}

	return nil
}

func ckksFullLogRegStats(results []ckksbackend.FullLogRegProbeResult) (float64, float64, float64, float64, int) {
	if len(results) == 0 {
		return 0, 0, 0, 0, 0
	}

	maxZError := 0.0
	sumZError := 0.0
	maxYError := 0.0
	sumYError := 0.0
	flips := 0

	for _, result := range results {
		sumZError += result.ZError
		sumYError += result.YError

		if result.ZError > maxZError {
			maxZError = result.ZError
		}

		if result.YError > maxYError {
			maxYError = result.YError
		}

		if result.DecisionFlip {
			flips++
		}
	}

	return maxZError, sumZError / float64(len(results)), maxYError, sumYError / float64(len(results)), flips
}
