package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const runSchema = "flipguard_journal_multiclass_run_v1"

type runManifest struct {
	SchemaVersion          string `json:"schema_version"`
	Stage                  string `json:"stage"`
	SourceCommit           string `json:"source_commit"`
	BinarySHA256           string `json:"binary_sha256"`
	GoVersion              string `json:"go_version"`
	GOOS                   string `json:"goos"`
	GOARCH                 string `json:"goarch"`
	LogicalCPUs            int    `json:"logical_cpus"`
	StartedAt              string `json:"started_at"`
	ProtocolManifestSHA256 string `json:"protocol_manifest_sha256"`
	PreflightSHA256        string `json:"preflight_sha256"`
	SecurityPolicyID       string `json:"security_policy_id"`
	SecurityPolicyDigest   string `json:"security_policy_digest"`
	DirectPolicyID         string `json:"direct_policy_id"`
	DirectPolicyDigest     string `json:"direct_policy_digest"`
	NoRetuning             bool   `json:"no_retuning"`
	ResumeEnabled          bool   `json:"resume_enabled"`
}

type selectionEnvelope struct {
	SchemaVersion string                                       `json:"schema_version"`
	SourceCommit  string                                       `json:"source_commit"`
	CompletedAt   string                                       `json:"completed_at"`
	Result        ckksplanner.AdaptiveMulticlassAutotuneResult `json:"result"`
}

type auditEnvelope struct {
	SchemaVersion string                                  `json:"schema_version"`
	SourceCommit  string                                  `json:"source_commit"`
	CompletedAt   string                                  `json:"completed_at"`
	Result        ckksplanner.MulticlassLockedAuditResult `json:"result"`
}

type catalogEntryResult struct {
	Static ckksplanner.MulticlassCatalogStaticEntry `json:"static"`
	Trial  *ckksplanner.MulticlassTrialResult       `json:"trial,omitempty"`
}

type catalogEnvelope struct {
	SchemaVersion          string               `json:"schema_version"`
	SourceCommit           string               `json:"source_commit"`
	CompletedAt            string               `json:"completed_at"`
	FormalDenominator      int                  `json:"formal_denominator"`
	EncryptedCandidates    int                  `json:"encrypted_candidates"`
	Safe                   int                  `json:"safe"`
	Rejected               int                  `json:"rejected"`
	Failed                 int                  `json:"failed"`
	PlanUnsupported        int                  `json:"plan_unsupported"`
	FastestSafeProfile     string               `json:"fastest_safe_profile,omitempty"`
	FastestSafeMeanTotalMS float64              `json:"fastest_safe_mean_total_ms,omitempty"`
	Entries                []catalogEntryResult `json:"entries"`
}

func main() {
	stage := flag.String("stage", "", "selection, catalog, or audit")
	modelPath := flag.String("model", "", "frozen model artifact")
	validationPath := flag.String("validation", "", "configuration-validation CSV")
	auditPath := flag.String("audit", "", "locked-audit CSV")
	sourcePath := flag.String("source", "results/source_datasets/mnist/mnist_784.arff.gz", "byte-pinned MNIST source")
	protocolPath := flag.String("protocol-manifest", "", "committed journal protocol manifest")
	preflightPath := flag.String("preflight", "", "committed model preflight")
	outputRoot := flag.String("output", "", "new result root")
	sourceCommit := flag.String("source-commit", "", "exact current source commit")
	resume := flag.Bool("resume", false, "resume verified atomic key-run ledgers")
	flag.Parse()
	if *stage != "selection" && *stage != "catalog" && *stage != "audit" {
		fatalf("--stage must be selection, catalog, or audit")
	}
	if *modelPath == "" || *validationPath == "" || *protocolPath == "" ||
		*preflightPath == "" || *outputRoot == "" || len(*sourceCommit) != 40 {
		fatalf("model, validation, protocol-manifest, preflight, output, and full source-commit are required")
	}
	if *stage == "audit" && *auditPath == "" {
		fatalf("--audit is required for locked audit")
	}
	current, err := gitHead()
	if err != nil || current != *sourceCommit {
		fatalf("source commit mismatch: current=%s declared=%s error=%v", current, *sourceCommit, err)
	}
	if err := os.MkdirAll(*outputRoot, 0o755); err != nil {
		fatalf("create output root: %v", err)
	}
	if err := verifyDiskBudget(*preflightPath, *outputRoot); err != nil {
		fatalf("disk feasibility gate: %v", err)
	}
	manifestPath := filepath.Join(*outputRoot, *stage+"_run_manifest.json")
	if _, err := os.Stat(manifestPath); errors.Is(err, os.ErrNotExist) {
		if *resume {
			fatalf("cannot resume without run manifest")
		}
		clean, err := gitClean()
		if err != nil || !clean {
			fatalf("new encrypted run requires clean source tree: clean=%t error=%v", clean, err)
		}
		manifest, err := newRunManifest(*stage, *sourceCommit, *protocolPath, *preflightPath, *resume)
		if err != nil {
			fatalf("build run manifest: %v", err)
		}
		if err := writeExclusiveJSON(manifestPath, manifest); err != nil {
			fatalf("write run manifest: %v", err)
		}
	} else if err != nil {
		fatalf("inspect run manifest: %v", err)
	} else {
		if !*resume {
			fatalf("result root exists; use --resume after verifying provenance")
		}
		var manifest runManifest
		if err := readJSON(manifestPath, &manifest); err != nil {
			fatalf("read run manifest: %v", err)
		}
		if manifest.SourceCommit != *sourceCommit || manifest.Stage != *stage {
			fatalf("resume manifest identity mismatch")
		}
	}
	if *stage == "selection" {
		runSelection(*modelPath, *validationPath, *sourcePath, *outputRoot, *sourceCommit)
	} else if *stage == "catalog" {
		runCatalog(*modelPath, *validationPath, *sourcePath, *outputRoot, *sourceCommit)
	} else {
		runAudit(*auditPath, *outputRoot, *sourceCommit)
	}
}

func runCatalog(modelPath, validationPath, sourcePath, outputRoot, sourceCommit string) {
	finalPath := filepath.Join(outputRoot, "catalog_result.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("catalog already complete: %s\n", finalPath)
		return
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourcePath = sourcePath
	options.ExpectedRole = "configuration_validation"
	options.SplitID = "mnist_sha_rank_validation_500_v1"
	contract, _, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build catalog contract: %v", err)
	}
	staticEntries, err := ckksplanner.BuildJournalMulticlassCatalog(contract)
	if err != nil {
		fatalf("build catalog inventory: %v", err)
	}
	result := catalogEnvelope{
		SchemaVersion:     runSchema,
		SourceCommit:      sourceCommit,
		FormalDenominator: len(staticEntries),
		Entries:           make([]catalogEntryResult, 0, len(staticEntries)),
	}
	for _, static := range staticEntries {
		entry := catalogEntryResult{Static: static}
		profileRoot := filepath.Join(outputRoot, "catalog", static.ProfileName)
		if err := os.MkdirAll(profileRoot, 0o755); err != nil {
			fatalf("create catalog profile root: %v", err)
		}
		if !static.EncryptedExecutionRequired {
			result.PlanUnsupported++
			if err := writeExclusiveOrVerifyJSON(filepath.Join(profileRoot, "static_result.json"), entry); err != nil {
				fatalf("write catalog static result %s: %v", static.ProfileName, err)
			}
			result.Entries = append(result.Entries, entry)
			continue
		}
		profile, err := ckksbackend.FindCKKSProfile(static.ProfileName)
		if err != nil {
			fatalf("load catalog profile %s: %v", static.ProfileName, err)
		}
		trialPath := filepath.Join(profileRoot, "trial_result.json")
		var trial ckksplanner.MulticlassTrialResult
		if _, err := os.Stat(trialPath); err == nil {
			if err := readJSON(trialPath, &trial); err != nil || trial.Candidate.ID != static.Candidate.ID {
				fatalf("resume catalog profile %s mismatch: %v", static.ProfileName, err)
			}
		} else {
			existing, err := loadKeyRuns(profileRoot, static.Candidate.ID, contract.Deployment.ValidationKeyRepeats)
			if err != nil {
				fatalf("load catalog %s key runs: %v", static.ProfileName, err)
			}
			trial, err = ckksplanner.ExecuteJournalMNISTMulticlassCatalogCandidate(
				contract,
				static.Candidate,
				profile,
				1,
				ckksplanner.MulticlassCandidateExecutionOptions{
					ExistingKeyRuns: existing,
					OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
						return writeExclusiveJSON(filepath.Join(profileRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence)
					},
				},
			)
			if err != nil {
				fatalf("execute catalog profile %s: %v", static.ProfileName, err)
			}
			if err := writeExclusiveJSON(trialPath, trial); err != nil {
				fatalf("write catalog profile %s: %v", static.ProfileName, err)
			}
		}
		result.EncryptedCandidates++
		entry.Trial = &trial
		switch trial.Status {
		case certify.StatusSafe:
			result.Safe++
			if result.FastestSafeProfile == "" || trial.MeanTotalMS < result.FastestSafeMeanTotalMS {
				result.FastestSafeProfile = static.ProfileName
				result.FastestSafeMeanTotalMS = trial.MeanTotalMS
			}
		case certify.StatusRejected:
			result.Rejected++
		default:
			result.Failed++
		}
		result.Entries = append(result.Entries, entry)
	}
	result.CompletedAt = time.Now().UTC().Format(time.RFC3339)
	if err := writeExclusiveJSON(finalPath, result); err != nil {
		fatalf("write catalog result: %v", err)
	}
	fmt.Printf("catalog denominator=%d encrypted=%d safe=%d rejected=%d failed=%d unsupported=%d fastest_safe=%s\n",
		result.FormalDenominator, result.EncryptedCandidates, result.Safe, result.Rejected,
		result.Failed, result.PlanUnsupported, result.FastestSafeProfile)
}

func runSelection(modelPath, validationPath, sourcePath, outputRoot, sourceCommit string) {
	finalPath := filepath.Join(outputRoot, "selection_result.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("selection already complete: %s\n", finalPath)
		return
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourcePath = sourcePath
	options.ExpectedRole = "configuration_validation"
	options.SplitID = "mnist_sha_rank_validation_500_v1"
	contract, _, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build selection contract: %v", err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		fatalf("synthesize selection plan: %v", err)
	}
	result := ckksplanner.AdaptiveMulticlassAutotuneResult{
		SchemaVersion:    ckksplanner.SynthesisPlanSchemaVersion,
		ExecutionAdapter: ckksbackend.JournalMNISTMulticlassExecutionAdapterV1,
		Plan:             plan,
		Trials:           make([]ckksplanner.MulticlassTrialResult, 0, contract.Deployment.MaxEncryptedTrials),
	}
	candidate := plan.InitialCandidates[0]
	for trialIndex := 1; trialIndex <= contract.Deployment.MaxEncryptedTrials; trialIndex++ {
		trialRoot := filepath.Join(outputRoot, fmt.Sprintf("trial_%02d_%s", trialIndex, candidate.ID))
		if err := os.MkdirAll(trialRoot, 0o755); err != nil {
			fatalf("create trial root: %v", err)
		}
		trialPath := filepath.Join(trialRoot, "trial_result.json")
		var trial ckksplanner.MulticlassTrialResult
		if _, err := os.Stat(trialPath); err == nil {
			if err := readJSON(trialPath, &trial); err != nil || trial.Candidate.ID != candidate.ID {
				fatalf("resume trial %d mismatch: %v", trialIndex, err)
			}
		} else {
			existing, err := loadKeyRuns(trialRoot, candidate.ID, contract.Deployment.ValidationKeyRepeats)
			if err != nil {
				fatalf("load trial %d key runs: %v", trialIndex, err)
			}
			trial, err = ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(
				contract, candidate, trialIndex,
				ckksplanner.MulticlassCandidateExecutionOptions{
					ExistingKeyRuns: existing,
					OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
						return writeExclusiveJSON(filepath.Join(trialRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence)
					},
				},
			)
			if err != nil {
				fatalf("execute trial %d: %v", trialIndex, err)
			}
			if err := writeExclusiveJSON(trialPath, trial); err != nil {
				fatalf("write trial %d result: %v", trialIndex, err)
			}
		}
		result.Trials = append(result.Trials, trial)
		result.TrialsUsed = len(result.Trials)
		result.EncryptedKeyRuns += trial.KeyRepeatsCompleted
		result.EncryptedSampleEvaluations += trial.EncryptedSampleEvaluations
		if trial.Status == certify.StatusSafe {
			selected := candidate
			result.Outcome = ckksplanner.AdaptiveOutcomeSelected
			result.Selected = &selected
			result.Reason = fmt.Sprintf("selected first SAFE multiclass candidate after %d trial(s)", result.TrialsUsed)
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
			fatalf("repair trial %d: %v", trialIndex, err)
		}
		result.Repairs++
	}
	if result.Outcome == "" {
		result.Outcome = ckksplanner.AdaptiveOutcomeNoSafe
		result.Reason = fmt.Sprintf("no SAFE candidate within frozen trial budget %d", contract.Deployment.MaxEncryptedTrials)
	}
	envelope := selectionEnvelope{SchemaVersion: runSchema, SourceCommit: sourceCommit, CompletedAt: time.Now().UTC().Format(time.RFC3339), Result: result}
	if err := writeExclusiveJSON(finalPath, envelope); err != nil {
		fatalf("write selection result: %v", err)
	}
	fmt.Printf("selection outcome=%s trials=%d repairs=%d key_runs=%d\n", result.Outcome, result.TrialsUsed, result.Repairs, result.EncryptedKeyRuns)
}

func runAudit(auditPath, outputRoot, sourceCommit string) {
	finalPath := filepath.Join(outputRoot, "locked_audit_result.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("locked audit already complete: %s\n", finalPath)
		return
	}
	selectionPath := filepath.Join(outputRoot, "selection_result.json")
	var selection selectionEnvelope
	if err := readJSON(selectionPath, &selection); err != nil {
		fatalf("read selection for audit: %v", err)
	}
	if selection.Result.Outcome != ckksplanner.AdaptiveOutcomeSelected || selection.Result.Selected == nil {
		fatalf("locked audit requires a selected validation literal")
	}
	selectionContract := selection.Result.Plan.Contract
	auditLedgerRoot := filepath.Join(outputRoot, "locked_audit")
	if err := os.MkdirAll(auditLedgerRoot, 0o755); err != nil {
		fatalf("create audit ledger: %v", err)
	}
	existing, err := loadKeyRuns(auditLedgerRoot, selection.Result.Selected.ID, selectionContract.Deployment.ValidationKeyRepeats)
	if err != nil {
		fatalf("load audit key runs: %v", err)
	}
	result, err := ckksplanner.RunJournalMNISTMulticlassLockedAuditWithOptions(
		selectionContract,
		*selection.Result.Selected,
		auditPath,
		"mnist_sha_rank_locked_audit_500_v1",
		ckksplanner.MulticlassCandidateExecutionOptions{
			ExistingKeyRuns: existing,
			OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
				return writeExclusiveJSON(filepath.Join(auditLedgerRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun)), evidence)
			},
		},
	)
	if err != nil {
		fatalf("run locked audit: %v", err)
	}
	envelope := auditEnvelope{SchemaVersion: runSchema, SourceCommit: sourceCommit, CompletedAt: time.Now().UTC().Format(time.RFC3339), Result: result}
	if err := writeExclusiveJSON(finalPath, envelope); err != nil {
		fatalf("write locked audit result: %v", err)
	}
	fmt.Printf("audit status=%s flips=%d rejects=%d retuning=%d\n", result.Trial.Status, result.Trial.Aggregation.ArgmaxFlips, result.Trial.Aggregation.ReserveViolations, result.RetuningCount)
}

func newRunManifest(stage, sourceCommit, protocolPath, preflightPath string, resume bool) (runManifest, error) {
	binary, err := os.Executable()
	if err != nil {
		return runManifest{}, err
	}
	binaryDigest, err := digestFile(binary)
	if err != nil {
		return runManifest{}, err
	}
	protocolDigest, err := digestFile(protocolPath)
	if err != nil {
		return runManifest{}, err
	}
	preflightDigest, err := digestFile(preflightPath)
	if err != nil {
		return runManifest{}, err
	}
	securityDigest, err := ckksplanner.SecurityPolicyDigest(ckksplanner.DefaultSecurityEnvelope())
	if err != nil {
		return runManifest{}, err
	}
	return runManifest{
		SchemaVersion: runSchema, Stage: stage, SourceCommit: sourceCommit,
		BinarySHA256: binaryDigest, GoVersion: runtime.Version(), GOOS: runtime.GOOS,
		GOARCH: runtime.GOARCH, LogicalCPUs: runtime.NumCPU(), StartedAt: time.Now().UTC().Format(time.RFC3339),
		ProtocolManifestSHA256: protocolDigest, PreflightSHA256: preflightDigest,
		SecurityPolicyID:     ckksplanner.SecurityPolicyV2ID,
		SecurityPolicyDigest: securityDigest,
		DirectPolicyID:       ckksplanner.DirectSynthesisPolicyV2ID,
		DirectPolicyDigest:   ckksplanner.MustDefaultDirectSynthesisPolicyDigest(),
		NoRetuning:           true, ResumeEnabled: true,
	}, nil
}

func loadKeyRuns(root, candidateID string, maximum int) ([]ckksplanner.MulticlassKeyRunEvidence, error) {
	result := make([]ckksplanner.MulticlassKeyRunEvidence, 0, maximum)
	for keyRun := 1; keyRun <= maximum; keyRun++ {
		path := filepath.Join(root, fmt.Sprintf("key_run_%02d.json", keyRun))
		if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
			break
		} else if err != nil {
			return nil, err
		}
		var evidence ckksplanner.MulticlassKeyRunEvidence
		if err := readJSON(path, &evidence); err != nil {
			return nil, err
		}
		if evidence.KeyRun != keyRun || evidence.CandidateID != candidateID {
			return nil, fmt.Errorf("key-run ledger %d identity mismatch", keyRun)
		}
		result = append(result, evidence)
	}
	return result, nil
}

func writeExclusiveJSON(path string, value any) error {
	if _, err := os.Stat(path); err == nil {
		return fmt.Errorf("refusing to overwrite %s", path)
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	temporary := path + ".tmp"
	if err := os.WriteFile(temporary, data, 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func writeExclusiveOrVerifyJSON(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if existing, err := os.ReadFile(path); err == nil {
		if !bytes.Equal(existing, data) {
			return fmt.Errorf("existing %s is not byte-identical", path)
		}
		return nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return writeExclusiveJSON(path, value)
}

func readJSON(path string, value any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	return decoder.Decode(value)
}

func digestFile(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", err
	}
	return "sha256:" + hex.EncodeToString(hasher.Sum(nil)), nil
}

func gitHead() (string, error) {
	output, err := exec.Command("git", "rev-parse", "HEAD").Output()
	return strings.TrimSpace(string(output)), err
}

func gitClean() (bool, error) {
	output, err := exec.Command("git", "status", "--porcelain").Output()
	return len(bytes.TrimSpace(output)) == 0, err
}

func verifyDiskBudget(preflightPath, outputRoot string) error {
	var preflight struct {
		DiskBudget map[string]json.RawMessage `json:"disk_budget"`
	}
	data, err := os.ReadFile(preflightPath)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(data, &preflight); err != nil {
		return err
	}
	minimum := int64(0)
	if raw, ok := preflight.DiskBudget["minimum_free_disk_bytes"]; ok {
		if err := json.Unmarshal(raw, &minimum); err != nil {
			return err
		}
	}
	var stats syscall.Statfs_t
	if err := syscall.Statfs(outputRoot, &stats); err != nil {
		return err
	}
	available := int64(stats.Bavail) * int64(stats.Bsize)
	if available < minimum {
		return fmt.Errorf("available bytes %d below declared minimum %d", available, minimum)
	}
	return nil
}

func fatalf(format string, values ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", values...)
	os.Exit(1)
}
