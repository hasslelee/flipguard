package ckksplanner

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"reflect"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	LockedAuditResultSchemaVersion = 1

	LockedAuditOutcomePass = "LOCKED_AUDIT_PASS"
	LockedAuditOutcomeFail = "LOCKED_AUDIT_FAIL"
)

// LockedAuditOptions identifies an immutable selection and its disjoint audit
// artifact. The selected literal is executed as-is; no synthesis or repair is
// allowed in this path.
type LockedAuditOptions struct {
	SelectionResultPath string
	AuditPath           string
	PreparedAuditPath   string
	AuditDataSpace      TabularDataSpace
	SplitManifestPath   string
	KeyRepeats          int
}

// LockedCandidateSelection is a provider-neutral, already-validated selection
// that can be replayed on a locked audit partition without synthesis.
type LockedCandidateSelection struct {
	SelectionResult ArtifactBinding
	Contract        WorkloadContract
	ContractDigest  string
	Candidate       SynthesizedCandidate
}

// LockedAuditResult records a no-retuning evaluation on a disjoint audit set.
type LockedAuditResult struct {
	SchemaVersion int `json:"schema_version"`

	Outcome string `json:"outcome"`
	Reason  string `json:"reason"`

	RetuningPerformed bool `json:"retuning_performed"`

	SelectionResult ArtifactBinding `json:"selection_result"`
	SplitManifest   ArtifactBinding `json:"split_manifest"`

	SelectionContractDigest string `json:"selection_contract_digest"`
	SelectionWorkloadID     string `json:"selection_workload_id"`

	AuditContract WorkloadContract `json:"audit_contract"`

	SelectedCandidate SynthesizedCandidate `json:"selected_candidate"`
	AuditTrial        TabularTrialResult   `json:"audit_trial"`
}

type lockedSplitManifest struct {
	SchemaVersion int    `json:"schema_version"`
	SplitSeed     int    `json:"split_seed"`
	DatasetID     string `json:"dataset_id"`
	ModelID       string `json:"model_id"`

	ModelArtifactDigest string `json:"model_artifact_digest"`

	ConfigurationValidation lockedSplitPartition `json:"configuration_validation"`
	LockedAuditTest         lockedSplitPartition `json:"locked_audit_test"`
}

type lockedSplitPartition struct {
	Path      string   `json:"path"`
	CSVDigest string   `json:"csv_digest"`
	RowIDs    []string `json:"row_ids"`
}

// RunLockedTabularAudit executes the selected candidate on the declared audit
// partition with fresh keys. It never invokes Synthesize or RepairCandidate.
func RunLockedTabularAudit(
	options LockedAuditOptions,
) (LockedAuditResult, error) {
	if strings.TrimSpace(options.SelectionResultPath) == "" {
		return LockedAuditResult{}, fmt.Errorf(
			"selection result path is empty",
		)
	}
	if strings.TrimSpace(options.AuditPath) == "" {
		return LockedAuditResult{}, fmt.Errorf("audit path is empty")
	}
	if strings.TrimSpace(options.SplitManifestPath) == "" {
		return LockedAuditResult{}, fmt.Errorf(
			"split manifest path is empty",
		)
	}
	if options.KeyRepeats <= 0 {
		return LockedAuditResult{}, fmt.Errorf(
			"audit key repeats must be positive",
		)
	}

	selectionBytes, err := os.ReadFile(options.SelectionResultPath)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read selection result: %w",
			err,
		)
	}
	selection := AdaptiveAutotuneResult{}
	if err := json.Unmarshal(selectionBytes, &selection); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"parse selection result: %w",
			err,
		)
	}
	selected, err := ValidateSelectedAutotuneResult(selection)
	if err != nil {
		return LockedAuditResult{}, err
	}
	if err := verifyContractArtifacts(selection.Plan.Contract); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"verify selection artifacts: %w",
			err,
		)
	}

	return runLockedTabularCandidateAudit(
		LockedCandidateSelection{
			SelectionResult: ArtifactBinding{
				Path:   options.SelectionResultPath,
				SHA256: digestBytes(selectionBytes),
			},
			Contract:       selection.Plan.Contract,
			ContractDigest: selection.Plan.ContractDigest,
			Candidate:      selected,
		},
		options,
		selectionBytes,
	)
}

// RunLockedTabularCandidateAudit replays one provider-neutral candidate on a
// declared disjoint audit split. Callers must validate how the candidate was
// selected before constructing LockedCandidateSelection.
func RunLockedTabularCandidateAudit(
	selection LockedCandidateSelection,
	options LockedAuditOptions,
) (LockedAuditResult, error) {
	if strings.TrimSpace(selection.SelectionResult.Path) == "" {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate selection result path is empty",
		)
	}
	if options.SelectionResultPath !=
		selection.SelectionResult.Path {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate selection result path mismatch",
		)
	}
	selectionBytes, err := os.ReadFile(
		selection.SelectionResult.Path,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read locked candidate selection result: %w",
			err,
		)
	}
	if digestBytes(selectionBytes) !=
		selection.SelectionResult.SHA256 {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate selection result digest mismatch",
		)
	}
	if err := selection.Contract.Validate(); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"validate locked candidate selection contract: %w",
			err,
		)
	}
	contractDigest, err := digestContract(selection.Contract)
	if err != nil {
		return LockedAuditResult{}, err
	}
	if contractDigest != selection.ContractDigest {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate selection contract digest mismatch",
		)
	}
	if err := verifyContractArtifacts(selection.Contract); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"verify locked candidate selection artifacts: %w",
			err,
		)
	}
	if _, err := selection.Candidate.Profile(); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"validate locked candidate literal: %w",
			err,
		)
	}
	securityPolicy := DefaultSecurityEnvelope()
	security, err := AssessLiteralSecurity(
		selection.Candidate.Parameters,
		selection.Contract.Deployment.SecurityBits,
		securityPolicy,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"assess locked candidate security: %w",
			err,
		)
	}
	if security.FinalAdmission != SecurityAdmissionPass ||
		!reflect.DeepEqual(security, selection.Candidate.Security) {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate Security V2 metadata mismatch",
		)
	}
	pathAllowed := false
	for _, allowed := range selection.Contract.Deployment.AllowedPaths {
		if allowed == selection.Candidate.Path {
			pathAllowed = true
			break
		}
	}
	if !pathAllowed {
		return LockedAuditResult{}, fmt.Errorf(
			"locked candidate path %q is outside selection contract",
			selection.Candidate.Path,
		)
	}

	return runLockedTabularCandidateAudit(
		selection,
		options,
		selectionBytes,
	)
}

func runLockedTabularCandidateAudit(
	selection LockedCandidateSelection,
	options LockedAuditOptions,
	selectionBytes []byte,
) (LockedAuditResult, error) {
	if strings.TrimSpace(options.AuditPath) == "" {
		return LockedAuditResult{}, fmt.Errorf("audit path is empty")
	}
	if strings.TrimSpace(options.SplitManifestPath) == "" {
		return LockedAuditResult{}, fmt.Errorf(
			"split manifest path is empty",
		)
	}
	if options.KeyRepeats <= 0 {
		return LockedAuditResult{}, fmt.Errorf(
			"audit key repeats must be positive",
		)
	}

	manifestBytes, err := os.ReadFile(options.SplitManifestPath)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read split manifest: %w",
			err,
		)
	}
	manifest := lockedSplitManifest{}
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"parse split manifest: %w",
			err,
		)
	}

	auditSourcePath := options.AuditPath
	activeAuditPath := auditSourcePath
	if strings.TrimSpace(options.PreparedAuditPath) != "" {
		dataSpace := options.AuditDataSpace
		if dataSpace == "" {
			dataSpace = TabularDataSpaceAuto
		}
		if _, err := MaterializeTabularValidationWithOptions(
			selection.Contract.ModelArtifact.Path,
			auditSourcePath,
			options.PreparedAuditPath,
			TabularMaterializationOptions{
				DataSpace: dataSpace,
			},
		); err != nil {
			return LockedAuditResult{}, fmt.Errorf(
				"materialize locked audit data: %w",
				err,
			)
		}
		activeAuditPath = options.PreparedAuditPath
	} else if options.AuditDataSpace != "" &&
		options.AuditDataSpace != TabularDataSpaceAuto {
		return LockedAuditResult{}, fmt.Errorf(
			"audit data space requires a prepared audit path",
		)
	}

	auditSourceBytes, err := os.ReadFile(auditSourcePath)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read locked audit source data: %w",
			err,
		)
	}
	if err := validateLockedSplit(
		selection.Contract,
		manifest,
		auditSourcePath,
		auditSourceBytes,
	); err != nil {
		return LockedAuditResult{}, err
	}

	validationRowIDs, err := readCSVRowIDs(
		selection.Contract.ValidationData.Path,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read selection validation row IDs: %w",
			err,
		)
	}
	auditRowIDs, err := readCSVRowIDs(activeAuditPath)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read locked audit row IDs: %w",
			err,
		)
	}
	if err := validateDisjointRowIDs(
		validationRowIDs,
		auditRowIDs,
	); err != nil {
		return LockedAuditResult{}, err
	}
	manifestValidationRowIDs, err := stringSet(
		manifest.ConfigurationValidation.RowIDs,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"split manifest validation row IDs: %w",
			err,
		)
	}
	manifestAuditRowIDs, err := stringSet(
		manifest.LockedAuditTest.RowIDs,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"split manifest audit row IDs: %w",
			err,
		)
	}
	if !equalStringSets(validationRowIDs, manifestValidationRowIDs) {
		return LockedAuditResult{}, fmt.Errorf(
			"actual selection validation row IDs do not match split manifest",
		)
	}
	if !equalStringSets(auditRowIDs, manifestAuditRowIDs) {
		return LockedAuditResult{}, fmt.Errorf(
			"actual locked audit row IDs do not match split manifest",
		)
	}

	selectionContract := selection.Contract
	contractOptions := DefaultTabularContractOptions()
	contractOptions.ModelPath =
		selectionContract.ModelArtifact.Path
	contractOptions.ValidationPath = activeAuditPath
	if activeAuditPath != auditSourcePath {
		contractOptions.SourceDataPath = auditSourcePath
	}
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
		[]tuner.ExecutionPath{selection.Candidate.Path}

	auditContract, err :=
		BuildTabularWorkloadContract(contractOptions)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"build locked audit contract: %w",
			err,
		)
	}
	if auditContract.ModelArtifact.SHA256 !=
		selectionContract.ModelArtifact.SHA256 {
		return LockedAuditResult{}, fmt.Errorf(
			"locked audit model digest does not match selection",
		)
	}

	trial, err := ExecuteTabularCandidate(
		auditContract,
		selection.Candidate,
		1,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"execute locked audit: %w",
			err,
		)
	}

	outcome := LockedAuditOutcomeFail
	reason := fmt.Sprintf(
		"locked candidate %s returned status %s on disjoint audit",
		selection.Candidate.ID,
		trial.Status,
	)
	if trial.Status == certify.StatusSafe {
		outcome = LockedAuditOutcomePass
		reason = fmt.Sprintf(
			"locked candidate %s remained SAFE on disjoint audit with %d fresh key run(s)",
			selection.Candidate.ID,
			trial.KeyRepeatsCompleted,
		)
	}

	return LockedAuditResult{
		SchemaVersion: LockedAuditResultSchemaVersion,

		Outcome: outcome,
		Reason:  reason,

		RetuningPerformed: false,

		SelectionResult: selection.SelectionResult,
		SplitManifest: ArtifactBinding{
			Path:   options.SplitManifestPath,
			SHA256: digestBytes(manifestBytes),
		},

		SelectionContractDigest: selection.ContractDigest,
		SelectionWorkloadID:     selection.Contract.WorkloadID,

		AuditContract: auditContract,

		SelectedCandidate: selection.Candidate,
		AuditTrial:        trial,
	}, nil
}

// ValidateSelectedAutotuneResult deterministically reproduces a serialized
// adaptive result's synthesis plan, repair chain, trial ledger, and final SAFE
// candidate before a locked audit may consume it.
func ValidateSelectedAutotuneResult(
	selection AdaptiveAutotuneResult,
) (SynthesizedCandidate, error) {
	if selection.SchemaVersion != SynthesisPlanSchemaVersion {
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported selection result schema version %d",
			selection.SchemaVersion,
		)
	}
	if selection.Outcome != AdaptiveOutcomeSelected ||
		selection.Selected == nil {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selection result has no selected candidate",
		)
	}
	if err := selection.Plan.Contract.Validate(); err != nil {
		return SynthesizedCandidate{}, fmt.Errorf(
			"validate selection contract: %w",
			err,
		)
	}
	digest, err := digestContract(selection.Plan.Contract)
	if err != nil {
		return SynthesizedCandidate{}, err
	}
	if digest != selection.Plan.ContractDigest {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selection contract digest mismatch",
		)
	}

	reproducedPlan, err := Synthesize(
		selection.Plan.Contract,
		selection.Plan.Policy,
	)
	if err != nil {
		return SynthesizedCandidate{}, fmt.Errorf(
			"reproduce selection synthesis plan: %w",
			err,
		)
	}
	if !reflect.DeepEqual(reproducedPlan, selection.Plan) {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selection synthesis plan does not reproduce",
		)
	}
	if selection.TrialsUsed != len(selection.Trials) ||
		selection.TrialsUsed == 0 ||
		selection.TrialsUsed >
			selection.Plan.Contract.Deployment.MaxEncryptedTrials {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selection trial ledger mismatch: trials_used=%d records=%d budget=%d",
			selection.TrialsUsed,
			len(selection.Trials),
			selection.Plan.Contract.Deployment.MaxEncryptedTrials,
		)
	}

	selected := *selection.Selected
	expectedCandidate := selection.Plan.InitialCandidates[0]
	encryptedKeyRuns := 0
	for index, trial := range selection.Trials {
		expectedTrialIndex := index + 1
		if trial.TrialIndex != expectedTrialIndex {
			return SynthesizedCandidate{}, fmt.Errorf(
				"selection trial %d records trial_index=%d",
				expectedTrialIndex,
				trial.TrialIndex,
			)
		}
		if !reflect.DeepEqual(
			trial.Candidate,
			expectedCandidate,
		) {
			return SynthesizedCandidate{}, fmt.Errorf(
				"selection trial %d candidate does not reproduce",
				expectedTrialIndex,
			)
		}
		if trial.KeyRepeatsRequested !=
			selection.Plan.Contract.Deployment.
				ValidationKeyRepeats ||
			trial.KeyRepeatsCompleted < 0 ||
			trial.KeyRepeatsCompleted >
				trial.KeyRepeatsRequested {
			return SynthesizedCandidate{}, fmt.Errorf(
				"selection trial %d key-repeat ledger mismatch",
				expectedTrialIndex,
			)
		}
		encryptedKeyRuns += trial.KeyRepeatsCompleted

		isFinal := index == len(selection.Trials)-1
		if isFinal {
			if trial.Status != certify.StatusSafe ||
				!reflect.DeepEqual(
					trial.Candidate,
					selected,
				) {
				return SynthesizedCandidate{}, fmt.Errorf(
					"selection final trial is not the selected SAFE candidate",
				)
			}
			if err := validateSelectionTrialState(
				trial,
				selection.Plan.Contract,
			); err != nil {
				return SynthesizedCandidate{}, fmt.Errorf(
					"selection trial %d: %w",
					expectedTrialIndex,
					err,
				)
			}
			continue
		}
		if trial.Status == certify.StatusSafe {
			return SynthesizedCandidate{}, fmt.Errorf(
				"selection contains a SAFE trial before the final selection",
			)
		}
		if err := validateSelectionTrialState(
			trial,
			selection.Plan.Contract,
		); err != nil {
			return SynthesizedCandidate{}, fmt.Errorf(
				"selection trial %d: %w",
				expectedTrialIndex,
				err,
			)
		}
		next, err := RepairCandidate(
			selection.Plan,
			expectedCandidate,
			trial.FailureSignal,
			expectedTrialIndex,
		)
		if err != nil {
			return SynthesizedCandidate{}, fmt.Errorf(
				"reproduce repair after selection trial %d: %w",
				expectedTrialIndex,
				err,
			)
		}
		expectedCandidate = next
	}
	if encryptedKeyRuns != selection.EncryptedKeyRuns {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selection encrypted-key ledger mismatch: recorded=%d reproduced=%d",
			selection.EncryptedKeyRuns,
			encryptedKeyRuns,
		)
	}
	return selected, nil
}

func validateSelectionTrialState(
	trial TabularTrialResult,
	contract WorkloadContract,
) error {
	switch trial.Status {
	case certify.StatusSafe:
		if trial.FailureSignal != "" ||
			trial.Failure != "" ||
			trial.Assurance !=
				certify.AssuranceObservedValidation ||
			trial.KeyRepeatsCompleted !=
				trial.KeyRepeatsRequested ||
			trial.SuccessRuns !=
				trial.KeyRepeatsRequested ||
			trial.DecisionFlips != 0 ||
			trial.ErrorViolations != 0 ||
			trial.VCert !=
				contract.Decision.CertifiableSamples ||
			trial.VAmb !=
				contract.Decision.AmbiguousSamples {
			return fmt.Errorf(
				"SAFE trial evidence is internally inconsistent",
			)
		}

	case certify.StatusRejected:
		if trial.FailureSignal != RepairNumericalReject ||
			trial.Failure != "" ||
			trial.Assurance != certify.AssuranceNone ||
			trial.KeyRepeatsCompleted !=
				trial.KeyRepeatsRequested ||
			trial.SuccessRuns !=
				trial.KeyRepeatsRequested ||
			trial.DecisionFlips+
				trial.ErrorViolations == 0 ||
			trial.VCert !=
				contract.Decision.CertifiableSamples ||
			trial.VAmb !=
				contract.Decision.AmbiguousSamples {
			return fmt.Errorf(
				"REJECTED trial evidence is internally inconsistent",
			)
		}

	case certify.StatusFailed:
		if trial.FailureSignal != RepairLevelFailure ||
			strings.TrimSpace(trial.Failure) == "" ||
			trial.Assurance != certify.AssuranceNone ||
			trial.SuccessRuns != 0 {
			return fmt.Errorf(
				"FAILED trial evidence is internally inconsistent",
			)
		}

	case certify.StatusAmbiguous:
		return fmt.Errorf(
			"AMBIGUOUS trial cannot precede a selected result",
		)

	default:
		return fmt.Errorf(
			"unsupported trial status %q",
			trial.Status,
		)
	}
	return nil
}

func validateLockedSplit(
	selectionContract WorkloadContract,
	manifest lockedSplitManifest,
	auditPath string,
	auditBytes []byte,
) error {
	if manifest.SchemaVersion != 1 {
		return fmt.Errorf(
			"unsupported split manifest schema version %d",
			manifest.SchemaVersion,
		)
	}
	if manifest.DatasetID != selectionContract.DatasetID ||
		manifest.ModelID != selectionContract.ModelID {
		return fmt.Errorf(
			"split manifest workload %s/%s does not match selection %s/%s",
			manifest.DatasetID,
			manifest.ModelID,
			selectionContract.DatasetID,
			selectionContract.ModelID,
		)
	}
	if manifest.ModelArtifactDigest !=
		selectionContract.ModelArtifact.SHA256 {
		return fmt.Errorf(
			"split manifest model digest does not match selection",
		)
	}
	expectedSplitID := fmt.Sprintf(
		"split_seed_%d",
		manifest.SplitSeed,
	)
	if selectionContract.SplitID != expectedSplitID {
		return fmt.Errorf(
			"split manifest seed implies %q, selection uses %q",
			expectedSplitID,
			selectionContract.SplitID,
		)
	}
	selectionPartition := selectionContract.ValidationData
	if selectionContract.SourceData != nil {
		selectionPartition = *selectionContract.SourceData
	}
	if manifest.ConfigurationValidation.Path !=
		selectionPartition.Path {
		return fmt.Errorf(
			"split manifest validation path %q does not match selection %q",
			manifest.ConfigurationValidation.Path,
			selectionPartition.Path,
		)
	}
	if manifest.ConfigurationValidation.CSVDigest !=
		selectionPartition.SHA256 {
		return fmt.Errorf(
			"split manifest validation digest does not match selection",
		)
	}
	if manifest.LockedAuditTest.Path != auditPath {
		return fmt.Errorf(
			"split manifest audit path %q does not match %q",
			manifest.LockedAuditTest.Path,
			auditPath,
		)
	}
	actualAuditDigest := digestBytes(auditBytes)
	if manifest.LockedAuditTest.CSVDigest != actualAuditDigest {
		return fmt.Errorf(
			"split manifest audit digest %s does not match actual %s",
			manifest.LockedAuditTest.CSVDigest,
			actualAuditDigest,
		)
	}
	if selectionPartition.SHA256 ==
		actualAuditDigest {
		return fmt.Errorf(
			"locked audit artifact is identical to selection validation",
		)
	}

	manifestValidation, err := stringSet(
		manifest.ConfigurationValidation.RowIDs,
	)
	if err != nil {
		return fmt.Errorf(
			"split manifest validation row IDs: %w",
			err,
		)
	}
	manifestAudit, err := stringSet(
		manifest.LockedAuditTest.RowIDs,
	)
	if err != nil {
		return fmt.Errorf(
			"split manifest audit row IDs: %w",
			err,
		)
	}
	if err := validateDisjointRowIDs(
		manifestValidation,
		manifestAudit,
	); err != nil {
		return fmt.Errorf(
			"split manifest partitions: %w",
			err,
		)
	}
	return nil
}

func readCSVRowIDs(path string) (map[string]struct{}, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()

	reader := csv.NewReader(handle)
	header, err := reader.Read()
	if err != nil {
		return nil, err
	}
	rowIDIndex := -1
	for index, name := range header {
		if name == "row_id" {
			rowIDIndex = index
			break
		}
	}
	if rowIDIndex < 0 {
		return nil, fmt.Errorf("CSV has no row_id column")
	}

	ids := make(map[string]struct{})
	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		if rowIDIndex >= len(record) {
			return nil, fmt.Errorf("CSV row is missing row_id")
		}
		rowID := strings.TrimSpace(record[rowIDIndex])
		if rowID == "" {
			return nil, fmt.Errorf("CSV contains empty row_id")
		}
		if _, exists := ids[rowID]; exists {
			return nil, fmt.Errorf(
				"CSV contains duplicate row_id %q",
				rowID,
			)
		}
		ids[rowID] = struct{}{}
	}
	if len(ids) == 0 {
		return nil, fmt.Errorf("CSV contains no rows")
	}
	return ids, nil
}

func validateDisjointRowIDs(
	left map[string]struct{},
	right map[string]struct{},
) error {
	for rowID := range left {
		if _, overlaps := right[rowID]; overlaps {
			return fmt.Errorf(
				"validation and locked audit overlap at row_id %q",
				rowID,
			)
		}
	}
	return nil
}

func stringSet(
	values []string,
) (map[string]struct{}, error) {
	result := make(map[string]struct{}, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" {
			return nil, fmt.Errorf("contains an empty row ID")
		}
		if _, exists := result[value]; exists {
			return nil, fmt.Errorf(
				"contains duplicate row ID %q",
				value,
			)
		}
		result[value] = struct{}{}
	}
	if len(result) == 0 {
		return nil, fmt.Errorf("contains no row IDs")
	}
	return result, nil
}

func equalStringSets(
	left map[string]struct{},
	right map[string]struct{},
) bool {
	if len(left) != len(right) {
		return false
	}
	for value := range left {
		if _, exists := right[value]; !exists {
			return false
		}
	}
	return true
}
