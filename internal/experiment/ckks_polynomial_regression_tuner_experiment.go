package experiment

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksPolynomialRegressionTunerOutputDir = "results/ckks_polynomial_regression_tuner"

type polynomialRegressionProfileSummaryRow struct {
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
}

// RunCKKSPolynomialRegressionTuner evaluates the standalone polynomial
// regression CKKS benchmark across CKKS parameter profiles and exports the
// results through the common tuner artifact format.
//
// This is the polynomial-regression counterpart of ckks_auto_tuner_eval.
// Candidate space:
//
//	profile in --ckks-profile-names
//	mode    = current polynomial-regression CKKS path
//
// The current polynomial-regression backend is a non-rescale path. Therefore,
// this experiment evaluates profile-level safety/latency trade-offs first.
func RunCKKSPolynomialRegressionTuner() error {
	options := GetRuntimeOptions()

	profiles, err := CKKSProfilesFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("select CKKS profiles: %w", err)
	}

	measurementRuns := options.CKKSTimingMeasurementRuns
	if measurementRuns <= 0 {
		measurementRuns = 1
	}

	errorBudget := options.CKKSScoreAbsErrorCap
	if errorBudget <= 0 {
		errorBudget = 1e-3
	}

	rows := make([]polynomialRegressionProfileSummaryRow, 0, len(profiles))
	evaluations := make([]tuner.CandidateEvaluation, 0, len(profiles))

	for _, profile := range profiles {
		row, evaluation := evaluatePolynomialRegressionProfileCandidate(
			profile,
			measurementRuns,
			errorBudget,
		)

		rows = append(rows, row)
		evaluations = append(evaluations, evaluation)
	}

	if len(evaluations) == 0 {
		return fmt.Errorf("no polynomial regression tuner evaluations produced")
	}

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe polynomial regression candidate: %w", err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only polynomial regression candidate: %w", err)
	}

	referenceEval := choosePolynomialRegressionTunerReference(evaluations)
	safe, rejected, failed := countAutoTunerEvaluationStatuses(evaluations)

	outputDir := CKKSResultDir(ckksPolynomialRegressionTunerOutputDir)

	profileSummaryPath := filepath.Join(outputDir, "profile_summary.csv")
	if err := writePolynomialRegressionProfileSummaryCSV(profileSummaryPath, rows); err != nil {
		return fmt.Errorf("write polynomial regression profile summary: %w", err)
	}

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		outputDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export polynomial regression tuner candidates: %w", err)
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
		return fmt.Errorf("export polynomial regression tuner selection: %w", err)
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
		WarmupRuns:       0,
		MeasurementRuns:  measurementRuns,

		Reference:   referenceEval,
		FastestSafe: fastestSafe,
		LatencyOnly: latencyOnly,
	})
	if err != nil {
		return fmt.Errorf("write polynomial regression tuner summary: %w", err)
	}

	fmt.Println("FlipGuard CKKS polynomial regression tuner")
	fmt.Printf(
		"profiles=%d candidates=%d safe=%d rejected=%d failed=%d error_budget=%.10f measurement_runs=%d\n",
		len(profiles),
		len(evaluations),
		safe,
		rejected,
		failed,
		errorBudget,
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

func evaluatePolynomialRegressionProfileCandidate(
	profile ckksbackend.CKKSProfile,
	measurementRuns int,
	errorBudget float64,
) (polynomialRegressionProfileSummaryRow, tuner.CandidateEvaluation) {
	logN := profile.Literal.LogN
	if logN <= 0 {
		logN = 14
	}

	baseRow := polynomialRegressionProfileSummaryRow{
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
	}

	candidate := tuner.ParameterCandidate{
		ID:          polynomialRegressionCandidateID(profile.Name),
		LogN:        baseRow.LogN,
		Slots:       baseRow.Slots,
		ChainLength: baseRow.LogQCount,
		ScaleBits:   baseRow.LogDefaultScale,
		Family:      inferProfileCandidateFamily(profile.Name),
		IsReference: strings.EqualFold(profile.Name, "default"),
	}

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		baseRow.Error = sanitizePolynomialRegressionTunerError(err)
		return baseRow, polynomialRegressionEvaluationFromRow(baseRow, candidate)
	}

	totalDuration := time.Duration(0)
	totalError := 0.0
	maxError := 0.0
	decisionFlips := 0
	errorViolations := 0
	successRuns := 0
	failedRuns := 0

	for run := 0; run < measurementRuns; run++ {
		start := time.Now()
		results, err := ctx.RunPolynomialRegressionProbe()
		elapsed := time.Since(start)

		if err != nil {
			failedRuns++
			if baseRow.Error == "" {
				baseRow.Error = sanitizePolynomialRegressionTunerError(err)
			}
			continue
		}

		successRuns++
		totalDuration += elapsed

		runMaxError, runMeanError, runFlips := summarizePolynomialRegressionProbe(results)

		totalError += runMeanError

		if runMaxError > maxError {
			maxError = runMaxError
		}

		decisionFlips += runFlips

		if runMaxError > errorBudget {
			errorViolations++
		}
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
		meanError = totalError / float64(successRuns)
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

	return row, polynomialRegressionEvaluationFromRow(row, candidate)
}

func polynomialRegressionEvaluationFromRow(
	row polynomialRegressionProfileSummaryRow,
	candidate tuner.ParameterCandidate,
) tuner.CandidateEvaluation {
	successRuns := row.SuccessRuns
	failedRuns := row.FailedRuns

	errorViolations := 0
	if row.ErrorViolations > 0 {
		errorViolations = row.ErrorViolations
	}

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
		ErrorViolations: errorViolations,
		MaxOutputError:  row.MaxOutputError,
		MeanTotalMS:     row.MeanTotalMS,
	}
}

func choosePolynomialRegressionTunerReference(
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

func polynomialRegressionCandidateID(profileName string) string {
	name := strings.TrimSpace(profileName)
	if name == "" {
		name = "unknown_profile"
	}

	name = strings.ReplaceAll(name, " ", "_")
	return fmt.Sprintf("%s_polyreg", name)
}

func sanitizePolynomialRegressionTunerError(err error) string {
	if err == nil {
		return ""
	}

	msg := strings.TrimSpace(err.Error())
	msg = strings.ReplaceAll(msg, "\n", " ")
	msg = strings.ReplaceAll(msg, "\r", " ")

	if len(msg) > 240 {
		msg = msg[:240]
	}

	return msg
}

func writePolynomialRegressionProfileSummaryCSV(
	path string,
	rows []polynomialRegressionProfileSummaryRow,
) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create polynomial regression profile summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"profile",
		"description",
		"status",
		"error",
		"logN",
		"slots",
		"log_q_count",
		"log_p_count",
		"log_qp_sum",
		"log_default_scale",
		"measurement_runs",
		"success_runs",
		"failed_runs",
		"decision_flips",
		"error_violations",
		"max_output_error",
		"mean_output_error",
		"mean_total_ms",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write polynomial regression profile summary header: %w", err)
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
			fmt.Sprintf("%.12g", row.MaxOutputError),
			fmt.Sprintf("%.12g", row.MeanOutputError),
			fmt.Sprintf("%.12g", row.MeanTotalMS),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write polynomial regression profile summary row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush polynomial regression profile summary csv: %w", err)
	}

	return nil
}
