package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSMulProbeCSV writes ciphertext-ciphertext multiplication probe results.
func WriteCKKSMulProbeCSV(path string, results []ckksbackend.MultiplicationProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS multiplication probe csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"z",
		"plain_z2",
		"raw_decoded_z2",
		"raw_abs_error",
		"scaled_decoded_z2",
		"scaled_abs_error",
		"selected_interpretation",
		"selected_z2",
		"selected_abs_error",
		"decode_scale_correction",
		"initial_level",
		"final_level",
		"input_degree",
		"output_degree",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS multiplication probe header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.Z),
			formatFloat(result.PlainZ2),
			formatFloat(result.RawDecodedZ2),
			formatFloat(result.RawAbsError),
			formatFloat(result.ScaledDecodedZ2),
			formatFloat(result.ScaledAbsError),
			string(result.SelectedInterpretation),
			formatFloat(result.SelectedZ2),
			formatFloat(result.SelectedAbsError),
			formatFloat(result.DecodeScaleCorrection),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.FinalLevel),
			strconv.Itoa(result.InputDegree),
			strconv.Itoa(result.OutputDegree),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS multiplication probe row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS multiplication probe csv: %w", err)
	}

	return nil
}

// WriteCKKSMulProbeMarkdown writes ciphertext-ciphertext multiplication probe results.
func WriteCKKSMulProbeMarkdown(path string, results []ckksbackend.MultiplicationProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS multiplication probe markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError := ckksMulProbeErrors(results)

	fmt.Fprintf(f, "# CKKS Multiplication Probe\n\n")
	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes the first ciphertext-ciphertext multiplication probe in the CKKS backend.\n\n")
	fmt.Fprintf(f, "The probe evaluates:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "z2 = z * z\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "The current probe uses `MulNew` without relinearization and without rescaling. It records the output degree, level, raw decoded value, scaled interpretation, and selected interpretation.\n\n")

	fmt.Fprintf(f, "## Aggregate Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_selected_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_selected_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n## Results\n\n")
	fmt.Fprintf(f, "| Index | z | Plain z2 | Raw z2 | Scaled z2 | Selected z2 | Mode | Error | In Degree | Out Degree | Initial Level | Final Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.10f | %.10f | %.10f | %.10f | %s | %.10f | %d | %d | %d | %d |\n",
			i,
			result.Z,
			result.PlainZ2,
			result.RawDecodedZ2,
			result.ScaledDecodedZ2,
			result.SelectedZ2,
			result.SelectedInterpretation,
			result.SelectedAbsError,
			result.InputDegree,
			result.OutputDegree,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	return nil
}

func ckksMulProbeErrors(results []ckksbackend.MultiplicationProbeResult) (float64, float64) {
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
