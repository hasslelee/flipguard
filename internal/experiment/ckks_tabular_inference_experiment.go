package experiment

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksTabularInferenceOutputDir = "results/ckks_tabular_inference"

// RunCKKSTabularInference runs a generic tabular encrypted inference workload.
func RunCKKSTabularInference() error {
	options := GetRuntimeOptions()

	datasetID := getenvDefault("TABULAR_DATASET_ID", "wdbc")
	modelID := getenvDefault("TABULAR_MODEL_ID", "linear_poly3")
	dataRoot := getenvDefault("TABULAR_DATA_ROOT", "datasets/tabular_suite")
	maxRows, err := getenvIntDefault("TABULAR_MAX_ROWS", 0)
	if err != nil {
		return err
	}

	profile, err := CKKSProfileFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profile: %w", err)
	}

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	config := ckksbackend.DefaultCKKSTabularInferenceConfig(datasetID, modelID)
	config.ModelPath = filepath.Join(dataRoot, datasetID, modelID, "model.json")
	config.TestPath = filepath.Join(dataRoot, datasetID, modelID, "test.csv")
	config.MaxRows = maxRows
	config.EvaluationMode = options.CKKSEvaluationMode
	config.ScoreAbsErrorCap = options.CKKSScoreAbsErrorCap
	config.ScoreRelErrorCap = options.CKKSScoreRelErrorCap

	records, summary, err := ctx.RunCKKSTabularInference(config)
	if err != nil {
		return fmt.Errorf("run CKKS tabular inference: %w", err)
	}

	outputDir := CKKSResultDir(ckksTabularInferenceOutputDir)

	if err := report.WriteCKKSTabularInferenceSummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS tabular inference summary: %w", err)
	}

	if err := report.WriteCKKSTabularInferenceRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS tabular inference records: %w", err)
	}

	fmt.Println("FlipGuard CKKS generic tabular encrypted inference")
	fmt.Printf(
		"dataset_id=%s model_id=%s model_type=%s profile=%s evaluation_mode=%s evaluated_rows=%d\n",
		summary.DatasetID,
		summary.ModelID,
		summary.ModelType,
		profile.Name,
		summary.EvaluationMode,
		summary.EvaluatedRows,
	)
	fmt.Printf(
		"plain_accuracy=%.6f ckks_accuracy=%.6f decision_match_rate=%.6f decision_flips=%d score_error_violations=%d max_y_error=%.10f\n",
		summary.PlainAccuracy,
		summary.CKKSAccuracy,
		summary.DecisionMatchRate,
		summary.DecisionFlips,
		summary.ScoreErrorViolations,
		summary.MaxYError,
	)
	fmt.Printf(
		"mean_model_eval_ms=%.6f mean_polynomial_ms=%.6f mean_eval_only_ms=%.6f mean_total_ms=%.6f p95_total_ms=%.6f\n",
		summary.MeanModelEvalMS,
		summary.MeanPolynomialMS,
		summary.MeanEvalOnlyMS,
		summary.MeanTotalEvalMS,
		summary.P95TotalEvalMS,
	)
	fmt.Println()
	fmt.Printf("Exported CKKS tabular inference files to %s/\n", outputDir)

	return nil
}

func getenvDefault(key string, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}

func getenvIntDefault(key string, defaultValue int) (int, error) {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue, nil
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parse environment variable %s=%q as int: %w", key, value, err)
	}

	return parsed, nil
}
