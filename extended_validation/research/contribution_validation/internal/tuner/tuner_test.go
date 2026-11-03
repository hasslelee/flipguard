package tuner

import (
	"errors"
	"testing"
)

func TestGenerateAroundReference(t *testing.T) {
	graph := GraphSummary{
		MultiplicativeDepth: 3,
		MulOps:              2,
		RescaleOps:          2,
	}

	ref := BuildReferenceConfiguration(graph, ReferencePolicy{
		InitialScaleBits: 45,
		ChainMargin:      4,
		MinLogN:          14,
	})

	if ref.ChainLength != 7 {
		t.Fatalf("expected chain 7 reference, got %d", ref.ChainLength)
	}
	if ref.ScaleBits != 45 {
		t.Fatalf("expected scale 45 reference, got %d", ref.ScaleBits)
	}

	candidates := GenerateAroundReference(ref, DefaultCandidateGenerationOptions())
	if len(candidates) == 0 {
		t.Fatal("expected generated candidates")
	}

	foundReferenceRescale := false
	for _, c := range candidates {
		if c.Candidate.IsReference && c.Path == PathRescale {
			foundReferenceRescale = true
		}
		if c.Candidate.ChainLength < 3 {
			t.Fatalf("invalid chain length: %d", c.Candidate.ChainLength)
		}
	}
	if !foundReferenceRescale {
		t.Fatal("expected reference + rescale candidate")
	}
}

func TestSelectFastestSafeAndLatencyOnly(t *testing.T) {
	ref := ParameterCandidate{
		ID:          "reference_chain7_scale45_N14",
		LogN:        14,
		ChainLength: 7,
		ScaleBits:   45,
		IsReference: true,
	}

	evals := []CandidateEvaluation{
		{
			Config: ExecutionConfiguration{
				Candidate: ParameterCandidate{
					ID:          "failed_chain3_scale35_N14",
					LogN:        14,
					ChainLength: 3,
					ScaleBits:   35,
				},
				Path: PathRescale,
			},
			SuccessRuns: 0,
			FailedRuns:  3,
			MeanTotalMS: 0,
		},
		{
			Config:      ExecutionConfiguration{Candidate: ref, Path: PathRescale},
			SuccessRuns: 3,
			MeanTotalMS: 100,
		},
		{
			Config: ExecutionConfiguration{
				Candidate: ParameterCandidate{
					ID:          "chain3_scale35_N14",
					LogN:        14,
					ChainLength: 3,
					ScaleBits:   35,
				},
				Path: PathNonRescale,
			},
			SuccessRuns:     3,
			MeanTotalMS:     50,
			DecisionFlips:   3,
			ErrorViolations: 10,
		},
		{
			Config: ExecutionConfiguration{
				Candidate: ParameterCandidate{
					ID:          "chain6_scale40_N14",
					LogN:        14,
					ChainLength: 6,
					ScaleBits:   40,
				},
				Path: PathNonRescale,
			},
			SuccessRuns: 3,
			MeanTotalMS: 80,
		},
	}

	best, err := SelectFastestSafe(evals)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if best.Config.Candidate.ID != "chain6_scale40_N14" {
		t.Fatalf("wrong selected safe candidate: %s", best.Config.Candidate.ID)
	}

	fastest, err := SelectLatencyOnly(evals)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if fastest.Config.Candidate.ID != "chain3_scale35_N14" {
		t.Fatalf("wrong latency-only candidate: %s", fastest.Config.Candidate.ID)
	}
	if fastest.FailedRuns > 0 {
		t.Fatal("latency-only must not select failed candidates")
	}
}

func TestSelectLatencyOnlyReturnsErrorWhenAllFailed(t *testing.T) {
	evals := []CandidateEvaluation{
		{
			Config: ExecutionConfiguration{
				Candidate: ParameterCandidate{
					ID:          "failed_a",
					LogN:        14,
					ChainLength: 3,
					ScaleBits:   35,
				},
				Path: PathRescale,
			},
			FailedRuns:  3,
			MeanTotalMS: 0,
		},
		{
			Config: ExecutionConfiguration{
				Candidate: ParameterCandidate{
					ID:          "failed_b",
					LogN:        14,
					ChainLength: 5,
					ScaleBits:   40,
				},
				Path: PathNonRescale,
			},
			FailedRuns:  3,
			MeanTotalMS: 0,
		},
	}

	_, err := SelectLatencyOnly(evals)
	if !errors.Is(err, ErrNoSuccessfulCandidate) {
		t.Fatalf("expected ErrNoSuccessfulCandidate, got %v", err)
	}
}
