package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSScaleProbeCSV writes scalar scale probe results to CSV.
func WriteCKKSScaleProbeCSV(path string, results []ckksbackend.ScalarScaleProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS scale probe csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
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
		"raw_over_plain",
		"scaled_over_plain",
		"correction_over_raw",
		"initial_level",
		"final_level",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS scale probe header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
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
			formatFloat(result.RawOverPlain),
			formatFloat(result.ScaledOverPlain),
			formatFloat(result.CorrectionOverRaw),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.FinalLevel),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS scale probe row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS scale probe csv: %w", err)
	}

	return nil
}

// WriteCKKSScaleProbeMarkdown writes scalar scale probe results to Markdown.
func WriteCKKSScaleProbeMarkdown(path string, results []ckksbackend.ScalarScaleProbeResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS scale probe markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError := ckksScaleProbeErrors(results)

	fmt.Fprintf(f, "# CKKS Scalar Scale Probe\n\n")

	fmt.Fprintf(f, "## English\n\n")
	fmt.Fprintf(f, "This report summarizes the observed scale behavior of the current Lattigo CKKS scalar multiplication and scalar-bias addition path.\n\n")
	fmt.Fprintf(f, "The probe evaluates expressions of the form:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "y = scalar * input + bias\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "The current backend observes two different interpretations:\n\n")
	fmt.Fprintf(f, "- without scalar bias, the raw decoded value already matches the plaintext-domain value\n")
	fmt.Fprintf(f, "- with scalar bias, the raw decoded value is approximately scaled by `2^log_default_scale`\n\n")
	fmt.Fprintf(f, "For diagnostics, the probe records both raw and scaled interpretations and selects the one with the smaller absolute error.\n\n")
	fmt.Fprintf(f, "This is a diagnostic artifact, not the final CKKS scale-management design.\n\n")

	fmt.Fprintf(f, "### Aggregate Selected Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_selected_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_selected_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n### Results\n\n")
	fmt.Fprintf(f, "| Index | Input | Scalar | Bias | Plain | Raw | Scaled | Selected | Mode | Error |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.4f | %.10f | %.10f | %s | %.10f |\n",
			i,
			result.Input,
			result.Scalar,
			result.Bias,
			result.PlainValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.SelectedValue,
			result.SelectedInterpretation,
			result.SelectedAbsError,
		)
	}

	fmt.Fprintf(f, "\n---\n\n")
	fmt.Fprintf(f, "## 한국어\n\n")
	fmt.Fprintf(f, "이 문서는 현재 Lattigo CKKS scalar multiplication 및 scalar-bias addition 경로의 scale behavior 관측 결과 요약.\n\n")
	fmt.Fprintf(f, "Probe 대상 수식:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "y = scalar * input + bias\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "현재 backend에서는 두 가지 해석이 관측된다.\n\n")
	fmt.Fprintf(f, "- scalar bias가 없을 때 raw decoded value가 plaintext-domain value와 직접 일치\n")
	fmt.Fprintf(f, "- scalar bias가 있을 때 raw decoded value가 대략 `2^log_default_scale`만큼 scaling\n\n")
	fmt.Fprintf(f, "진단을 위해 probe는 raw 해석과 scaled 해석을 모두 기록하고, absolute error가 더 작은 해석을 선택한다.\n\n")
	fmt.Fprintf(f, "이 문서는 diagnostic artifact이며, 최종 CKKS scale-management 설계가 아니다.\n\n")

	fmt.Fprintf(f, "### Aggregate Selected Error\n\n")
	fmt.Fprintf(f, "| 항목 | 값 |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_selected_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_selected_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n### Results\n\n")
	fmt.Fprintf(f, "| Index | Input | Scalar | Bias | Plain | Raw | Scaled | Selected | Mode | Error |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.4f | %.10f | %.10f | %s | %.10f |\n",
			i,
			result.Input,
			result.Scalar,
			result.Bias,
			result.PlainValue,
			result.RawDecodedValue,
			result.ScaledDecodedValue,
			result.SelectedValue,
			result.SelectedInterpretation,
			result.SelectedAbsError,
		)
	}

	return nil
}

func ckksScaleProbeErrors(results []ckksbackend.ScalarScaleProbeResult) (float64, float64) {
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
