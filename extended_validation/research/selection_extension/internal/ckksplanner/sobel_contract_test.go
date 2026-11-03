package ckksplanner

import (
	"encoding/csv"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestBuildSobelWorkloadContractBindsSourceAndGraph(t *testing.T) {
	root := t.TempDir()
	sourcePath := filepath.Join(root, "source.tgz")
	modelPath := filepath.Join(root, "model.json")
	validationPath := filepath.Join(root, "validation.csv")

	source := []byte("deterministic-test-source")
	if err := os.WriteFile(sourcePath, source, 0o644); err != nil {
		t.Fatal(err)
	}
	sourceDigest := digestBytes(source)
	extractionDigest :=
		"sha256:07c196374cea947c5bd9d8d478311e75ba4754f875c4f19ce0387241d55da699"

	model := sobelModelArtifact{
		SchemaVersion:          BSDS500SobelModelSchemaV1,
		DatasetID:              "bsds500",
		DatasetName:            "Berkeley Segmentation Data Set 500",
		ModelID:                BSDS500SobelModelType,
		ModelType:              BSDS500SobelModelType,
		InputDim:               9,
		GraphFormula:           "Gx^2 + Gy^2",
		DecisionThreshold:      0.2,
		PackingScope:           ScalarReplicatedPackingV1,
		ExtractionPolicyID:     BSDS500SobelPatchExtractionV1,
		ExtractionPolicyDigest: extractionDigest,
	}
	model.SourceArchive.URL = "https://example.invalid/source.tgz"
	model.SourceArchive.SHA256 = sourceDigest
	model.DirectPolicyReference.PolicyID =
		DirectSynthesisPolicyV2ID
	model.DirectPolicyReference.PolicyDigest =
		MustDefaultDirectSynthesisPolicyDigest()
	model.DirectPolicyReference.Relationship =
		"frozen_constants_reused;model_type_not_added_to_policy_supported_models"
	encoded, err := json.Marshal(model)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(modelPath, encoded, 0o644); err != nil {
		t.Fatal(err)
	}

	file, err := os.Create(validationPath)
	if err != nil {
		t.Fatal(err)
	}
	writer := csv.NewWriter(file)
	header := []string{
		"row_id",
		"plaintext_score",
		"decision_threshold",
		"plaintext_decision",
		"source_archive_sha256",
		"extraction_policy_digest",
		"p00", "p01", "p02",
		"p10", "p11", "p12",
		"p20", "p21", "p22",
	}
	if err := writer.Write(header); err != nil {
		t.Fatal(err)
	}
	for _, row := range [][]string{
		{
			"0", "0", "0.2", "false",
			sourceDigest, extractionDigest,
			"0", "0", "0", "0", "0", "0", "0", "0", "0",
		},
		{
			"1", "16", "0.2", "true",
			sourceDigest, extractionDigest,
			"0", "0", "1", "0", "0", "1", "0", "0", "1",
		},
	} {
		if err := writer.Write(row); err != nil {
			t.Fatal(err)
		}
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		t.Fatal(err)
	}
	if err := file.Close(); err != nil {
		t.Fatal(err)
	}

	options := DefaultPrimarySobelContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceArchivePath = sourcePath
	options.SplitID = "test/sobel"
	contract, err := BuildSobelWorkloadContract(options)
	if err != nil {
		t.Fatalf("BuildSobelWorkloadContract failed: %v", err)
	}
	if contract.ModelType != BSDS500SobelModelType {
		t.Fatalf("model type=%s", contract.ModelType)
	}
	if contract.Decision.ValidationSamples != 2 ||
		contract.Decision.CertifiableSamples != 2 {
		t.Fatalf("unexpected decision counts: %+v", contract.Decision)
	}
	if contract.Graph.MultiplicativeDepth != 1 {
		t.Fatalf(
			"multiplicative depth=%d, want 1",
			contract.Graph.MultiplicativeDepth,
		)
	}
	if contract.Deployment.RescaleLevelsConsumed <= 0 {
		t.Fatalf(
			"rescale levels=%d, want positive",
			contract.Deployment.RescaleLevelsConsumed,
		)
	}
	if contract.SourceData == nil ||
		contract.SourceData.SHA256 != sourceDigest {
		t.Fatalf("source binding=%+v", contract.SourceData)
	}
}
