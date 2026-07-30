package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSCubicProbeCSV writes encrypted cubic probe results.
func WriteCKKSCubicProbeCSV(path string, results []ckksbackend.CubicProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS cubic probe csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"z",
		"plain_z3",
		"raw_decoded_z3",
		"raw_abs_error",
		"scaled_decoded_z3",
		"scaled_abs_error",
		"selected_interpretation",
		"selected_z3",
		"selected_abs_error",
		"decode_scale_correction",
		"initial_level",
		"z2_level",
		"z3_level",
		"z_degree",
		"z2_degree",
		"z3_degree",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS cubic probe header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.Z),
			formatFloat(result.PlainZ3),
			formatFloat(result.RawDecodedZ3),
			formatFloat(result.RawAbsError),
			formatFloat(result.ScaledDecodedZ3),
			formatFloat(result.ScaledAbsError),
			string(result.SelectedInterpretation),
			formatFloat(result.SelectedZ3),
			formatFloat(result.SelectedAbsError),
			formatFloat(result.DecodeScaleCorrection),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.Z2Level),
			strconv.Itoa(result.Z3Level),
			strconv.Itoa(result.ZDegree),
			strconv.Itoa(result.Z2Degree),
			strconv.Itoa(result.Z3Degree),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS cubic probe row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS cubic probe csv: %w", err)
	}

	return nil
}

// WriteCKKSCubicProbeMarkdown writes encrypted cubic probe results.
func WriteCKKSCubicProbeMarkdown(path string, results []ckksbackend.CubicProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS cubic probe markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError := ckksCubicProbeErrors(results)

	fmt.Fprintf(f, "# CKKS Cubic Probe\n\n")
	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes encrypted cubic probe results in the CKKS backend.\n\n")
	fmt.Fprintf(f, "The probe evaluates:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "z2 = z * z\n")
	fmt.Fprintf(f, "z3 = z2 * z\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "The current path uses relinearization after each ciphertext-ciphertext multiplication and does not rescale. The goal is to determine whether the encrypted cubic term can be evaluated before implementing the full polynomial path.\n\n")

	fmt.Fprintf(f, "## Aggregate Selected Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_selected_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_selected_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n## Results\n\n")
	fmt.Fprintf(f, "| Index | z | Plain z3 | Selected z3 | Mode | Error | z Degree | z2 Degree | z3 Degree | Initial Level | z2 Level | z3 Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.10f | %.10f | %s | %.10f | %d | %d | %d | %d | %d | %d |\n",
			i,
			result.Z,
			result.PlainZ3,
			result.SelectedZ3,
			result.SelectedInterpretation,
			result.SelectedAbsError,
			result.ZDegree,
			result.Z2Degree,
			result.Z3Degree,
			result.InitialLevel,
			result.Z2Level,
			result.Z3Level,
		)
	}

	return nil
}

func ckksCubicProbeErrors(results []ckksbackend.CubicProbeResult) (float64, float64) {
	if len(results) == 0 {
		return 0, 0
	}

	maxError := 0.0
	sumError := 0.0

	for _, result := range results {
		sumError += result.SelectedAbsError
		if result.SelectedAbsError > maxError {
			maxError = result.SelectedAbsError
		}
	}

	return maxError, sumError / float64(len(results))
}
