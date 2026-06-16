package report

import (
	"encoding/csv"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSTimingBenchmarkSummaryCSV writes CKKS timing benchmark summary data.
func WriteCKKSTimingBenchmarkSummaryCSV(
	path string,
	summary ckksbackend.CKKSTimingBenchmarkSummary,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS timing benchmark summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"warmup_runs",
		"measurement_runs",
		"context_setup_ms",
		"crypto_setup_ms",
		"mean_encode_encrypt_ms",
		"mean_linear_eval_ms",
		"mean_polynomial_eval_ms",
		"mean_eval_only_ms",
		"mean_decrypt_decode_ms",
		"mean_total_eval_ms",
		"median_total_eval_ms",
		"p95_total_eval_ms",
		"min_total_eval_ms",
		"max_total_eval_ms",
		"max_y_error",
		"mean_y_error",
		"decision_flips",
		"initial_level",
		"final_y_level",
		"log_default_scale",
		"max_slots",
	}

	record := []string{
		fmt.Sprintf("%d", summary.WarmupRuns),
		fmt.Sprintf("%d", summary.MeasurementRuns),
		formatCKKSTimingFloat(summary.ContextSetupMS),
		formatCKKSTimingFloat(summary.CryptoSetupMS),
		formatCKKSTimingFloat(summary.MeanEncodeEncryptMS),
		formatCKKSTimingFloat(summary.MeanLinearEvalMS),
		formatCKKSTimingFloat(summary.MeanPolynomialEvalMS),
		formatCKKSTimingFloat(summary.MeanEvalOnlyMS),
		formatCKKSTimingFloat(summary.MeanDecryptDecodeMS),
		formatCKKSTimingFloat(summary.MeanTotalEvalMS),
		formatCKKSTimingFloat(summary.MedianTotalEvalMS),
		formatCKKSTimingFloat(summary.P95TotalEvalMS),
		formatCKKSTimingFloat(summary.MinTotalEvalMS),
		formatCKKSTimingFloat(summary.MaxTotalEvalMS),
		formatCKKSTimingFloat(summary.MaxYError),
		formatCKKSTimingFloat(summary.MeanYError),
		fmt.Sprintf("%d", summary.DecisionFlips),
		fmt.Sprintf("%d", summary.InitialLevel),
		fmt.Sprintf("%d", summary.FinalYLevel),
		fmt.Sprintf("%d", summary.LogDefaultScale),
		fmt.Sprintf("%d", summary.MaxSlots),
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS timing benchmark summary header: %w", err)
	}

	if err := w.Write(record); err != nil {
		return fmt.Errorf("write CKKS timing benchmark summary record: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS timing benchmark summary csv: %w", err)
	}

	return nil
}

// WriteCKKSTimingBenchmarkRecordsCSV writes CKKS timing benchmark run records.
func WriteCKKSTimingBenchmarkRecordsCSV(
	path string,
	records []ckksbackend.CKKSTimingBenchmarkRecord,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS timing benchmark records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"run",
		"encode_encrypt_ms",
		"linear_eval_ms",
		"polynomial_eval_ms",
		"eval_only_ms",
		"decrypt_decode_ms",
		"total_eval_ms",
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
		"y_level",
		"z_degree",
		"y_degree",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS timing benchmark records header: %w", err)
	}

	for i, record := range records {
		row := []string{
			fmt.Sprintf("%d", record.Run),
			formatCKKSTimingFloat(record.EncodeEncryptMS),
			formatCKKSTimingFloat(record.LinearEvalMS),
			formatCKKSTimingFloat(record.PolynomialEvalMS),
			formatCKKSTimingFloat(record.EvalOnlyMS),
			formatCKKSTimingFloat(record.DecryptDecodeMS),
			formatCKKSTimingFloat(record.TotalEvalMS),
			formatCKKSTimingFloat(record.PlainZ),
			formatCKKSTimingFloat(record.CKKSZ),
			formatCKKSTimingFloat(record.ZError),
			formatCKKSTimingFloat(record.PlainY),
			formatCKKSTimingFloat(record.CKKSY),
			formatCKKSTimingFloat(record.YError),
			fmt.Sprintf("%t", record.PlainDecision),
			fmt.Sprintf("%t", record.CKKSDecision),
			fmt.Sprintf("%t", record.DecisionFlip),
			fmt.Sprintf("%d", record.InitialLevel),
			fmt.Sprintf("%d", record.ZLevel),
			fmt.Sprintf("%d", record.YLevel),
			fmt.Sprintf("%d", record.ZDegree),
			fmt.Sprintf("%d", record.YDegree),
		}

		if err := w.Write(row); err != nil {
			return fmt.Errorf("write CKKS timing benchmark record %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS timing benchmark records csv: %w", err)
	}

	return nil
}

func formatCKKSTimingFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
