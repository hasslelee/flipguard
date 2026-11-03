package report

import (
	"os"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/tuner"
)

func TestExportTunerCandidateEvaluations(t *testing.T) {
	outDir := t.TempDir()

	evals := []tuner.CandidateEvaluation{
		{
			Config: tuner.ExecutionConfiguration{
				Candidate: tuner.ParameterCandidate{
					ID:          "reference_chain7_scale45_N14",
					LogN:        14,
					Slots:       8192,
					ChainLength: 7,
					ScaleBits:   45,
					Family:      "reference",
					IsReference: true,
				},
				Path: tuner.PathRescale,
			},
			SuccessRuns:     3,
			FailedRuns:      0,
			MaxOutputError:  0.00125,
			MeanTotalMS:     12.5,
			DecisionFlips:   0,
			ErrorViolations: 0,
		},
		{
			Config: tuner.ExecutionConfiguration{
				Candidate: tuner.ParameterCandidate{
					ID:          "candidate_chain4_scale35_N14",
					LogN:        14,
					Slots:       8192,
					ChainLength: 4,
					ScaleBits:   35,
					Family:      "local",
					IsReference: false,
				},
				Path: tuner.PathNonRescale,
			},
			SuccessRuns:     3,
			FailedRuns:      0,
			MaxOutputError:  0.08,
			MeanTotalMS:     7.1,
			DecisionFlips:   2,
			ErrorViolations: 5,
		},
	}

	path, err := ExportTunerCandidateEvaluations(outDir, "candidates", evals)
	if err != nil {
		t.Fatalf("ExportTunerCandidateEvaluations failed: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read exported csv: %v", err)
	}

	content := string(data)

	assertContains(t, content, "candidate_id,path,logN,slots,chain_length,scale_bits")
	assertContains(t, content, "reference_chain7_scale45_N14,rescale,14,8192,7,45,reference,true,SAFE")
	assertContains(t, content, "candidate_chain4_scale35_N14,non-rescale,14,8192,4,35,local,false,REJECTED")
}

func TestExportTunerSelectionRecords(t *testing.T) {
	outDir := t.TempDir()

	selected := tuner.CandidateEvaluation{
		Config: tuner.ExecutionConfiguration{
			Candidate: tuner.ParameterCandidate{
				ID:          "candidate_chain6_scale40_N14",
				LogN:        14,
				Slots:       8192,
				ChainLength: 6,
				ScaleBits:   40,
				Family:      "local",
				IsReference: false,
			},
			Path: tuner.PathNonRescale,
		},
		SuccessRuns:     5,
		FailedRuns:      0,
		DecisionFlips:   0,
		ErrorViolations: 0,
		MaxOutputError:  0.003,
		MeanTotalMS:     8.4,
	}

	unsafeFastest := tuner.CandidateEvaluation{
		Config: tuner.ExecutionConfiguration{
			Candidate: tuner.ParameterCandidate{
				ID:          "candidate_chain3_scale30_N14",
				LogN:        14,
				Slots:       8192,
				ChainLength: 3,
				ScaleBits:   30,
				Family:      "local",
				IsReference: false,
			},
			Path: tuner.PathNonRescale,
		},
		SuccessRuns:     5,
		FailedRuns:      0,
		DecisionFlips:   4,
		ErrorViolations: 9,
		MaxOutputError:  0.12,
		MeanTotalMS:     5.2,
	}

	records := []TunerSelectionRecord{
		{
			Policy:     "fastest_safe",
			Evaluation: selected,
		},
		{
			Policy:     "latency_only",
			Evaluation: unsafeFastest,
		},
	}

	path, err := ExportTunerSelectionRecords(outDir, "selection", records)
	if err != nil {
		t.Fatalf("ExportTunerSelectionRecords failed: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read exported csv: %v", err)
	}

	content := string(data)

	assertContains(t, content, "policy,candidate_id,path,logN,slots,chain_length,scale_bits")
	assertContains(t, content, "fastest_safe,candidate_chain6_scale40_N14,non-rescale,14,8192,6,40,local,false,SAFE")
	assertContains(t, content, "latency_only,candidate_chain3_scale30_N14,non-rescale,14,8192,3,30,local,false,REJECTED")
}

func assertContains(t *testing.T, content string, want string) {
	t.Helper()

	if !strings.Contains(content, want) {
		t.Fatalf("expected exported content to contain %q\ncontent:\n%s", want, content)
	}
}
