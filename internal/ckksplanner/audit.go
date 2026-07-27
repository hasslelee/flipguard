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
	SplitManifestPath   string
	KeyRepeats          int
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
	selected, err := validateLockedSelection(selection)
	if err != nil {
		return LockedAuditResult{}, err
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

	auditBytes, err := os.ReadFile(options.AuditPath)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read locked audit data: %w",
			err,
		)
	}
	if err := validateLockedSplit(
		selection.Plan.Contract,
		manifest,
		options.AuditPath,
		auditBytes,
	); err != nil {
		return LockedAuditResult{}, err
	}

	validationRowIDs, err := readCSVRowIDs(
		selection.Plan.Contract.ValidationData.Path,
	)
	if err != nil {
		return LockedAuditResult{}, fmt.Errorf(
			"read selection validation row IDs: %w",
			err,
		)
	}
	auditRowIDs, err := readCSVRowIDs(options.AuditPath)
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

	selectionContract := selection.Plan.Contract
	contractOptions := DefaultTabularContractOptions()
	contractOptions.ModelPath =
		selectionContract.ModelArtifact.Path
	contractOptions.ValidationPath = options.AuditPath
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
		selected,
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
		selected.ID,
		trial.Status,
	)
	if trial.Status == certify.StatusSafe {
		outcome = LockedAuditOutcomePass
		reason = fmt.Sprintf(
			"locked candidate %s remained SAFE on disjoint audit with %d fresh key run(s)",
			selected.ID,
			trial.KeyRepeatsCompleted,
		)
	}

	return LockedAuditResult{
		SchemaVersion: LockedAuditResultSchemaVersion,

		Outcome: outcome,
		Reason:  reason,

		RetuningPerformed: false,

		SelectionResult: ArtifactBinding{
			Path:   options.SelectionResultPath,
			SHA256: digestBytes(selectionBytes),
		},
		SplitManifest: ArtifactBinding{
			Path:   options.SplitManifestPath,
			SHA256: digestBytes(manifestBytes),
		},

		SelectionContractDigest: selection.Plan.ContractDigest,
		SelectionWorkloadID:     selection.Plan.Contract.WorkloadID,

		AuditContract: auditContract,

		SelectedCandidate: selected,
		AuditTrial:        trial,
	}, nil
}

func validateLockedSelection(
	selection AdaptiveAutotuneResult,
) (SynthesizedCandidate, error) {
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

	selected := *selection.Selected
	safeMatches := 0
	for _, trial := range selection.Trials {
		if trial.Status == certify.StatusSafe &&
			reflect.DeepEqual(trial.Candidate, selected) {
			safeMatches++
		}
	}
	if safeMatches != 1 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"selected candidate has %d exact SAFE trial matches",
			safeMatches,
		)
	}
	return selected, nil
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
	if manifest.ConfigurationValidation.Path !=
		selectionContract.ValidationData.Path {
		return fmt.Errorf(
			"split manifest validation path %q does not match selection %q",
			manifest.ConfigurationValidation.Path,
			selectionContract.ValidationData.Path,
		)
	}
	if manifest.ConfigurationValidation.CSVDigest !=
		selectionContract.ValidationData.SHA256 {
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
	if selectionContract.ValidationData.SHA256 ==
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
