package certify

import (
	"math"
	"strings"
	"testing"
)

func TestAggregateObservedCandidateExcludesAmbiguousObservations(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "candidate",
		},
		Samples: []ObservedSample{
			{
				ID:           "ambiguous",
				PlainScore:   0.5,
				Threshold:    0.5,
				ApproxScores: []float64{0.9, 0.1},
			},
			{
				ID:           "positive",
				PlainScore:   0.75,
				Threshold:    0.5,
				ApproxScores: []float64{0.74, 0.76},
			},
			{
				ID:           "negative",
				PlainScore:   0.25,
				Threshold:    0.5,
				ApproxScores: []float64{0.24, 0.26},
			},
		},
		MeanTotalMS: 10,
	}

	aggregation, err := AggregateObservedCandidate(
		input,
		0.01,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"AggregateObservedCandidate failed: %v",
			err,
		)
	}

	if aggregation.Coverage.Total != 3 {
		t.Fatalf(
			"expected total=3, got %d",
			aggregation.Coverage.Total,
		)
	}
	if aggregation.Coverage.VCert != 2 {
		t.Fatalf(
			"expected V_cert=2, got %d",
			aggregation.Coverage.VCert,
		)
	}
	if aggregation.Coverage.VAmb != 1 {
		t.Fatalf(
			"expected V_amb=1, got %d",
			aggregation.Coverage.VAmb,
		)
	}

	if aggregation.Evidence.SuccessRuns != 2 {
		t.Fatalf(
			"expected success runs=2, got %d",
			aggregation.Evidence.SuccessRuns,
		)
	}
	if aggregation.TotalObservations != 6 {
		t.Fatalf(
			"expected total observations=6, got %d",
			aggregation.TotalObservations,
		)
	}
	if aggregation.CertifiedObservations != 4 {
		t.Fatalf(
			"expected certified observations=4, got %d",
			aggregation.CertifiedObservations,
		)
	}
	if aggregation.AmbiguousObservations != 2 {
		t.Fatalf(
			"expected ambiguous observations=2, got %d",
			aggregation.AmbiguousObservations,
		)
	}

	if aggregation.Evidence.DecisionFlips != 0 {
		t.Fatalf(
			"expected zero V_cert flips, got %d",
			aggregation.Evidence.DecisionFlips,
		)
	}
	if aggregation.Evidence.ErrorViolations != 0 {
		t.Fatalf(
			"expected zero V_cert violations, got %d",
			aggregation.Evidence.ErrorViolations,
		)
	}

	if math.Abs(
		aggregation.Evidence.MaxObservedError-0.01,
	) > 1e-12 {
		t.Fatalf(
			"expected V_cert maximum error 0.01, got %.12f",
			aggregation.Evidence.MaxObservedError,
		)
	}
	if math.Abs(
		aggregation.Evidence.MaxObservedBudgetUsage-0.08,
	) > 1e-12 {
		t.Fatalf(
			"expected maximum budget usage 0.08, got %.12f",
			aggregation.Evidence.MaxObservedBudgetUsage,
		)
	}
	if math.Abs(
		aggregation.MaxObservedErrorAll-0.4,
	) > 1e-12 {
		t.Fatalf(
			"expected all-region maximum error 0.4, got %.12f",
			aggregation.MaxObservedErrorAll,
		)
	}

	summary, err := CertifyAndSelect(
		[]CandidateEvidence{
			aggregation.Evidence,
		},
		aggregation.Coverage,
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelect failed: %v",
			err,
		)
	}
	if summary.Outcome != OutcomeSelected {
		t.Fatalf(
			"expected SELECTED, got %s",
			summary.Outcome,
		)
	}
	if summary.Selected == nil {
		t.Fatal("expected selected candidate")
	}
	if summary.Selected.Assurance !=
		AssuranceObservedValidation {
		t.Fatalf(
			"expected OBSERVED_VALIDATION, got %s",
			summary.Selected.Assurance,
		)
	}
}

func TestAggregateObservedCandidateCountsCertifiedFailures(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "unsafe",
		},
		Samples: []ObservedSample{
			{
				ID:           "positive",
				PlainScore:   0.75,
				Threshold:    0.5,
				ApproxScores: []float64{0.40},
			},
			{
				ID:           "negative",
				PlainScore:   0.25,
				Threshold:    0.5,
				ApproxScores: []float64{0.26},
			},
		},
		MeanTotalMS: 5,
	}

	aggregation, err := AggregateObservedCandidate(
		input,
		0.01,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"AggregateObservedCandidate failed: %v",
			err,
		)
	}

	if aggregation.Evidence.DecisionFlips != 1 {
		t.Fatalf(
			"expected one V_cert flip, got %d",
			aggregation.Evidence.DecisionFlips,
		)
	}
	if aggregation.Evidence.ErrorViolations != 1 {
		t.Fatalf(
			"expected one V_cert violation, got %d",
			aggregation.Evidence.ErrorViolations,
		)
	}
	if math.Abs(
		aggregation.Evidence.MaxObservedBudgetUsage-2.8,
	) > 1e-12 {
		t.Fatalf(
			"expected maximum budget usage 2.8, got %.12f",
			aggregation.Evidence.MaxObservedBudgetUsage,
		)
	}

	summary, err := CertifyAndSelect(
		[]CandidateEvidence{
			aggregation.Evidence,
		},
		aggregation.Coverage,
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelect failed: %v",
			err,
		)
	}
	if summary.Outcome != OutcomeNoSafe {
		t.Fatalf(
			"expected NO_SAFE, got %s",
			summary.Outcome,
		)
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected one rejected candidate, got %d",
			summary.RejectedCount,
		)
	}
}

func TestAggregateObservedCandidateTreatsFloorEqualityAsAmbiguous(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "boundary",
		},
		Samples: []ObservedSample{
			{
				ID:           "equal_floor",
				PlainScore:   0.625,
				Threshold:    0.5,
				ApproxScores: []float64{0.0},
			},
			{
				ID:           "certified",
				PlainScore:   0.75,
				Threshold:    0.5,
				ApproxScores: []float64{0.74},
			},
		},
		MeanTotalMS: 5,
	}

	aggregation, err := AggregateObservedCandidate(
		input,
		0.125,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"AggregateObservedCandidate failed: %v",
			err,
		)
	}

	if aggregation.Coverage.VCert != 1 {
		t.Fatalf(
			"expected V_cert=1, got %d",
			aggregation.Coverage.VCert,
		)
	}
	if aggregation.Coverage.VAmb != 1 {
		t.Fatalf(
			"expected V_amb=1, got %d",
			aggregation.Coverage.VAmb,
		)
	}
	if aggregation.Evidence.DecisionFlips != 0 {
		t.Fatalf(
			"expected boundary flip to be excluded, got %d",
			aggregation.Evidence.DecisionFlips,
		)
	}
}

func TestAggregateObservedCandidateRejectsBudgetEquality(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "equal_observed_budget",
		},
		Samples: []ObservedSample{
			{
				ID:           "sample",
				PlainScore:   0.75,
				Threshold:    0.5,
				ApproxScores: []float64{0.625},
			},
		},
		MeanTotalMS: 5,
	}

	// Margin is 0.25. With safety factor 0.5, both the
	// observed error and the protected budget equal 0.125.
	aggregation, err := AggregateObservedCandidate(
		input,
		0.01,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"AggregateObservedCandidate failed: %v",
			err,
		)
	}

	if aggregation.Evidence.DecisionFlips != 0 {
		t.Fatalf(
			"expected zero decision flips, got %d",
			aggregation.Evidence.DecisionFlips,
		)
	}
	if aggregation.Evidence.ErrorViolations != 1 {
		t.Fatalf(
			"expected equality to count as one violation, got %d",
			aggregation.Evidence.ErrorViolations,
		)
	}
	if math.Abs(
		aggregation.Evidence.MaxObservedBudgetUsage-1,
	) > 1e-12 {
		t.Fatalf(
			"expected equality budget usage 1, got %.12f",
			aggregation.Evidence.MaxObservedBudgetUsage,
		)
	}
}

func TestAggregateObservedCandidateRejectsInconsistentRunCounts(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "inconsistent",
		},
		Samples: []ObservedSample{
			{
				ID:           "a",
				PlainScore:   0.25,
				Threshold:    0.5,
				ApproxScores: []float64{0.24, 0.25},
			},
			{
				ID:           "b",
				PlainScore:   0.75,
				Threshold:    0.5,
				ApproxScores: []float64{0.74},
			},
		},
		MeanTotalMS: 5,
	}

	_, err := AggregateObservedCandidate(
		input,
		0.01,
		0.5,
	)
	if err == nil {
		t.Fatal("expected inconsistent run-count error")
	}
	if !strings.Contains(err.Error(), "observations; expected") {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestAggregateObservedCandidateRejectsMixedThresholds(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "mixed_threshold",
		},
		Samples: []ObservedSample{
			{
				ID:           "a",
				PlainScore:   0.25,
				Threshold:    0.5,
				ApproxScores: []float64{0.24},
			},
			{
				ID:           "b",
				PlainScore:   0.75,
				Threshold:    0.6,
				ApproxScores: []float64{0.74},
			},
		},
		MeanTotalMS: 5,
	}

	_, err := AggregateObservedCandidate(
		input,
		0.01,
		0.5,
	)
	if err == nil {
		t.Fatal("expected mixed-threshold error")
	}
	if !strings.Contains(err.Error(), "uses threshold") {
		t.Fatalf(
			"unexpected error: %v",
			err,
		)
	}
}

func TestAggregateObservedCandidatePreservesAnalyticalProof(
	t *testing.T,
) {
	proof := &AnalyticalBoundProof{
		Method:  "unit-test-envelope",
		Version: "v1",

		Guarantee: AnalyticalGuaranteeDeterministic,

		ScopeDigest:      analyticalProofTestDigest,
		DerivationDigest: analyticalProofTestDigest,

		MaxErrorBound: 0.01,
	}

	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "proof_backed_candidate",
		},

		Samples: []ObservedSample{
			{
				ID:           "sample-1",
				PlainScore:   0.30,
				Threshold:    0.50,
				ApproxScores: []float64{0.301},
			},
			{
				ID:           "sample-2",
				PlainScore:   0.70,
				Threshold:    0.50,
				ApproxScores: []float64{0.699},
			},
		},

		MeanTotalMS: 10,

		AnalyticalBoundProvided: true,
		MaxErrorBound:           0.01,
		AnalyticalProof:         proof,
	}

	aggregation, err := AggregateObservedCandidate(
		input,
		0.001,
		0.5,
	)
	if err != nil {
		t.Fatalf(
			"AggregateObservedCandidate failed: %v",
			err,
		)
	}

	evidence := aggregation.Evidence

	if !evidence.AnalyticalBoundProvided {
		t.Fatal(
			"expected analytical bound presence",
		)
	}
	if evidence.AnalyticalProof == nil {
		t.Fatal(
			"expected analytical proof metadata",
		)
	}
	if evidence.AnalyticalProof == proof {
		t.Fatal(
			"expected analytical proof to be cloned",
		)
	}
	if evidence.MaxErrorBound !=
		proof.MaxErrorBound {
		t.Fatalf(
			"bound mismatch: got %.12g, expected %.12g",
			evidence.MaxErrorBound,
			proof.MaxErrorBound,
		)
	}
	if evidence.AnalyticalProof.ScopeDigest !=
		proof.ScopeDigest {
		t.Fatal(
			"analytical scope digest was not preserved",
		)
	}
	if evidence.AnalyticalProof.
		DerivationDigest !=
		proof.DerivationDigest {
		t.Fatal(
			"analytical derivation digest was not preserved",
		)
	}
}

func TestAggregateObservedCandidateRejectsScalarWithoutProofMetadata(
	t *testing.T,
) {
	input := ObservedCandidateInput{
		Candidate: CandidateDescriptor{
			ID: "scalar_only_candidate",
		},

		Samples: []ObservedSample{
			{
				ID:           "sample-1",
				PlainScore:   0.30,
				Threshold:    0.50,
				ApproxScores: []float64{0.301},
			},
		},

		MeanTotalMS: 10,

		AnalyticalBoundProvided: true,
		MaxErrorBound:           0.01,
	}

	_, err := AggregateObservedCandidate(
		input,
		0.001,
		0.5,
	)
	if err == nil {
		t.Fatal(
			"expected scalar-only analytical bound to fail",
		)
	}
	if !strings.Contains(
		err.Error(),
		"does not match proof metadata",
	) {
		t.Fatalf(
			"unexpected scalar-only error: %v",
			err,
		)
	}
}
