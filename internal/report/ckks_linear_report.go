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
	fmt.Fprintf(f, "This is not the full polynomial inference path yet. It validates ciphertext-constant multiplication, ciphertext addition, decryption, decoding, and comparison against the plaintext linear reference.\n\n")
	fmt.Fprintf(f, "The current implementation uses a temporary decode-scale correction for scalar multiplication output. A later step should replace this with explicit CKKS scale and rescale management.\n\n")

	fmt.Fprintf(f, "### Aggregate Error\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n### Per-Sample Results\n\n")
	fmt.Fprintf(f, "| Index | x1 | x2 | x3 | Plain z | CKKS z | Abs Error | Initial Level | Final Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.10f | %.10f | %d | %d |\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.AbsError,
			result.InitialLevel,
			result.FinalLevel,
		)
	}

	fmt.Fprintf(f, "\n---\n\n")
	fmt.Fprintf(f, "## 한국어\n\n")
	fmt.Fprintf(f, "이 문서는 현재 `logreg_small` benchmark의 linear part에 대한 encrypted CKKS evaluation 결과 요약.\n\n")
	fmt.Fprintf(f, "대상 수식:\n\n")
	fmt.Fprintf(f, "```text\n")
	fmt.Fprintf(f, "z = 0.8*x1 - 0.5*x2 + 1.2*x3 - 0.3\n")
	fmt.Fprintf(f, "```\n\n")
	fmt.Fprintf(f, "아직 전체 polynomial inference 경로는 아니다. Ciphertext-constant multiplication, ciphertext addition, decryption, decoding, plaintext linear reference와의 비교를 검증하는 단계다.\n\n")
	fmt.Fprintf(f, "현재 구현은 scalar multiplication 출력에 대해 임시 decode-scale correction 사용. 이후 explicit CKKS scale 및 rescale management 방식으로 대체 필요.\n\n")

	fmt.Fprintf(f, "### Aggregate Error\n\n")
	fmt.Fprintf(f, "| 항목 | 값 |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| samples | %d |\n", len(results))
	fmt.Fprintf(f, "| max_abs_error | %.10f |\n", maxError)
	fmt.Fprintf(f, "| mean_abs_error | %.10f |\n", meanError)

	fmt.Fprintf(f, "\n### Per-Sample Results\n\n")
	fmt.Fprintf(f, "| Index | x1 | x2 | x3 | Plain z | CKKS z | Abs Error | Initial Level | Final Level |\n")
	fmt.Fprintf(f, "|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")

	for i, result := range results {
		fmt.Fprintf(
			f,
			"| %d | %.6f | %.6f | %.6f | %.10f | %.10f | %.10f | %d | %d |\n",
			i,
			result.Input.X1,
			result.Input.X2,
			result.Input.X3,
			result.PlainZ,
			result.CKKSZ,
			result.AbsError,
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
