package ckksplanner

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"reflect"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	CNNLiteLockedAuditSchemaVersion = 1
	CNNLiteLockedAuditPass          = "LOCKED_AUDIT_PASS"
	CNNLiteLockedAuditFail          = "LOCKED_AUDIT_FAIL"
)

type CNNLiteLockedAuditOptions struct {
	SelectionResultPath string
	AuditPath           string
	SourcePath          string
	ManifestPath        string
	KeyRepeats          int
}

type CNNLiteLockedAuditResult struct {
	SchemaVersion int `json:"schema_version"`

	ExecutionAdapter string `json:"execution_adapter"`
	Outcome          string `json:"outcome"`
	Reason           string `json:"reason"`

	RetuningPerformed bool `json:"retuning_performed"`

	SelectionResult ArtifactBinding `json:"selection_result"`
	InputManifest   ArtifactBinding `json:"input_manifest"`

	SelectionContractDigest string `json:"selection_contract_digest"`
	SelectionWorkloadID     string `json:"selection_workload_id"`

	AuditContract WorkloadContract `json:"audit_contract"`

	SelectedCandidate SynthesizedCandidate `json:"selected_candidate"`
	AuditTrial        CNNLiteTrialResult   `json:"audit_trial"`
}

type cnnLiteInputManifest struct {
	SchemaVersion          string `json:"schema_version"`
	ExtractionPolicyID     string `json:"extraction_policy_id"`
	ExtractionPolicyDigest string `json:"extraction_policy_digest"`

	SourceArchive ArtifactBinding `json:"source_archive"`
	Model         ArtifactBinding `json:"model"`
	Partitions    map[string]struct {
		Path   string `json:"path"`
		SHA256 string `json:"sha256"`
	} `json:"partitions"`
}

func RunLockedCNNLiteAudit(
	options CNNLiteLockedAuditOptions,
) (CNNLiteLockedAuditResult, error) {
	if strings.TrimSpace(options.SelectionResultPath) == "" ||
		strings.TrimSpace(options.AuditPath) == "" ||
		strings.TrimSpace(options.SourcePath) == "" ||
		strings.TrimSpace(options.ManifestPath) == "" {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite locked audit paths must be non-empty",
		)
	}
	if options.KeyRepeats <= 0 {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite audit key repeats must be positive",
		)
	}
	selectionBytes, err := os.ReadFile(options.SelectionResultPath)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"read CNN-lite selection: %w",
			err,
		)
	}
	selection := AdaptiveCNNLiteAutotuneResult{}
	if err := json.Unmarshal(selectionBytes, &selection); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"parse CNN-lite selection: %w",
			err,
		)
	}
	selected, err := ValidateSelectedCNNLiteAutotuneResult(selection)
	if err != nil {
		return CNNLiteLockedAuditResult{}, err
	}
	if err := verifyContractArtifacts(selection.Plan.Contract); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"verify CNN-lite selection artifacts: %w",
			err,
		)
	}

	manifestBytes, err := os.ReadFile(options.ManifestPath)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"read CNN-lite input manifest: %w",
			err,
		)
	}
	manifest := cnnLiteInputManifest{}
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"parse CNN-lite input manifest: %w",
			err,
		)
	}
	if manifest.SchemaVersion != MNISTCNNLiteModelSchemaV1 ||
		manifest.ExtractionPolicyID !=
			MNISTCNNLiteExtractionPolicyV1 {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite input manifest identity changed",
		)
	}
	selectionContract := selection.Plan.Contract
	if err := validateSHA256(
		manifest.ExtractionPolicyDigest,
	); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite extraction manifest digest: %w",
			err,
		)
	}
	modelBytes, err := os.ReadFile(
		selectionContract.ModelArtifact.Path,
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"read selected CNN-lite model: %w",
			err,
		)
	}
	model := cnnLiteModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"parse selected CNN-lite model: %w",
			err,
		)
	}
	if model.ExtractionPolicyDigest !=
		manifest.ExtractionPolicyDigest {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite manifest extraction policy binding changed",
		)
	}
	if manifest.Model.SHA256 !=
		selectionContract.ModelArtifact.SHA256 ||
		selectionContract.SourceData == nil ||
		manifest.SourceArchive.SHA256 !=
			selectionContract.SourceData.SHA256 {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite manifest model/source binding changed",
		)
	}
	validationManifest, ok :=
		manifest.Partitions["configuration_validation"]
	if !ok ||
		validationManifest.SHA256 !=
			selectionContract.ValidationData.SHA256 {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite validation is not bound by input manifest",
		)
	}
	auditBytes, err := os.ReadFile(options.AuditPath)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"read CNN-lite audit CSV: %w",
			err,
		)
	}
	auditManifest, ok := manifest.Partitions["locked_audit_test"]
	if !ok || auditManifest.SHA256 != digestBytes(auditBytes) {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite audit CSV is not bound by input manifest",
		)
	}
	validationIDs, err := readCSVRowIDs(
		selectionContract.ValidationData.Path,
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, err
	}
	auditIDs, err := readCSVRowIDs(options.AuditPath)
	if err != nil {
		return CNNLiteLockedAuditResult{}, err
	}
	if err := validateDisjointRowIDs(validationIDs, auditIDs); err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite validation/audit identity: %w",
			err,
		)
	}
	validationPartitions, err := readCSVIdentityColumn(
		selectionContract.ValidationData.Path,
		"source_partition",
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, err
	}
	auditPartitions, err := readCSVIdentityColumn(
		options.AuditPath,
		"source_partition",
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, err
	}
	if !reflect.DeepEqual(
		validationPartitions,
		map[string]struct{}{"train": {}},
	) || !reflect.DeepEqual(
		auditPartitions,
		map[string]struct{}{"test": {}},
	) {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite official train/test role boundary changed",
		)
	}

	contractOptions := DefaultPrimaryCNNLiteContractOptions()
	contractOptions.ModelPath =
		selectionContract.ModelArtifact.Path
	contractOptions.ValidationPath = options.AuditPath
	contractOptions.SourcePath = options.SourcePath
	contractOptions.SplitID =
		selectionContract.SplitID + "/locked_audit"
	contractOptions.MarginFloor =
		selectionContract.Decision.MarginFloor
	contractOptions.SafetyFactor =
		selectionContract.Decision.SafetyFactor
	contractOptions.SecurityBits =
		selectionContract.Deployment.SecurityBits
	contractOptions.MaxEncryptedTrials = 1
	contractOptions.ValidationKeyRepeats = options.KeyRepeats
	contractOptions.AllowedPaths =
		[]tuner.ExecutionPath{selected.Path}
	auditContract, err := BuildCNNLiteWorkloadContract(
		contractOptions,
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"build CNN-lite locked audit contract: %w",
			err,
		)
	}
	if auditContract.ModelArtifact.SHA256 !=
		selectionContract.ModelArtifact.SHA256 ||
		auditContract.SourceData == nil ||
		selectionContract.SourceData == nil ||
		auditContract.SourceData.SHA256 !=
			selectionContract.SourceData.SHA256 {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"CNN-lite locked audit model/source identity changed",
		)
	}
	trial, err := ExecuteCNNLiteCandidate(
		auditContract,
		selected,
		1,
	)
	if err != nil {
		return CNNLiteLockedAuditResult{}, fmt.Errorf(
			"execute CNN-lite locked audit: %w",
			err,
		)
	}
	outcome := CNNLiteLockedAuditFail
	reason := fmt.Sprintf(
		"locked CNN-lite candidate %s returned status %s",
		selected.ID,
		trial.Status,
	)
	if trial.Status == certify.StatusSafe {
		outcome = CNNLiteLockedAuditPass
		reason = fmt.Sprintf(
			"locked CNN-lite candidate %s remained SAFE on official test rows",
			selected.ID,
		)
	}
	return CNNLiteLockedAuditResult{
		SchemaVersion:     CNNLiteLockedAuditSchemaVersion,
		ExecutionAdapter:  selection.ExecutionAdapter,
		Outcome:           outcome,
		Reason:            reason,
		RetuningPerformed: false,
		SelectionResult: ArtifactBinding{
			Path:   options.SelectionResultPath,
			SHA256: digestBytes(selectionBytes),
		},
		InputManifest: ArtifactBinding{
			Path:   options.ManifestPath,
			SHA256: digestBytes(manifestBytes),
		},
		SelectionContractDigest: selection.Plan.ContractDigest,
		SelectionWorkloadID:     selection.Plan.Contract.WorkloadID,
		AuditContract:           auditContract,
		SelectedCandidate:       selected,
		AuditTrial:              trial,
	}, nil
}

func ValidateSelectedCNNLiteAutotuneResult(
	selection AdaptiveCNNLiteAutotuneResult,
) (SynthesizedCandidate, error) {
	if selection.ExecutionAdapter != MNISTCNNLiteGraphAdapterV1 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported CNN-lite execution adapter %q",
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
		if err := validateCNNLiteSampleLedger(
			trial,
			selection.Plan.Contract,
		); err != nil {
			return SynthesizedCandidate{}, fmt.Errorf(
				"CNN-lite trial %d sample ledger: %w",
				trial.TrialIndex,
				err,
			)
		}
		if trial.Status == certify.StatusSafe ||
			trial.Status == certify.StatusRejected {
			expected := selection.Plan.Contract.Decision.ValidationSamples *
				trial.KeyRepeatsCompleted
			if trial.EncryptedSampleEvaluations != expected {
				return SynthesizedCandidate{}, fmt.Errorf(
					"CNN-lite trial %d encrypted sample ledger mismatch",
					trial.TrialIndex,
				)
			}
		}
	}
	if encryptedSamples != selection.EncryptedSampleEvaluations {
		return SynthesizedCandidate{}, fmt.Errorf(
			"CNN-lite aggregate encrypted sample ledger mismatch",
		)
	}
	selected, err := ValidateSelectedAutotuneResult(converted)
	if err != nil {
		return SynthesizedCandidate{}, err
	}
	if !reflect.DeepEqual(selected, *selection.Selected) {
		return SynthesizedCandidate{}, fmt.Errorf(
			"CNN-lite selected literal identity changed",
		)
	}
	return selected, nil
}

func validateCNNLiteSampleLedger(
	trial CNNLiteTrialResult,
	contract WorkloadContract,
) error {
	if len(trial.SampleLedger) !=
		trial.EncryptedSampleEvaluations {
		return fmt.Errorf(
			"rows=%d encrypted_sample_evaluations=%d",
			len(trial.SampleLedger),
			trial.EncryptedSampleEvaluations,
		)
	}
	if len(trial.SampleLedger) == 0 &&
		trial.Status != certify.StatusFailed {
		return fmt.Errorf("non-FAILED trial has no sample ledger")
	}
	seen := make(map[string]struct{}, len(trial.SampleLedger))
	flips := 0
	violations := 0
	maxError := 0.0
	maxUsage := 0.0
	for index, sample := range trial.SampleLedger {
		if sample.KeyRun <= 0 ||
			sample.KeyRun > trial.KeyRepeatsCompleted {
			return fmt.Errorf(
				"row %d invalid key run %d",
				index,
				sample.KeyRun,
			)
		}
		key := fmt.Sprintf("%d/%d", sample.KeyRun, sample.RowID)
		if _, exists := seen[key]; exists {
			return fmt.Errorf(
				"duplicate observation %s",
				key,
			)
		}
		seen[key] = struct{}{}
		if sample.SampleID !=
			fmt.Sprintf("mnist_%05d", sample.RowID) {
			return fmt.Errorf(
				"row %d sample identity changed",
				index,
			)
		}
		if !closeFloat(
			sample.Threshold,
			contract.Decision.Threshold,
		) {
			return fmt.Errorf(
				"row %d threshold changed",
				index,
			)
		}
		margin := math.Abs(
			sample.PlainScore - sample.Threshold,
		)
		if !closeFloat(sample.Margin, margin) {
			return fmt.Errorf(
				"row %d margin changed",
				index,
			)
		}
		observedError := math.Abs(
			sample.CKKSScore - sample.PlainScore,
		)
		if !closeFloat(sample.AbsError, observedError) {
			return fmt.Errorf(
				"row %d absolute error changed",
				index,
			)
		}
		certifiable :=
			margin > contract.Decision.MarginFloor
		if sample.Certifiable != certifiable {
			return fmt.Errorf(
				"row %d certifiable flag changed",
				index,
			)
		}
		budget := 0.0
		usage := 0.0
		violation := false
		if certifiable {
			budget = contract.Decision.SafetyFactor * margin
			usage = observedError / budget
			violation = observedError >= budget
		}
		if !closeFloat(sample.ErrorBudget, budget) ||
			!closeFloat(sample.ErrorBudgetUsage, usage) ||
			sample.ErrorViolation != violation {
			return fmt.Errorf(
				"row %d budget observation changed",
				index,
			)
		}
		if sample.PlainDecision !=
			(sample.PlainScore >= sample.Threshold) ||
			sample.CKKSDecision !=
				(sample.CKKSScore >= sample.Threshold) ||
			sample.DecisionFlip !=
				(sample.PlainDecision != sample.CKKSDecision) {
			return fmt.Errorf(
				"row %d decision observation changed",
				index,
			)
		}
		maxError = math.Max(maxError, observedError)
		maxUsage = math.Max(maxUsage, usage)
		if sample.DecisionFlip {
			flips++
		}
		if violation {
			violations++
		}
	}
	if flips != trial.DecisionFlips ||
		violations != trial.ErrorViolations ||
		!closeFloat(maxError, trial.MaxObservedError) ||
		!closeFloat(maxUsage, trial.MaxErrorBudgetUsage) {
		return fmt.Errorf(
			"aggregate mismatch flips=%d/%d violations=%d/%d max_error=%.12g/%.12g max_usage=%.12g/%.12g",
			flips,
			trial.DecisionFlips,
			violations,
			trial.ErrorViolations,
			maxError,
			trial.MaxObservedError,
			maxUsage,
			trial.MaxErrorBudgetUsage,
		)
	}
	return nil
}
