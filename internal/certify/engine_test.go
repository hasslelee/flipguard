package certify

import (
	"math"
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
		t.Fatalf("AnalyzeValidationCoverage failed: %v", err)
	}

	if coverage.Total != 4 {
		t.Fatalf("expected total=4, got %d", coverage.Total)
	}
	if coverage.VCert != 2 {
		t.Fatalf("expected V_cert=2, got %d", coverage.VCert)
	}
	if coverage.VAmb != 2 {
		t.Fatalf("expected V_amb=2, got %d", coverage.VAmb)
	}
	if math.Abs(coverage.CoverageRate-0.5) > 1e-12 {
		t.Fatalf(
			"expected coverage rate 0.5, got %.12f",
			coverage.CoverageRate,
		)
	}
	if math.Abs(coverage.MinMargin-0.0) > 1e-12 {
		t.Fatalf(
			"expected minimum margin 0, got %.12f",
			coverage.MinMargin,
		)
	}
	if math.Abs(coverage.MinCertifiedMargin-0.02) > 1e-12 {
		t.Fatalf(
			"expected minimum certified margin 0.02, got %.12f",
			coverage.MinCertifiedMargin,
		)
	}
}

func TestCertifyAndSelectFastestSafe(t *testing.T) {
	coverage, err := AnalyzeValidationCoverage(
		[]float64{
			0.20,
			0.40,
			0.60,
			0.80,
		},
		0.5,
		0.05,
	)
	if err != nil {
		t.Fatalf("AnalyzeValidationCoverage failed: %v", err)
	}

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
			SuccessRuns:      3,
			MaxObservedError: 0.0001,
			MeanTotalMS:      100,
		},
		{
			Candidate: CandidateDescriptor{
				ID:          "latency_only_unsafe",
				Path:        "non-rescale",
				LogN:        14,
				ChainLength: 3,
				ScaleBits:   30,
			},
			SuccessRuns:      3,
			DecisionFlips:    2,
			ErrorViolations:  4,
			MaxObservedError: 0.2,
			MeanTotalMS:      40,
		},
		{
			Candidate: CandidateDescriptor{
				ID:          "fastest_safe",
				Path:        "non-rescale",
				LogN:        14,
				ChainLength: 5,
				ScaleBits:   40,
			},
			SuccessRuns:      3,
			MaxObservedError: 0.0002,
			MeanTotalMS:      75,
		},
	}

	summary, err := CertifyAndSelect(evidences, coverage)
	if err != nil {
		t.Fatalf("CertifyAndSelect failed: %v", err)
	}

	if summary.Outcome != OutcomeSelected {
		t.Fatalf("expected SELECTED, got %s", summary.Outcome)
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
	if summary.SafeCount != 2 {
		t.Fatalf("expected safe count 2, got %d", summary.SafeCount)
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
}

func TestCertifyAndSelectReturnsNoSafe(t *testing.T) {
	coverage, err := AnalyzeValidationCoverage(
		[]float64{0.30, 0.70},
		0.5,
		0.01,
	)
	if err != nil {
		t.Fatalf("AnalyzeValidationCoverage failed: %v", err)
	}

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
			SuccessRuns:     3,
			DecisionFlips:   1,
			ErrorViolations: 2,
			MeanTotalMS:     10,
		},
	}

	summary, err := CertifyAndSelect(evidences, coverage)
	if err != nil {
		t.Fatalf("CertifyAndSelect failed: %v", err)
	}

	if summary.Outcome != OutcomeNoSafe {
		t.Fatalf("expected NO_SAFE, got %s", summary.Outcome)
	}
	if summary.Selected != nil {
		t.Fatal("expected no selected candidate")
	}
	if summary.FailedCount != 1 {
		t.Fatalf("expected failed count 1, got %d", summary.FailedCount)
	}
	if summary.RejectedCount != 1 {
		t.Fatalf(
			"expected rejected count 1, got %d",
			summary.RejectedCount,
		)
	}
}

func TestCertifyAndSelectMarksAllAmbiguous(t *testing.T) {
	coverage, err := AnalyzeValidationCoverage(
		[]float64{
			0.500,
			0.505,
			0.495,
		},
		0.5,
		0.01,
	)
	if err != nil {
		t.Fatalf("AnalyzeValidationCoverage failed: %v", err)
	}

	evidences := []CandidateEvidence{
		{
			Candidate: CandidateDescriptor{
				ID: "successful_but_uncertifiable",
			},
			SuccessRuns: 1,
			MeanTotalMS: 10,
		},
	}

	summary, err := CertifyAndSelect(evidences, coverage)
	if err != nil {
		t.Fatalf("CertifyAndSelect failed: %v", err)
	}

	if summary.Outcome != OutcomeNoSafe {
		t.Fatalf("expected NO_SAFE, got %s", summary.Outcome)
	}
	if summary.AmbiguousCount != 1 {
		t.Fatalf(
			"expected ambiguous count 1, got %d",
			summary.AmbiguousCount,
		)
	}
	if summary.Certificates[0].Status != StatusAmbiguous {
		t.Fatalf(
			"expected AMBIGUOUS, got %s",
			summary.Certificates[0].Status,
		)
	}
}
