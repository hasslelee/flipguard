package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const schema = "flipguard_model_family_expansion_v17_multiclass_seed_case_v1"

func main() {
	model := flag.String("model", "", "V17 trained multiclass model")
	validation := flag.String("validation", "", "frozen configuration-selection CSV")
	audit := flag.String("audit", "", "disjoint locked-audit CSV")
	source := flag.String("source", "", "byte-pinned MNIST source")
	seed := flag.Uint64("training-seed", 0, "predeclared model-training seed")
	out := flag.String("out-root", "", "result root")
	flag.Parse()
	if *model == "" || *validation == "" || *audit == "" || *source == "" || *out == "" {
		fatalf("all path flags are required")
	}
	finalPath := filepath.Join(*out, "case_summary.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("multiclass seed case already complete: %s\n", finalPath)
		return
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath, options.ValidationPath, options.SourcePath = *model, *validation, *source
	options.ExpectedRole = "configuration_validation"
	options.SplitID = fmt.Sprintf("v17_multiclass_training_seed_%d/configuration_selection", *seed)
	contract, _, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build selection contract: %v", err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		fatalf("synthesize: %v", err)
	}
	selectionPath := filepath.Join(*out, "selection.json")
	timingPath := filepath.Join(*out, "stage_timing.json")
	timings := map[string]float64{}
	load(timingPath, &timings)
	var selection ckksplanner.AdaptiveMulticlassAutotuneResult
	if !load(selectionPath, &selection) {
		started := time.Now()
		selection = ckksplanner.AdaptiveMulticlassAutotuneResult{SchemaVersion: ckksplanner.SynthesisPlanSchemaVersion, ExecutionAdapter: "mnist_multiclass_feature_ciphertext_batch_adapter_v1", Plan: plan, Trials: make([]ckksplanner.MulticlassTrialResult, 0, contract.Deployment.MaxEncryptedTrials)}
		candidate := plan.InitialCandidates[0]
		for trialIndex := 1; trialIndex <= contract.Deployment.MaxEncryptedTrials; trialIndex++ {
			trialRoot := filepath.Join(*out, fmt.Sprintf("trial_%02d_%s", trialIndex, candidate.ID))
			if err := os.MkdirAll(trialRoot, 0o755); err != nil {
				fatalf("create trial root: %v", err)
			}
			trialPath := filepath.Join(trialRoot, "trial.json")
			var trial ckksplanner.MulticlassTrialResult
			if !load(trialPath, &trial) {
				existing := loadKeyRuns(trialRoot, candidate.ID, contract.Deployment.ValidationKeyRepeats)
				trial, err = ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(contract, candidate, trialIndex, ckksplanner.MulticlassCandidateExecutionOptions{ExistingKeyRuns: existing, OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
					return writeExclusive(filepath.Join(trialRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence)
				}})
				if err != nil {
					fatalf("execute trial %d: %v", trialIndex, err)
				}
				writeAtomic(trialPath, trial)
			}
			selection.Trials = append(selection.Trials, trial)
			selection.TrialsUsed++
			selection.EncryptedKeyRuns += trial.KeyRepeatsCompleted
			selection.EncryptedSampleEvaluations += trial.EncryptedSampleEvaluations
			if trial.Status == certify.StatusSafe {
				copy := candidate
				selection.Outcome, selection.Selected = ckksplanner.AdaptiveOutcomeSelected, &copy
				selection.Reason = fmt.Sprintf("selected first SAFE candidate after %d trial(s)", selection.TrialsUsed)
				break
			}
			if trialIndex == contract.Deployment.MaxEncryptedTrials || trial.FailureSignal == "" {
				break
			}
			candidate, err = ckksplanner.RepairCandidate(plan, candidate, trial.FailureSignal, trialIndex)
			if err != nil {
				if errors.Is(err, ckksplanner.ErrRepairExhausted) {
					break
				}
				fatalf("repair: %v", err)
			}
			selection.Repairs++
		}
		if selection.Outcome == "" {
			selection.Outcome = ckksplanner.AdaptiveOutcomeNoSafe
			selection.Reason = fmt.Sprintf("no SAFE candidate within trial budget %d", contract.Deployment.MaxEncryptedTrials)
		}
		writeAtomic(selectionPath, selection)
		timings["selection_wall_clock_ms"] = float64(time.Since(started).Microseconds()) / 1000
		writeAtomic(timingPath, timings)
	}
	var auditResult ckksplanner.MulticlassLockedAuditResult
	if selection.Selected != nil {
		auditPath := filepath.Join(*out, "independent_evaluation.json")
		if !load(auditPath, &auditResult) {
			started := time.Now()
			auditRoot := filepath.Join(*out, "independent_key_runs")
			if err := os.MkdirAll(auditRoot, 0o755); err != nil {
				fatalf("create audit root: %v", err)
			}
			existing := loadKeyRuns(auditRoot, selection.Selected.ID, contract.Deployment.ValidationKeyRepeats)
			auditResult, err = ckksplanner.RunJournalMNISTMulticlassLockedAuditWithOptions(contract, *selection.Selected, *audit, fmt.Sprintf("v17_multiclass_training_seed_%d/locked_audit", *seed), ckksplanner.MulticlassCandidateExecutionOptions{ExistingKeyRuns: existing, OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
				return writeExclusive(filepath.Join(auditRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence)
			}})
			if err != nil {
				fatalf("independent evaluation: %v", err)
			}
			writeAtomic(auditPath, auditResult)
			timings["independent_wall_clock_ms"] = float64(time.Since(started).Microseconds()) / 1000
			writeAtomic(timingPath, timings)
		}
	}
	summary := map[string]any{"schema_version": schema, "dataset_id": contract.DatasetID, "model_id": contract.ModelID, "training_seed": *seed, "direct_outcome": selection.Outcome, "direct_trials": selection.TrialsUsed, "direct_repairs": selection.Repairs, "direct_key_runs": selection.EncryptedKeyRuns, "direct_encrypted_sample_evaluations": selection.EncryptedSampleEvaluations, "direct_selected": selection.Selected, "independent_status": auditResult.Trial.Status, "independent_flips": auditResult.Trial.Aggregation.ArgmaxFlips, "independent_violations": auditResult.Trial.Aggregation.ReserveViolations, "retuning_count": auditResult.RetuningCount, "selection_wall_clock_ms": timings["selection_wall_clock_ms"], "independent_wall_clock_ms": timings["independent_wall_clock_ms"]}
	writeAtomic(finalPath, summary)
	fmt.Printf("model=%s seed=%d outcome=%s trials=%d independent=%s\n", contract.ModelID, *seed, selection.Outcome, selection.TrialsUsed, auditResult.Trial.Status)
}

func loadKeyRuns(root, candidate string, maximum int) []ckksplanner.MulticlassKeyRunEvidence {
	rows := make([]ckksplanner.MulticlassKeyRunEvidence, 0, maximum)
	for key := 1; key <= maximum; key++ {
		var item ckksplanner.MulticlassKeyRunEvidence
		if !load(filepath.Join(root, fmt.Sprintf("key_run_%02d.json", key)), &item) {
			break
		}
		if item.CandidateID != candidate || item.KeyRun != key {
			fatalf("key-run identity mismatch")
		}
		rows = append(rows, item)
	}
	return rows
}

func load(path string, target any) bool {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return false
	}
	if err != nil || json.Unmarshal(data, target) != nil {
		fatalf("cannot read verified JSON %s", path)
	}
	return true
}

func writeExclusive(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	handle, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	if _, err := handle.Write(data); err != nil {
		handle.Close()
		return err
	}
	return handle.Close()
}

func writeAtomic(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatalf("marshal: %v", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path+".tmp", data, 0o644); err != nil {
		fatalf("write: %v", err)
	}
	if err := os.Rename(path+".tmp", path); err != nil {
		fatalf("publish: %v", err)
	}
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-multiclass-seed-case: "+format+"\n", args...)
	os.Exit(1)
}
