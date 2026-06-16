package experiment

import (
	"fmt"
	"math"
	"path/filepath"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksProfileBenchmarkOutputDir = "results/ckks_profile_benchmark"

// RunCKKSProfileBenchmark runs timing benchmarks across selected CKKS profiles.
func RunCKKSProfileBenchmark() error {
	profiles, err := CKKSProfilesFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profiles: %w", err)
	}

	config := CKKSTimingBenchmarkConfigFromRuntimeOptions()
	options := GetRuntimeOptions()

	scoreErrorBudget, err := profileBenchmarkScoreErrorBudget(
		config.Input,
		options.CKKSScoreAbsErrorCap,
		options.CKKSScoreRelErrorCap,
	)
	if err != nil {
		return fmt.Errorf("compute profile benchmark score error budget: %w", err)
	}

	summaryRows := make([]report.CKKSProfileBenchmarkSummaryRow, 0, len(profiles))
	recordRows := make([]report.CKKSProfileBenchmarkRecordRow, 0, len(profiles)*config.MeasurementRuns)

	for _, profile := range profiles {
		summaryRow, profileRecordRows := runSingleCKKSProfileBenchmark(profile, config)

		applyCKKSProfileBenchmarkSafety(&summaryRow, scoreErrorBudget)

		summaryRows = append(summaryRows, summaryRow)
		recordRows = append(recordRows, profileRecordRows...)
	}

	applyCKKSProfileBenchmarkSpeedups(summaryRows)

	successCount := 0
	acceptedCount := 0
	for _, row := range summaryRows {
		if row.Status == "ok" {
			successCount++
		}

		if row.ProfileAccepted {
			acceptedCount++
		}
	}

	if successCount == 0 {
		return fmt.Errorf("all CKKS profile benchmarks failed")
	}

	outputDir := CKKSResultDir(ckksProfileBenchmarkOutputDir)

	if err := report.WriteCKKSProfileBenchmarkSummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summaryRows,
	); err != nil {
		return fmt.Errorf("write CKKS profile benchmark summary CSV: %w", err)
	}

	if err := report.WriteCKKSProfileBenchmarkRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		recordRows,
	); err != nil {
		return fmt.Errorf("write CKKS profile benchmark records CSV: %w", err)
	}

	fmt.Println("FlipGuard CKKS profile benchmark")
	fmt.Printf(
		"profiles=%d successful_profiles=%d accepted_profiles=%d warmup_runs=%d measurement_runs=%d score_error_budget=%.10f\n",
		len(profiles),
		successCount,
		acceptedCount,
		config.WarmupRuns,
		config.MeasurementRuns,
		scoreErrorBudget,
	)
	fmt.Println()

	for _, row := range summaryRows {
		fmt.Printf(
			"profile=%s status=%s accepted=%t decision_safe=%t score_error_violation=%t log_q_count=%d log_p_count=%d log_qp_sum=%d max_level=%d log_default_scale=%d mean_eval_only_ms=%.6f mean_total_ms=%.6f speedup_eval_only=%.6f decision_flips=%d max_y_error=%.10f error=%s\n",
			row.ProfileName,
			row.Status,
			row.ProfileAccepted,
			row.DecisionSafe,
			row.ScoreErrorViolation,
			row.LogQCount,
			row.LogPCount,
			row.LogQPSum,
			row.MaxLevel,
			row.LogDefaultScale,
			row.MeanEvalOnlyMS,
			row.MeanTotalEvalMS,
			row.SpeedupVsDefaultEvalOnly,
			row.DecisionFlips,
			row.MaxYError,
			row.Error,
		)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS profile benchmark files to %s/\n", outputDir)

	return nil
}

func runSingleCKKSProfileBenchmark(
	profile ckksbackend.CKKSProfile,
	config ckksbackend.CKKSTimingBenchmarkConfig,
) (report.CKKSProfileBenchmarkSummaryRow, []report.CKKSProfileBenchmarkRecordRow) {
	baseRow := report.CKKSProfileBenchmarkSummaryRow{
		ProfileName:     profile.Name,
		Description:     profile.Description,
		Status:          "failed",
		LogQCount:       profile.LogQCount(),
		LogPCount:       profile.LogPCount(),
		LogQPSum:        profile.LogQPSum(),
		LogDefaultScale: profile.LogDefaultScale(),
		WarmupRuns:      config.WarmupRuns,
		MeasurementRuns: config.MeasurementRuns,
	}

	contextStart := time.Now()

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		baseRow.Error = sanitizeProfileBenchmarkError(err)
		return baseRow, nil
	}

	contextSetupMS := float64(time.Since(contextStart).Nanoseconds()) / 1e6

	records, summary, err := ctx.RunCKKSTimingBenchmark(config)
	if err != nil {
		baseRow.Error = sanitizeProfileBenchmarkError(err)
		baseRow.ContextSetupMS = contextSetupMS
		baseRow.MaxLevel = ctx.MaxLevel()
		baseRow.MaxSlots = ctx.MaxSlots()
		return baseRow, nil
	}

	summary.ContextSetupMS = contextSetupMS

	row := report.CKKSProfileBenchmarkSummaryRow{
		ProfileName:          profile.Name,
		Description:          profile.Description,
		Status:               "ok",
		Error:                "",
		LogQCount:            profile.LogQCount(),
		LogPCount:            profile.LogPCount(),
		LogQPSum:             profile.LogQPSum(),
		MaxLevel:             ctx.MaxLevel(),
		MaxSlots:             ctx.MaxSlots(),
		LogDefaultScale:      ctx.LogDefaultScale(),
		WarmupRuns:           summary.WarmupRuns,
		MeasurementRuns:      summary.MeasurementRuns,
		ContextSetupMS:       summary.ContextSetupMS,
		CryptoSetupMS:        summary.CryptoSetupMS,
		MeanEncodeEncryptMS:  summary.MeanEncodeEncryptMS,
		MeanLinearEvalMS:     summary.MeanLinearEvalMS,
		MeanPolynomialEvalMS: summary.MeanPolynomialEvalMS,
		MeanEvalOnlyMS:       summary.MeanEvalOnlyMS,
		MeanDecryptDecodeMS:  summary.MeanDecryptDecodeMS,
		MeanTotalEvalMS:      summary.MeanTotalEvalMS,
		MedianTotalEvalMS:    summary.MedianTotalEvalMS,
		P95TotalEvalMS:       summary.P95TotalEvalMS,
		DecisionFlips:        summary.DecisionFlips,
		MaxYError:            summary.MaxYError,
		MeanYError:           summary.MeanYError,
	}

	recordRows := make([]report.CKKSProfileBenchmarkRecordRow, 0, len(records))
	for _, record := range records {
		recordRows = append(recordRows, report.CKKSProfileBenchmarkRecordRow{
			ProfileName: profile.Name,
			Record:      record,
		})
	}

	return row, recordRows
}

func applyCKKSProfileBenchmarkSafety(
	row *report.CKKSProfileBenchmarkSummaryRow,
	scoreErrorBudget float64,
) {
	row.ScoreErrorBudget = scoreErrorBudget

	if row.Status != "ok" {
		row.DecisionSafe = false
		row.ScoreErrorViolation = true
		row.ProfileAccepted = false
		return
	}

	row.DecisionSafe = row.DecisionFlips == 0
	row.ScoreErrorViolation = row.MaxYError > scoreErrorBudget
	row.ProfileAccepted = row.DecisionSafe && !row.ScoreErrorViolation
}

func applyCKKSProfileBenchmarkSpeedups(rows []report.CKKSProfileBenchmarkSummaryRow) {
	defaultEvalOnly := 0.0
	defaultTotal := 0.0

	for _, row := range rows {
		if row.ProfileName == "default" && row.Status == "ok" {
			defaultEvalOnly = row.MeanEvalOnlyMS
			defaultTotal = row.MeanTotalEvalMS
			break
		}
	}

	if defaultEvalOnly <= 0 || defaultTotal <= 0 {
		return
	}

	for i := range rows {
		if rows[i].Status != "ok" {
			continue
		}

		if rows[i].MeanEvalOnlyMS > 0 {
			rows[i].SpeedupVsDefaultEvalOnly = defaultEvalOnly / rows[i].MeanEvalOnlyMS
		}

		if rows[i].MeanTotalEvalMS > 0 {
			rows[i].SpeedupVsDefaultTotal = defaultTotal / rows[i].MeanTotalEvalMS
		}
	}
}

func profileBenchmarkScoreErrorBudget(
	input ckksbackend.LogRegSmallInput,
	absCap float64,
	relCap float64,
) (float64, error) {
	if absCap <= 0 && relCap <= 0 {
		return 0, fmt.Errorf("at least one score error cap must be positive")
	}

	plainZ := ckksbackend.EvalLogRegSmallLinearPlain(input)
	plainY := ckksbackend.EvalLogRegSmallPolynomialPlain(plainZ)

	budget := math.Inf(1)

	if absCap > 0 {
		budget = math.Min(budget, absCap)
	}

	if relCap > 0 {
		relBudget := relCap * math.Max(math.Abs(plainY), 1e-12)
		budget = math.Min(budget, relBudget)
	}

	if math.IsInf(budget, 1) || budget <= 0 {
		return 0, fmt.Errorf("invalid score error budget %.10f", budget)
	}

	return budget, nil
}

func sanitizeProfileBenchmarkError(err error) string {
	if err == nil {
		return ""
	}

	return strings.ReplaceAll(err.Error(), "\n", " ")
}
