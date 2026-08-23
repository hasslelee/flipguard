package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const schema = "flipguard_model_family_expansion_v17_tabular_paired_latency_v1"

type finiteResult struct {
	FastestSafe *ckksplanner.SynthesizedCandidate `json:"fastest_safe"`
}

type caseSummary struct {
	DirectIndependentStatus  certify.CandidateStatus `json:"direct_independent_status"`
	FastestIndependentStatus certify.CandidateStatus `json:"fastest_safe_independent_status"`
}

type keyedResult struct {
	Keyset      int                                    `json:"keyset"`
	Measurement ckksbackend.PairedTabularLatencyResult `json:"measurement"`
}

func main() {
	caseRoot := flag.String("case-root", "", "completed direct/B3/independent case root")
	out := flag.String("out", "", "paired result path")
	flag.Parse()
	if *caseRoot == "" || *out == "" {
		fatalf("--case-root and --out are required")
	}
	if _, err := os.Stat(*out); err == nil {
		fmt.Printf("paired latency already complete: %s\n", *out)
		return
	}
	var selection ckksplanner.AdaptiveAutotuneResult
	var finite finiteResult
	var summary caseSummary
	readJSON(filepath.Join(*caseRoot, "selection.json"), &selection)
	readJSON(filepath.Join(*caseRoot, "exhaustive.json"), &finite)
	readJSON(filepath.Join(*caseRoot, "case_summary.json"), &summary)
	status := "SAFE_TO_SAFE_ELIGIBLE"
	result := map[string]any{"schema_version": schema, "warmup_runs": 1, "measurement_passes": 6, "selected_rows": 20, "fresh_keysets": 3, "order": "balanced_cyclic_and_reverse_row_rotated_v1", "outlier_removal": false}
	if selection.Selected == nil || finite.FastestSafe == nil || summary.DirectIndependentStatus != certify.StatusSafe || summary.FastestIndependentStatus != certify.StatusSafe {
		status = "NOT_EVALUATED_NON_SAFE_ARM"
		result["status"] = status
		result["safe_to_safe_eligible"] = false
		writeAtomic(*out, result)
		fmt.Printf("paired latency status=%s output=%s\n", status, *out)
		return
	}
	selected, err := ckksplanner.ValidateSelectedAutotuneResult(selection)
	if err != nil {
		fatalf("validate direct selection: %v", err)
	}
	if selected.ID != selection.Selected.ID {
		fatalf("direct selected identity changed")
	}
	directProfile, err := selected.Profile()
	if err != nil {
		fatalf("materialize direct: %v", err)
	}
	finiteProfile, err := finite.FastestSafe.Profile()
	if err != nil {
		fatalf("materialize finite fastest SAFE: %v", err)
	}
	contract := selection.Plan.Contract
	independentData := filepath.Join(*caseRoot, "independent_evaluation.prepared.csv")
	if _, err := os.Stat(independentData); err != nil {
		fatalf("independent-evaluation materialization: %v", err)
	}
	keysets := make([]keyedResult, 0, 3)
	timingFlips := map[string]int{"direct": 0, "finite_fastest_safe": 0}
	timingViolations := map[string]int{"direct": 0, "finite_fastest_safe": 0}
	for keyset := 1; keyset <= 3; keyset++ {
		measurement, runErr := ckksbackend.RunPairedTabularLatency(ckksbackend.PairedTabularLatencyConfig{
			ModelPath: contract.ModelArtifact.Path, TestPath: independentData,
			DatasetID: contract.DatasetID, ModelID: contract.ModelID, MaxRows: 20,
			WarmupRuns: 1, MeasureRuns: 6,
			Arms: []ckksbackend.PairedTabularLatencyArm{
				{ID: "direct", Role: "flipguard_bounded_direct", CandidateID: selected.ID, Profile: directProfile, EvaluationMode: string(selected.Path)},
				{ID: "finite_fastest_safe", Role: "v17_depth_complete_finite_fastest_safe", CandidateID: finite.FastestSafe.ID, Profile: finiteProfile, EvaluationMode: string(finite.FastestSafe.Path)},
			},
		})
		if runErr != nil {
			fatalf("keyset %d paired latency: %v", keyset, runErr)
		}
		accumulateTimingStability(
			measurement.Records, contract.Decision.Threshold,
			contract.Decision.MarginFloor, contract.Decision.SafetyFactor,
			timingFlips, timingViolations,
		)
		keysets = append(keysets, keyedResult{Keyset: keyset, Measurement: measurement})
	}
	if timingFlips["direct"]+timingFlips["finite_fastest_safe"]+
		timingViolations["direct"]+timingViolations["finite_fastest_safe"] > 0 {
		status = "DIAGNOSTIC_TIMING_NON_STABLE"
	}
	result["status"] = status
	result["safe_to_safe_eligible"] = status == "SAFE_TO_SAFE_ELIGIBLE"
	result["timing_decision_flips"] = timingFlips
	result["timing_reserve_policy_violations"] = timingViolations
	result["direct_candidate"] = selected
	result["finite_fastest_safe_candidate"] = finite.FastestSafe
	result["keysets"] = keysets
	writeAtomic(*out, result)
	fmt.Printf("paired latency status=%s keysets=%d output=%s\n", status, len(keysets), *out)
}

func boolInt(value bool) int {
	if value {
		return 1
	}
	return 0
}

func accumulateTimingStability(
	records []ckksbackend.PairedTabularLatencyRecord,
	threshold, marginFloor, utilizationCap float64,
	flips, violations map[string]int,
) {
	for _, record := range records {
		flips[record.ArmID] += boolInt(record.DecisionFlip)
		margin := math.Abs(record.PlainY - threshold)
		if margin > marginFloor && record.YError >= utilizationCap*margin {
			violations[record.ArmID]++
		}
	}
}

func readJSON(path string, target any) {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		fatalf("parse %s: %v", path, err)
	}
}

func writeAtomic(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatalf("marshal: %v", err)
	}
	data = append(data, '\n')
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	if err := os.WriteFile(path+".tmp", data, 0o644); err != nil {
		fatalf("write: %v", err)
	}
	if err := os.Rename(path+".tmp", path); err != nil {
		fatalf("publish: %v", err)
	}
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-tabular-paired-latency: "+format+"\n", args...)
	os.Exit(1)
}
