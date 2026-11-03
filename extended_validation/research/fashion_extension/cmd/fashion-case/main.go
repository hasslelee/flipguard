// Data and checkpoint orchestration around the unchanged multiclass policies.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"os"
	"path/filepath"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func load(p string, v any) { b, e := os.ReadFile(p); must(e); must(json.Unmarshal(b, v)) }
func save(p string, v any) {
	must(os.MkdirAll(filepath.Dir(p), 0755))
	f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
	must(e)
	defer f.Close()
	en := json.NewEncoder(f)
	en.SetIndent("", "  ")
	must(en.Encode(v))
	must(f.Sync())
}
func exists(p string) bool { _, e := os.Stat(p); return e == nil }
func execute(c ckksplanner.WorkloadContract, cand ckksplanner.SynthesizedCandidate, idx int, out string) ckksplanner.MulticlassTrialResult {
	var old []ckksplanner.MulticlassKeyRunEvidence
	for k := 1; k <= c.Deployment.ValidationKeyRepeats; k++ {
		p := filepath.Join(out, fmt.Sprintf("key_%d.json", k))
		if !exists(p) {
			break
		}
		var ev ckksplanner.MulticlassKeyRunEvidence
		load(p, &ev)
		old = append(old, ev)
	}
	t, e := ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(c, cand, idx, ckksplanner.MulticlassCandidateExecutionOptions{ExistingKeyRuns: old, OnKeyRun: func(ev ckksplanner.MulticlassKeyRunEvidence) error {
		save(filepath.Join(out, fmt.Sprintf("key_%d.json", ev.KeyRun)), ev)
		fmt.Printf("key_complete candidate=%s key=%d total_ms=%.3f\n", cand.ID, ev.KeyRun, ev.Summary.TotalMS)
		return nil
	}})
	must(e)
	return t
}
func main() {
	mode := flag.String("mode", "plan", "plan|direct|candidate|audit|timing")
	model := flag.String("model", "", "model")
	data := flag.String("data", "", "500 rows")
	source := flag.String("source", "", "source manifest")
	out := flag.String("out", "", "exclusive output directory")
	planFile := flag.String("plan", "", "frozen plan")
	candFile := flag.String("candidate", "", "frozen candidate")
	otherFile := flag.String("other", "", "timing comparator")
	keyset := flag.Int("keyset", 1, "keyset")
	flag.Parse()
	must(os.MkdirAll(*out, 0755))
	if exists(filepath.Join(*out, "result.json")) {
		panic("completed output exists")
	}
	stage := *mode
	started := time.Now()
	defer func() {
		if r := recover(); r != nil {
			p := filepath.Join(*out, fmt.Sprintf("failure_%d.json", time.Now().UnixNano()))
			save(p, map[string]any{"stage": stage, "error": fmt.Sprint(r), "utc": time.Now().UTC()})
			fmt.Fprintln(os.Stderr, r)
			os.Exit(1)
		}
	}()
	var plan ckksplanner.SynthesisPlan
	if *mode == "plan" {
		o := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
		o.ModelPath = *model
		o.ValidationPath = *data
		o.SourcePath = *source
		o.SplitID = "fashion_train/configuration_selection"
		o.ExpectedRole = "configuration_validation"
		c, scope, e := ckksplanner.BuildJournalMNISTMulticlassContract(o)
		must(e)
		plan, candidates, e := ckksplanner.BuildV17DepthCompleteFiniteSet(c)
		must(e)
		save(filepath.Join(*out, "plan.json"), plan)
		save(filepath.Join(*out, "scope.json"), scope)
		save(filepath.Join(*out, "candidates.json"), candidates)
		save(filepath.Join(*out, "result.json"), map[string]any{"seconds": time.Since(started).Seconds(), "candidate_count": len(candidates)})
		return
	}
	load(*planFile, &plan)
	if *mode == "direct" {
		// Same loop and first-SAFE/repair semantics as RunAdaptiveJournalMNISTMulticlassAutotune.
		result := ckksplanner.AdaptiveMulticlassAutotuneResult{SchemaVersion: ckksplanner.SynthesisPlanSchemaVersion, ExecutionAdapter: ckksbackend.JournalMNISTMulticlassExecutionAdapterV1, Plan: plan}
		cand := plan.InitialCandidates[0]
		for idx := 1; idx <= plan.Contract.Deployment.MaxEncryptedTrials; idx++ {
			trialRoot := filepath.Join(*out, fmt.Sprintf("trial_%d", idx))
			var trial ckksplanner.MulticlassTrialResult
			if exists(filepath.Join(trialRoot, "trial.json")) {
				load(filepath.Join(trialRoot, "trial.json"), &trial)
				if trial.Candidate.ID != cand.ID {
					panic("resume candidate mismatch")
				}
			} else {
				trial = execute(plan.Contract, cand, idx, trialRoot)
				save(filepath.Join(trialRoot, "trial.json"), trial)
			}
			result.Trials = append(result.Trials, trial)
			result.TrialsUsed = len(result.Trials)
			result.EncryptedKeyRuns += trial.KeyRepeatsCompleted
			result.EncryptedSampleEvaluations += trial.EncryptedSampleEvaluations
			if trial.Status == certify.StatusSafe {
				result.Outcome = ckksplanner.AdaptiveOutcomeSelected
				selected := cand
				result.Selected = &selected
				result.Reason = "first SAFE under unchanged multiclass policy"
				break
			}
			if idx == plan.Contract.Deployment.MaxEncryptedTrials || trial.FailureSignal == "" {
				break
			}
			next, e := ckksplanner.RepairCandidate(plan, cand, trial.FailureSignal, idx)
			if errors.Is(e, ckksplanner.ErrRepairExhausted) {
				break
			}
			must(e)
			cand = next
			result.Repairs++
		}
		if result.Selected == nil {
			result.Outcome = ckksplanner.AdaptiveOutcomeNoSafe
			result.Reason = "no SAFE within frozen budget"
		}
		save(filepath.Join(*out, "result.json"), result)
	} else {
		var cand ckksplanner.SynthesizedCandidate
		load(*candFile, &cand)
		switch *mode {
		case "candidate":
			t := execute(plan.Contract, cand, 1, *out)
			save(filepath.Join(*out, "result.json"), t)
		case "audit":
			o := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
			o.ModelPath = plan.Contract.ModelArtifact.Path
			o.SourcePath = plan.Contract.SourceData.Path
			o.ValidationPath = *data
			o.ExpectedRole = "locked_audit"
			o.SplitID = "fashion_test/locked_audit"
			c, _, e := ckksplanner.BuildJournalMNISTMulticlassContract(o)
			must(e)
			c.Calibration = plan.Contract.Calibration
			contractPath := filepath.Join(*out, "audit_contract.json")
			if exists(contractPath) {
				var previous ckksplanner.WorkloadContract
				load(contractPath, &previous)
				a, e := ckksplanner.WorkloadContractDigest(previous)
				must(e)
				b, e := ckksplanner.WorkloadContractDigest(c)
				must(e)
				if a != b {
					panic("audit resume contract mismatch")
				}
			} else {
				save(contractPath, c)
			}
			t := execute(c, cand, 1, *out)
			save(filepath.Join(*out, "result.json"), t)
		case "timing":
			var other ckksplanner.SynthesizedCandidate
			load(*otherFile, &other)
			p, e := cand.Profile()
			must(e)
			q, e := other.Profile()
			must(e)
			// Original V17 final-PDF batch runner: twenty deterministic sample slots.
			rows := make([]int, 20)
			for i := range rows {
				rows[i] = i * 499 / 19
			}
			cfg := ckksbackend.V17PrimaryPairedLatencyConfig{Kind: ckksbackend.V17PairedKindJournalMNIST, ModelPath: plan.Contract.ModelArtifact.Path, DataPath: *data, SelectedRowIDs: rows, Keyset: *keyset, WarmupRuns: 1, MeasurementRuns: 6, MarginFloor: 0.001, UtilizationCap: 0.5, Arms: []ckksbackend.V17PrimaryPairedLatencyArm{{ID: "proposed", Role: "direct", CandidateID: cand.ID, Profile: p}, {ID: "comparator", Role: "frozen_comparator", CandidateID: other.ID, Profile: q}}}
			f, e := os.OpenFile(filepath.Join(*out, "records.jsonl"), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
			must(e)
			defer f.Close()
			enc := json.NewEncoder(f)
			res, e := ckksbackend.RunV17PrimaryPairedLatencyKeyset(cfg, func(r ckksbackend.V17PrimaryPairedLatencyRecord) error {
				if e := enc.Encode(r); e != nil {
					return e
				}
				return f.Sync()
			})
			must(e)
			save(filepath.Join(*out, "result.json"), res)
		default:
			panic("invalid mode")
		}
	}
	save(filepath.Join(*out, "wall.json"), map[string]any{"stage": stage, "seconds": time.Since(started).Seconds(), "utc": time.Now().UTC()})
}
