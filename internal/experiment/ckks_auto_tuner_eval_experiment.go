package experiment

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksAutoTunerEvalOutputDir = "results/ckks_auto_tuner_eval"

// RunCKKSAutoTunerEval evaluates real CKKS profile candidates and exports them
// through the common FlipGuard tuner artifact format.
//
// Unlike ckks_auto_tuner_smoke, this experiment does not use synthetic safety
// outcomes. It reuses the existing CKKS profile benchmark implementation and
// converts each measured profile/mode row into a tuner.CandidateEvaluation.
//
// Candidate space:
//
//	profile in --ckks-profile-names
//	mode    in naive,rescale
//
// Selection policies:
//
//	reference     : default/naive if available, otherwise first candidate
//	fastest_safe  : lowest measured total latency among SAFE candidates
//	latency_only  : lowest measured total latency among successfully executed candidates
func RunCKKSAutoTunerEval() error {
	options := GetRuntimeOptions()

	profiles, err := CKKSProfilesFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profiles: %w", err)
	}

	baseConfig := CKKSTimingBenchmarkConfigFromRuntimeOptions()

	scoreErrorBudget, err := profileBenchmarkScoreErrorBudget(
		baseConfig.Input,
		options.CKKSScoreAbsErrorCap,
		options.CKKSScoreRelErrorCap,
	)
	if err != nil {
		return fmt.Errorf("compute score error budget: %w", err)
	}

	modes := []string{
		ckksbackend.CKKSEvaluationModeNaive,
		"rescale",
	}

	summaryRows := make([]report.CKKSProfileBenchmarkSummaryRow, 0, len(profiles)*len(modes))
	evaluations := make([]tuner.CandidateEvaluation, 0, len(profiles)*len(modes))

	for _, mode := range modes {
		config := baseConfig
		config.EvaluationMode = mode

		for _, profile := range profiles {
			summaryRow, _ := runSingleCKKSProfileBenchmark(profile, config)
			applyCKKSProfileBenchmarkSafety(&summaryRow, scoreErrorBudget)

			summaryRows = append(summaryRows, summaryRow)
			evaluations = append(evaluations, tunerEvaluationFromProfileBenchmarkRow(summaryRow))
		}
	}

	if len(evaluations) == 0 {
		return fmt.Errorf("no CKKS auto-tuner candidate evaluations produced")
	}

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe CKKS candidate: %w", err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only CKKS candidate: %w", err)
	}

	referenceEval := chooseAutoTunerEvalReference(evaluations)

	accepted, rejected, failed := countAutoTunerEvaluationStatuses(evaluations)

	outputDir := CKKSResultDir(ckksAutoTunerEvalOutputDir)

	profileSummaryPath := filepath.Join(outputDir, "profile_summary.csv")
	if err := report.WriteCKKSProfileBenchmarkSummaryCSV(profileSummaryPath, summaryRows); err != nil {
		return fmt.Errorf("write CKKS auto-tuner profile summary: %w", err)
	}

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		outputDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export tuner candidate evaluations: %w", err)
	}

	selectionPath, err := report.ExportTunerSelectionRecords(
		outputDir,
		"tuner_selection.csv",
		[]report.TunerSelectionRecord{
			{
				Policy:     "reference",
				Evaluation: referenceEval,
			},
			{
				Policy:     "fastest_safe",
				Evaluation: fastestSafe,
			},
			{
				Policy:     "latency_only",
				Evaluation: latencyOnly,
			},
		},
	)
	if err != nil {
		return fmt.Errorf("export tuner selection records: %w", err)
	}

	summaryPath, err := writeCKKSAutoTunerEvalSummary(ckksAutoTunerEvalSummaryInput{
		OutputDir: outputDir,

		ProfileCount:   len(profiles),
		ModeCount:      len(modes),
		CandidateCount: len(evaluations),
		SafeCount:      accepted,
		RejectedCount:  rejected,
		FailedCount:    failed,

		ScoreErrorBudget: scoreErrorBudget,
		WarmupRuns:       baseConfig.WarmupRuns,
		MeasurementRuns:  baseConfig.MeasurementRuns,

		Reference:   referenceEval,
		FastestSafe: fastestSafe,
		LatencyOnly: latencyOnly,
	})
	if err != nil {
		return fmt.Errorf("write CKKS auto-tuner evaluation summary: %w", err)
	}

	fmt.Println("FlipGuard CKKS auto-tuner evaluation")
	fmt.Printf(
		"profiles=%d modes=%d candidates=%d safe=%d rejected=%d failed=%d score_error_budget=%.10f warmup_runs=%d measurement_runs=%d\n",
		len(profiles),
		len(modes),
		len(evaluations),
		accepted,
		rejected,
		failed,
		scoreErrorBudget,
		baseConfig.WarmupRuns,
		baseConfig.MeasurementRuns,
	)
	fmt.Println()

	printAutoTunerEvalSelection("Reference", referenceEval)
	printAutoTunerEvalSelection("Fastest safe", fastestSafe)
	printAutoTunerEvalSelection("Latency-only", latencyOnly)

	fmt.Println()
	fmt.Printf("Wrote %s\n", profileSummaryPath)
	fmt.Printf("Wrote %s\n", candidatesPath)
	fmt.Printf("Wrote %s\n", selectionPath)
	fmt.Printf("Wrote %s\n", summaryPath)

	return nil
}

func countAutoTunerEvaluationStatuses(evaluations []tuner.CandidateEvaluation) (safe int, rejected int, failed int) {
	for _, evaluation := range evaluations {
		switch evaluation.Status() {
		case "SAFE":
			safe++
		case "REJECTED":
			rejected++
		case "FAILED":
			failed++
		}
	}

	return safe, rejected, failed
}

func tunerEvaluationFromProfileBenchmarkRow(
	row report.CKKSProfileBenchmarkSummaryRow,
) tuner.CandidateEvaluation {
	candidate := tuner.ParameterCandidate{
		ID:          profileCandidateID(row.ProfileName, row.EvaluationMode),
		LogN:        inferLogNFromProfileBenchmarkRow(row),
		Slots:       row.MaxSlots,
		ChainLength: row.LogQCount,
		ScaleBits:   row.LogDefaultScale,
		Family:      inferProfileCandidateFamily(row.ProfileName),
		IsReference: isReferenceProfileCandidate(row.ProfileName, row.EvaluationMode),
	}

	if candidate.Slots <= 0 {
		candidate.Slots = slotsFromProfileLogN(candidate.LogN)
	}

	successRuns := row.MeasurementRuns
	if successRuns <= 0 {
		successRuns = 1
	}

	failedRuns := 0
	if row.Status != "ok" {
		failedRuns = successRuns
		successRuns = 0
	}

	errorViolations := 0
	if row.ScoreErrorViolation {
		errorViolations = maxIntForAutoTunerEval(successRuns, 1)
	}

	decisionFlips := row.DecisionFlips

	return tuner.CandidateEvaluation{
		Config: tuner.ExecutionConfiguration{
			Candidate: candidate,
			Path:      executionPathFromProfileMode(row.EvaluationMode),
		},
		SuccessRuns:     successRuns,
		FailedRuns:      failedRuns,
		DecisionFlips:   decisionFlips,
		ErrorViolations: errorViolations,
		MaxOutputError:  row.MaxYError,
		MeanTotalMS:     row.MeanTotalEvalMS,
	}
}

func chooseAutoTunerEvalReference(
	evaluations []tuner.CandidateEvaluation,
) tuner.CandidateEvaluation {
	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.IsReference &&
			evaluation.Config.Path == tuner.PathNonRescale {
			return evaluation
		}
	}

	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.IsReference {
			return evaluation
		}
	}

	for _, evaluation := range evaluations {
		if evaluation.IsSafe() {
			return evaluation
		}
	}

	return evaluations[0]
}

func profileCandidateID(profileName string, mode string) string {
	cleanProfile := strings.ReplaceAll(strings.TrimSpace(profileName), " ", "_")
	cleanMode := strings.ReplaceAll(strings.TrimSpace(mode), " ", "_")

	if cleanProfile == "" {
		cleanProfile = "unknown_profile"
	}
	if cleanMode == "" {
		cleanMode = "unknown_mode"
	}

	return fmt.Sprintf("%s_%s", cleanProfile, cleanMode)
}

func inferLogNFromProfileBenchmarkRow(row report.CKKSProfileBenchmarkSummaryRow) int {
	if row.MaxSlots > 1 {
		logSlots := 0
		slots := row.MaxSlots
		for slots > 1 {
			slots >>= 1
			logSlots++
		}
		return logSlots + 1
	}

	name := strings.ToLower(row.ProfileName)
	if strings.Contains(name, "logn15") || strings.Contains(name, "n15") {
		return 15
	}

	return 14
}

func inferProfileCandidateFamily(profileName string) string {
	name := strings.ToLower(profileName)

	switch {
	case name == "default":
		return "reference"
	case strings.Contains(name, "deep_chain"):
		return "deep_chain"
	case strings.Contains(name, "short_chain"):
		return "short_chain"
	case strings.Contains(name, "scale"):
		return "scale_sweep"
	default:
		return "profile"
	}
}

func isReferenceProfileCandidate(profileName string, mode string) bool {
	return strings.EqualFold(profileName, "default") &&
		strings.EqualFold(mode, ckksbackend.CKKSEvaluationModeNaive)
}

func executionPathFromProfileMode(mode string) tuner.ExecutionPath {
	mode = strings.ToLower(strings.TrimSpace(mode))

	switch mode {
	case "naive", "non-rescale", "non_rescale":
		return tuner.PathNonRescale
	case "rescale":
		return tuner.PathRescale
	default:
		return tuner.PathRescale
	}
}

func slotsFromProfileLogN(logN int) int {
	if logN <= 1 {
		return 1
	}
	return 1 << (logN - 1)
}

func maxIntForAutoTunerEval(a int, b int) int {
	if a > b {
		return a
	}
	return b
}

func printAutoTunerEvalSelection(label string, evaluation tuner.CandidateEvaluation) {
	fmt.Printf(
		"%s: candidate=%s path=%s status=%s mean_total_ms=%.6f max_output_error=%.10f flips=%d violations=%d failures=%d chain=%d scale=%d logN=%d\n",
		label,
		evaluation.Config.Candidate.ID,
		evaluation.Config.Path,
		evaluation.Status(),
		evaluation.MeanTotalMS,
		evaluation.MaxOutputError,
		evaluation.DecisionFlips,
		evaluation.ErrorViolations,
		evaluation.FailedRuns,
		evaluation.Config.Candidate.ChainLength,
		evaluation.Config.Candidate.ScaleBits,
		evaluation.Config.Candidate.LogN,
	)
}
