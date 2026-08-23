package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const schema = "flipguard_model_family_expansion_v17_packed_cnn_case_v1"

type exhaustiveResult struct {
	SchemaVersion          string                            `json:"schema_version"`
	GeneratorID            string                            `json:"generator_id"`
	FormalDenominator      int                               `json:"formal_denominator"`
	Entries                []ckksplanner.CNNLiteTrialResult  `json:"entries"`
	Safe                   int                               `json:"safe"`
	Rejected               int                               `json:"rejected"`
	Failed                 int                               `json:"failed"`
	FastestSafe            *ckksplanner.SynthesizedCandidate `json:"fastest_safe,omitempty"`
	FastestSafeMeanTotalMS float64                           `json:"fastest_safe_mean_total_ms,omitempty"`
}

func main() {
	model := flag.String("model", "", "frozen CNN-lite model")
	selection := flag.String("selection", "", "configuration-selection CSV")
	audit := flag.String("audit", "", "independent held-out CSV")
	source := flag.String("source", "", "byte-pinned MNIST source")
	manifest := flag.String("manifest", "", "frozen CNN-lite extraction manifest")
	out := flag.String("out-root", "", "case output root")
	stopRequest := flag.String("stop-request", "", "optional checkpoint request file checked after each finite candidate")
	flag.Parse()
	if *model == "" || *selection == "" || *audit == "" || *source == "" || *manifest == "" || *out == "" {
		fatalf("all flags are required")
	}
	if _, err := os.Stat(filepath.Join(*out, "case_summary.json")); err == nil {
		fmt.Printf("packed case already complete: %s\n", *out)
		return
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	options := ckksplanner.DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = *model
	options.ValidationPath = *selection
	options.SourcePath = *source
	options.SplitID = "v17_p6_packed_cnn_lite/configuration_selection"
	contract, err := ckksplanner.BuildPackedCNNLiteWorkloadContract(options)
	if err != nil {
		fatalf("build packed contract: %v", err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		fatalf("synthesize: %v", err)
	}
	selectionPath := filepath.Join(*out, "selection.json")
	timingPath := filepath.Join(*out, "stage_timing.json")
	timings := map[string]float64{}
	load(timingPath, &timings)
	var selected ckksplanner.AdaptiveCNNLiteAutotuneResult
	if !load(selectionPath, &selected) {
		started := time.Now()
		selected, err = ckksplanner.RunAdaptivePackedCNNLiteAutotune(plan)
		if err != nil {
			fatalf("selection: %v", err)
		}
		writeAtomic(selectionPath, selected)
		timings["selection_wall_clock_ms"] = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingPath, timings)
	}
	finitePath := filepath.Join(*out, "exhaustive.json")
	var finite exhaustiveResult
	if !load(finitePath, &finite) {
		started := time.Now()
		_, candidates, err := ckksplanner.BuildV17DepthCompleteFiniteSet(contract)
		if err != nil {
			fatalf("finite set: %v", err)
		}
		finite = exhaustiveResult{SchemaVersion: schema, GeneratorID: ckksplanner.V17DepthCompleteCandidateGeneratorID, FormalDenominator: len(candidates), Entries: make([]ckksplanner.CNNLiteTrialResult, 0, len(candidates))}
		for index, candidate := range candidates {
			trialPath := filepath.Join(*out, "exhaustive_candidates", fmt.Sprintf("candidate_%02d_%s", index+1, candidate.ID), "trial.json")
			var trial ckksplanner.CNNLiteTrialResult
			if !load(trialPath, &trial) {
				trial, err = ckksplanner.ExecutePackedCNNLiteCandidate(contract, candidate, index+1)
				if err != nil {
					fatalf("candidate %d: %v", index+1, err)
				}
				if err := os.MkdirAll(filepath.Dir(trialPath), 0o755); err != nil {
					fatalf("create finite candidate checkpoint: %v", err)
				}
				writeAtomic(trialPath, trial)
			}
			finite.Entries = append(finite.Entries, trial)
			switch trial.Status {
			case certify.StatusSafe:
				finite.Safe++
				if finite.FastestSafe == nil || trial.MeanTotalMS < finite.FastestSafeMeanTotalMS {
					copy := candidate
					finite.FastestSafe = &copy
					finite.FastestSafeMeanTotalMS = trial.MeanTotalMS
				}
			case certify.StatusRejected:
				finite.Rejected++
			default:
				finite.Failed++
			}
			if *stopRequest != "" {
				if _, err := os.Stat(*stopRequest); err == nil {
					fmt.Printf("checkpoint after packed candidate %s\n", candidate.ID)
					os.Exit(75)
				} else if !os.IsNotExist(err) {
					fatalf("inspect stop request: %v", err)
				}
			}
		}
		writeAtomic(finitePath, finite)
		timings["exhaustive_wall_clock_ms"] = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingPath, timings)
	}
	auditPath := filepath.Join(*out, "direct_independent_evaluation.json")
	var auditResult ckksplanner.CNNLiteLockedAuditResult
	independentStarted := time.Now()
	independentExecuted := false
	if selected.Selected != nil && !load(auditPath, &auditResult) {
		independentExecuted = true
		auditResult, err = ckksplanner.RunLockedCNNLiteAudit(ckksplanner.CNNLiteLockedAuditOptions{SelectionResultPath: selectionPath, AuditPath: *audit, SourcePath: *source, ManifestPath: *manifest, KeyRepeats: 3})
		if err != nil {
			fatalf("locked audit: %v", err)
		}
		writeAtomic(auditPath, auditResult)
	}
	fastestAuditPath := filepath.Join(*out, "fastest_safe_independent_evaluation.json")
	var fastestAudit ckksplanner.CNNLiteTrialResult
	if finite.FastestSafe != nil && !load(fastestAuditPath, &fastestAudit) {
		independentExecuted = true
		auditOptions := ckksplanner.DefaultPrimaryCNNLiteContractOptions()
		auditOptions.ModelPath = *model
		auditOptions.ValidationPath = *audit
		auditOptions.SourcePath = *source
		auditOptions.SplitID = "v17_p6_packed_cnn_lite/independent_evaluation"
		auditOptions.MaxEncryptedTrials = 1
		auditOptions.ValidationKeyRepeats = 3
		auditOptions.AllowedPaths = []tuner.ExecutionPath{finite.FastestSafe.Path}
		fastestContract, buildErr := ckksplanner.BuildPackedCNNLiteWorkloadContract(auditOptions)
		if buildErr != nil {
			fatalf("build fastest-SAFE independent contract: %v", buildErr)
		}
		if fastestContract.ModelArtifact.SHA256 != contract.ModelArtifact.SHA256 || fastestContract.SourceData == nil || contract.SourceData == nil || fastestContract.SourceData.SHA256 != contract.SourceData.SHA256 {
			fatalf("fastest-SAFE independent model/source identity mismatch")
		}
		fastestAudit, err = ckksplanner.ExecutePackedCNNLiteCandidate(fastestContract, *finite.FastestSafe, 1)
		if err != nil {
			fatalf("fastest-SAFE independent evaluation: %v", err)
		}
		writeAtomic(fastestAuditPath, fastestAudit)
	}
	if independentExecuted {
		timings["independent_wall_clock_ms"] = float64(time.Since(independentStarted).Microseconds()) / 1000
		writeAtomic(timingPath, timings)
	}
	regret := 0.0
	directRank := 0
	directInFinite := false
	if finite.FastestSafeMeanTotalMS > 0 {
		for _, trial := range selected.Trials {
			if trial.Status == certify.StatusSafe {
				regret = (trial.MeanTotalMS - finite.FastestSafeMeanTotalMS) / finite.FastestSafeMeanTotalMS
				directRank = 1
				for _, finiteTrial := range finite.Entries {
					if selected.Selected != nil && finiteTrial.Candidate.ID == selected.Selected.ID {
						directInFinite = true
					}
					if selected.Selected != nil && finiteTrial.Candidate.ID != selected.Selected.ID && finiteTrial.Status == certify.StatusSafe && finiteTrial.MeanTotalMS < trial.MeanTotalMS {
						directRank++
					}
				}
				break
			}
		}
	}
	exhaustiveKeyRuns, exhaustiveSamples := 0, 0
	for _, trial := range finite.Entries {
		exhaustiveKeyRuns += trial.KeyRepeatsCompleted
		exhaustiveSamples += trial.EncryptedSampleEvaluations
	}
	summary := map[string]any{
		"schema_version": schema, "dataset_id": contract.DatasetID, "model_id": "packed_cnn_lite_binary01_v17", "split_id": "v17_p6_packed_cnn_lite",
		"selection_outcome": selected.Outcome, "direct_trials": selected.TrialsUsed, "direct_repairs": max(0, selected.TrialsUsed-1),
		"direct_key_runs": selected.EncryptedKeyRuns, "direct_encrypted_sample_evaluations": selected.EncryptedSampleEvaluations,
		"selected": selected.Selected, "exhaustive_denominator": finite.FormalDenominator, "exhaustive_safe": finite.Safe,
		"exhaustive_key_runs": exhaustiveKeyRuns, "exhaustive_encrypted_sample_evaluations": exhaustiveSamples,
		"fastest_safe": finite.FastestSafe, "latency_regret": regret,
		"direct_selected_safe_rank": directRank, "direct_selected_in_finite_set": directInFinite,
		"independent_outcome": auditResult.Outcome, "independent_status": auditResult.AuditTrial.Status,
		"independent_flips": auditResult.AuditTrial.DecisionFlips, "independent_violations": auditResult.AuditTrial.ErrorViolations,
		"direct_selection_repeated_key_decision_disagreements":   cnnTrialKeyDisagreements(selectedTrial(selected)),
		"direct_independent_repeated_key_decision_disagreements": cnnTrialKeyDisagreements(auditResult.AuditTrial),
		"fastest_safe_independent_status":                        fastestAudit.Status, "fastest_safe_independent_flips": fastestAudit.DecisionFlips,
		"fastest_safe_independent_violations": fastestAudit.ErrorViolations, "retuning": auditResult.RetuningPerformed,
		"fastest_safe_independent_repeated_key_decision_disagreements": cnnTrialKeyDisagreements(fastestAudit),
		"false_no_safe":           selected.Outcome == ckksplanner.AdaptiveOutcomeNoSafe && finite.Safe > 0,
		"selection_wall_clock_ms": timings["selection_wall_clock_ms"], "exhaustive_wall_clock_ms": timings["exhaustive_wall_clock_ms"], "independent_wall_clock_ms": timings["independent_wall_clock_ms"],
	}
	writeAtomic(filepath.Join(*out, "case_summary.json"), summary)
	fmt.Printf("packed case direct=%s trials=%d exhaustive=%d safe=%d audit=%s\n", selected.Outcome, selected.TrialsUsed, finite.FormalDenominator, finite.Safe, auditResult.Outcome)
}

func selectedTrial(result ckksplanner.AdaptiveCNNLiteAutotuneResult) ckksplanner.CNNLiteTrialResult {
	if result.Selected == nil {
		return ckksplanner.CNNLiteTrialResult{}
	}
	for _, trial := range result.Trials {
		if trial.Candidate.ID == result.Selected.ID {
			return trial
		}
	}
	return ckksplanner.CNNLiteTrialResult{}
}

func cnnTrialKeyDisagreements(trial ckksplanner.CNNLiteTrialResult) int {
	decisions := make(map[string]map[bool]struct{})
	for _, row := range trial.SampleLedger {
		if decisions[row.SampleID] == nil {
			decisions[row.SampleID] = make(map[bool]struct{})
		}
		decisions[row.SampleID][row.CKKSDecision] = struct{}{}
	}
	count := 0
	for _, observed := range decisions {
		if len(observed) > 1 {
			count++
		}
	}
	return count
}

func load(path string, target any) bool {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return false
	}
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		fatalf("parse %s: %v", path, err)
	}
	return true
}
func writeAtomic(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatalf("marshal: %v", err)
	}
	data = append(data, '\n')
	temp := path + ".tmp"
	if err := os.WriteFile(temp, data, 0o644); err != nil {
		fatalf("write temp: %v", err)
	}
	if err := os.Rename(temp, path); err != nil {
		fatalf("publish: %v", err)
	}
}
func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-packed-cnn-case: "+format+"\n", args...)
	os.Exit(1)
}
