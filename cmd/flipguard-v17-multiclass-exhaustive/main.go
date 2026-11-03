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

const schema = "flipguard_model_family_expansion_v17_multiclass_exhaustive_v1"

var errCheckpointRequested = errors.New("checkpoint requested after durable key run")

type result struct {
	SchemaVersion          string                              `json:"schema_version"`
	GeneratorID            string                              `json:"generator_id"`
	ModelID                string                              `json:"model_id"`
	FormalDenominator      int                                 `json:"formal_denominator"`
	Entries                []ckksplanner.MulticlassTrialResult `json:"entries"`
	Safe                   int                                 `json:"safe"`
	Rejected               int                                 `json:"rejected"`
	Failed                 int                                 `json:"failed"`
	FastestSafe            *ckksplanner.SynthesizedCandidate   `json:"fastest_safe,omitempty"`
	FastestSafeMeanTotalMS float64                             `json:"fastest_safe_mean_total_ms,omitempty"`
	FastestSafeAudit       *ckksplanner.MulticlassTrialResult  `json:"fastest_safe_independent_evaluation,omitempty"`
	RetuningCount          int                                 `json:"retuning_count"`
	WallClockMS            float64                             `json:"wall_clock_ms"`
}

func main() {
	model := flag.String("model", "", "frozen multiclass model")
	validation := flag.String("validation", "", "frozen 500-image configuration-validation CSV")
	audit := flag.String("audit", "", "frozen disjoint 500-image independent-evaluation CSV")
	source := flag.String("source", "", "byte-pinned MNIST source")
	out := flag.String("out-root", "", "exclusive model result root")
	stopRequest := flag.String("stop-request", "", "optional checkpoint request file checked after each durable key run")
	flag.Parse()
	if *model == "" || *validation == "" || *audit == "" || *source == "" || *out == "" {
		fatalf("all flags are required")
	}
	finalPath := filepath.Join(*out, "exhaustive.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("multiclass exhaustive already complete: %s\n", finalPath)
		return
	}
	if err := os.MkdirAll(*out, 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = *model
	options.ValidationPath = *validation
	options.SourcePath = *source
	options.ExpectedRole = "configuration_validation"
	options.SplitID = "mnist_sha_rank_validation_500_v1"
	contract, _, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build contract: %v", err)
	}
	_, candidates, err := ckksplanner.BuildV17DepthCompleteFiniteSet(contract)
	if err != nil {
		fatalf("build finite set: %v", err)
	}
	started := time.Now()
	output := result{SchemaVersion: schema, GeneratorID: ckksplanner.V17DepthCompleteCandidateGeneratorID, ModelID: contract.ModelID, FormalDenominator: len(candidates), Entries: make([]ckksplanner.MulticlassTrialResult, 0, len(candidates))}
	for index, candidate := range candidates {
		candidateRoot := filepath.Join(*out, fmt.Sprintf("candidate_%02d_%s", index+1, candidate.ID))
		if err := os.MkdirAll(candidateRoot, 0o755); err != nil {
			fatalf("candidate root: %v", err)
		}
		trialPath := filepath.Join(candidateRoot, "trial.json")
		var trial ckksplanner.MulticlassTrialResult
		if !load(trialPath, &trial) {
			trial, err = executeCheckpointed(contract, candidate, index+1, candidateRoot, *stopRequest)
			if err != nil {
				if errors.Is(err, errCheckpointRequested) {
					fmt.Printf("checkpoint_after_key_run model=%s candidate=%s persisted=%d\n", contract.ModelID, candidate.ID, len(loadKeyRuns(candidateRoot, candidate.ID, contract.Deployment.ValidationKeyRepeats)))
					os.Exit(75)
				}
				fatalf("candidate %d: %v", index+1, err)
			}
			writeAtomic(trialPath, trial)
		}
		output.Entries = append(output.Entries, trial)
		switch trial.Status {
		case certify.StatusSafe:
			output.Safe++
			if output.FastestSafe == nil || trial.MeanTotalMS < output.FastestSafeMeanTotalMS {
				copy := candidate
				output.FastestSafe = &copy
				output.FastestSafeMeanTotalMS = trial.MeanTotalMS
			}
		case certify.StatusRejected:
			output.Rejected++
		default:
			output.Failed++
		}
	}
	if output.FastestSafe != nil {
		auditOptions := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
		auditOptions.ModelPath = *model
		auditOptions.ValidationPath = *audit
		auditOptions.SourcePath = *source
		auditOptions.ExpectedRole = "locked_audit"
		auditOptions.SplitID = "mnist_sha_rank_locked_audit_500_v1"
		auditContract, _, buildErr := ckksplanner.BuildJournalMNISTMulticlassContract(auditOptions)
		if buildErr != nil {
			fatalf("build independent-evaluation contract: %v", buildErr)
		}
		if auditContract.ModelArtifact.SHA256 != contract.ModelArtifact.SHA256 ||
			auditContract.SourceData == nil || contract.SourceData == nil ||
			auditContract.SourceData.SHA256 != contract.SourceData.SHA256 {
			fatalf("independent-evaluation model/source identity mismatch")
		}
		auditRoot := filepath.Join(*out, "fastest_safe_independent_evaluation")
		if err := os.MkdirAll(auditRoot, 0o755); err != nil {
			fatalf("independent-evaluation root: %v", err)
		}
		auditPath := filepath.Join(auditRoot, "trial.json")
		var auditTrial ckksplanner.MulticlassTrialResult
		if !load(auditPath, &auditTrial) {
			auditTrial, err = executeCheckpointed(auditContract, *output.FastestSafe, 1, auditRoot, *stopRequest)
			if err != nil {
				if errors.Is(err, errCheckpointRequested) {
					fmt.Printf("checkpoint_after_key_run model=%s candidate=%s role=independent_evaluation\n", contract.ModelID, output.FastestSafe.ID)
					os.Exit(75)
				}
				fatalf("fastest-SAFE independent evaluation: %v", err)
			}
			writeAtomic(auditPath, auditTrial)
		}
		output.FastestSafeAudit = &auditTrial
	}
	output.WallClockMS = float64(time.Since(started).Microseconds()) / 1000
	writeAtomic(finalPath, output)
	fmt.Printf("model=%s denominator=%d safe=%d rejected=%d failed=%d\n", output.ModelID, output.FormalDenominator, output.Safe, output.Rejected, output.Failed)
}

func executeCheckpointed(contract ckksplanner.WorkloadContract, candidate ckksplanner.SynthesizedCandidate, trialIndex int, root, stopRequest string) (ckksplanner.MulticlassTrialResult, error) {
	existing := loadKeyRuns(root, candidate.ID, contract.Deployment.ValidationKeyRepeats)
	return ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(contract, candidate, trialIndex, ckksplanner.MulticlassCandidateExecutionOptions{
		ExistingKeyRuns: existing,
		OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
			if err := writeExclusive(filepath.Join(root, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence); err != nil {
				return err
			}
			if stopRequest != "" {
				if _, err := os.Stat(stopRequest); err == nil {
					return errCheckpointRequested
				} else if !os.IsNotExist(err) {
					return fmt.Errorf("inspect checkpoint request: %w", err)
				}
			}
			return nil
		},
	})
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
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		fatalf("parse %s: %v", path, err)
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
	temp := path + ".tmp"
	if err := os.WriteFile(temp, data, 0o644); err != nil {
		fatalf("write temp: %v", err)
	}
	if err := os.Rename(temp, path); err != nil {
		fatalf("publish: %v", err)
	}
}
func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-multiclass-exhaustive: "+format+"\n", args...)
	os.Exit(1)
}
