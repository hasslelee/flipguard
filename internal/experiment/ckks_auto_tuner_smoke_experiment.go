package experiment

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const ckksAutoTunerSmokeResultDir = "results/ckks_auto_tuner_smoke"

// RunCKKSAutoTunerSmoke runs a deterministic smoke test for the FlipGuard
// auto-tuner pipeline.
//
// This experiment does not yet re-execute CKKS for every generated candidate.
// Instead, it verifies that the following paper-facing pipeline works:
//
//  1. build a conservative reference configuration from a workload graph,
//  2. generate nearby candidate configurations,
//  3. evaluate candidates with deterministic synthetic validation results,
//  4. select the fastest safe candidate,
//  5. export candidate and selection CSV artifacts.
//
// The next implementation step is to replace the synthetic evaluator with
// measured CKKS candidate evaluation for concrete workloads.
func RunCKKSAutoTunerSmoke() error {
	graph := tuner.GraphSummary{
		MultiplicativeDepth: 3,
		AddOps:              18,
		MulOps:              6,
		RotOps:              0,
		RescaleOps:          3,
		Notes: []string{
			"synthetic polynomial/MLP-like CKKS workload",
			"used only to validate the auto-tuner reporting pipeline",
		},
	}

	reference := tuner.BuildReferenceConfiguration(graph, tuner.ReferencePolicy{
		SecurityBits:     128,
		InitialScaleBits: 45,
		ChainMargin:      4,
		MinLogN:          14,
		MaxLogN:          15,
	})

	candidates := tuner.GenerateAroundReference(reference, tuner.DefaultCandidateGenerationOptions())
	evaluations := evaluateSmokeCandidates(graph, reference, candidates)

	fastestSafe, err := tuner.SelectFastestSafe(evaluations)
	if err != nil {
		return fmt.Errorf("select fastest safe candidate: %w", err)
	}

	latencyOnly, err := tuner.SelectLatencyOnly(evaluations)
	if err != nil {
		return fmt.Errorf("select latency-only candidate: %w", err)
	}

	referenceEval, ok := findReferenceEvaluation(evaluations)
	if !ok {
		return fmt.Errorf("reference evaluation not found")
	}

	candidatesPath, err := report.ExportTunerCandidateEvaluations(
		ckksAutoTunerSmokeResultDir,
		"tuner_candidates.csv",
		evaluations,
	)
	if err != nil {
		return fmt.Errorf("export tuner candidate evaluations: %w", err)
	}

	selectionPath, err := report.ExportTunerSelectionRecords(
		ckksAutoTunerSmokeResultDir,
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

	fmt.Printf("Generated %d tuner candidate evaluations\n", len(evaluations))
	fmt.Printf("Reference candidate: %s/%s status=%s mean_total_ms=%.4f\n",
		referenceEval.Config.Candidate.ID,
		referenceEval.Config.Path,
		referenceEval.Status(),
		referenceEval.MeanTotalMS,
	)
	fmt.Printf("Fastest safe candidate: %s/%s status=%s mean_total_ms=%.4f\n",
		fastestSafe.Config.Candidate.ID,
		fastestSafe.Config.Path,
		fastestSafe.Status(),
		fastestSafe.MeanTotalMS,
	)
	fmt.Printf("Latency-only candidate: %s/%s status=%s mean_total_ms=%.4f\n",
		latencyOnly.Config.Candidate.ID,
		latencyOnly.Config.Path,
		latencyOnly.Status(),
		latencyOnly.MeanTotalMS,
	)
	fmt.Printf("Wrote %s\n", candidatesPath)
	fmt.Printf("Wrote %s\n", selectionPath)

	return nil
}

func evaluateSmokeCandidates(
	graph tuner.GraphSummary,
	reference tuner.ParameterCandidate,
	candidates []tuner.ExecutionConfiguration,
) []tuner.CandidateEvaluation {
	evaluations := make([]tuner.CandidateEvaluation, 0, len(candidates))

	referenceConfig := tuner.ExecutionConfiguration{
		Candidate: reference,
		Path:      tuner.PathRescale,
	}

	referenceCost := tuner.EstimateRelativeCost(graph, referenceConfig).RelativeCost
	if referenceCost <= 0 {
		referenceCost = 1
	}

	for _, candidate := range candidates {
		evaluations = append(evaluations, evaluateSmokeCandidate(graph, reference, referenceCost, candidate))
	}

	return evaluations
}

func evaluateSmokeCandidate(
	graph tuner.GraphSummary,
	reference tuner.ParameterCandidate,
	referenceCost float64,
	config tuner.ExecutionConfiguration,
) tuner.CandidateEvaluation {
	candidate := config.Candidate

	cost := tuner.EstimateRelativeCost(graph, config)
	meanTotalMS := 100.0 * cost.RelativeCost / referenceCost

	outputError := syntheticOutputError(reference, config)
	errorTolerance := 0.02

	evaluation := tuner.CandidateEvaluation{
		Config:          config,
		SuccessRuns:     5,
		FailedRuns:      0,
		DecisionFlips:   0,
		ErrorViolations: 0,
		MaxOutputError:  outputError,
		MeanTotalMS:     meanTotalMS,
	}

	// Candidates with insufficient chain length are treated as execution
	// failures in the smoke model. In real experiments this will be determined
	// by the CKKS backend.
	if candidate.ChainLength <= graph.MultiplicativeDepth {
		evaluation.SuccessRuns = 0
		evaluation.FailedRuns = 5
		return evaluation
	}

	if outputError > errorTolerance {
		evaluation.ErrorViolations = 5
	}

	// The smoke model makes the fastest low-scale configurations unsafe so
	// that the exported selection table demonstrates the difference between
	// latency-only selection and FlipGuard's fastest-safe selection.
	if outputError > 0.04 {
		evaluation.DecisionFlips = 3
	} else if outputError > errorTolerance {
		evaluation.DecisionFlips = 1
	}

	return evaluation
}

func syntheticOutputError(reference tuner.ParameterCandidate, config tuner.ExecutionConfiguration) float64 {
	candidate := config.Candidate

	chainPenalty := float64(reference.ChainLength) / float64(candidate.ChainLength)
	scalePenalty := math.Pow(2, float64(reference.ScaleBits-candidate.ScaleBits)/5.0)

	pathPenalty := 1.0
	if config.Path == tuner.PathNonRescale {
		pathPenalty = 1.25
	}

	return 0.002 * chainPenalty * scalePenalty * pathPenalty
}

func findReferenceEvaluation(evaluations []tuner.CandidateEvaluation) (tuner.CandidateEvaluation, bool) {
	for _, evaluation := range evaluations {
		if evaluation.Config.Candidate.IsReference && evaluation.Config.Path == tuner.PathRescale {
			return evaluation, true
		}
	}

	return tuner.CandidateEvaluation{}, false
}
