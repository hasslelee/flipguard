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

const schema = "flipguard_model_family_expansion_v17_tabular_case_v1"

type exhaustiveResult struct {
	SchemaVersion          string                            `json:"schema_version"`
	GeneratorID            string                            `json:"generator_id"`
	FormalDenominator      int                               `json:"formal_denominator"`
	Entries                []ckksplanner.TabularTrialResult  `json:"entries"`
	Safe                   int                               `json:"safe"`
	Rejected               int                               `json:"rejected"`
	Failed                 int                               `json:"failed"`
	FastestSafe            *ckksplanner.SynthesizedCandidate `json:"fastest_safe,omitempty"`
	FastestSafeMeanTotalMS float64                           `json:"fastest_safe_mean_total_ms,omitempty"`
}

type legacyExecutionEntry struct {
	Static ckksplanner.V17LegacyFiniteEntry `json:"static"`
	Trial  *ckksplanner.TabularTrialResult  `json:"trial,omitempty"`
}

type legacyResult struct {
	SchemaVersion        string                            `json:"schema_version"`
	GeneratorID          string                            `json:"generator_id"`
	Contract             ckksplanner.WorkloadContract      `json:"contract"`
	ContractDigest       string                            `json:"contract_digest"`
	FormalRows           int                               `json:"formal_rows"`
	Entries              []legacyExecutionEntry            `json:"entries"`
	Executed             int                               `json:"executed"`
	Safe                 int                               `json:"safe"`
	Rejected             int                               `json:"rejected"`
	Failed               int                               `json:"failed"`
	PlanUnsupported      int                               `json:"plan_unsupported"`
	LatencyOnlyCandidate *ckksplanner.SynthesizedCandidate `json:"latency_only_candidate,omitempty"`
	LatencyOnlyStatus    certify.CandidateStatus           `json:"latency_only_gate_status,omitempty"`
	LatencyOnlyMeanMS    float64                           `json:"latency_only_mean_total_ms,omitempty"`
	FixedDefault         ckksplanner.V17LegacyFiniteEntry  `json:"fixed_default"`
}

type summary struct {
	SchemaVersion                        string                            `json:"schema_version"`
	DatasetID                            string                            `json:"dataset_id"`
	ModelID                              string                            `json:"model_id"`
	SplitID                              string                            `json:"split_id"`
	DirectOutcome                        string                            `json:"direct_outcome"`
	DirectTrials                         int                               `json:"direct_trials"`
	DirectRepairs                        int                               `json:"direct_repairs"`
	DirectKeyRuns                        int                               `json:"direct_key_runs"`
	DirectEncryptedSampleEvaluations     int                               `json:"direct_encrypted_sample_evaluations"`
	DirectSelected                       *ckksplanner.SynthesizedCandidate `json:"direct_selected,omitempty"`
	ExhaustiveDenominator                int                               `json:"exhaustive_denominator"`
	ExhaustiveSafe                       int                               `json:"exhaustive_safe"`
	ExhaustiveKeyRuns                    int                               `json:"exhaustive_key_runs"`
	ExhaustiveEncryptedSampleEvaluations int                               `json:"exhaustive_encrypted_sample_evaluations"`
	FastestSafe                          *ckksplanner.SynthesizedCandidate `json:"fastest_safe,omitempty"`
	DirectIndependentStatus              certify.CandidateStatus           `json:"direct_independent_status,omitempty"`
	DirectIndependentFlips               int                               `json:"direct_independent_flips"`
	DirectIndependentViolations          int                               `json:"direct_independent_violations"`
	DirectSelectionKeyDisagreements      int                               `json:"direct_selection_repeated_key_decision_disagreements"`
	DirectIndependentKeyDisagreements    int                               `json:"direct_independent_repeated_key_decision_disagreements"`
	FastestIndependentStatus             certify.CandidateStatus           `json:"fastest_safe_independent_status,omitempty"`
	FastestIndependentFlips              int                               `json:"fastest_safe_independent_flips"`
	FastestIndependentViolations         int                               `json:"fastest_safe_independent_violations"`
	FastestIndependentKeyDisagreements   int                               `json:"fastest_safe_independent_repeated_key_decision_disagreements"`
	FalseNoSafe                          bool                              `json:"false_no_safe"`
	LatencyRegret                        float64                           `json:"latency_regret,omitempty"`
	DirectSelectedSafeRank               int                               `json:"direct_selected_safe_rank,omitempty"`
	DirectSelectedInFiniteSet            bool                              `json:"direct_selected_in_finite_set"`
	SelectionWallClockMS                 float64                           `json:"selection_wall_clock_ms"`
	ExhaustiveWallClockMS                float64                           `json:"exhaustive_wall_clock_ms"`
	IndependentWallClockMS               float64                           `json:"independent_wall_clock_ms"`
	LegacyFiniteRows                     int                               `json:"legacy_finite_rows"`
	LegacyFiniteExecuted                 int                               `json:"legacy_finite_executed"`
	LegacyFiniteSafe                     int                               `json:"legacy_finite_safe"`
	LegacyFiniteRejected                 int                               `json:"legacy_finite_rejected"`
	LegacyFiniteFailed                   int                               `json:"legacy_finite_failed"`
	LegacyFinitePlanUnsupported          int                               `json:"legacy_finite_plan_unsupported"`
	LatencyOnlyCandidate                 *ckksplanner.SynthesizedCandidate `json:"latency_only_candidate,omitempty"`
	LatencyOnlyGateStatus                certify.CandidateStatus           `json:"latency_only_gate_status,omitempty"`
	FixedDefaultStatus                   string                            `json:"fixed_default_status"`
	LegacyFiniteWallClockMS              float64                           `json:"legacy_finite_wall_clock_ms"`
}

type stageTiming struct {
	SelectionMS   float64 `json:"selection_wall_clock_ms"`
	ExhaustiveMS  float64 `json:"exhaustive_wall_clock_ms"`
	IndependentMS float64 `json:"independent_wall_clock_ms"`
	LegacyMS      float64 `json:"legacy_finite_wall_clock_ms"`
}

func main() {
	modelPath := flag.String("model", "", "trained model artifact")
	selectionPath := flag.String("selection", "", "configuration-selection feature CSV")
	independentPath := flag.String("independent", "", "independent-evaluation feature CSV")
	datasetID := flag.String("dataset", "", "dataset identity")
	modelID := flag.String("model-id", "", "model identity")
	splitID := flag.String("split-id", "", "outer-fold and training-seed identity")
	outRoot := flag.String("out-root", "", "case output directory")
	stopAfter := flag.String("stop-after", "", "test-only controlled interruption point: selection")
	flag.Parse()
	if *modelPath == "" || *selectionPath == "" || *independentPath == "" || *datasetID == "" || *modelID == "" || *splitID == "" || *outRoot == "" {
		fatalf("all flags are required")
	}
	if _, err := os.Stat(filepath.Join(*outRoot, "case_summary.json")); err == nil {
		fmt.Printf("case already complete: %s\n", *outRoot)
		return
	}
	if err := os.MkdirAll(*outRoot, 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	selectionPrepared := filepath.Join(*outRoot, "configuration_selection.prepared.csv")
	independentPrepared := filepath.Join(*outRoot, "independent_evaluation.prepared.csv")
	ensurePrepared(*modelPath, *selectionPath, selectionPrepared)
	selectionContract := buildContract(*modelPath, *selectionPath, selectionPrepared, *datasetID, *modelID, *splitID+"/configuration_selection")

	selectionFile := filepath.Join(*outRoot, "selection.json")
	timingFile := filepath.Join(*outRoot, "stage_timing.json")
	var timings stageTiming
	load(timingFile, &timings)
	var direct ckksplanner.AdaptiveAutotuneResult
	if !load(selectionFile, &direct) {
		started := time.Now()
		plan, err := ckksplanner.Synthesize(selectionContract, ckksplanner.DefaultPrimarySynthesisPolicy())
		if err != nil {
			fatalf("direct synthesis: %v", err)
		}
		direct, err = ckksplanner.RunAdaptiveTabularAutotuneWithOptions(
			plan,
			ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true},
		)
		if err != nil {
			fatalf("direct selection: %v", err)
		}
		writeAtomic(selectionFile, direct)
		timings.SelectionMS = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingFile, timings)
	}
	if *stopAfter == "selection" {
		fmt.Printf("controlled interruption after durable selection checkpoint: %s\n", selectionFile)
		os.Exit(75)
	} else if *stopAfter != "" {
		fatalf("unsupported --stop-after value %q", *stopAfter)
	}

	exhaustiveFile := filepath.Join(*outRoot, "exhaustive.json")
	var exhaustive exhaustiveResult
	if !load(exhaustiveFile, &exhaustive) {
		started := time.Now()
		_, candidates, err := ckksplanner.BuildV17DepthCompleteFiniteSet(selectionContract)
		if err != nil {
			fatalf("build depth-complete finite set: %v", err)
		}
		exhaustive = exhaustiveResult{SchemaVersion: schema, GeneratorID: ckksplanner.V17DepthCompleteCandidateGeneratorID, FormalDenominator: len(candidates), Entries: make([]ckksplanner.TabularTrialResult, 0, len(candidates))}
		for index, candidate := range candidates {
			trialPath := filepath.Join(*outRoot, "exhaustive_candidates", fmt.Sprintf("candidate_%02d_%s", index+1, candidate.ID), "trial.json")
			var trial ckksplanner.TabularTrialResult
			if !load(trialPath, &trial) {
				if err := os.MkdirAll(filepath.Dir(trialPath), 0o755); err != nil {
					fatalf("create exhaustive candidate directory: %v", err)
				}
				trial, err = ckksplanner.ExecuteTabularCandidateWithOptions(
					selectionContract,
					candidate,
					index+1,
					ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true},
				)
				if err != nil {
					fatalf("exhaustive candidate %d: %v", index+1, err)
				}
				writeAtomic(trialPath, trial)
			}
			exhaustive.Entries = append(exhaustive.Entries, trial)
			switch trial.Status {
			case certify.StatusSafe:
				exhaustive.Safe++
			case certify.StatusRejected:
				exhaustive.Rejected++
			default:
				exhaustive.Failed++
			}
		}
		for _, trial := range exhaustive.Entries {
			if trial.Status == certify.StatusSafe &&
				(exhaustive.FastestSafe == nil || trial.MeanTotalMS < exhaustive.FastestSafeMeanTotalMS) {
				candidate := trial.Candidate
				exhaustive.FastestSafe = &candidate
				exhaustive.FastestSafeMeanTotalMS = trial.MeanTotalMS
			}
		}
		writeAtomic(exhaustiveFile, exhaustive)
		timings.ExhaustiveMS = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingFile, timings)
	}

	legacyFile := filepath.Join(*outRoot, "legacy_finite.json")
	var legacy legacyResult
	if !load(legacyFile, &legacy) {
		started := time.Now()
		legacyContract := buildContractWithPaths(
			*modelPath, *selectionPath, selectionPrepared, *datasetID, *modelID,
			*splitID+"/configuration_selection/legacy_B2",
			[]tuner.ExecutionPath{tuner.PathRescale, tuner.PathNonRescale},
		)
		entries, err := ckksplanner.BuildV17LegacyFiniteSet(legacyContract)
		if err != nil {
			fatalf("build legacy finite set: %v", err)
		}
		fixedDefault, err := ckksplanner.BuildV17FixedDefaultBaseline(legacyContract)
		if err != nil {
			fatalf("build fixed-default baseline: %v", err)
		}
		legacyDigest, err := ckksplanner.WorkloadContractDigest(legacyContract)
		if err != nil {
			fatalf("digest legacy finite-set contract: %v", err)
		}
		legacy = legacyResult{
			SchemaVersion: schema, GeneratorID: ckksplanner.V17LegacyFiniteSetID,
			Contract: legacyContract, ContractDigest: legacyDigest,
			FormalRows: len(entries), Entries: make([]legacyExecutionEntry, 0, len(entries)),
			FixedDefault: fixedDefault,
		}
		for index, entry := range entries {
			output := legacyExecutionEntry{Static: entry}
			if entry.EncryptedExecutionRequired {
				trialPath := filepath.Join(*outRoot, "legacy_candidates", fmt.Sprintf("candidate_%02d_%s", index+1, entry.Candidate.ID), "trial.json")
				var trial ckksplanner.TabularTrialResult
				if !load(trialPath, &trial) {
					if err := os.MkdirAll(filepath.Dir(trialPath), 0o755); err != nil {
						fatalf("create legacy candidate directory: %v", err)
					}
					trial, err = ckksplanner.ExecuteTabularCandidateWithOptions(
						legacyContract,
						entry.Candidate,
						index+1,
						ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true},
					)
					if err != nil {
						fatalf("legacy candidate %d: %v", index+1, err)
					}
					writeAtomic(trialPath, trial)
				}
				output.Trial = &trial
				legacy.Executed++
				switch trial.Status {
				case certify.StatusSafe:
					legacy.Safe++
				case certify.StatusRejected:
					legacy.Rejected++
				default:
					legacy.Failed++
				}
				if trial.SuccessRuns == trial.KeyRepeatsRequested &&
					trial.KeyRepeatsCompleted == trial.KeyRepeatsRequested &&
					(legacy.LatencyOnlyCandidate == nil || trial.MeanTotalMS < legacy.LatencyOnlyMeanMS) {
					candidate := entry.Candidate
					legacy.LatencyOnlyCandidate = &candidate
					legacy.LatencyOnlyStatus = trial.Status
					legacy.LatencyOnlyMeanMS = trial.MeanTotalMS
				}
			} else {
				legacy.PlanUnsupported++
			}
			legacy.Entries = append(legacy.Entries, output)
		}
		writeAtomic(legacyFile, legacy)
		timings.LegacyMS = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingFile, timings)
	}

	ensurePrepared(*modelPath, *independentPath, independentPrepared)
	independentContract := buildContract(*modelPath, *independentPath, independentPrepared, *datasetID, *modelID, *splitID+"/independent_evaluation")
	var directAudit ckksplanner.TabularTrialResult
	independentStarted := time.Now()
	independentExecuted := false
	if direct.Selected != nil {
		path := filepath.Join(*outRoot, "direct_independent_evaluation.json")
		if !load(path, &directAudit) {
			independentExecuted = true
			var err error
			directAudit, err = ckksplanner.ExecuteTabularCandidateWithOptions(
				independentContract,
				*direct.Selected,
				1,
				ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true},
			)
			if err != nil {
				fatalf("direct independent evaluation: %v", err)
			}
			writeAtomic(path, directAudit)
		}
	}
	var fastestAudit ckksplanner.TabularTrialResult
	if exhaustive.FastestSafe != nil {
		path := filepath.Join(*outRoot, "fastest_safe_independent_evaluation.json")
		if !load(path, &fastestAudit) {
			independentExecuted = true
			var err error
			fastestAudit, err = ckksplanner.ExecuteTabularCandidateWithOptions(
				independentContract,
				*exhaustive.FastestSafe,
				1,
				ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true},
			)
			if err != nil {
				fatalf("fastest-SAFE independent evaluation: %v", err)
			}
			writeAtomic(path, fastestAudit)
		}
	}
	if independentExecuted {
		timings.IndependentMS = float64(time.Since(independentStarted).Microseconds()) / 1000
		writeAtomic(timingFile, timings)
	}
	directSamples, exhaustiveKeys, exhaustiveSamples := 0, 0, 0
	for _, trial := range direct.Trials {
		directSamples += trial.KeyRepeatsCompleted * selectionContract.Decision.ValidationSamples
	}
	for _, trial := range exhaustive.Entries {
		exhaustiveKeys += trial.KeyRepeatsCompleted
		exhaustiveSamples += trial.KeyRepeatsCompleted * selectionContract.Decision.ValidationSamples
	}
	selectionDisagreements := selectedTrialKeyDisagreements(direct)
	directAuditDisagreements := trialKeyDisagreements(directAudit)
	fastestAuditDisagreements := trialKeyDisagreements(fastestAudit)
	result := summary{SchemaVersion: schema, DatasetID: *datasetID, ModelID: *modelID, SplitID: *splitID, DirectOutcome: direct.Outcome, DirectTrials: direct.TrialsUsed, DirectRepairs: max(0, direct.TrialsUsed-1), DirectKeyRuns: direct.EncryptedKeyRuns, DirectEncryptedSampleEvaluations: directSamples, DirectSelected: direct.Selected, ExhaustiveDenominator: exhaustive.FormalDenominator, ExhaustiveSafe: exhaustive.Safe, ExhaustiveKeyRuns: exhaustiveKeys, ExhaustiveEncryptedSampleEvaluations: exhaustiveSamples, FastestSafe: exhaustive.FastestSafe, DirectIndependentStatus: directAudit.Status, DirectIndependentFlips: directAudit.DecisionFlips, DirectIndependentViolations: directAudit.ErrorViolations, DirectSelectionKeyDisagreements: selectionDisagreements, DirectIndependentKeyDisagreements: directAuditDisagreements, FastestIndependentStatus: fastestAudit.Status, FastestIndependentFlips: fastestAudit.DecisionFlips, FastestIndependentViolations: fastestAudit.ErrorViolations, FastestIndependentKeyDisagreements: fastestAuditDisagreements, FalseNoSafe: direct.Outcome == ckksplanner.AdaptiveOutcomeNoSafe && exhaustive.Safe > 0, SelectionWallClockMS: timings.SelectionMS, ExhaustiveWallClockMS: timings.ExhaustiveMS, IndependentWallClockMS: timings.IndependentMS, LegacyFiniteRows: legacy.FormalRows, LegacyFiniteExecuted: legacy.Executed, LegacyFiniteSafe: legacy.Safe, LegacyFiniteRejected: legacy.Rejected, LegacyFiniteFailed: legacy.Failed, LegacyFinitePlanUnsupported: legacy.PlanUnsupported, LatencyOnlyCandidate: legacy.LatencyOnlyCandidate, LatencyOnlyGateStatus: legacy.LatencyOnlyStatus, FixedDefaultStatus: legacy.FixedDefault.StaticStatus, LegacyFiniteWallClockMS: timings.LegacyMS}
	if direct.Selected != nil && exhaustive.FastestSafeMeanTotalMS > 0 {
		for _, trial := range direct.Trials {
			if trial.Status == certify.StatusSafe {
				result.LatencyRegret = (trial.MeanTotalMS - exhaustive.FastestSafeMeanTotalMS) / exhaustive.FastestSafeMeanTotalMS
				result.DirectSelectedSafeRank = 1
				for _, finiteTrial := range exhaustive.Entries {
					if finiteTrial.Candidate.ID == direct.Selected.ID {
						result.DirectSelectedInFiniteSet = true
					}
					if finiteTrial.Candidate.ID != direct.Selected.ID && finiteTrial.Status == certify.StatusSafe && finiteTrial.MeanTotalMS < trial.MeanTotalMS {
						result.DirectSelectedSafeRank++
					}
				}
				break
			}
		}
	}
	writeAtomic(filepath.Join(*outRoot, "case_summary.json"), result)
	fmt.Printf("case=%s/%s/%s direct=%s trials=%d exhaustive=%d safe=%d audit=%s\n", *datasetID, *modelID, *splitID, result.DirectOutcome, result.DirectTrials, result.ExhaustiveDenominator, result.ExhaustiveSafe, result.DirectIndependentStatus)
}

func selectedTrialKeyDisagreements(result ckksplanner.AdaptiveAutotuneResult) int {
	if result.Selected == nil {
		return 0
	}
	for _, trial := range result.Trials {
		if trial.Candidate.ID == result.Selected.ID {
			return trialKeyDisagreements(trial)
		}
	}
	return 0
}

func trialKeyDisagreements(trial ckksplanner.TabularTrialResult) int {
	if len(trial.SampleLedger) == 0 {
		return 0
	}
	count, err := ckksplanner.CountTabularRepeatedKeyDecisionDisagreements(trial.SampleLedger)
	if err != nil {
		fatalf("count repeated-key decision disagreements: %v", err)
	}
	return count
}

func ensurePrepared(model, source, target string) {
	if _, err := os.Stat(target); err == nil {
		return
	}
	_, err := ckksplanner.MaterializeTabularValidationWithOptions(model, source, target, ckksplanner.TabularMaterializationOptions{DataSpace: ckksplanner.TabularDataSpaceRaw})
	if err != nil {
		fatalf("materialize %s: %v", source, err)
	}
}

func buildContract(model, source, prepared, dataset, modelID, split string) ckksplanner.WorkloadContract {
	return buildContractWithPaths(model, source, prepared, dataset, modelID, split, []tuner.ExecutionPath{tuner.PathRescale})
}

func buildContractWithPaths(model, source, prepared, dataset, modelID, split string, paths []tuner.ExecutionPath) ckksplanner.WorkloadContract {
	options := ckksplanner.DefaultPrimaryTabularContractOptions()
	options.ModelPath, options.SourceDataPath, options.ValidationPath = model, source, prepared
	options.SplitID = split
	options.AllowedPaths = append([]tuner.ExecutionPath(nil), paths...)
	contract, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		fatalf("build contract: %v", err)
	}
	if contract.DatasetID != dataset || contract.ModelID != modelID {
		fatalf("model identity mismatch: got %s/%s expected %s/%s", contract.DatasetID, contract.ModelID, dataset, modelID)
	}
	return contract
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
		fatalf("marshal %s: %v", path, err)
	}
	data = append(data, '\n')
	temp := path + ".tmp"
	if err := os.WriteFile(temp, data, 0o644); err != nil {
		fatalf("write %s: %v", temp, err)
	}
	if err := os.Rename(temp, path); err != nil {
		fatalf("publish %s: %v", path, err)
	}
}

func fatalf(format string, args ...any) { fmt.Fprintf(os.Stderr, format+"\n", args...); os.Exit(1) }
