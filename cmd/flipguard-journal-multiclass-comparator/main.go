package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const (
	schemaVersion       = "flipguard_journal_multiclass_graph_only_comparator_v1"
	graphOnlyPlanOK     = "PLAN_OK_SECURITY_ADMITTED"
	comparatorID        = "graph_only_fixed_logit_tolerance_0.001"
	expectedProtocolSHA = "sha256:caf39e2b38f8c1a46bb1fece30d68d758b613e2459e51e6af9898e535620b269"
)

type preflightEnvelope struct {
	SchemaVersion                 string                    `json:"schema_version"`
	SourceCommit                  string                    `json:"source_commit"`
	GraphOnlyFixedToleranceStatus string                    `json:"graph_only_fixed_tolerance_status"`
	GraphOnlyFixedTolerancePlan   ckksplanner.SynthesisPlan `json:"graph_only_fixed_tolerance_plan"`
}

type runManifest struct {
	SchemaVersion          string `json:"schema_version"`
	ComparatorID           string `json:"comparator_id"`
	ComparatorSourceCommit string `json:"comparator_source_commit"`
	PreflightSourceCommit  string `json:"preflight_source_commit"`
	BinarySHA256           string `json:"binary_sha256"`
	ProtocolSHA256         string `json:"protocol_manifest_sha256"`
	PreflightSHA256        string `json:"preflight_sha256"`
	DirectPolicyDigest     string `json:"direct_policy_digest"`
	SecurityPolicyDigest   string `json:"security_policy_digest"`
	CandidateID            string `json:"candidate_id"`
	NoAuditRetuning        bool   `json:"no_audit_retuning"`
	FreshKeyRepeats        int    `json:"fresh_key_repeats"`
	StartedAt              string `json:"started_at"`
	GoVersion              string `json:"go_version"`
	GOOS                   string `json:"goos"`
	GOARCH                 string `json:"goarch"`
}

type resultEnvelope struct {
	SchemaVersion          string                            `json:"schema_version"`
	ComparatorID           string                            `json:"comparator_id"`
	ComparatorSourceCommit string                            `json:"comparator_source_commit"`
	PreflightSourceCommit  string                            `json:"preflight_source_commit"`
	Candidate              ckksplanner.SynthesizedCandidate  `json:"candidate"`
	Trial                  ckksplanner.MulticlassTrialResult `json:"trial"`
	CompletedAt            string                            `json:"completed_at"`
}

func main() {
	preflightPath := flag.String("preflight", "", "frozen MLP preflight JSON")
	protocolPath := flag.String("protocol-manifest", "", "frozen journal protocol manifest")
	outputRoot := flag.String("output", "", "new comparator result directory")
	sourceCommit := flag.String("source-commit", "", "exact comparator source commit")
	flag.Parse()
	if *preflightPath == "" || *protocolPath == "" || *outputRoot == "" || *sourceCommit == "" {
		fatalf("--preflight, --protocol-manifest, --output, and --source-commit are required")
	}
	if err := run(*preflightPath, *protocolPath, *outputRoot, *sourceCommit); err != nil {
		fatalf("%v", err)
	}
}

func run(preflightPath, protocolPath, outputRoot, sourceCommit string) error {
	resultPath := filepath.Join(outputRoot, "result.json")
	if _, err := os.Stat(resultPath); err == nil {
		fmt.Printf("graph-only comparator already complete: %s\n", resultPath)
		return nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	var preflight preflightEnvelope
	if err := readJSON(preflightPath, &preflight); err != nil {
		return fmt.Errorf("read preflight: %w", err)
	}
	if err := validatePreflight(preflight); err != nil {
		return err
	}
	protocolDigest, err := digestFile(protocolPath)
	if err != nil {
		return fmt.Errorf("digest protocol: %w", err)
	}
	if protocolDigest != expectedProtocolSHA {
		return fmt.Errorf("protocol digest %s; expected %s", protocolDigest, expectedProtocolSHA)
	}
	candidate := preflight.GraphOnlyFixedTolerancePlan.InitialCandidates[0]
	if err := os.MkdirAll(outputRoot, 0o755); err != nil {
		return fmt.Errorf("create output: %w", err)
	}
	manifestPath := filepath.Join(outputRoot, "run_manifest.json")
	if _, err := os.Stat(manifestPath); errors.Is(err, os.ErrNotExist) {
		manifest, err := newRunManifest(
			preflightPath,
			protocolPath,
			sourceCommit,
			preflight.SourceCommit,
			preflight.GraphOnlyFixedTolerancePlan,
			candidate,
		)
		if err != nil {
			return err
		}
		if err := writeExclusiveJSON(manifestPath, manifest); err != nil {
			return err
		}
	} else if err != nil {
		return err
	}
	ledgerRoot := filepath.Join(outputRoot, "key_runs")
	if err := os.MkdirAll(ledgerRoot, 0o755); err != nil {
		return err
	}
	existing, err := loadKeyRuns(
		ledgerRoot,
		candidate.ID,
		preflight.GraphOnlyFixedTolerancePlan.Contract.Deployment.ValidationKeyRepeats,
	)
	if err != nil {
		return err
	}
	trial, err := ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(
		preflight.GraphOnlyFixedTolerancePlan.Contract,
		candidate,
		1,
		ckksplanner.MulticlassCandidateExecutionOptions{
			ExistingKeyRuns: existing,
			OnKeyRun: func(evidence ckksplanner.MulticlassKeyRunEvidence) error {
				path := filepath.Join(ledgerRoot, fmt.Sprintf("key_run_%02d.json", evidence.KeyRun))
				return writeExclusiveJSON(path, evidence)
			},
		},
	)
	if err != nil {
		return fmt.Errorf("execute graph-only comparator: %w", err)
	}
	result := resultEnvelope{
		SchemaVersion: schemaVersion, ComparatorID: comparatorID,
		ComparatorSourceCommit: sourceCommit, PreflightSourceCommit: preflight.SourceCommit,
		Candidate: candidate, Trial: trial, CompletedAt: time.Now().UTC().Format(time.RFC3339),
	}
	if err := writeExclusiveJSON(resultPath, result); err != nil {
		return err
	}
	fmt.Printf(
		"graph-only status=%s candidate=%s flips=%d rejects=%d key_runs=%d\n",
		trial.Status,
		candidate.ID,
		trial.Aggregation.ArgmaxFlips,
		trial.Aggregation.ReserveViolations,
		trial.KeyRepeatsCompleted,
	)
	return nil
}

func validatePreflight(preflight preflightEnvelope) error {
	if preflight.GraphOnlyFixedToleranceStatus != graphOnlyPlanOK {
		return fmt.Errorf("graph-only status %q is not executable", preflight.GraphOnlyFixedToleranceStatus)
	}
	plan := preflight.GraphOnlyFixedTolerancePlan
	if len(plan.InitialCandidates) != 1 {
		return fmt.Errorf("graph-only preflight has %d initial candidates", len(plan.InitialCandidates))
	}
	if plan.DirectPolicyDigest != ckksplanner.MustDefaultDirectSynthesisPolicyDigest() {
		return fmt.Errorf("direct policy digest mismatch")
	}
	securityDigest, err := ckksplanner.SecurityPolicyDigest(ckksplanner.DefaultSecurityEnvelope())
	if err != nil {
		return err
	}
	if plan.SecurityPolicyDigest != securityDigest {
		return fmt.Errorf("security policy digest mismatch")
	}
	candidate := plan.InitialCandidates[0]
	if candidate.Security.FinalAdmission != "PASS" {
		return fmt.Errorf("graph-only candidate is not Security-V2 admitted")
	}
	if plan.Contract.ModelType != "mlp_square_multiclass" {
		return fmt.Errorf("comparator v1 is frozen to the MLP-100 graph")
	}
	if plan.Contract.Deployment.ValidationKeyRepeats != 3 {
		return fmt.Errorf("fresh-key repeat count changed")
	}
	return nil
}

func newRunManifest(
	preflightPath, protocolPath, sourceCommit, preflightCommit string,
	plan ckksplanner.SynthesisPlan,
	candidate ckksplanner.SynthesizedCandidate,
) (runManifest, error) {
	binaryPath, err := os.Executable()
	if err != nil {
		return runManifest{}, err
	}
	binaryDigest, err := digestFile(binaryPath)
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
	return runManifest{
		SchemaVersion: schemaVersion, ComparatorID: comparatorID,
		ComparatorSourceCommit: sourceCommit, PreflightSourceCommit: preflightCommit,
		BinarySHA256: binaryDigest, ProtocolSHA256: protocolDigest, PreflightSHA256: preflightDigest,
		DirectPolicyDigest: plan.DirectPolicyDigest, SecurityPolicyDigest: plan.SecurityPolicyDigest,
		CandidateID: candidate.ID, NoAuditRetuning: true,
		FreshKeyRepeats: plan.Contract.Deployment.ValidationKeyRepeats,
		StartedAt:       time.Now().UTC().Format(time.RFC3339), GoVersion: runtime.Version(),
		GOOS: runtime.GOOS, GOARCH: runtime.GOARCH,
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

func readJSON(path string, value any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, value)
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

func digestFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	value := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(value[:]), nil
}

func fatalf(format string, values ...any) {
	fmt.Fprintf(os.Stderr, "error: "+format+"\n", values...)
	os.Exit(1)
}
