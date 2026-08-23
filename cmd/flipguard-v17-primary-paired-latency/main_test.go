package main

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

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
