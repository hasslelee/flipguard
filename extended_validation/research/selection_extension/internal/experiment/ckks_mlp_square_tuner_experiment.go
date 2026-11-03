package experiment

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksMLPSquareTunerOutputDir = "results/ckks_mlp_square_tuner"

type mlpSquareProfileSummaryRow struct {
	ProfileName     string
	Description     string
	Status          string
	Error           string
	LogN            int
	Slots           int
	LogQCount       int
	LogPCount       int
	LogQPSum        int
	LogDefaultScale int

	MeasurementRuns int
	SuccessRuns     int
	FailedRuns      int

	DecisionFlips   int
	ErrorViolations int
	MaxOutputError  float64
	MeanOutputError float64
	MeanTotalMS     float64

	Reference bool
}

// RunCKKSMLPSquareTuner evaluates the MLP-square CKKS benchmark across CKKS
// parameter profiles and selects the fastest decision-safe configuration.
//
// MLP-square is a CKKS-friendly neural inference workload using one square
// activation layer:
//
//	h = W1*x + b1
//	a = h^2
//	y = W2*a + b2
//
// Candidate space:
//
//	profile in --ckks-profile-names
//	mode    = current MLP-square CKKS path
func RunCKKSMLPSquareTuner() error {
	options := GetRuntimeOptions()

	profiles, err := CKKSProfilesFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profiles: %w", err)
	}
	if len(profiles) == 0 {
		return fmt.Errorf("no CKKS profiles configured")
	}

	measurementRuns := options.CKKSTimingMeasurementRuns
	if measurementRuns <= 0 {
		measurementRuns = 1
	}

	warmupRuns := options.CKKSTimingWarmupRuns
	if warmupRuns < 0 {
		warmupRuns = 0
	}

	errorBudget := options.CKKSScoreAbsErrorCap
	if errorBudget <= 0 {
		errorBudget = 1e-3
	}

	rows := make([]mlpSquareProfileSummaryRow, 0, len(profiles))
	evaluations := make([]tuner.CandidateEvaluation, 0, len(profiles))

	for _, profile := range profiles {
		row, evaluation := evaluateMLPSquareProfileCandidate(
			profile,
			measurementRuns,
			warmupRuns,
			errorBudget,
		)

		rows = append(rows, row)
		evaluations = append(evaluations, evaluation)
	}

	if len(evaluations) == 0 {
		return fmt.Errorf("no MLP-square tuner evaluations produced")
	}

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe MLP-square candidate: %w", err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only MLP-square candidate: %w", err)
	}

	referenceEval := chooseMLPSquareTunerReference(evaluations)
	safe, rejected, failed := countAutoTunerEvaluationStatuses(evaluations)

	outputDir := CKKSResultDir(ckksMLPSquareTunerOutputDir)

	profileSummaryPath := filepath.Join(outputDir, "profile_summary.csv")
	if err := writeMLPSquareProfileSummaryCSV(profileSummaryPath, rows); err != nil {
		return fmt.Errorf("write MLP-square profile summary: %w", err)
	}

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		outputDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export MLP-square tuner candidates: %w", err)
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
		return fmt.Errorf("export MLP-square tuner selection: %w", err)
	}

	summaryPath, err := writeCKKSAutoTunerEvalSummary(ckksAutoTunerEvalSummaryInput{
		OutputDir: outputDir,

		ProfileCount:   len(profiles),
		ModeCount:      1,
		CandidateCount: len(evaluations),
		SafeCount:      safe,
		RejectedCount:  rejected,
		FailedCount:    failed,

		ScoreErrorBudget: errorBudget,
		WarmupRuns:       warmupRuns,
		MeasurementRuns:  measurementRuns,

		Reference:   referenceEval,
		FastestSafe: fastestSafe,
		LatencyOnly: latencyOnly,
	})
	if err != nil {
		return fmt.Errorf("write MLP-square tuner summary: %w", err)
	}

	fmt.Println("FlipGuard CKKS MLP-square tuner")
	fmt.Printf(
		"profiles=%d candidates=%d safe=%d rejected=%d failed=%d error_budget=%.10f warmup_runs=%d measurement_runs=%d\n",
		len(profiles),
		len(evaluations),
		safe,
		rejected,
		failed,
		errorBudget,
		warmupRuns,
		measurementRuns,
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

func evaluateMLPSquareProfileCandidate(
	profile ckksbackend.CKKSProfile,
	measurementRuns int,
	warmupRuns int,
	errorBudget float64,
) (mlpSquareProfileSummaryRow, tuner.CandidateEvaluation) {
	logN := profile.Literal.LogN
	if logN <= 0 {
		logN = 14
	}

	baseRow := mlpSquareProfileSummaryRow{
		ProfileName:     profile.Name,
		Description:     profile.Description,
		Status:          "failed",
		LogN:            logN,
		Slots:           slotsFromProfileLogN(logN),
		LogQCount:       profile.LogQCount(),
		LogPCount:       profile.LogPCount(),
		LogQPSum:        profile.LogQPSum(),
		LogDefaultScale: profile.LogDefaultScale(),
		MeasurementRuns: measurementRuns,
		SuccessRuns:     0,
		FailedRuns:      measurementRuns,
		Reference:       strings.EqualFold(profile.Name, "default"),
	}

	candidate := tuner.ParameterCandidate{
		ID:          mlpSquareCandidateID(profile.Name),
		LogN:        baseRow.LogN,
		Slots:       baseRow.Slots,
		ChainLength: baseRow.LogQCount,
		ScaleBits:   baseRow.LogDefaultScale,
		Family:      inferProfileCandidateFamily(profile.Name),
		IsReference: baseRow.Reference,
	}

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		baseRow.Error = sanitizeMLPSquareTunerError(err)
		return baseRow, mlpSquareEvaluationFromRow(baseRow, candidate)
	}

	for warmup := 0; warmup < warmupRuns; warmup++ {
		if _, err := ctx.RunMLPSquareProbe(); err != nil {
			baseRow.Error = sanitizeMLPSquareTunerError(err)
			return baseRow, mlpSquareEvaluationFromRow(baseRow, candidate)
		}
	}

	totalDuration := time.Duration(0)
	totalMeanError := 0.0
	maxError := 0.0
	decisionFlips := 0
	errorViolations := 0
	successRuns := 0
	failedRuns := 0

	for run := 0; run < measurementRuns; run++ {
		start := time.Now()
		results, err := ctx.RunMLPSquareProbe()
		elapsed := time.Since(start)

		if err != nil {
			failedRuns++
			if baseRow.Error == "" {
				baseRow.Error = sanitizeMLPSquareTunerError(err)
			}
			continue
		}

		successRuns++
		totalDuration += elapsed

		runFlips, runViolations, runMaxError, runMeanError := summarizeMLPSquareProbeResults(
			results,
			errorBudget,
		)

		decisionFlips += runFlips
		errorViolations += runViolations
		maxError = math.Max(maxError, runMaxError)
		totalMeanError += runMeanError
	}

	status := "ok"
	if failedRuns > 0 && successRuns == 0 {
		status = "failed"
	} else if failedRuns > 0 {
		status = "partial"
	}

	meanTotalMS := 0.0
	if successRuns > 0 {
		meanTotalMS = float64(totalDuration.Microseconds()) / 1000.0 / float64(successRuns)
	}

	meanError := 0.0
	if successRuns > 0 {
		meanError = totalMeanError / float64(successRuns)
	}

	row := baseRow
	row.Status = status
	row.SuccessRuns = successRuns
	row.FailedRuns = failedRuns
	row.DecisionFlips = decisionFlips
	row.ErrorViolations = errorViolations
	row.MaxOutputError = maxError
	row.MeanOutputError = meanError
	row.MeanTotalMS = meanTotalMS

	return row, mlpSquareEvaluationFromRow(row, candidate)
}

func summarizeMLPSquareProbeResults(
	results []ckksbackend.MLPSquareProbeResult,
	errorBudget float64,
) (decisionFlips int, errorViolations int, maxOutputError float64, meanOutputError float64) {
	totalError := 0.0

	for _, result := range results {
		if result.Flip {
			decisionFlips++
		}

		if result.AbsError > errorBudget {
			errorViolations++
		}

		maxOutputError = math.Max(maxOutputError, result.AbsError)
		totalError += result.AbsError
	}

	if len(results) > 0 {
		meanOutputError = totalError / float64(len(results))
	}

	return decisionFlips, errorViolations, maxOutputError, meanOutputError
}

func mlpSquareEvaluationFromRow(
	row mlpSquareProfileSummaryRow,
	candidate tuner.ParameterCandidate,
) tuner.CandidateEvaluation {
	successRuns := row.SuccessRuns
	failedRuns := row.FailedRuns

	if row.Status == "failed" && failedRuns == 0 {
		failedRuns = row.MeasurementRuns
		successRuns = 0
	}

	return tuner.CandidateEvaluation{
		Config: tuner.ExecutionConfiguration{
			Candidate: candidate,
			Path:      tuner.PathNonRescale,
		},
		SuccessRuns:     successRuns,
		FailedRuns:      failedRuns,
		DecisionFlips:   row.DecisionFlips,
		ErrorViolations: row.ErrorViolations,
		MaxOutputError:  row.MaxOutputError,
		MeanTotalMS:     row.MeanTotalMS,
	}
}

func chooseMLPSquareTunerReference(
	evaluations []tuner.CandidateEvaluation,
) tuner.CandidateEvaluation {
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

func mlpSquareCandidateID(profileName string) string {
	name := strings.TrimSpace(profileName)
	if name == "" {
		name = "unknown_profile"
	}

	name = strings.ReplaceAll(name, " ", "_")
	return fmt.Sprintf("%s_mlp_square", name)
}

func sanitizeMLPSquareTunerError(err error) string {
	if err == nil {
		return ""
	}

	msg := strings.TrimSpace(err.Error())
	if msg == "" {
		return ""
	}

	msg = strings.ReplaceAll(msg, "\n", " ")
	msg = strings.ReplaceAll(msg, "\r", " ")
	return msg
}

func writeMLPSquareProfileSummaryCSV(
	path string,
	rows []mlpSquareProfileSummaryRow,
) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create MLP-square profile summary CSV: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"profile_name",
		"description",
		"status",
		"error",
		"logN",
		"slots",
		"logQ_count",
		"logP_count",
		"logQP_sum",
		"log_default_scale",
		"measurement_runs",
		"success_runs",
		"failed_runs",
		"decision_flips",
		"error_violations",
		"max_output_error",
		"mean_output_error",
		"mean_total_ms",
		"is_reference",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write MLP-square profile summary header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.ProfileName,
			row.Description,
			row.Status,
			row.Error,
			fmt.Sprintf("%d", row.LogN),
			fmt.Sprintf("%d", row.Slots),
			fmt.Sprintf("%d", row.LogQCount),
			fmt.Sprintf("%d", row.LogPCount),
			fmt.Sprintf("%d", row.LogQPSum),
			fmt.Sprintf("%d", row.LogDefaultScale),
			fmt.Sprintf("%d", row.MeasurementRuns),
			fmt.Sprintf("%d", row.SuccessRuns),
			fmt.Sprintf("%d", row.FailedRuns),
			fmt.Sprintf("%d", row.DecisionFlips),
			fmt.Sprintf("%d", row.ErrorViolations),
			fmt.Sprintf("%.12f", row.MaxOutputError),
			fmt.Sprintf("%.12f", row.MeanOutputError),
			fmt.Sprintf("%.6f", row.MeanTotalMS),
			fmt.Sprintf("%t", row.Reference),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write MLP-square profile summary row %d: %w", i, err)
		}
	}

	return nil
}
