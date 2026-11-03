// This command is orchestration only. All synthesis, repair, security,
// certification, materialization and HE routines are unmodified source copies.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

type finiteResult struct {
	GeneratorID       string                            `json:"generator_id"`
	FormalDenominator int                               `json:"formal_denominator"`
	Entries           []ckksplanner.TabularTrialResult  `json:"entries"`
	FastestSafe       *ckksplanner.SynthesizedCandidate `json:"fastest_safe,omitempty"`
	FastestExecutable *ckksplanner.SynthesizedCandidate `json:"fastest_executable,omitempty"`
	MinimumError      *ckksplanner.SynthesizedCandidate `json:"minimum_error,omitempty"`
}
type role struct {
	Name      string                            `json:"role"`
	Candidate *ckksplanner.SynthesizedCandidate `json:"candidate"`
}

func save(path string, v any) {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		panic(err)
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		panic(err)
	}
	if err = os.WriteFile(path+".tmp", append(b, '\n'), 0644); err != nil {
		panic(err)
	}
	if err = os.Rename(path+".tmp", path); err != nil {
		panic(err)
	}
}
func contract(model, raw, prepared, split string) ckksplanner.WorkloadContract {
	if _, err := ckksplanner.MaterializeTabularValidationWithOptions(model, raw, prepared, ckksplanner.TabularMaterializationOptions{DataSpace: ckksplanner.TabularDataSpaceRaw}); err != nil {
		panic(err)
	}
	options := ckksplanner.DefaultPrimaryTabularContractOptions()
	options.ModelPath, options.SourceDataPath, options.ValidationPath = model, raw, prepared
	options.SplitID = split
	options.AllowedPaths = []tuner.ExecutionPath{tuner.PathRescale}
	c, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		panic(err)
	}
	return c
}
func elapsed(start time.Time) float64 { return float64(time.Since(start).Microseconds()) / 1000 }
func executable(t ckksplanner.TabularTrialResult) bool {
	return t.SuccessRuns == 3 && t.KeyRepeatsCompleted == 3 && t.KeyRepeatsRequested == 3
}
func main() {
	model := flag.String("model", "", "frozen model")
	selection := flag.String("selection", "", "raw selection inputs")
	independent := flag.String("independent", "", "raw separate inputs; read only after selections")
	smoke := flag.String("smoke", "", "two raw development rows for plumbing mode")
	output := flag.String("out-root", "", "fresh output root")
	mode := flag.String("mode", "run", "preflight or run")
	flag.Parse()
	if *model == "" || *selection == "" || *output == "" {
		panic("model, selection, out-root required")
	}
	if _, err := os.Stat(*output); !os.IsNotExist(err) {
		panic("output already exists or cannot be inspected")
	}
	if err := os.MkdirAll(*output, 0755); err != nil {
		panic(err)
	}
	stage := "materialization"
	defer func() {
		if r := recover(); r != nil {
			save(filepath.Join(*output, "EXECUTION_FAILURE.json"), map[string]any{"stage": stage, "error": fmt.Sprint(r), "utc": time.Now().UTC()})
			fmt.Fprintln(os.Stderr, r)
			os.Exit(1)
		}
	}()
	times := map[string]float64{}
	start := time.Now()
	c := contract(*model, *selection, filepath.Join(*output, "configuration_selection.prepared.csv"), "split0_seed0/configuration_selection")
	times["selection_materialization_contract_ms"] = elapsed(start)
	save(filepath.Join(*output, "selection_contract.json"), c)
	stage = "synthesis"
	start = time.Now()
	plan, err := ckksplanner.Synthesize(c, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		panic(err)
	}
	times["synthesis_ms"] = elapsed(start)
	save(filepath.Join(*output, "initial_plan.json"), plan)
	if *mode == "preflight" {
		_, finite, err := ckksplanner.BuildV17DepthCompleteFiniteSet(c)
		if err != nil {
			panic(err)
		}
		save(filepath.Join(*output, "finite_static.json"), finite)
		if *smoke == "" {
			panic("preflight needs smoke rows")
		}
		sc := contract(*model, *smoke, filepath.Join(*output, "smoke.prepared.csv"), "split0_seed0/development_plumbing")
		if len(plan.InitialCandidates) > 0 {
			stage = "plumbing_ckks"
			trial, err := ckksplanner.ExecuteTabularCandidateWithOptions(sc, plan.InitialCandidates[0], 1, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
			if err != nil {
				panic(err)
			}
			save(filepath.Join(*output, "smoke_trial.json"), trial)
		}
		save(filepath.Join(*output, "COMPLETED.json"), map[string]any{"mode": *mode, "scientific_rejection_is_not_exclusion": true, "utc": time.Now().UTC()})
		return
	}
	if *mode != "run" || *independent == "" {
		panic("invalid mode or missing independent input")
	}
	stage = "bounded_selection"
	start = time.Now()
	direct, err := ckksplanner.RunAdaptiveTabularAutotuneWithOptions(plan, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
	if err != nil {
		panic(err)
	}
	times["bounded_selection_ms"] = elapsed(start)
	times["direct_selection_total_ms"] = times["synthesis_ms"] + times["bounded_selection_ms"]
	save(filepath.Join(*output, "selection.json"), direct)
	save(filepath.Join(*output, "stage_timing.json"), times)
	fmt.Printf("selection %s trials=%d\n", direct.Outcome, direct.TrialsUsed)
	stage = "finite_reference"
	start = time.Now()
	_, candidates, err := ckksplanner.BuildV17DepthCompleteFiniteSet(c)
	if err != nil {
		panic(err)
	}
	finite := finiteResult{GeneratorID: ckksplanner.V17DepthCompleteCandidateGeneratorID, FormalDenominator: len(candidates), Entries: make([]ckksplanner.TabularTrialResult, 0, len(candidates))}
	bestSafe, bestExec, bestError := 0.0, 0.0, 0.0
	for index, candidate := range candidates {
		ct := time.Now()
		trial, err := ckksplanner.ExecuteTabularCandidateWithOptions(c, candidate, index+1, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
		if err != nil {
			panic(err)
		}
		save(filepath.Join(*output, "finite_candidates", fmt.Sprintf("%02d.json", index+1)), map[string]any{"trial": trial, "wall_ms": elapsed(ct)})
		finite.Entries = append(finite.Entries, trial)
		if trial.Status == certify.StatusSafe && (finite.FastestSafe == nil || trial.MeanTotalMS < bestSafe) {
			cp := candidate
			finite.FastestSafe = &cp
			bestSafe = trial.MeanTotalMS
		}
		if executable(trial) {
			if finite.FastestExecutable == nil || trial.MeanTotalMS < bestExec {
				cp := candidate
				finite.FastestExecutable = &cp
				bestExec = trial.MeanTotalMS
			}
			if finite.MinimumError == nil || trial.MaxObservedError < bestError {
				cp := candidate
				finite.MinimumError = &cp
				bestError = trial.MaxObservedError
			}
		}
		fmt.Printf("finite %d/%d %s\n", index+1, len(candidates), trial.Status)
	}
	times["finite_search_total_ms"] = elapsed(start)
	save(filepath.Join(*output, "exhaustive.json"), finite)
	roles := []role{{"direct", direct.Selected}, {"finite_fastest_safe", finite.FastestSafe}, {"initial_criteria_off", nil}, {"finite_fastest_executable", finite.FastestExecutable}}
	if len(direct.Trials) > 0 && executable(direct.Trials[0]) {
		cp := direct.Trials[0].Candidate
		roles[2].Candidate = &cp
	}
	save(filepath.Join(*output, "FROZEN_SELECTION_ROLES.json"), roles)
	save(filepath.Join(*output, "stage_timing.json"), times)
	// No materialization or score inspection of the independent inputs precedes this point.
	stage = "independent_evaluation"
	start = time.Now()
	ic := contract(*model, *independent, filepath.Join(*output, "independent_evaluation.prepared.csv"), "split0_seed0/independent_evaluation")
	save(filepath.Join(*output, "independent_contract.json"), ic)
	times["independent_materialization_contract_ms"] = elapsed(start)
	audits := map[string]ckksplanner.TabularTrialResult{}
	bindings := map[string]string{}
	for _, arm := range roles {
		if arm.Candidate == nil {
			bindings[arm.Name] = "NOT_SELECTED_OR_NOT_EXECUTABLE"
			continue
		}
		id := arm.Candidate.ID
		bindings[arm.Name] = id
		if _, ok := audits[id]; ok {
			continue
		}
		start = time.Now()
		trial, err := ckksplanner.ExecuteTabularCandidateWithOptions(ic, *arm.Candidate, 1, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
		if err != nil {
			panic(err)
		}
		audits[id] = trial
		save(filepath.Join(*output, "audit_candidates", id+".json"), map[string]any{"trial": trial, "wall_ms": elapsed(start)})
		fmt.Printf("audit %s %s flips=%d violations=%d\n", arm.Name, trial.Status, trial.DecisionFlips, trial.ErrorViolations)
	}
	save(filepath.Join(*output, "audit_role_bindings.json"), bindings)
	stage = "paired_latency"
	arms := []ckksbackend.PairedTabularLatencyArm{}
	for _, arm := range roles {
		if arm.Candidate != nil {
			profile, err := arm.Candidate.Profile()
			if err != nil {
				panic(err)
			}
			arms = append(arms, ckksbackend.PairedTabularLatencyArm{ID: arm.Name, Role: arm.Name, CandidateID: arm.Candidate.ID, Profile: profile, EvaluationMode: string(arm.Candidate.Path)})
		}
	}
	start = time.Now()
	if len(arms) >= 2 {
		for keyset := 1; keyset <= 3; keyset++ {
			measurement, err := ckksbackend.RunPairedTabularLatency(ckksbackend.PairedTabularLatencyConfig{ModelPath: *model, TestPath: filepath.Join(*output, "independent_evaluation.prepared.csv"), DatasetID: c.DatasetID, ModelID: c.ModelID, MaxRows: 20, WarmupRuns: 1, MeasureRuns: 6, Arms: arms})
			if err != nil {
				panic(err)
			}
			save(filepath.Join(*output, "paired_latency", fmt.Sprintf("keyset_%d.json", keyset)), map[string]any{"keyset": keyset, "measurement": measurement, "utc_completed": time.Now().UTC()})
			fmt.Printf("paired keyset=%d completed\n", keyset)
		}
	}
	times["paired_latency_wall_ms"] = elapsed(start)
	save(filepath.Join(*output, "stage_timing.json"), times)
	save(filepath.Join(*output, "COMPLETED.json"), map[string]any{"mode": *mode, "utc": time.Now().UTC(), "direct_outcome": direct.Outcome, "audit_unique_candidates": len(audits), "legacy_b2": "NOT_RUN_OUTSIDE_PRIMARY_FINITE_REFERENCE", "paired_arms": len(arms)})
}
