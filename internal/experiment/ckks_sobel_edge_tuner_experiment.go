package experiment

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksSobelEdgeTunerOutputDir = "results/ckks_sobel_edge_tuner"

type ckksSobelEdgeProfileSummaryRow struct {
	ProfileName string

	CandidateID string
	Status      string

	SuccessRuns int
	FailedRuns  int

	DecisionFlips   int
	ErrorViolations int
	MaxOutputError  float64

	MeanTotalMS float64

	ChainLength int
	ScaleBits   int
	LogN        int
	Slots       int

	Reference bool
}

// RunCKKSSobelEdgeTuner evaluates CKKS Sobel edge profile candidates and selects
// the fastest decision-safe configuration.
func RunCKKSSobelEdgeTuner() error {
	options := GetRuntimeOptions()

	errorBudget := options.CKKSScoreAbsErrorCap
	if errorBudget <= 0 {
		errorBudget = 1e-3
	}

	profiles, err := CKKSProfilesFromRuntimeOptions()
	if err != nil {
		return fmt.Errorf("load CKKS profiles from runtime options: %w", err)
	}
	if len(profiles) == 0 {
		return fmt.Errorf("no CKKS profiles configured")
	}

	evaluations := make([]tuner.CandidateEvaluation, 0, len(profiles))
	summaryRows := make([]ckksSobelEdgeProfileSummaryRow, 0, len(profiles))

	for _, profile := range profiles {
		evaluation := evaluateSobelEdgeProfile(profile, options, errorBudget)
		evaluations = append(evaluations, evaluation)

		row := sobelEdgeSummaryRowFromEvaluation(profile.Name, evaluation)
		summaryRows = append(summaryRows, row)
	}

	referenceEvaluation, err := selectSobelEdgeReference(evaluations)
	if err != nil {
		return fmt.Errorf("select Sobel edge reference: %w", err)
	}

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe Sobel edge candidate: %w", err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only Sobel edge candidate: %w", err)
	}

	outputDir := CKKSResultDir(ckksSobelEdgeTunerOutputDir)

	profileSummaryPath := filepath.Join(outputDir, "profile_summary.csv")
	if err := writeSobelEdgeProfileSummaryCSV(profileSummaryPath, summaryRows); err != nil {
		return fmt.Errorf("write CKKS Sobel edge profile summary: %w", err)
	}

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		outputDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export CKKS Sobel edge tuner candidates: %w", err)
	}

	selectionPath, err := report.ExportTunerSelectionRecords(
		outputDir,
		"tuner_selection.csv",
		[]report.TunerSelectionRecord{
			{
				Policy:     "reference",
				Evaluation: referenceEvaluation,
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
		return fmt.Errorf("export CKKS Sobel edge tuner selection: %w", err)
	}

	selectionSummaryPath := filepath.Join(outputDir, "selection_summary.md")
	if err := writeSobelEdgeSelectionSummary(
		selectionSummaryPath,
		evaluations,
		referenceEvaluation,
		fastestSafe,
		latencyOnly,
		errorBudget,
		options,
	); err != nil {
		return fmt.Errorf("write CKKS Sobel edge selection summary: %w", err)
	}

	safeCount, rejectedCount, failedCount := countSobelEdgeStatuses(evaluations)

	fmt.Println("FlipGuard CKKS Sobel edge tuner")
	fmt.Printf(
		"profiles=%d candidates=%d safe=%d rejected=%d failed=%d error_budget=%.10f measurement_runs=%d\n",
		len(profiles),
		len(evaluations),
		safeCount,
		rejectedCount,
		failedCount,
		errorBudget,
		options.CKKSTimingMeasurementRuns,
	)
	fmt.Println()

	printSobelEdgeSelection("Reference", referenceEvaluation)
	printSobelEdgeSelection("Fastest safe", fastestSafe)
	printSobelEdgeSelection("Latency-only", latencyOnly)

	fmt.Println()
	fmt.Printf("Wrote %s\n", profileSummaryPath)
	fmt.Printf("Wrote %s\n", candidatesPath)
	fmt.Printf("Wrote %s\n", selectionPath)
	fmt.Printf("Wrote %s\n", selectionSummaryPath)

	return nil
}

func evaluateSobelEdgeProfile(
	profile ckksbackend.CKKSProfile,
	options RuntimeOptions,
	errorBudget float64,
) tuner.CandidateEvaluation {
	cfg := sobelEdgeExecutionConfiguration(profile)

	measurementRuns := options.CKKSTimingMeasurementRuns
	if measurementRuns <= 0 {
		measurementRuns = 3
	}

	warmupRuns := options.CKKSTimingWarmupRuns
	if warmupRuns < 0 {
		warmupRuns = 0
	}

	ctx, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		return tuner.CandidateEvaluation{
			Config:     cfg,
			FailedRuns: measurementRuns,
		}
	}

	for i := 0; i < warmupRuns; i++ {
		if _, err := ctx.RunSobelEdgeProbe(); err != nil {
			return tuner.CandidateEvaluation{
				Config:     cfg,
				FailedRuns: measurementRuns,
			}
		}
	}

	successRuns := 0
	failedRuns := 0
	decisionFlips := 0
	errorViolations := 0
	maxOutputError := 0.0
	totalDuration := time.Duration(0)

	for i := 0; i < measurementRuns; i++ {
		start := time.Now()
		results, err := ctx.RunSobelEdgeProbe()
		elapsed := time.Since(start)

		if err != nil {
			failedRuns++
			continue
		}

		successRuns++
		totalDuration += elapsed

		runFlips, runViolations, runMaxError := summarizeSobelEdgeProbeResults(results, errorBudget)

		decisionFlips += runFlips
		errorViolations += runViolations
		maxOutputError = math.Max(maxOutputError, runMaxError)
	}

	meanTotalMS := 0.0
	if successRuns > 0 {
		meanTotalMS = float64(totalDuration.Microseconds()) / 1000.0 / float64(successRuns)
	}

	return tuner.CandidateEvaluation{
		Config: cfg,

		SuccessRuns: successRuns,
		FailedRuns:  failedRuns,

		DecisionFlips:   decisionFlips,
		ErrorViolations: errorViolations,
		MaxOutputError:  maxOutputError,

		MeanTotalMS: meanTotalMS,
	}
}

func sobelEdgeExecutionConfiguration(
	profile ckksbackend.CKKSProfile,
) tuner.ExecutionConfiguration {
	logN := profile.Literal.LogN
	if logN <= 0 {
		logN = 14
	}

	return tuner.ExecutionConfiguration{
		Candidate: tuner.ParameterCandidate{
			ID:          fmt.Sprintf("%s_sobel", profile.Name),
			LogN:        logN,
			Slots:       slotsFromProfileLogN(logN),
			ChainLength: profile.LogQCount(),
			ScaleBits:   profile.LogDefaultScale(),
			Family:      inferProfileCandidateFamily(profile.Name),
			IsReference: profile.Name == "default",
		},
		Path: tuner.PathNonRescale,
	}
}

func summarizeSobelEdgeProbeResults(
	results []ckksbackend.SobelEdgeProbeResult,
	errorBudget float64,
) (decisionFlips int, errorViolations int, maxOutputError float64) {
	for _, result := range results {
		if result.Flip {
			decisionFlips++
		}

		if result.AbsError > errorBudget {
			errorViolations++
		}

		maxOutputError = math.Max(maxOutputError, result.AbsError)
	}

	return decisionFlips, errorViolations, maxOutputError
}

func selectSobelEdgeReference(
	evaluations []tuner.CandidateEvaluation,
) (tuner.CandidateEvaluation, error) {
	if len(evaluations) == 0 {
		return tuner.CandidateEvaluation{}, fmt.Errorf("empty evaluation list")
	}

	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.IsReference {
			return evaluation, nil
		}
	}

	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.ID == "default_sobel" {
			return evaluation, nil
		}
	}

	return evaluations[0], nil
}

func sobelEdgeSummaryRowFromEvaluation(
	profileName string,
	evaluation tuner.CandidateEvaluation,
) ckksSobelEdgeProfileSummaryRow {
	return ckksSobelEdgeProfileSummaryRow{
		ProfileName: profileName,

		CandidateID: evaluation.Config.Candidate.ID,
		Status:      evaluation.Status(),

		SuccessRuns: evaluation.SuccessRuns,
		FailedRuns:  evaluation.FailedRuns,

		DecisionFlips:   evaluation.DecisionFlips,
		ErrorViolations: evaluation.ErrorViolations,
		MaxOutputError:  evaluation.MaxOutputError,

		MeanTotalMS: evaluation.MeanTotalMS,

		ChainLength: evaluation.Config.Candidate.ChainLength,
		ScaleBits:   evaluation.Config.Candidate.ScaleBits,
		LogN:        evaluation.Config.Candidate.LogN,
		Slots:       evaluation.Config.Candidate.Slots,

		Reference: evaluation.Config.Candidate.IsReference,
	}
}

func writeSobelEdgeProfileSummaryCSV(
	path string,
	rows []ckksSobelEdgeProfileSummaryRow,
) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create Sobel edge profile summary CSV: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"profile_name",
		"candidate_id",
		"status",
		"success_runs",
		"failed_runs",
		"decision_flips",
		"error_violations",
		"max_output_error",
		"mean_total_ms",
		"chain_length",
		"scale_bits",
		"logN",
		"slots",
		"is_reference",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write Sobel edge profile summary header: %w", err)
	}

	for i, row := range rows {
		record := []string{
			row.ProfileName,
			row.CandidateID,
			row.Status,
			fmt.Sprintf("%d", row.SuccessRuns),
			fmt.Sprintf("%d", row.FailedRuns),
			fmt.Sprintf("%d", row.DecisionFlips),
			fmt.Sprintf("%d", row.ErrorViolations),
			fmt.Sprintf("%.12g", row.MaxOutputError),
			fmt.Sprintf("%.12f", row.MeanTotalMS),
			fmt.Sprintf("%d", row.ChainLength),
			fmt.Sprintf("%d", row.ScaleBits),
			fmt.Sprintf("%d", row.LogN),
			fmt.Sprintf("%d", row.Slots),
			fmt.Sprintf("%t", row.Reference),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write Sobel edge profile summary row %d: %w", i, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush Sobel edge profile summary CSV: %w", err)
	}

	return nil
}

func writeSobelEdgeSelectionSummary(
	path string,
	evaluations []tuner.CandidateEvaluation,
	reference tuner.CandidateEvaluation,
	fastestSafe tuner.CandidateEvaluation,
	latencyOnly tuner.CandidateEvaluation,
	errorBudget float64,
	options RuntimeOptions,
) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	safeCount, rejectedCount, failedCount := countSobelEdgeStatuses(evaluations)

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create Sobel edge selection summary: %w", err)
	}
	defer f.Close()

	fmt.Fprintf(f, "# CKKS Sobel Edge Tuner\n\n")
	fmt.Fprintf(f, "## Summary\n\n")
	fmt.Fprintf(f, "- profiles: %d\n", len(evaluations))
	fmt.Fprintf(f, "- safe: %d\n", safeCount)
	fmt.Fprintf(f, "- rejected: %d\n", rejectedCount)
	fmt.Fprintf(f, "- failed: %d\n", failedCount)
	fmt.Fprintf(f, "- error budget: %.10f\n", errorBudget)
	fmt.Fprintf(f, "- warmup runs: %d\n", options.CKKSTimingWarmupRuns)
	fmt.Fprintf(f, "- measurement runs: %d\n\n", options.CKKSTimingMeasurementRuns)

	fmt.Fprintf(f, "## Selection\n\n")
	fmt.Fprintf(f, "| Policy | Candidate | Path | Status | Mean ms | Max Error | Flips | Violations | Chain | Scale | LogN |\n")
	fmt.Fprintf(f, "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")

	writeSobelEdgeSelectionSummaryRow(f, "reference", reference)
	writeSobelEdgeSelectionSummaryRow(f, "fastest_safe", fastestSafe)
	writeSobelEdgeSelectionSummaryRow(f, "latency_only", latencyOnly)

	fmt.Fprintf(f, "\n## Interpretation\n\n")
	fmt.Fprintf(
		f,
		"Sobel edge detection is a quadratic vision-kernel workload with a thresholded edge decision. ",
	)
	fmt.Fprintf(
		f,
		"The tuner reports whether shallow CKKS chains can preserve the edge/non-edge decision while reducing latency. ",
	)
	fmt.Fprintf(
		f,
		"Latency-only selection is reported separately to expose candidates that may be fast but violate decision stability.\n",
	)

	return nil
}

func writeSobelEdgeSelectionSummaryRow(
	f *os.File,
	policy string,
	evaluation tuner.CandidateEvaluation,
) {
	fmt.Fprintf(
		f,
		"| %s | `%s` | `%s` | %s | %.6f | %.12g | %d | %d | %d | %d | %d |\n",
		policy,
		evaluation.Config.Candidate.ID,
		evaluation.Config.Path,
		evaluation.Status(),
		evaluation.MeanTotalMS,
		evaluation.MaxOutputError,
		evaluation.DecisionFlips,
		evaluation.ErrorViolations,
		evaluation.Config.Candidate.ChainLength,
		evaluation.Config.Candidate.ScaleBits,
		evaluation.Config.Candidate.LogN,
	)
}

func printSobelEdgeSelection(
	label string,
	evaluation tuner.CandidateEvaluation,
) {
	fmt.Printf(
		"%s: candidate=%s path=%s status=%s mean_total_ms=%.6f max_output_error=%.12f flips=%d violations=%d failures=%d chain=%d scale=%d logN=%d\n",
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

func countSobelEdgeStatuses(
	evaluations []tuner.CandidateEvaluation,
) (safeCount int, rejectedCount int, failedCount int) {
	for _, evaluation := range evaluations {
		switch evaluation.Status() {
		case "SAFE":
			safeCount++
		case "REJECTED":
			rejectedCount++
		case "FAILED":
			failedCount++
		}
	}

	return safeCount, rejectedCount, failedCount
}
