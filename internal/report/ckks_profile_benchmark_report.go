package report

import (
	"encoding/csv"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// CKKSProfileBenchmarkSummaryRow stores one profile benchmark summary row.
type CKKSProfileBenchmarkSummaryRow struct {
	ProfileName              string
	Description              string
	Status                   string
	Error                    string
	LogQCount                int
	LogPCount                int
	LogQPSum                 int
	MaxLevel                 int
	MaxSlots                 int
	LogDefaultScale          int
	WarmupRuns               int
	MeasurementRuns          int
	ContextSetupMS           float64
	CryptoSetupMS            float64
	MeanEncodeEncryptMS      float64
	MeanLinearEvalMS         float64
	MeanPolynomialEvalMS     float64
	MeanEvalOnlyMS           float64
	MeanDecryptDecodeMS      float64
	MeanTotalEvalMS          float64
	MedianTotalEvalMS        float64
	P95TotalEvalMS           float64
	SpeedupVsDefaultEvalOnly float64
	SpeedupVsDefaultTotal    float64
	DecisionFlips            int
	MaxYError                float64
	MeanYError               float64
	ScoreErrorBudget         float64
	ScoreErrorViolation      bool
	DecisionSafe             bool
	ProfileAccepted          bool
}

// CKKSProfileBenchmarkRecordRow stores one profile benchmark record row.
type CKKSProfileBenchmarkRecordRow struct {
	ProfileName string
	Record      ckksbackend.CKKSTimingBenchmarkRecord
}

// WriteCKKSProfileBenchmarkSummaryCSV writes CKKS profile benchmark summary rows.
func WriteCKKSProfileBenchmarkSummaryCSV(
	path string,
	rows []CKKSProfileBenchmarkSummaryRow,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS profile benchmark summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"profile",
		"description",
		"status",
		"error",
		"log_q_count",
		"log_p_count",
		"log_qp_sum",
		"max_level",
		"max_slots",
		"log_default_scale",
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
		"speedup_vs_default_eval_only",
		"speedup_vs_default_total",
		"decision_flips",
		"max_y_error",
		"mean_y_error",
		"score_error_budget",
		"score_error_violation",
		"decision_safe",
		"profile_accepted",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS profile benchmark summary header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.ProfileName,
			row.Description,
			row.Status,
			row.Error,
			fmt.Sprintf("%d", row.LogQCount),
			fmt.Sprintf("%d", row.LogPCount),
			fmt.Sprintf("%d", row.LogQPSum),
			fmt.Sprintf("%d", row.MaxLevel),
			fmt.Sprintf("%d", row.MaxSlots),
			fmt.Sprintf("%d", row.LogDefaultScale),
			fmt.Sprintf("%d", row.WarmupRuns),
			fmt.Sprintf("%d", row.MeasurementRuns),
			formatCKKSProfileBenchmarkFloat(row.ContextSetupMS),
			formatCKKSProfileBenchmarkFloat(row.CryptoSetupMS),
			formatCKKSProfileBenchmarkFloat(row.MeanEncodeEncryptMS),
			formatCKKSProfileBenchmarkFloat(row.MeanLinearEvalMS),
			formatCKKSProfileBenchmarkFloat(row.MeanPolynomialEvalMS),
			formatCKKSProfileBenchmarkFloat(row.MeanEvalOnlyMS),
			formatCKKSProfileBenchmarkFloat(row.MeanDecryptDecodeMS),
			formatCKKSProfileBenchmarkFloat(row.MeanTotalEvalMS),
			formatCKKSProfileBenchmarkFloat(row.MedianTotalEvalMS),
			formatCKKSProfileBenchmarkFloat(row.P95TotalEvalMS),
			formatCKKSProfileBenchmarkFloat(row.SpeedupVsDefaultEvalOnly),
			formatCKKSProfileBenchmarkFloat(row.SpeedupVsDefaultTotal),
			fmt.Sprintf("%d", row.DecisionFlips),
			formatCKKSProfileBenchmarkFloat(row.MaxYError),
			formatCKKSProfileBenchmarkFloat(row.MeanYError),
			formatCKKSProfileBenchmarkFloat(row.ScoreErrorBudget),
			fmt.Sprintf("%t", row.ScoreErrorViolation),
			fmt.Sprintf("%t", row.DecisionSafe),
			fmt.Sprintf("%t", row.ProfileAccepted),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write CKKS profile benchmark summary row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS profile benchmark summary csv: %w", err)
	}

	return nil
}

// WriteCKKSProfileBenchmarkRecordsCSV writes CKKS profile benchmark run records.
func WriteCKKSProfileBenchmarkRecordsCSV(
	path string,
	rows []CKKSProfileBenchmarkRecordRow,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS profile benchmark records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"profile",
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
		return fmt.Errorf("write CKKS profile benchmark records header: %w", err)
	}

	for i, row := range rows {
		record := row.Record

		csvRecord := []string{
			row.ProfileName,
			fmt.Sprintf("%d", record.Run),
			formatCKKSProfileBenchmarkFloat(record.EncodeEncryptMS),
			formatCKKSProfileBenchmarkFloat(record.LinearEvalMS),
			formatCKKSProfileBenchmarkFloat(record.PolynomialEvalMS),
			formatCKKSProfileBenchmarkFloat(record.EvalOnlyMS),
			formatCKKSProfileBenchmarkFloat(record.DecryptDecodeMS),
			formatCKKSProfileBenchmarkFloat(record.TotalEvalMS),
			formatCKKSProfileBenchmarkFloat(record.PlainZ),
			formatCKKSProfileBenchmarkFloat(record.CKKSZ),
			formatCKKSProfileBenchmarkFloat(record.ZError),
			formatCKKSProfileBenchmarkFloat(record.PlainY),
			formatCKKSProfileBenchmarkFloat(record.CKKSY),
			formatCKKSProfileBenchmarkFloat(record.YError),
			fmt.Sprintf("%t", record.PlainDecision),
			fmt.Sprintf("%t", record.CKKSDecision),
			fmt.Sprintf("%t", record.DecisionFlip),
			fmt.Sprintf("%d", record.InitialLevel),
			fmt.Sprintf("%d", record.ZLevel),
			fmt.Sprintf("%d", record.YLevel),
			fmt.Sprintf("%d", record.ZDegree),
			fmt.Sprintf("%d", record.YDegree),
		}

		if err := w.Write(csvRecord); err != nil {
			return fmt.Errorf("write CKKS profile benchmark record row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS profile benchmark records csv: %w", err)
	}

	return nil
}

func formatCKKSProfileBenchmarkFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
