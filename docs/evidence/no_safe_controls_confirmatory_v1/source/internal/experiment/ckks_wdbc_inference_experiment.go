package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksWDBCInferenceOutputDir = "results/ckks_wdbc_inference"

// RunCKKSWDBCInference runs WDBC encrypted inference evaluation.
func RunCKKSWDBCInference() error {
	options := GetRuntimeOptions()

	profile, err := CKKSProfileFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profile: %w", err)
	}

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	config := ckksbackend.DefaultCKKSWDBCInferenceConfig()
	config.EvaluationMode = options.CKKSEvaluationMode
	config.ScoreAbsErrorCap = options.CKKSScoreAbsErrorCap
	config.ScoreRelErrorCap = options.CKKSScoreRelErrorCap

	records, summary, err := ctx.RunCKKSWDBCInference(config)
	if err != nil {
		return fmt.Errorf("run CKKS WDBC inference: %w", err)
	}

	outputDir := CKKSResultDir(ckksWDBCInferenceOutputDir)

	if err := report.WriteCKKSWDBCInferenceSummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS WDBC inference summary: %w", err)
	}

	if err := report.WriteCKKSWDBCInferenceRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS WDBC inference records: %w", err)
	}

	fmt.Println("FlipGuard CKKS WDBC encrypted inference")
	fmt.Printf(
		"dataset=%s model=%s profile=%s evaluation_mode=%s evaluated_rows=%d\n",
		summary.Dataset,
		summary.Model,
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
		"mean_eval_only_ms=%.6f mean_total_ms=%.6f median_total_ms=%.6f p95_total_ms=%.6f\n",
		summary.MeanEvalOnlyMS,
		summary.MeanTotalEvalMS,
		summary.MedianTotalEvalMS,
		summary.P95TotalEvalMS,
	)
	fmt.Println()
	fmt.Printf("Exported CKKS WDBC inference files to %s/\n", outputDir)

	return nil
}
