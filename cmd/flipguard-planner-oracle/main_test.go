package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadModelGraphMatchesLinearRuntimeStructure(t *testing.T) {
	path := filepath.Join(
		"..",
		"..",
		"datasets",
		"tabular_suite",
		"iris_binary",
		"linear_poly3",
		"model.json",
	)

	_, graph, err := loadModelGraph(path)
	if err != nil {
		t.Fatalf("loadModelGraph failed: %v", err)
	}

	if graph.MultiplicativeDepth != 2 {
		t.Fatalf("expected depth 2, got %d", graph.MultiplicativeDepth)
	}
	if graph.MulOps != 8 {
		t.Fatalf("expected 8 total multiplications, got %d", graph.MulOps)
	}
	if graph.AddOps != 6 {
		t.Fatalf("expected 6 additions, got %d", graph.AddOps)
	}
	if graph.RescaleOps != 2 {
		t.Fatalf("expected 2 rescale sites, got %d", graph.RescaleOps)
	}
}

func TestLoadModelGraphMatchesMLPRuntimeStructure(t *testing.T) {
	path := filepath.Join(
		"..",
		"..",
		"datasets",
		"tabular_suite",
		"iris_binary",
		"mlp_square_linear_score",
		"model.json",
	)

	_, graph, err := loadModelGraph(path)
	if err != nil {
		t.Fatalf("loadModelGraph failed: %v", err)
	}

	if graph.MultiplicativeDepth != 1 {
		t.Fatalf("expected depth 1, got %d", graph.MultiplicativeDepth)
	}
	if graph.MulOps != 25 {
		t.Fatalf("expected 25 total multiplications, got %d", graph.MulOps)
	}
	if graph.AddOps != 21 {
		t.Fatalf("expected 21 additions, got %d", graph.AddOps)
	}
	if graph.RescaleOps != 1 {
		t.Fatalf("expected 1 rescale site, got %d", graph.RescaleOps)
	}
}

func TestCompareProjectionReportsRecallRegretAndPruning(t *testing.T) {
	records := []candidateRecord{
		candidateForTest("a", "SAFE", 10),
		candidateForTest("b", "SAFE", 12),
		candidateForTest("c", "REJECTED", 8),
		candidateForTest("d", "FAILED", 0),
	}

	result, err := compareProjection(
		records,
		[]projectedCandidate{
			{CandidateID: "b"},
			{CandidateID: "c"},
		},
	)
	if err != nil {
		t.Fatalf("compareProjection failed: %v", err)
	}

	if result.SafeRecall != 0.5 {
		t.Fatalf("expected SAFE recall 0.5, got %g", result.SafeRecall)
	}
	if result.OptimumRecall != 0 {
		t.Fatalf("expected optimum recall 0, got %g", result.OptimumRecall)
	}
	if result.LatencyRegret != 0.2 {
		t.Fatalf("expected latency regret 0.2, got %g", result.LatencyRegret)
	}
	if result.PruningRatio != 0.5 {
		t.Fatalf("expected pruning ratio 0.5, got %g", result.PruningRatio)
	}
	if result.FalseNoSafe {
		t.Fatal("did not expect false NO_SAFE")
	}
}

func TestCompareProjectionMakesNoSafeDenominatorsUndefined(t *testing.T) {
	records := []candidateRecord{
		candidateForTest("a", "REJECTED", 10),
		candidateForTest("b", "FAILED", 0),
	}

	result, err := compareProjection(
		records,
		[]projectedCandidate{{CandidateID: "a"}},
	)
	if err != nil {
		t.Fatalf("compareProjection failed: %v", err)
	}

	if result.OracleOutcome != "NO_SAFE" {
		t.Fatalf("expected oracle NO_SAFE, got %s", result.OracleOutcome)
	}
	if result.SafeRecallDefined ||
		result.OptimumRecallDefined ||
		result.LatencyRegretDefined {
		t.Fatal("NO_SAFE metrics must be undefined")
	}
	if result.FalseNoSafe {
		t.Fatal("oracle NO_SAFE is not false NO_SAFE")
	}
}

func TestSmokeProjectionStaysInsideOracleMatrix(t *testing.T) {
	repositoryRoot, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatalf("resolve repository root: %v", err)
	}

	originalWorkingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	if err := os.Chdir(repositoryRoot); err != nil {
		t.Fatalf("change to repository root: %v", err)
	}
	t.Cleanup(func() {
		if err := os.Chdir(originalWorkingDirectory); err != nil {
			t.Errorf("restore working directory: %v", err)
		}
	})

	candidatePath := filepath.Join(
		repositoryRoot,
		"results",
		"thesis_grade_protocol",
		"tabular_validation_oracle_v1",
		"smoke",
		"summary",
		"candidate_certificates.csv",
	)
	coveragePath := filepath.Join(
		repositoryRoot,
		"results",
		"thesis_grade_protocol",
		"tabular_validation_oracle_v1",
		"smoke",
		"summary",
		"validation_coverage.csv",
	)

	if _, err := os.Stat(candidatePath); err != nil {
		t.Skipf("smoke evidence is unavailable: %v", err)
	}

	candidates, err := loadCandidateRecords(candidatePath)
	if err != nil {
		t.Fatalf("loadCandidateRecords failed: %v", err)
	}
	coverage, err := loadCoverageRecords(coveragePath)
	if err != nil {
		t.Fatalf("loadCoverageRecords failed: %v", err)
	}

	groups := groupCandidateRecords(candidates)
	if len(groups) != 5 {
		t.Fatalf("expected five alpha groups, got %d", len(groups))
	}

	for key, records := range groups {
		split := splitKey{
			Seed:      key.Seed,
			DatasetID: key.DatasetID,
			ModelID:   key.ModelID,
		}
		plan, err := buildGroupPlan(key, records, coverage[split])
		if err != nil {
			t.Fatalf("buildGroupPlan failed: %v", err)
		}

		oracleIDs := make(map[string]bool)
		for _, record := range records {
			oracleIDs[record.CandidateID] = true
		}
		for _, candidate := range plan.Candidates {
			if !oracleIDs[candidate.CandidateID] {
				t.Fatalf(
					"planner candidate %s is outside smoke oracle",
					candidate.CandidateID,
				)
			}
		}
	}
}

func candidateForTest(
	id string,
	status string,
	latency float64,
) candidateRecord {
	return candidateRecord{
		CandidateID:       id,
		CertificateStatus: status,
		MeanTotalMS:       latency,
		HasLatency:        latency > 0,
	}
}
