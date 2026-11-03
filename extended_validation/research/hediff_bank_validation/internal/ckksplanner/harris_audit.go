package ckksplanner

import (
	"encoding/csv"
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
	HarrisLockedAuditSchemaVersion = 1
	HarrisLockedAuditPass          = "LOCKED_AUDIT_PASS"
	HarrisLockedAuditFail          = "LOCKED_AUDIT_FAIL"
)

type HarrisLockedAuditOptions struct {
	SelectionResultPath    string
	AuditPath              string
	SourceArchivePath      string
	ExtractionManifestPath string
	KeyRepeats             int
}

type HarrisLockedAuditResult struct {
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
	AuditTrial        HarrisTrialResult    `json:"audit_trial"`
}

type harrisExtractionManifest struct {
	SchemaVersion string `json:"schema_version"`
	Partitions    map[string]struct {
		Path   string `json:"path"`
		SHA256 string `json:"sha256"`
	} `json:"partitions"`
}

func RunLockedHarrisAudit(
	options HarrisLockedAuditOptions,
) (HarrisLockedAuditResult, error) {
	if strings.TrimSpace(options.SelectionResultPath) == "" ||
		strings.TrimSpace(options.AuditPath) == "" ||
		strings.TrimSpace(options.SourceArchivePath) == "" ||
		strings.TrimSpace(options.ExtractionManifestPath) == "" {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris locked audit paths must be non-empty",
		)
	}
	if options.KeyRepeats <= 0 {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris audit key repeats must be positive",
		)
	}

	selectionBytes, err := os.ReadFile(options.SelectionResultPath)
	if err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"read Harris selection: %w",
			err,
		)
	}
	selection := AdaptiveHarrisAutotuneResult{}
	if err := json.Unmarshal(selectionBytes, &selection); err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"parse Harris selection: %w",
			err,
		)
	}
	selected, err := ValidateSelectedHarrisAutotuneResult(selection)
	if err != nil {
		return HarrisLockedAuditResult{}, err
	}
	if err := verifyContractArtifacts(selection.Plan.Contract); err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"verify Harris selection artifacts: %w",
			err,
		)
	}

	manifestBytes, err := os.ReadFile(options.ExtractionManifestPath)
	if err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"read Harris extraction manifest: %w",
			err,
		)
	}
	manifest := harrisExtractionManifest{}
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"parse Harris extraction manifest: %w",
			err,
		)
	}
	if manifest.SchemaVersion != BSDS500HarrisModelSchemaV1 {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris extraction manifest schema changed",
		)
	}
	validationManifest, ok :=
		manifest.Partitions["configuration_validation"]
	if !ok ||
		validationManifest.SHA256 !=
			selection.Plan.Contract.ValidationData.SHA256 {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris selection validation is not bound by extraction manifest",
		)
	}
	auditBytes, err := os.ReadFile(options.AuditPath)
	if err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"read Harris audit CSV: %w",
			err,
		)
	}
	auditManifest, ok := manifest.Partitions["locked_audit_test"]
	if !ok || auditManifest.SHA256 != digestBytes(auditBytes) {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris audit CSV is not bound by extraction manifest",
		)
	}

	validationIDs, err := readCSVRowIDs(
		selection.Plan.Contract.ValidationData.Path,
	)
	if err != nil {
		return HarrisLockedAuditResult{}, err
	}
	auditIDs, err := readCSVRowIDs(options.AuditPath)
	if err != nil {
		return HarrisLockedAuditResult{}, err
	}
	if err := validateDisjointRowIDs(validationIDs, auditIDs); err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris validation/audit row identity: %w",
			err,
		)
	}
	validationImages, err := readCSVIdentityColumn(
		selection.Plan.Contract.ValidationData.Path,
		"image_id",
	)
	if err != nil {
		return HarrisLockedAuditResult{}, err
	}
	auditImages, err := readCSVIdentityColumn(options.AuditPath, "image_id")
	if err != nil {
		return HarrisLockedAuditResult{}, err
	}
	for imageID := range validationImages {
		if _, overlap := auditImages[imageID]; overlap {
			return HarrisLockedAuditResult{}, fmt.Errorf(
				"Harris validation/audit image identity overlaps at %s",
				imageID,
			)
		}
	}

	selectionContract := selection.Plan.Contract
	contractOptions := DefaultPrimaryHarrisContractOptions()
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
	auditContract, err := BuildHarrisWorkloadContract(contractOptions)
	if err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"build Harris locked audit contract: %w",
			err,
		)
	}
	if auditContract.ModelArtifact.SHA256 !=
		selectionContract.ModelArtifact.SHA256 ||
		auditContract.SourceData == nil ||
		selectionContract.SourceData == nil ||
		auditContract.SourceData.SHA256 !=
			selectionContract.SourceData.SHA256 {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"Harris locked audit model/source identity changed",
		)
	}
	trial, err := ExecuteHarrisCandidate(
		auditContract,
		selected,
		1,
	)
	if err != nil {
		return HarrisLockedAuditResult{}, fmt.Errorf(
			"execute Harris locked audit: %w",
			err,
		)
	}
	outcome := HarrisLockedAuditFail
	reason := fmt.Sprintf(
		"locked Harris candidate %s returned status %s",
		selected.ID,
		trial.Status,
	)
	if trial.Status == certify.StatusSafe {
		outcome = HarrisLockedAuditPass
		reason = fmt.Sprintf(
			"locked Harris candidate %s remained SAFE on the disjoint test images",
			selected.ID,
		)
	}
	return HarrisLockedAuditResult{
		SchemaVersion:     HarrisLockedAuditSchemaVersion,
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

func ValidateSelectedHarrisAutotuneResult(
	selection AdaptiveHarrisAutotuneResult,
) (SynthesizedCandidate, error) {
	if selection.ExecutionAdapter !=
		BSDS500HarrisExecutionAdapterV1 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported Harris execution adapter %q",
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
		if err := validateHarrisSampleLedger(
			trial,
			selection.Plan.Contract,
		); err != nil {
			return SynthesizedCandidate{}, fmt.Errorf(
				"Harris trial %d sample ledger: %w",
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
					"Harris trial %d encrypted sample ledger mismatch",
					trial.TrialIndex,
				)
			}
		}
	}
	if encryptedSamples != selection.EncryptedSampleEvaluations {
		return SynthesizedCandidate{}, fmt.Errorf(
			"Harris aggregate encrypted sample ledger mismatch",
		)
	}
	selected, err := ValidateSelectedAutotuneResult(converted)
	if err != nil {
		return SynthesizedCandidate{}, err
	}
	if !reflect.DeepEqual(selected, *selection.Selected) {
		return SynthesizedCandidate{}, fmt.Errorf(
			"Harris selected literal identity changed",
		)
	}
	return selected, nil
}

func validateHarrisSampleLedger(
	trial HarrisTrialResult,
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

	flips := 0
	violations := 0
	maxError := 0.0
	maxUsage := 0.0
	seen := make(
		map[string]struct{},
		len(trial.SampleLedger),
	)
	for index, sample := range trial.SampleLedger {
		if sample.KeyRun <= 0 ||
			sample.KeyRun > trial.KeyRepeatsCompleted {
			return fmt.Errorf(
				"row %d has invalid key run",
				index,
			)
		}
		identity := fmt.Sprintf(
			"%d/%d",
			sample.KeyRun,
			sample.RowID,
		)
		if _, exists := seen[identity]; exists {
			return fmt.Errorf(
				"duplicate key/sample identity %s",
				identity,
			)
		}
		seen[identity] = struct{}{}
		if sample.ImageID == "" ||
			sample.SourcePartition == "" ||
			!closeFloat(
				sample.Threshold,
				contract.Decision.Threshold,
			) {
			return fmt.Errorf(
				"row %d identity changed",
				index,
			)
		}

		margin := math.Abs(
			sample.PlainScore - sample.Threshold,
		)
		observedError := math.Abs(
			sample.CKKSScore - sample.PlainScore,
		)
		certifiable :=
			margin > contract.Decision.MarginFloor
		plainDecision :=
			sample.PlainScore >= sample.Threshold
		ckksDecision :=
			sample.CKKSScore >= sample.Threshold
		if !closeFloat(sample.Margin, margin) ||
			!closeFloat(sample.AbsError, observedError) ||
			sample.Certifiable != certifiable ||
			sample.PlainDecision != plainDecision ||
			sample.CKKSDecision != ckksDecision ||
			sample.DecisionFlip !=
				(plainDecision != ckksDecision) {
			return fmt.Errorf(
				"row %d derived observation changed",
				index,
			)
		}
		if !certifiable {
			if sample.ErrorBudget != 0 ||
				sample.ErrorBudgetUsage != 0 ||
				sample.ErrorViolation {
				return fmt.Errorf(
					"row %d ambiguous budget changed",
					index,
				)
			}
			continue
		}

		budget := contract.Decision.SafetyFactor * margin
		usage := observedError / budget
		violation := observedError >= budget
		if !closeFloat(sample.ErrorBudget, budget) ||
			!closeFloat(sample.ErrorBudgetUsage, usage) ||
			sample.ErrorViolation != violation {
			return fmt.Errorf(
				"row %d budget observation changed",
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

func readCSVIdentityColumn(
	path string,
	column string,
) (map[string]struct{}, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open CSV identity source: %w", err)
	}
	defer file.Close()
	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read CSV identity source: %w", err)
	}
	if len(records) < 2 {
		return nil, fmt.Errorf("CSV identity source has no rows")
	}
	columnIndex := -1
	for index, name := range records[0] {
		if name == column {
			columnIndex = index
			break
		}
	}
	if columnIndex < 0 {
		return nil, fmt.Errorf("CSV identity source has no %s", column)
	}
	values := make(map[string]struct{})
	for rowIndex, record := range records[1:] {
		if columnIndex >= len(record) {
			return nil, fmt.Errorf(
				"CSV identity row %d missing %s",
				rowIndex+2,
				column,
			)
		}
		value := strings.TrimSpace(record[columnIndex])
		if value == "" {
			return nil, fmt.Errorf(
				"CSV identity row %d has empty %s",
				rowIndex+2,
				column,
			)
		}
		values[value] = struct{}{}
	}
	return values, nil
}
