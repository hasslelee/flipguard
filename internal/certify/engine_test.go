package certify

import (
	"math"
	"strings"
	"testing"
)

func TestAnalyzeValidationCoverage(t *testing.T) {
	coverage, err := AnalyzeValidationCoverage(
		[]float64{
			0.500,
			0.505,
			0.520,
			0.470,
		},
		0.5,
		0.01,
	)
	if err != nil {
		t.Fatalf(
			"AnalyzeValidationCoverage failed: %v",
			err,
		)
	}

	if coverage.Threshold != 0.5 {
		t.Fatalf(
			"expected threshold 0.5, got %.12f",
			coverage.Threshold,
		)
	}
	if coverage.MarginFloor != 0.01 {
		t.Fatalf(
			"expected margin floor 0.01, got %.12f",
			coverage.MarginFloor,
		)
	}
	if coverage.Total != 4 {
		t.Fatalf(
			"expected total=4, got %d",
			coverage.Total,
		)
	}
	if coverage.VCert != 2 {
		t.Fatalf(
			"expected V_cert=2, got %d",
			coverage.VCert,
		)
	}
	if coverage.VAmb != 2 {
		t.Fatalf(
			"expected V_amb=2, got %d",
			coverage.VAmb,
		)
	}
	if math.Abs(coverage.CoverageRate-0.5) > 1e-12 {
		t.Fatalf(
			"expected coverage rate 0.5, got %.12f",
			coverage.CoverageRate,
		)
	}
	if math.Abs(coverage.MinMargin) > 1e-12 {
		t.Fatalf(
			"expected minimum margin 0, got %.12f",
			coverage.MinMargin,
		)
	}
	if math.Abs(
		coverage.MinCertifiedMargin-0.02,
	) > 1e-12 {
		t.Fatalf(
			"expected minimum certified margin 0.02, got %.12f",
			coverage.MinCertifiedMargin,
		)
	}
}

func TestCertifyAndSelectFastestObservedSafe(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.20, 0.40, 0.60, 0.80},
		0.5,
		0.05,
	)

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID:          "reference",
				Path:        "rescale",
				LogN:        14,
				ChainLength: 7,
				ScaleBits:   45,
				IsReference: true,
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			MaxObservedError:   0.0001,
			MeanTotalMS:        100,
		},
		{
			Candidate: CandidateDescriptor{
				ID:          "latency_only_unsafe",
				Path:        "non-rescale",
				LogN:        14,
				ChainLength: 3,
				ScaleBits:   30,
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			DecisionFlips:      2,
			ErrorViolations:    4,
			MaxObservedError:   0.2,
			MeanTotalMS:        40,
		},
		{
			Candidate: CandidateDescriptor{
				ID:          "fastest_safe",
				Path:        "non-rescale",
				LogN:        14,
				ChainLength: 5,
				ScaleBits:   40,
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			MaxObservedError:   0.0002,
			MeanTotalMS:        75,
		},
	}

	summary, err := CertifyAndSelect(
		evidences,
		coverage,
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
	if summary.Selected.Candidate.ID != "fastest_safe" {
		t.Fatalf(
			"expected fastest_safe, got %s",
			summary.Selected.Candidate.ID,
		)
	}
	if summary.Selected.Assurance !=
		AssuranceObservedValidation {
		t.Fatalf(
			"expected OBSERVED_VALIDATION, got %s",
			summary.Selected.Assurance,
		)
	}
	if summary.SafeCount != 2 {
		t.Fatalf(
			"expected safe count 2, got %d",
			summary.SafeCount,
		)
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
}

func TestStrictHybridSelectsBoundedCandidate(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.30, 0.40, 0.60, 0.70},
		0.5,
		0.01,
	)

	// Min certified margin is 0.1.
	// SafetyFactor 0.5 gives an analytical budget of 0.05.
	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "observed_only_fast",
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			MeanTotalMS:        40,
		},
		{
			Candidate: CandidateDescriptor{
				ID: "loose_bound",
			},
			SuccessRuns:             3,
			ObservedValidation:      true,
			AnalyticalBoundProvided: true,
			MaxErrorBound:           0.06,
			MeanTotalMS:             60,
		},
		{
			Candidate: CandidateDescriptor{
				ID: "hybrid_safe",
			},
			SuccessRuns:             3,
			ObservedValidation:      true,
			AnalyticalBoundProvided: true,
			MaxErrorBound:           0.04,
			MeanTotalMS:             80,
		},
	}

	summary, err := CertifyAndSelectWithPolicy(
		evidences,
		coverage,
		StrictHybridCertificationPolicy(),
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelectWithPolicy failed: %v",
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
		t.Fatal("expected selected hybrid candidate")
	}
	if summary.Selected.Candidate.ID != "hybrid_safe" {
		t.Fatalf(
			"expected hybrid_safe, got %s",
			summary.Selected.Candidate.ID,
		)
	}
	if summary.Selected.Assurance != AssuranceHybrid {
		t.Fatalf(
			"expected HYBRID, got %s",
			summary.Selected.Assurance,
		)
	}
	if summary.SafeCount != 1 {
		t.Fatalf(
			"expected safe count 1, got %d",
			summary.SafeCount,
		)
	}
	if summary.RejectedCount != 2 {
		t.Fatalf(
			"expected rejected count 2, got %d",
			summary.RejectedCount,
		)
	}
}

func TestStrictHybridAcceptsExplicitZeroBound(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.30, 0.70},
		0.5,
		0.01,
	)

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "zero_bound_candidate",
			},
			SuccessRuns:             3,
			ObservedValidation:      true,
			AnalyticalBoundProvided: true,
			MaxErrorBound:           0,
			MeanTotalMS:             10,
		},
	}

	summary, err := CertifyAndSelectWithPolicy(
		evidences,
		coverage,
		StrictHybridCertificationPolicy(),
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelectWithPolicy failed: %v",
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
	if summary.Selected.Assurance != AssuranceHybrid {
		t.Fatalf(
			"expected HYBRID, got %s",
			summary.Selected.Assurance,
		)
	}
	if !summary.Selected.AnalyticalBoundProvided {
		t.Fatal("expected analytical bound to be marked as provided")
	}
	if !summary.Selected.AnalyticalBoundSatisfied {
		t.Fatal("expected explicit zero bound to satisfy the budget")
	}
}

func TestStrictHybridRejectsBoundEquality(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.25, 0.75},
		0.5,
		0.01,
	)

	// The minimum certified margin is 0.25. With a safety factor
	// of 0.5, the protected analytical budget is exactly 0.125.
	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "equal_bound",
			},
			SuccessRuns:             3,
			ObservedValidation:      true,
			AnalyticalBoundProvided: true,
			MaxErrorBound:           0.125,
			MeanTotalMS:             10,
		},
	}

	summary, err := CertifyAndSelectWithPolicy(
		evidences,
		coverage,
		StrictHybridCertificationPolicy(),
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelectWithPolicy failed: %v",
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
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
	if summary.Certificates[0].
		AnalyticalBoundSatisfied {
		t.Fatal(
			"expected equality with analytical budget to be rejected",
		)
	}
}

func TestStrictHybridReturnsNoSafeWithoutBound(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.30, 0.70},
		0.5,
		0.01,
	)

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "observed_only",
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			MeanTotalMS:        10,
		},
	}

	summary, err := CertifyAndSelectWithPolicy(
		evidences,
		coverage,
		StrictHybridCertificationPolicy(),
	)
	if err != nil {
		t.Fatalf(
			"CertifyAndSelectWithPolicy failed: %v",
			err,
		)
	}

	if summary.Outcome != OutcomeNoSafe {
		t.Fatalf(
			"expected NO_SAFE, got %s",
			summary.Outcome,
		)
	}
	if summary.Selected != nil {
		t.Fatal("expected no selected candidate")
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
	if !strings.Contains(
		summary.Certificates[0].Reason,
		"analytical error bound is missing",
	) {
		t.Fatalf(
			"unexpected rejection reason: %s",
			summary.Certificates[0].Reason,
		)
	}
}

func TestCertifyAndSelectReturnsNoSafe(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{0.30, 0.70},
		0.5,
		0.01,
	)

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "failed_candidate",
			},
			FailedRuns: 3,
		},
		{
			Candidate: CandidateDescriptor{
				ID: "rejected_candidate",
			},
			SuccessRuns:        3,
			ObservedValidation: true,
			DecisionFlips:      1,
			ErrorViolations:    2,
			MeanTotalMS:        10,
		},
	}

	summary, err := CertifyAndSelect(
		evidences,
		coverage,
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
	if summary.Selected != nil {
		t.Fatal("expected no selected candidate")
	}
	if summary.FailedCount != 1 {
		t.Fatalf(
			"expected failed count 1, got %d",
			summary.FailedCount,
		)
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
}

func TestCertifyAndSelectMarksAllAmbiguous(
	t *testing.T,
) {
	coverage := mustCoverage(
		t,
		[]float64{
			0.500,
			0.505,
			0.495,
		},
		0.5,
		0.01,
	)

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "successful_but_uncertifiable",
			},
			SuccessRuns:        1,
			ObservedValidation: true,
			MeanTotalMS:        10,
		},
	}

	summary, err := CertifyAndSelect(
		evidences,
		coverage,
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
	if summary.AmbiguousCount != 1 {
		t.Fatalf(
			"expected ambiguous count 1, got %d",
			summary.AmbiguousCount,
		)
	}
	if summary.Certificates[0].Status !=
		StatusAmbiguous {
		t.Fatalf(
			"expected AMBIGUOUS, got %s",
			summary.Certificates[0].Status,
		)
	}
}

func mustCoverage(
	t *testing.T,
	scores []float64,
	threshold float64,
	marginFloor float64,
) ValidationCoverage {
	t.Helper()

	coverage, err := AnalyzeValidationCoverage(
		scores,
		threshold,
		marginFloor,
	)
	if err != nil {
		t.Fatalf(
			"AnalyzeValidationCoverage failed: %v",
			err,
		)
	}

	return coverage
}
