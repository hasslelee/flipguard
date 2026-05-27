package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSBiasProbeCSV writes bias-addition probe results to CSV.
func WriteCKKSBiasProbeCSV(path string, pairs []ckksbackend.BiasAdditionProbePair) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS bias probe csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"case_index",
		"method",
		"input",
		"scalar",
		"bias",
		"plain_value",
		"raw_decoded_value",
		"raw_abs_error",
		"scaled_decoded_value",
		"scaled_abs_error",
		"selected_interpretation",
		"selected_value",
		"selected_abs_error",
		"decode_scale_correction",
		"initial_level",
		"final_level",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS bias probe header: %w", err)
	}

	for i, pair := range pairs {
		results := []ckksbackend.BiasAdditionProbeResult{
			pair.ScalarBias,
			pair.PlaintextBias,
		}

		for _, result := range results {
			record := []string{
				strconv.Itoa(i),
				string(result.Method),
				formatFloat(result.Input),
				formatFloat(result.Scalar),
				formatFloat(result.Bias),
				formatFloat(result.PlainValue),
				formatFloat(result.RawDecodedValue),
				formatFloat(result.RawAbsError),
				formatFloat(result.ScaledDecodedValue),
				formatFloat(result.ScaledAbsError),
				string(result.SelectedInterpretation),
				formatFloat(result.SelectedValue),
				formatFloat(result.SelectedAbsError),
				formatFloat(result.DecodeScaleCorrection),
				strconv.Itoa(result.InitialLevel),
				strconv.Itoa(result.FinalLevel),
				strconv.Itoa(result.LogDefaultScale),
			}

			if err := w.Write(record); err != nil {
				return fmt.Errorf("write CKKS bias probe row %d/%s: %w", i, result.Method, err)
			}
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS bias probe csv: %w", err)
	}

	return nil
}

// WriteCKKSBiasProbeMarkdown writes bias-addition probe results to Markdown.
func WriteCKKSBiasProbeMarkdown(path string, pairs []ckksbackend.BiasAdditionProbePair) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS bias probe markdown: %w", err)
	}
	defer f.Close()

	fmt.Fprintf(f, "# CKKS Bias Addition Probe\n\n")

	fmt.Fprintf(f, "## English\n\n")
	fmt.Fprintf(f, "This report compares two ways of adding scalar bias terms in the current CKKS backend.\n\n")
	fmt.Fprintf(f, "Compared methods:\n\n")
	fmt.Fprintf(f, "- `scalar_bias`: `AddNew(ciphertext, float64_bias)`\n")
	fmt.Fprintf(f, "- `plaintext_bias`: encode the bias as CKKS plaintext and call `AddNew(ciphertext, plaintext_bias)`\n\n")
	fmt.Fprintf(f, "The goal is to determine whether plaintext bias addition avoids the temporary decode-scale correction currently used by the linear probe.\n\n")

	writeBiasProbeMarkdownTable(f, pairs)

	fmt.Fprintf(f, "\n---\n\n")
	fmt.Fprintf(f, "## 한국어\n\n")
	fmt.Fprintf(f, "이 문서는 현재 CKKS backend에서 scalar bias term을 더하는 두 방식 비교.\n\n")
	fmt.Fprintf(f, "비교 방식:\n\n")
	fmt.Fprintf(f, "- `scalar_bias`: `AddNew(ciphertext, float64_bias)`\n")
	fmt.Fprintf(f, "- `plaintext_bias`: bias를 CKKS plaintext로 encode한 뒤 `AddNew(ciphertext, plaintext_bias)` 호출\n\n")
	fmt.Fprintf(f, "목표는 plaintext bias addition이 현재 linear probe의 임시 decode-scale correction을 피할 수 있는지 확인하는 것이다.\n\n")

	writeBiasProbeMarkdownTable(f, pairs)

	return nil
}

func writeBiasProbeMarkdownTable(f *os.File, pairs []ckksbackend.BiasAdditionProbePair) {
	fmt.Fprintf(f, "### Results\n\n")
	fmt.Fprintf(f, "| Case | Method | Plain | Raw | Scaled | Selected | Mode | Error |\n")
	fmt.Fprintf(f, "|---:|---|---:|---:|---:|---:|---|---:|\n")

	for i, pair := range pairs {
		results := []ckksbackend.BiasAdditionProbeResult{
			pair.ScalarBias,
			pair.PlaintextBias,
		}

		for _, result := range results {
			fmt.Fprintf(
				f,
				"| %d | %s | %.10f | %.6f | %.10f | %.10f | %s | %.10f |\n",
				i,
				result.Method,
				result.PlainValue,
				result.RawDecodedValue,
				result.ScaledDecodedValue,
				result.SelectedValue,
				result.SelectedInterpretation,
				result.SelectedAbsError,
			)
		}
	}
}
