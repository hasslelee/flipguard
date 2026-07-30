package report

import (
	"encoding/csv"
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSTabularInferenceSummaryCSV writes generic tabular encrypted inference summary.
func WriteCKKSTabularInferenceSummaryCSV(
	path string,
	summary ckksbackend.CKKSTabularInferenceSummary,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS tabular inference summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"dataset_id",
		"dataset_name",
		"model_id",
		"model_type",
		"train_samples",
		"test_samples",
		"evaluated_rows",
		"input_dim",
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
		"mean_model_eval_ms",
		"mean_polynomial_ms",
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
		summary.DatasetID,
		summary.DatasetName,
		summary.ModelID,
		summary.ModelType,
		fmt.Sprintf("%d", summary.TrainSamples),
		fmt.Sprintf("%d", summary.TestSamples),
		fmt.Sprintf("%d", summary.EvaluatedRows),
		fmt.Sprintf("%d", summary.InputDim),
		summary.EvaluationMode,
		formatCKKSTabularInferenceFloat(summary.PlainAccuracy),
		formatCKKSTabularInferenceFloat(summary.CKKSAccuracy),
		formatCKKSTabularInferenceFloat(summary.DecisionMatchRate),
		fmt.Sprintf("%d", summary.DecisionFlips),
		formatCKKSTabularInferenceFloat(summary.ScoreAbsErrorCap),
		formatCKKSTabularInferenceFloat(summary.ScoreRelErrorCap),
		fmt.Sprintf("%d", summary.ScoreErrorViolations),
		formatCKKSTabularInferenceFloat(summary.MaxYError),
		formatCKKSTabularInferenceFloat(summary.MeanYError),
		formatCKKSTabularInferenceFloat(summary.MaxErrorUsage),
		formatCKKSTabularInferenceFloat(summary.MeanErrorUsage),
		formatCKKSTabularInferenceFloat(summary.MeanEncodeEncryptMS),
		formatCKKSTabularInferenceFloat(summary.MeanModelEvalMS),
		formatCKKSTabularInferenceFloat(summary.MeanPolynomialMS),
		formatCKKSTabularInferenceFloat(summary.MeanEvalOnlyMS),
		formatCKKSTabularInferenceFloat(summary.MeanDecryptDecodeMS),
		formatCKKSTabularInferenceFloat(summary.MeanTotalEvalMS),
		formatCKKSTabularInferenceFloat(summary.MedianTotalEvalMS),
		formatCKKSTabularInferenceFloat(summary.P95TotalEvalMS),
		fmt.Sprintf("%d", summary.InitialLevel),
		fmt.Sprintf("%d", summary.FinalYLevel),
		fmt.Sprintf("%d", summary.LogDefaultScale),
		fmt.Sprintf("%d", summary.MaxSlots),
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS tabular inference summary header: %w", err)
	}

	if err := w.Write(record); err != nil {
		return fmt.Errorf("write CKKS tabular inference summary record: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS tabular inference summary csv: %w", err)
	}

	return nil
}

// WriteCKKSTabularInferenceRecordsCSV writes generic tabular encrypted inference records.
func WriteCKKSTabularInferenceRecordsCSV(
	path string,
	records []ckksbackend.CKKSTabularInferenceRecord,
) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS tabular inference records csv: %w", err)
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
		"model_eval_ms",
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
		return fmt.Errorf("write CKKS tabular inference records header: %w", err)
	}

	for i, record := range records {
		csvRecord := []string{
			fmt.Sprintf("%d", record.RowID),
			fmt.Sprintf("%d", record.Label),
			formatCKKSTabularInferenceFloat(record.PlainZ),
			formatCKKSTabularInferenceFloat(record.CKKSZ),
			formatCKKSTabularInferenceFloat(record.ZError),
			formatCKKSTabularInferenceFloat(record.PlainY),
			formatCKKSTabularInferenceFloat(record.CKKSY),
			formatCKKSTabularInferenceFloat(record.YError),
			formatCKKSTabularInferenceFloat(record.ErrorBudget),
			formatCKKSTabularInferenceFloat(record.ErrorUsage),
			fmt.Sprintf("%t", record.ErrorViolation),
			fmt.Sprintf("%t", record.PlainDecision),
			fmt.Sprintf("%t", record.CKKSDecision),
			fmt.Sprintf("%t", record.DecisionFlip),
			fmt.Sprintf("%t", record.PlainCorrect),
			fmt.Sprintf("%t", record.CKKSCorrect),
			formatCKKSTabularInferenceFloat(record.EncodeEncryptMS),
			formatCKKSTabularInferenceFloat(record.ModelEvalMS),
			formatCKKSTabularInferenceFloat(record.PolynomialEvalMS),
			formatCKKSTabularInferenceFloat(record.EvalOnlyMS),
			formatCKKSTabularInferenceFloat(record.DecryptDecodeMS),
			formatCKKSTabularInferenceFloat(record.TotalEvalMS),
			fmt.Sprintf("%d", record.InitialLevel),
			fmt.Sprintf("%d", record.ZLevel),
			fmt.Sprintf("%d", record.YLevel),
			fmt.Sprintf("%d", record.ZDegree),
			fmt.Sprintf("%d", record.YDegree),
		}

		if err := w.Write(csvRecord); err != nil {
			return fmt.Errorf("write CKKS tabular inference record row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS tabular inference records csv: %w", err)
	}

	return nil
}

func formatCKKSTabularInferenceFloat(value float64) string {
	return fmt.Sprintf("%.10f", value)
}
