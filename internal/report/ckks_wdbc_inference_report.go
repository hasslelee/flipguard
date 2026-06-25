package report

import (
	"encoding/csv"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSWDBCInferenceSummaryCSV writes WDBC encrypted inference summary.
func WriteCKKSWDBCInferenceSummaryCSV(
	path string,
	summary ckksbackend.CKKSWDBCInferenceSummary,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS WDBC inference summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"dataset",
		"model",
		"test_samples",
		"evaluated_rows",
		"evaluation_mode",
		"plain_accuracy",
		"ckks_accuracy",
		"decision_match_rate",
		"decision_flips",
		"score_abs_error_cap",
		"score_rel_error_cap",
		"score_error_violations",
		"max_y_error",
		"mean_y_error",
		"max_error_usage",
		"mean_error_usage",
		"mean_encode_encrypt_ms",
		"mean_linear_eval_ms",
		"mean_polynomial_eval_ms",
		"mean_eval_only_ms",
		"mean_decrypt_decode_ms",
		"mean_total_eval_ms",
		"median_total_eval_ms",
		"p95_total_eval_ms",
		"initial_level",
		"final_y_level",
		"log_default_scale",
		"max_slots",
	}

	record := []string{
		summary.Dataset,
		summary.Model,
		fmt.Sprintf("%d", summary.TestSamples),
		fmt.Sprintf("%d", summary.EvaluatedRows),
		summary.EvaluationMode,
		formatCKKSWDBCInferenceFloat(summary.PlainAccuracy),
		formatCKKSWDBCInferenceFloat(summary.CKKSAccuracy),
		formatCKKSWDBCInferenceFloat(summary.DecisionMatchRate),
		fmt.Sprintf("%d", summary.DecisionFlips),
		formatCKKSWDBCInferenceFloat(summary.ScoreAbsErrorCap),
		formatCKKSWDBCInferenceFloat(summary.ScoreRelErrorCap),
		fmt.Sprintf("%d", summary.ScoreErrorViolations),
		formatCKKSWDBCInferenceFloat(summary.MaxYError),
		formatCKKSWDBCInferenceFloat(summary.MeanYError),
		formatCKKSWDBCInferenceFloat(summary.MaxErrorUsage),
		formatCKKSWDBCInferenceFloat(summary.MeanErrorUsage),
		formatCKKSWDBCInferenceFloat(summary.MeanEncodeEncryptMS),
		formatCKKSWDBCInferenceFloat(summary.MeanLinearEvalMS),
		formatCKKSWDBCInferenceFloat(summary.MeanPolynomialEvalMS),
		formatCKKSWDBCInferenceFloat(summary.MeanEvalOnlyMS),
		formatCKKSWDBCInferenceFloat(summary.MeanDecryptDecodeMS),
		formatCKKSWDBCInferenceFloat(summary.MeanTotalEvalMS),
		formatCKKSWDBCInferenceFloat(summary.MedianTotalEvalMS),
		formatCKKSWDBCInferenceFloat(summary.P95TotalEvalMS),
		fmt.Sprintf("%d", summary.InitialLevel),
		fmt.Sprintf("%d", summary.FinalYLevel),
		fmt.Sprintf("%d", summary.LogDefaultScale),
		fmt.Sprintf("%d", summary.MaxSlots),
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS WDBC inference summary header: %w", err)
	}

	if err := w.Write(record); err != nil {
		return fmt.Errorf("write CKKS WDBC inference summary record: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS WDBC inference summary csv: %w", err)
	}

	return nil
}

// WriteCKKSWDBCInferenceRecordsCSV writes WDBC encrypted inference records.
func WriteCKKSWDBCInferenceRecordsCSV(
	path string,
	records []ckksbackend.CKKSWDBCInferenceRecord,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS WDBC inference records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"row_id",
		"label",
		"plain_z",
		"ckks_z",
		"z_error",
		"plain_y",
		"ckks_y",
		"y_error",
		"error_budget",
		"error_usage",
		"error_violation",
		"plain_decision",
		"ckks_decision",
		"decision_flip",
		"plain_correct",
		"ckks_correct",
		"encode_encrypt_ms",
		"linear_eval_ms",
		"polynomial_eval_ms",
		"eval_only_ms",
		"decrypt_decode_ms",
		"total_eval_ms",
		"initial_level",
		"z_level",
		"y_level",
		"z_degree",
		"y_degree",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS WDBC inference records header: %w", err)
	}

	for i, record := range records {
		csvRecord := []string{
			fmt.Sprintf("%d", record.RowID),
			fmt.Sprintf("%d", record.Label),
			formatCKKSWDBCInferenceFloat(record.PlainZ),
			formatCKKSWDBCInferenceFloat(record.CKKSZ),
			formatCKKSWDBCInferenceFloat(record.ZError),
			formatCKKSWDBCInferenceFloat(record.PlainY),
			formatCKKSWDBCInferenceFloat(record.CKKSY),
			formatCKKSWDBCInferenceFloat(record.YError),
			formatCKKSWDBCInferenceFloat(record.ErrorBudget),
			formatCKKSWDBCInferenceFloat(record.ErrorUsage),
			fmt.Sprintf("%t", record.ErrorViolation),
			fmt.Sprintf("%t", record.PlainDecision),
			fmt.Sprintf("%t", record.CKKSDecision),
			fmt.Sprintf("%t", record.DecisionFlip),
			fmt.Sprintf("%t", record.PlainCorrect),
			fmt.Sprintf("%t", record.CKKSCorrect),
			formatCKKSWDBCInferenceFloat(record.EncodeEncryptMS),
			formatCKKSWDBCInferenceFloat(record.LinearEvalMS),
			formatCKKSWDBCInferenceFloat(record.PolynomialEvalMS),
			formatCKKSWDBCInferenceFloat(record.EvalOnlyMS),
			formatCKKSWDBCInferenceFloat(record.DecryptDecodeMS),
			formatCKKSWDBCInferenceFloat(record.TotalEvalMS),
			fmt.Sprintf("%d", record.InitialLevel),
			fmt.Sprintf("%d", record.ZLevel),
			fmt.Sprintf("%d", record.YLevel),
			fmt.Sprintf("%d", record.ZDegree),
			fmt.Sprintf("%d", record.YDegree),
		}

		if err := w.Write(csvRecord); err != nil {
			return fmt.Errorf("write CKKS WDBC inference record row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS WDBC inference records csv: %w", err)
	}

	return nil
}

func formatCKKSWDBCInferenceFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
