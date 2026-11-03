package main

import (
	"math"
	"path/filepath"
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

func TestLoadOrRunThreeKeysetsPreservesThirtySixRecordsAndEighteenPairs(t *testing.T) {
	keysetResults := make([]ckksbackend.V17PrimaryPairedLatencyResult, 0, 3)
	allRecords := make([]ckksbackend.V17PrimaryPairedLatencyRecord, 0, 36)
	for keyset := 1; keyset <= 3; keyset++ {
		result, created, err := loadOrRunKeyset(filepath.Join(t.TempDir(), "missing.json"), func() (ckksbackend.V17PrimaryPairedLatencyResult, error) {
			records := make([]ckksbackend.V17PrimaryPairedLatencyRecord, 0, 12)
			for measurement := 1; measurement <= 6; measurement++ {
				records = append(records,
					ckksbackend.V17PrimaryPairedLatencyRecord{Keyset: keyset, MeasurementRun: measurement, ArmID: "direct", TotalMS: 2, EvaluationOnlyMS: 1},
					ckksbackend.V17PrimaryPairedLatencyRecord{Keyset: keyset, MeasurementRun: measurement, ArmID: "finite_fastest_safe", TotalMS: 4, EvaluationOnlyMS: 2},
				)
			}
			return ckksbackend.V17PrimaryPairedLatencyResult{Records: records}, nil
		})
		if err != nil {
			t.Fatalf("keyset %d: %v", keyset, err)
		}
		if !created {
			t.Fatalf("keyset %d unexpectedly loaded a cached result", keyset)
		}
		keysetResults = append(keysetResults, result)
		allRecords = append(allRecords, result.Records...)
	}
	if len(keysetResults) != 3 || len(allRecords) != 36 {
		t.Fatalf("keysets=%d records=%d, want 3 and 36", len(keysetResults), len(allRecords))
	}
	if pairs := summarizePairs(allRecords)["pairs"]; pairs != 18 {
		t.Fatalf("pairs=%v, want 18", pairs)
	}
}

func TestSummarizePairsUsesMatchedKeysetAndPass(t *testing.T) {
	records := []ckksbackend.V17PrimaryPairedLatencyRecord{
		{Keyset: 1, MeasurementRun: 1, ArmID: "direct", TotalMS: 2, EvaluationOnlyMS: 1},
		{Keyset: 1, MeasurementRun: 1, ArmID: "finite_fastest_safe", TotalMS: 8, EvaluationOnlyMS: 2},
		{Keyset: 2, MeasurementRun: 1, ArmID: "direct", TotalMS: 3, EvaluationOnlyMS: 2},
		{Keyset: 2, MeasurementRun: 1, ArmID: "finite_fastest_safe", TotalMS: 12, EvaluationOnlyMS: 4},
	}
	summary := summarizePairs(records)
	if summary["pairs"] != 2 {
		t.Fatalf("pairs=%v, want 2", summary["pairs"])
	}
	if math.Abs(summary["finite_over_direct_geometric_mean_total_ratio"]-4) > 1e-12 {
		t.Fatalf("ratio=%v, want 4", summary["finite_over_direct_geometric_mean_total_ratio"])
	}
	if math.Abs(summary["finite_over_direct_geometric_mean_eval_only_ratio"]-2) > 1e-12 {
		t.Fatalf("eval ratio=%v, want 2", summary["finite_over_direct_geometric_mean_eval_only_ratio"])
	}
}

func TestSummarizePairsDropsIncompletePairs(t *testing.T) {
	summary := summarizePairs([]ckksbackend.V17PrimaryPairedLatencyRecord{
		{Keyset: 1, MeasurementRun: 1, ArmID: "direct", TotalMS: 2},
	})
	if summary["pairs"] != 0 {
		t.Fatalf("pairs=%v, want 0", summary["pairs"])
	}
}

func TestContainsSafeCandidateAuditRequiresMatchingIdentityAndStatus(t *testing.T) {
	document := map[string]any{"result": map[string]any{"trial": map[string]any{
		"status": "SAFE", "candidate": map[string]any{"id": "candidate-a"},
	}}}
	if !containsSafeCandidateAudit(document, "candidate-a") {
		t.Fatal("matching SAFE audit was not found")
	}
	if containsSafeCandidateAudit(document, "candidate-b") {
		t.Fatal("mismatched candidate was accepted")
	}
	document["result"].(map[string]any)["trial"].(map[string]any)["status"] = "REJECTED"
	if containsSafeCandidateAudit(document, "candidate-a") {
		t.Fatal("REJECTED audit was accepted")
	}
}
