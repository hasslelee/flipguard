package ckksplanner

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	SobelLockedAuditSchemaVersion = 1
	SobelLockedAuditPass          = "LOCKED_AUDIT_PASS"
	SobelLockedAuditFail          = "LOCKED_AUDIT_FAIL"
)

type SobelLockedAuditOptions struct {
	SelectionResultPath    string
	AuditPath              string
	SourceArchivePath      string
	ExtractionManifestPath string
	KeyRepeats             int
}

type SobelLockedAuditResult struct {
	SchemaVersion int `json:"schema_version"`

	ExecutionAdapter string `json:"execution_adapter"`
	Outcome          string `json:"outcome"`
	Reason           string `json:"reason"`

	RetuningPerformed bool `json:"retuning_performed"`

	SelectionResult    ArtifactBinding `json:"selection_result"`
	ExtractionManifest ArtifactBinding `json:"extraction_manifest"`

	SelectionContractDigest string `json:"selection_contract_digest"`
	SelectionWorkloadID     string `json:"selection_workload_id"`

	AuditContract WorkloadContract `json:"audit_contract"`

	SelectedCandidate SynthesizedCandidate `json:"selected_candidate"`
	AuditTrial        SobelTrialResult     `json:"audit_trial"`
}

type sobelExtractionManifest struct {
	SchemaVersion string `json:"schema_version"`
	Partitions    map[string]struct {
		Path   string `json:"path"`
		SHA256 string `json:"sha256"`
	} `json:"partitions"`
}

func RunLockedSobelAudit(
	options SobelLockedAuditOptions,
) (SobelLockedAuditResult, error) {
	if strings.TrimSpace(options.SelectionResultPath) == "" ||
		strings.TrimSpace(options.AuditPath) == "" ||
		strings.TrimSpace(options.SourceArchivePath) == "" ||
		strings.TrimSpace(options.ExtractionManifestPath) == "" {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel locked audit paths must be non-empty",
		)
	}
	if options.KeyRepeats <= 0 {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel audit key repeats must be positive",
		)
	}

	selectionBytes, err := os.ReadFile(options.SelectionResultPath)
	if err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"read Sobel selection: %w",
			err,
		)
	}
	selection := AdaptiveSobelAutotuneResult{}
	if err := json.Unmarshal(selectionBytes, &selection); err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"parse Sobel selection: %w",
			err,
		)
	}
	selected, err := ValidateSelectedSobelAutotuneResult(selection)
	if err != nil {
		return SobelLockedAuditResult{}, err
	}
	if err := verifyContractArtifacts(selection.Plan.Contract); err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"verify Sobel selection artifacts: %w",
			err,
		)
	}

	manifestBytes, err := os.ReadFile(options.ExtractionManifestPath)
	if err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"read Sobel extraction manifest: %w",
			err,
		)
	}
	manifest := sobelExtractionManifest{}
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"parse Sobel extraction manifest: %w",
			err,
		)
	}
	if manifest.SchemaVersion != BSDS500SobelModelSchemaV1 {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel extraction manifest schema changed",
		)
	}
	validationManifest, ok :=
		manifest.Partitions["configuration_validation"]
	if !ok ||
		validationManifest.SHA256 !=
			selection.Plan.Contract.ValidationData.SHA256 {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel selection validation is not bound by extraction manifest",
		)
	}
	auditBytes, err := os.ReadFile(options.AuditPath)
	if err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"read Sobel audit CSV: %w",
			err,
		)
	}
	auditManifest, ok := manifest.Partitions["locked_audit_test"]
	if !ok || auditManifest.SHA256 != digestBytes(auditBytes) {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel audit CSV is not bound by extraction manifest",
		)
	}

	validationIDs, err := readCSVRowIDs(
		selection.Plan.Contract.ValidationData.Path,
	)
	if err != nil {
		return SobelLockedAuditResult{}, err
	}
	auditIDs, err := readCSVRowIDs(options.AuditPath)
	if err != nil {
		return SobelLockedAuditResult{}, err
	}
	if err := validateDisjointRowIDs(validationIDs, auditIDs); err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel validation/audit row identity: %w",
			err,
		)
	}

	selectionContract := selection.Plan.Contract
	contractOptions := DefaultPrimarySobelContractOptions()
	contractOptions.ModelPath =
		selectionContract.ModelArtifact.Path
	contractOptions.ValidationPath = options.AuditPath
	contractOptions.SourceArchivePath =
		options.SourceArchivePath
	contractOptions.SplitID =
		selectionContract.SplitID + "/locked_audit"
	contractOptions.MarginFloor =
		selectionContract.Decision.MarginFloor
	contractOptions.SafetyFactor =
		selectionContract.Decision.SafetyFactor
	contractOptions.SecurityBits =
		selectionContract.Deployment.SecurityBits
	contractOptions.MaxEncryptedTrials = 1
	contractOptions.ValidationKeyRepeats =
		options.KeyRepeats
	contractOptions.AllowedPaths =
		[]tuner.ExecutionPath{selected.Path}
	auditContract, err := BuildSobelWorkloadContract(contractOptions)
	if err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"build Sobel locked audit contract: %w",
			err,
		)
	}
	if auditContract.ModelArtifact.SHA256 !=
		selectionContract.ModelArtifact.SHA256 ||
		auditContract.SourceData == nil ||
		selectionContract.SourceData == nil ||
		auditContract.SourceData.SHA256 !=
			selectionContract.SourceData.SHA256 {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"Sobel locked audit model/source identity changed",
		)
	}
	trial, err := ExecuteSobelCandidate(
		auditContract,
		selected,
		1,
	)
	if err != nil {
		return SobelLockedAuditResult{}, fmt.Errorf(
			"execute Sobel locked audit: %w",
			err,
		)
	}
	outcome := SobelLockedAuditFail
	reason := fmt.Sprintf(
		"locked Sobel candidate %s returned status %s",
		selected.ID,
		trial.Status,
	)
	if trial.Status == certify.StatusSafe {
		outcome = SobelLockedAuditPass
		reason = fmt.Sprintf(
			"locked Sobel candidate %s remained SAFE on the disjoint test images",
			selected.ID,
		)
	}
	return SobelLockedAuditResult{
		SchemaVersion:     SobelLockedAuditSchemaVersion,
		ExecutionAdapter:  selection.ExecutionAdapter,
		Outcome:           outcome,
		Reason:            reason,
		RetuningPerformed: false,
		SelectionResult: ArtifactBinding{
			Path:   options.SelectionResultPath,
			SHA256: digestBytes(selectionBytes),
		},
		ExtractionManifest: ArtifactBinding{
			Path:   options.ExtractionManifestPath,
			SHA256: digestBytes(manifestBytes),
		},
		SelectionContractDigest: selection.Plan.ContractDigest,
		SelectionWorkloadID:     selection.Plan.Contract.WorkloadID,
		AuditContract:           auditContract,
		SelectedCandidate:       selected,
		AuditTrial:              trial,
	}, nil
}

func ValidateSelectedSobelAutotuneResult(
	selection AdaptiveSobelAutotuneResult,
) (SynthesizedCandidate, error) {
	if selection.ExecutionAdapter !=
		"bsds500_sobel_rescale_graph_adapter_v1" {
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported Sobel execution adapter %q",
			selection.ExecutionAdapter,
		)
	}
	converted := AdaptiveAutotuneResult{
		SchemaVersion:    selection.SchemaVersion,
		Plan:             selection.Plan,
		Outcome:          selection.Outcome,
		Reason:           selection.Reason,
		TrialsUsed:       selection.TrialsUsed,
		Trials:           make([]TabularTrialResult, len(selection.Trials)),
		EncryptedKeyRuns: selection.EncryptedKeyRuns,
		Selected:         selection.Selected,
	}
	encryptedSamples := 0
	for index, trial := range selection.Trials {
		converted.Trials[index] = TabularTrialResult{
			TrialIndex:          trial.TrialIndex,
			Candidate:           trial.Candidate,
			Status:              trial.Status,
			Assurance:           trial.Assurance,
			Reason:              trial.Reason,
			FailureSignal:       trial.FailureSignal,
			Failure:             trial.Failure,
			KeyRepeatsRequested: trial.KeyRepeatsRequested,
			KeyRepeatsCompleted: trial.KeyRepeatsCompleted,
			SuccessRuns:         trial.SuccessRuns,
			DecisionFlips:       trial.DecisionFlips,
			ErrorViolations:     trial.ErrorViolations,
			MaxObservedError:    trial.MaxObservedError,
			MaxErrorBudgetUsage: trial.MaxErrorBudgetUsage,
			VCert:               trial.VCert,
			VAmb:                trial.VAmb,
			MeanTotalMS:         trial.MeanTotalMS,
			MedianMS:            trial.MedianMS,
			P95MS:               trial.P95MS,
		}
		encryptedSamples += trial.EncryptedSampleEvaluations
		if trial.Status == certify.StatusSafe ||
			trial.Status == certify.StatusRejected {
			expected := selection.Plan.Contract.Decision.ValidationSamples *
				trial.KeyRepeatsCompleted
			if trial.EncryptedSampleEvaluations != expected {
				return SynthesizedCandidate{}, fmt.Errorf(
					"Sobel trial %d encrypted sample ledger mismatch",
					trial.TrialIndex,
				)
			}
		}
	}
	if encryptedSamples != selection.EncryptedSampleEvaluations {
		return SynthesizedCandidate{}, fmt.Errorf(
			"Sobel aggregate encrypted sample ledger mismatch",
		)
	}
	selected, err := ValidateSelectedAutotuneResult(converted)
	if err != nil {
		return SynthesizedCandidate{}, err
	}
	if !reflect.DeepEqual(selected, *selection.Selected) {
		return SynthesizedCandidate{}, fmt.Errorf(
			"Sobel selected literal identity changed",
		)
	}
	return selected, nil
}
