package certify

import (
	"fmt"
	"math"
)

// ObservedSample stores the plaintext decision reference and all successful
// CKKS observations for one validation sample.
//
// ApproxScores must contain exactly one score for every successful execution
// run of the candidate. All samples in one aggregation must have the same
// number of approximate scores.
type ObservedSample struct {
	ID string

	PlainScore float64
	Threshold  float64

	ApproxScores []float64
}

// ObservedCandidateInput contains sample-level evidence for one candidate.
type ObservedCandidateInput struct {
	Candidate CandidateDescriptor

	Samples []ObservedSample

	FailedRuns int

	MeanTotalMS float64

	AnalyticalBoundProvided bool
	MaxErrorBound           float64
	AnalyticalProof         *AnalyticalBoundProof
}

// ObservedAggregation contains the evidence consumed by the certification
// engine and additional observation counts needed for reporting.
//
// ValidationCoverage counts unique plaintext samples. Observation counts include
// repeated CKKS executions.
type ObservedAggregation struct {
	Evidence CandidateEvidence
	Coverage ValidationCoverage

	TotalObservations     int
	CertifiedObservations int
	AmbiguousObservations int

	// MaxObservedErrorAll includes both V_cert and V_amb observations.
	// Evidence.MaxObservedError is restricted to V_cert.
	MaxObservedErrorAll float64
}

// AggregateObservedCandidate partitions validation samples by plaintext margin
// and aggregates decision flips and margin-budget violations over V_cert.
//
// A certified observation violates the protected observed-error budget when:
//
//	|approxScore - plainScore| >= safetyFactor * |plainScore - threshold|
//
// Equality is conservatively treated as unsafe so accepted observations
// satisfy a strict decision-margin condition.
//
// Observations belonging to V_amb are excluded from DecisionFlips,
// ErrorViolations, and Evidence.MaxObservedError.
func AggregateObservedCandidate(
	input ObservedCandidateInput,
	marginFloor float64,
	safetyFactor float64,
) (ObservedAggregation, error) {
	if input.Candidate.ID == "" {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate ID is empty",
		)
	}
	if len(input.Samples) == 0 {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s has no validation samples",
			input.Candidate.ID,
		)
	}
	if !isFinite(marginFloor) || marginFloor < 0 {
		return ObservedAggregation{}, fmt.Errorf(
			"margin floor must be finite and non-negative: %.12g",
			marginFloor,
		)
	}
	if input.FailedRuns < 0 {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s has negative failed runs",
			input.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(input.MeanTotalMS) {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s has invalid mean latency",
			input.Candidate.ID,
		)
	}
	if !isNonNegativeFinite(input.MaxErrorBound) {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s has invalid analytical error bound",
			input.Candidate.ID,
		)
	}

	proofProvided := input.AnalyticalProof != nil

	if input.AnalyticalBoundProvided != proofProvided {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s analytical bound presence does not match proof metadata",
			input.Candidate.ID,
		)
	}

	if !proofProvided &&
		input.MaxErrorBound != 0 {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s supplies a nonzero analytical bound without proof metadata",
			input.Candidate.ID,
		)
	}

	if proofProvided {
		if err := input.AnalyticalProof.Validate(); err != nil {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s has invalid analytical proof: %w",
				input.Candidate.ID,
				err,
			)
		}

		if input.MaxErrorBound !=
			input.AnalyticalProof.MaxErrorBound {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s analytical bound scalar %.12g does not match proof bound %.12g",
				input.Candidate.ID,
				input.MaxErrorBound,
				input.AnalyticalProof.MaxErrorBound,
			)
		}
	}

	policy := CertificationPolicy{
		SafetyFactor:              safetyFactor,
		RequireObservedValidation: true,
	}
	if err := policy.Validate(); err != nil {
		return ObservedAggregation{}, fmt.Errorf(
			"invalid observed-evidence policy: %w",
			err,
		)
	}

	threshold := input.Samples[0].Threshold
	if !isFinite(threshold) {
		return ObservedAggregation{}, fmt.Errorf(
			"candidate %s has a non-finite validation threshold",
			input.Candidate.ID,
		)
	}

	successRuns := len(input.Samples[0].ApproxScores)
	plainScores := make([]float64, 0, len(input.Samples))
	seenIDs := make(map[string]struct{}, len(input.Samples))

	for sampleIndex, sample := range input.Samples {
		if sample.ID == "" {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s has an empty sample ID at index %d",
				input.Candidate.ID,
				sampleIndex,
			)
		}
		if _, exists := seenIDs[sample.ID]; exists {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s has duplicate sample ID %q",
				input.Candidate.ID,
				sample.ID,
			)
		}
		seenIDs[sample.ID] = struct{}{}

		if !isFinite(sample.PlainScore) {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s sample %q has a non-finite plaintext score",
				input.Candidate.ID,
				sample.ID,
			)
		}
		if !isFinite(sample.Threshold) {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s sample %q has a non-finite threshold",
				input.Candidate.ID,
				sample.ID,
			)
		}
		if sample.Threshold != threshold {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s sample %q uses threshold %.12g; expected %.12g",
				input.Candidate.ID,
				sample.ID,
				sample.Threshold,
				threshold,
			)
		}
		if len(sample.ApproxScores) != successRuns {
			return ObservedAggregation{}, fmt.Errorf(
				"candidate %s sample %q has %d observations; expected %d",
				input.Candidate.ID,
				sample.ID,
				len(sample.ApproxScores),
				successRuns,
			)
		}

		for runIndex, approxScore := range sample.ApproxScores {
			if !isFinite(approxScore) {
				return ObservedAggregation{}, fmt.Errorf(
					"candidate %s sample %q run %d has a non-finite approximate score",
					input.Candidate.ID,
					sample.ID,
					runIndex,
				)
			}
		}

		plainScores = append(plainScores, sample.PlainScore)
	}

	coverage, err := AnalyzeValidationCoverage(
		plainScores,
		threshold,
		marginFloor,
	)
	if err != nil {
		return ObservedAggregation{}, fmt.Errorf(
			"analyze candidate %s validation coverage: %w",
			input.Candidate.ID,
			err,
		)
	}

	aggregation := ObservedAggregation{
		Coverage: coverage,

		TotalObservations:     coverage.Total * successRuns,
		CertifiedObservations: coverage.VCert * successRuns,
		AmbiguousObservations: coverage.VAmb * successRuns,
	}

	evidence := CandidateEvidence{
		Candidate: input.Candidate,

		SuccessRuns: successRuns,
		FailedRuns:  input.FailedRuns,

		ObservedValidation: successRuns > 0,

		AnalyticalBoundProvided: proofProvided,
		MaxErrorBound:           input.MaxErrorBound,
		AnalyticalProof: cloneAnalyticalBoundProof(
			input.AnalyticalProof,
		),

		MeanTotalMS: input.MeanTotalMS,
	}

	for _, sample := range input.Samples {
		margin := math.Abs(sample.PlainScore - threshold)
		ambiguous := margin <= marginFloor
		plainDecision := classifyObservedScore(
			sample.PlainScore,
			threshold,
		)

		for _, approxScore := range sample.ApproxScores {
			observedError := math.Abs(
				approxScore - sample.PlainScore,
			)
			aggregation.MaxObservedErrorAll = math.Max(
				aggregation.MaxObservedErrorAll,
				observedError,
			)

			if ambiguous {
				continue
			}

			evidence.MaxObservedError = math.Max(
				evidence.MaxObservedError,
				observedError,
			)

			approxDecision := classifyObservedScore(
				approxScore,
				threshold,
			)
			if plainDecision != approxDecision {
				evidence.DecisionFlips++
			}

			observedBudget := safetyFactor * margin
			if observedError >= observedBudget {
				evidence.ErrorViolations++
			}
		}
	}

	aggregation.Evidence = evidence

	return aggregation, nil
}

func classifyObservedScore(
	score float64,
	threshold float64,
) bool {
	return score >= threshold
}
