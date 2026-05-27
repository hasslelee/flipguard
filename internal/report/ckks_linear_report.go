package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSLinearSummaryCSV writes encrypted linear logreg evaluation results.
func WriteCKKSLinearSummaryCSV(path string, results []ckksbackend.LinearLogRegResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS linear summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"index",
		"x1",
		"x2",
		"x3",
		"plain_z",
		"raw_ckks_z",
		"ckks_z",
		"decode_scale_correction",
		"abs_error",
		"initial_level",
		"final_level",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS linear summary header: %w", err)
	}

	for i, result := range results {
		record := []string{
			strconv.Itoa(i),
			formatFloat(result.Input.X1),
			formatFloat(result.Input.X2),
			formatFloat(result.Input.X3),
			formatFloat(result.PlainZ),
			formatFloat(result.RawCKKSZ),
			formatFloat(result.CKKSZ),
			formatFloat(result.DecodeScaleCorrection),
			formatFloat(result.AbsError),
			strconv.Itoa(result.InitialLevel),
			strconv.Itoa(result.FinalLevel),
			strconv.Itoa(result.LogDefaultScale),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS linear summary row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS linear summary csv: %w", err)
	}

	return nil
}

// WriteCKKSLinearMarkdown writes a Markdown report for encrypted linear logreg evaluation.
func WriteCKKSLinearMarkdown(path string, results []ckksbackend.LinearLogRegResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS linear markdown: %w", err)
	}
	defer f.Close()

	maxError, meanError := ckksLinearErrors(results)

	fmt.Fprintf(f, "# CKKS Linear logreg_small Evaluation\n\n")

	fmt.Fprintf(f, "## English\n\n")
	fmt.Fprintf(f, "This report summarizes encrypted CKKS evaluation of the linear part of the current `logreg_small` benchmark.\n\n")
	fmt.Fprintf(f, "Target expression:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "This is not the full polynomial inference path yet. It validates ciphertext-constant multiplication, ciphertext addition, plaintext-bias addition, decryption, decoding, and comparison against the plaintext linear reference.\n\n")
	fmt.Fprintf(f, "The current implementation adds the bias term as a CKKS plaintext. Therefore the decoded linear output is expected to be directly in the plaintext domain, without the previous post-decode scale correction.\n\n")

	fmt.Fprintf(f, "### Aggregate Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n### Per-Sample Results\n\n")
	fmt.Fprintf(f, "| Index | x1 | x2 | x3 | Plain z | CKKS z | Abs Error | Correction | Initial Level | Final Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.10f | %.10f | %.1f | %d | %d |\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.AbsError,
			result.DecodeScaleCorrection,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	return nil
}

func ckksLinearErrors(results []ckksbackend.LinearLogRegResult) (float64, float64) {
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
