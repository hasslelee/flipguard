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

func writeSelectionFixture(
	t *testing.T,
	modelPath string,
	validationPath string,
) (string, AdaptiveAutotuneResult) {
	t.Helper()

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
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
