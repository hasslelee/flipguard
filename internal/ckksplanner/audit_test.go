package ckksplanner

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func TestRunLockedTabularAuditPassesWithoutRetuning(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	selectionPath, selection := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{3, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		validationPath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"3", "4", "5"},
	)

	result, err := RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          2,
		},
	)
	if err != nil {
		t.Fatalf("run locked audit: %v", err)
	}
	if result.Outcome != LockedAuditOutcomePass {
		t.Fatalf(
			"expected PASS, got %s: %s",
			result.Outcome,
			result.Reason,
		)
	}
	if result.RetuningPerformed {
		t.Fatal("locked audit reported retuning")
	}
	if !reflect.DeepEqual(
		result.SelectedCandidate,
		*selection.Selected,
	) {
		t.Fatal("locked audit changed the selected candidate")
	}
	if result.AuditTrial.KeyRepeatsRequested != 2 ||
		result.AuditTrial.KeyRepeatsCompleted != 2 ||
		result.AuditTrial.SuccessRuns != 2 {
		t.Fatalf(
			"unexpected audit key evidence: %+v",
			result.AuditTrial,
		)
	}
	if result.AuditContract.ValidationData.SHA256 ==
		selection.Plan.Contract.ValidationData.SHA256 {
		t.Fatal("audit reused configuration-validation data")
	}
}

func TestRunLockedTabularCandidateAuditPassesWithoutSynthesis(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	selectionPath, selection := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)
	selectionBytes, err := os.ReadFile(selectionPath)
	if err != nil {
		t.Fatalf("read selection fixture: %v", err)
	}
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{3, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		validationPath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"3", "4", "5"},
	)

	result, err := RunLockedTabularCandidateAudit(
		LockedCandidateSelection{
			SelectionResult: ArtifactBinding{
				Path:   selectionPath,
				SHA256: digestBytes(selectionBytes),
			},
			Contract:       selection.Plan.Contract,
			ContractDigest: selection.Plan.ContractDigest,
			Candidate:      *selection.Selected,
		},
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          2,
		},
	)
	if err != nil {
		t.Fatalf("run provider-neutral locked audit: %v", err)
	}
	if result.Outcome != LockedAuditOutcomePass ||
		result.RetuningPerformed ||
		!reflect.DeepEqual(
			result.SelectedCandidate,
			*selection.Selected,
		) {
		t.Fatalf("unexpected provider-neutral audit result: %+v", result)
	}
}

func TestRunLockedTabularAuditAcceptsReplayVerifiedMaterialization(
	t *testing.T,
) {
	modelPath, sourcePath := writeLinearFixture(t, false)
	preparedPath := filepath.Join(
		filepath.Dir(modelPath),
		"prepared_validation.csv",
	)
	if _, err := MaterializeTabularValidationWithOptions(
		modelPath,
		sourcePath,
		preparedPath,
		TabularMaterializationOptions{
			DataSpace: TabularDataSpaceModelInput,
		},
	); err != nil {
		t.Fatalf("materialize validation fixture: %v", err)
	}
	selectionPath, selection := writeSelectionFixtureWithSource(
		t,
		modelPath,
		preparedPath,
		sourcePath,
	)
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{3, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		sourcePath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"3", "4", "5"},
	)
	preparedAuditPath := filepath.Join(
		filepath.Dir(modelPath),
		"prepared_locked_audit.csv",
	)

	result, err := RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			PreparedAuditPath:   preparedAuditPath,
			AuditDataSpace:      TabularDataSpaceModelInput,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          1,
		},
	)
	if err != nil {
		t.Fatalf("run materialized locked audit: %v", err)
	}
	if result.Outcome != LockedAuditOutcomePass {
		t.Fatalf(
			"expected materialized PASS, got %s: %s",
			result.Outcome,
			result.Reason,
		)
	}
	if selection.Plan.Contract.SourceData == nil ||
		selection.Plan.Contract.InputMaterialization == nil ||
		!selection.Plan.Contract.InputMaterialization.
			SourceReplayVerified {
		t.Fatal("selection did not bind verified source replay")
	}
	if result.AuditContract.SourceData == nil ||
		result.AuditContract.SourceData.Path != auditPath ||
		result.AuditContract.ValidationData.Path !=
			preparedAuditPath ||
		result.AuditContract.InputMaterialization == nil ||
		!result.AuditContract.InputMaterialization.
			SourceReplayVerified {
		t.Fatal("audit did not bind verified source replay")
	}
}

func TestRunLockedTabularAuditRejectsMutatedSelectionSource(
	t *testing.T,
) {
	modelPath, sourcePath := writeLinearFixture(t, false)
	preparedPath := filepath.Join(
		filepath.Dir(modelPath),
		"prepared_validation.csv",
	)
	if _, err := MaterializeTabularValidationWithOptions(
		modelPath,
		sourcePath,
		preparedPath,
		TabularMaterializationOptions{
			DataSpace: TabularDataSpaceModelInput,
		},
	); err != nil {
		t.Fatalf("materialize validation fixture: %v", err)
	}
	selectionPath, _ := writeSelectionFixtureWithSource(
		t,
		modelPath,
		preparedPath,
		sourcePath,
	)
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{3, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		sourcePath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"3", "4", "5"},
	)
	sourceBytes, err := os.ReadFile(sourcePath)
	if err != nil {
		t.Fatalf("read source fixture: %v", err)
	}
	if err := os.WriteFile(
		sourcePath,
		append(sourceBytes, '\n'),
		0o600,
	); err != nil {
		t.Fatalf("mutate source fixture: %v", err)
	}

	_, err = RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          1,
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "source data digest changed") {
		t.Fatalf(
			"expected mutated source rejection, got %v",
			err,
		)
	}
}

func TestRunLockedTabularAuditRejectsRowOverlap(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	selectionPath, _ := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{0, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		validationPath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"0", "4", "5"},
	)

	_, err := RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          1,
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "overlap at row_id") {
		t.Fatalf("expected overlap rejection, got %v", err)
	}
}

func TestValidateSelectedAutotuneResultRejectsMutations(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	_, valid := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)

	tests := []struct {
		name       string
		mutate     func(*AdaptiveAutotuneResult)
		wantReason string
	}{
		{
			name: "result schema",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.SchemaVersion++
			},
			wantReason: "selection result schema version",
		},
		{
			name: "contract",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Plan.Contract.Decision.OutputErrorBudget *= 0.5
			},
			wantReason: "selection contract digest mismatch",
		},
		{
			name: "policy",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Plan.Policy.MinScaleBits++
			},
			wantReason: "synthesis plan does not reproduce",
		},
		{
			name: "candidate and matching trial",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Plan.InitialCandidates[0].ID += "_mutated"
				result.Trials[0].Candidate.ID += "_mutated"
				result.Selected.ID += "_mutated"
			},
			wantReason: "synthesis plan does not reproduce",
		},
		{
			name: "trial count",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.TrialsUsed++
			},
			wantReason: "trial ledger mismatch",
		},
		{
			name: "trial index",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Trials[0].TrialIndex++
			},
			wantReason: "records trial_index",
		},
		{
			name: "key repeats",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Trials[0].KeyRepeatsRequested++
			},
			wantReason: "key-repeat ledger mismatch",
		},
		{
			name: "final status",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.Trials[len(result.Trials)-1].Status =
					"REJECTED"
			},
			wantReason: "final trial is not the selected SAFE candidate",
		},
		{
			name: "encrypted key count",
			mutate: func(result *AdaptiveAutotuneResult) {
				result.EncryptedKeyRuns++
			},
			wantReason: "encrypted-key ledger mismatch",
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			mutated := cloneAdaptiveResult(t, valid)
			test.mutate(&mutated)
			_, err := ValidateSelectedAutotuneResult(mutated)
			if err == nil ||
				!strings.Contains(
					err.Error(),
					test.wantReason,
				) {
				t.Fatalf(
					"expected %q rejection, got %v",
					test.wantReason,
					err,
				)
			}
		})
	}
}

func TestValidateSelectedAutotuneResultAcceptsReproducedRepair(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	_, valid := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)
	repaired, err := RepairCandidate(
		valid.Plan,
		valid.Plan.InitialCandidates[0],
		RepairNumericalReject,
		1,
	)
	if err != nil {
		t.Fatalf("build repair fixture: %v", err)
	}

	rejected := valid.Trials[0]
	rejected.Status = "REJECTED"
	rejected.Assurance = "NONE"
	rejected.FailureSignal = RepairNumericalReject
	rejected.DecisionFlips = 1
	rejected.ErrorViolations = 1

	safe := valid.Trials[0]
	safe.TrialIndex = 2
	safe.Candidate = repaired

	valid.Trials = []TabularTrialResult{rejected, safe}
	valid.TrialsUsed = 2
	valid.EncryptedKeyRuns =
		rejected.KeyRepeatsCompleted +
			safe.KeyRepeatsCompleted
	valid.Selected = &repaired

	selected, err := ValidateSelectedAutotuneResult(valid)
	if err != nil {
		t.Fatalf("validate reproduced repair ledger: %v", err)
	}
	if !reflect.DeepEqual(selected, repaired) {
		t.Fatal("validated repair candidate changed")
	}

	mutated := cloneAdaptiveResult(t, valid)
	mutated.Trials[0].FailureSignal = RepairLevelFailure
	_, err = ValidateSelectedAutotuneResult(mutated)
	if err == nil ||
		!strings.Contains(
			err.Error(),
			"REJECTED trial evidence",
		) {
		t.Fatalf(
			"expected repair-signal mutation rejection, got %v",
			err,
		)
	}
}

func TestRunLockedTabularAuditRejectsMutatedAuditArtifact(
	t *testing.T,
) {
	modelPath, validationPath := writeLinearFixture(t, false)
	selectionPath, _ := writeSelectionFixture(
		t,
		modelPath,
		validationPath,
	)
	auditPath := writeAuditCSVFixture(
		t,
		filepath.Dir(modelPath),
		[]int{3, 4, 5},
	)
	manifestPath := writeSplitManifestFixture(
		t,
		modelPath,
		validationPath,
		auditPath,
		[]string{"0", "1", "2"},
		[]string{"3", "4", "5"},
	)
	auditBytes, err := os.ReadFile(auditPath)
	if err != nil {
		t.Fatalf("read audit fixture: %v", err)
	}
	if err := os.WriteFile(
		auditPath,
		append(auditBytes, '\n'),
		0o600,
	); err != nil {
		t.Fatalf("mutate audit fixture: %v", err)
	}

	_, err = RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          1,
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "audit digest") {
		t.Fatalf(
			"expected mutated audit digest rejection, got %v",
			err,
		)
	}
}

func TestRunLockedTabularAuditRejectsMalformedSelectionJSON(
	t *testing.T,
) {
	root := t.TempDir()
	selectionPath := filepath.Join(root, "selection.json")
	auditPath := filepath.Join(root, "audit.csv")
	manifestPath := filepath.Join(root, "manifest.json")
	if err := os.WriteFile(
		selectionPath,
		[]byte("{not-json\n"),
		0o600,
	); err != nil {
		t.Fatalf("write malformed selection: %v", err)
	}

	_, err := RunLockedTabularAudit(
		LockedAuditOptions{
			SelectionResultPath: selectionPath,
			AuditPath:           auditPath,
			SplitManifestPath:   manifestPath,
			KeyRepeats:          1,
		},
	)
	if err == nil ||
		!strings.Contains(err.Error(), "parse selection result") {
		t.Fatalf(
			"expected malformed selection rejection, got %v",
			err,
		)
	}
}

func cloneAdaptiveResult(
	t *testing.T,
	value AdaptiveAutotuneResult,
) AdaptiveAutotuneResult {
	t.Helper()

	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("marshal adaptive result clone: %v", err)
	}
	cloned := AdaptiveAutotuneResult{}
	if err := json.Unmarshal(encoded, &cloned); err != nil {
		t.Fatalf("unmarshal adaptive result clone: %v", err)
	}
	return cloned
}

func writeSelectionFixture(
	t *testing.T,
	modelPath string,
	validationPath string,
) (string, AdaptiveAutotuneResult) {
	return writeSelectionFixtureWithSource(
		t,
		modelPath,
		validationPath,
		"",
	)
}

func writeSelectionFixtureWithSource(
	t *testing.T,
	modelPath string,
	validationPath string,
	sourcePath string,
) (string, AdaptiveAutotuneResult) {
	t.Helper()

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = sourcePath
	options.SplitID = "split_seed_0"
	options.MarginFloor = 0.01
	options.MaxEncryptedTrials = 2
	options.ValidationKeyRepeats = 1

	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build selection contract: %v", err)
	}
	plan, err := Synthesize(contract, DefaultSynthesisPolicy())
	if err != nil {
		t.Fatalf("synthesize selection: %v", err)
	}
	selection, err := RunAdaptiveTabularAutotune(plan)
	if err != nil {
		t.Fatalf("run selection: %v", err)
	}
	if selection.Outcome != AdaptiveOutcomeSelected {
		t.Fatalf(
			"fixture did not select: %s",
			selection.Reason,
		)
	}

	encoded, err := json.MarshalIndent(selection, "", "  ")
	if err != nil {
		t.Fatalf("marshal selection: %v", err)
	}
	selectionPath := filepath.Join(
		filepath.Dir(modelPath),
		"selection.json",
	)
	if err := os.WriteFile(
		selectionPath,
		append(encoded, '\n'),
		0o600,
	); err != nil {
		t.Fatalf("write selection: %v", err)
	}
	return selectionPath, selection
}

func writeAuditCSVFixture(
	t *testing.T,
	root string,
	rowIDs []int,
) string {
	t.Helper()
	if len(rowIDs) != 3 {
		t.Fatalf("audit fixture requires three row IDs")
	}

	values := []float64{-0.8, 0.6, 1.2}
	contents :=
		"row_id,label,raw_logit,scaled_logit,polynomial_score,plaintext_decision,x_0\n"
	for index, value := range values {
		score := linearFixtureScore(value)
		contents += fmt.Sprintf(
			"%d,1,0,0,%.15g,%t,%.15g\n",
			rowIDs[index],
			score,
			score >= 0.5,
			value,
		)
	}

	path := filepath.Join(root, "locked_audit_test.csv")
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatalf("write audit CSV: %v", err)
	}
	return path
}

func writeSplitManifestFixture(
	t *testing.T,
	modelPath string,
	validationPath string,
	auditPath string,
	validationRowIDs []string,
	auditRowIDs []string,
) string {
	t.Helper()

	modelBytes, err := os.ReadFile(modelPath)
	if err != nil {
		t.Fatalf("read model fixture: %v", err)
	}
	validationBytes, err := os.ReadFile(validationPath)
	if err != nil {
		t.Fatalf("read validation fixture: %v", err)
	}
	auditBytes, err := os.ReadFile(auditPath)
	if err != nil {
		t.Fatalf("read audit fixture: %v", err)
	}

	manifest := lockedSplitManifest{
		SchemaVersion:       1,
		SplitSeed:           0,
		DatasetID:           "toy",
		ModelID:             "linear_poly3",
		ModelArtifactDigest: digestBytes(modelBytes),
		ConfigurationValidation: lockedSplitPartition{
			Path:      validationPath,
			CSVDigest: digestBytes(validationBytes),
			RowIDs:    validationRowIDs,
		},
		LockedAuditTest: lockedSplitPartition{
			Path:      auditPath,
			CSVDigest: digestBytes(auditBytes),
			RowIDs:    auditRowIDs,
		},
	}
	encoded, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatalf("marshal split manifest: %v", err)
	}

	path := filepath.Join(
		filepath.Dir(modelPath),
		"split_manifest.json",
	)
	if err := os.WriteFile(
		path,
		append(encoded, '\n'),
		0o600,
	); err != nil {
		t.Fatalf("write split manifest: %v", err)
	}
	return path
}
