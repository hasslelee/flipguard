package experiment

import (
	"fmt"
	"path/filepath"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksTimingBenchmarkOutputDir = "results/ckks_timing_benchmark"

// RunCKKSTimingBenchmark measures the current CKKS encrypted inference path.
func RunCKKSTimingBenchmark() error {
	profile, err := CKKSProfileFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profile: %w", err)
	}

	contextStart := time.Now()

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	contextSetupMS := float64(time.Since(contextStart).Nanoseconds()) / 1e6

	config := CKKSTimingBenchmarkConfigFromRuntimeOptions()
	outputDir := CKKSResultDir(ckksTimingBenchmarkOutputDir)

	records, summary, err := ctx.RunCKKSTimingBenchmark(config)
	if err != nil {
		return fmt.Errorf("run CKKS timing benchmark: %w", err)
	}

	summary.ContextSetupMS = contextSetupMS

	if err := report.WriteCKKSTimingBenchmarkSummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS timing benchmark summary CSV: %w", err)
	}

	if err := report.WriteCKKSTimingBenchmarkRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS timing benchmark records CSV: %w", err)
	}

	fmt.Println("FlipGuard CKKS timing benchmark")
	fmt.Printf("profile=%s evaluation_mode=%s warmup_runs=%d measurement_runs=%d\n", ctx.ProfileName(), summary.EvaluationMode, summary.WarmupRuns, summary.MeasurementRuns)
	fmt.Printf("context_setup_ms=%.6f crypto_setup_ms=%.6f\n", summary.ContextSetupMS, summary.CryptoSetupMS)
	fmt.Println()
	fmt.Printf(
		"mean_total_ms=%.6f median_total_ms=%.6f p95_total_ms=%.6f min_total_ms=%.6f max_total_ms=%.6f\n",
		summary.MeanTotalEvalMS,
		summary.MedianTotalEvalMS,
		summary.P95TotalEvalMS,
		summary.MinTotalEvalMS,
		summary.MaxTotalEvalMS,
	)
	fmt.Printf(
		"mean_encode_encrypt_ms=%.6f mean_linear_eval_ms=%.6f mean_polynomial_eval_ms=%.6f mean_eval_only_ms=%.6f mean_decrypt_decode_ms=%.6f\n",
		summary.MeanEncodeEncryptMS,
		summary.MeanLinearEvalMS,
		summary.MeanPolynomialEvalMS,
		summary.MeanEvalOnlyMS,
		summary.MeanDecryptDecodeMS,
	)
	fmt.Println()
	fmt.Printf(
		"decision_flips=%d max_y_error=%.10f mean_y_error=%.10f initial_level=%d final_y_level=%d log_default_scale=%d max_slots=%d\n",
		summary.DecisionFlips,
		summary.MaxYError,
		summary.MeanYError,
		summary.InitialLevel,
		summary.FinalYLevel,
		summary.LogDefaultScale,
		summary.MaxSlots,
	)

	fmt.Println()
	fmt.Printf("Exported CKKS timing benchmark files to %s/\n", outputDir)

	return nil
}
