package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunRequiresInputs(t *testing.T) {
	var stdout bytes.Buffer
	err := run(nil, &stdout)
	if err == nil || !strings.HasSuffix(err.Error(), " is required") {
		t.Fatalf("expected missing required-input error, got %v", err)
	}
}

func TestRunMaterializesRawSelectedFeatures(t *testing.T) {
	root := t.TempDir()
	modelPath := filepath.Join(root, "model.json")
	dataPath := filepath.Join(root, "data.csv")
	outputPath := filepath.Join(root, "prepared.csv")
	manifestPath := filepath.Join(root, "materialization.json")
	model := `{
  "dataset_id": "fixture",
  "dataset_name": "fixture",
  "model_id": "linear_poly3",
  "model_type": "linear_poly3",
  "task": "binary classification",
  "label_mapping": {"0": "negative", "1": "positive"},
  "selected_feature_indices": [1],
  "selected_feature_names": ["selected"],
  "input_dim": 1,
  "standardization": {"mean": [10.0], "std": [2.0]},
  "raw_model": {"weights": [1.0], "bias": 0.0},
  "scaled_model_for_ckks": {"weights": [1.0], "bias": 0.0},
  "max_scaled_logit_target": 1.0,
  "polynomial_score": {
    "formula": "0.5 + 0.197*z - 0.004*z^3",
    "decision_threshold": 0.5
  }
}`
	if err := os.WriteFile(modelPath, []byte(model), 0o644); err != nil {
		t.Fatal(err)
	}
	data := "row_id,label,x_1\n7,1,12\n"
	if err := os.WriteFile(dataPath, []byte(data), 0o644); err != nil {
		t.Fatal(err)
	}
	var stdout bytes.Buffer
	err := run(
		[]string{
			"--model", modelPath,
			"--data", dataPath,
			"--data-space", "raw",
			"--out", outputPath,
			"--manifest-out", manifestPath,
		},
		&stdout,
	)
	if err != nil {
		t.Fatalf("run materializer: %v", err)
	}
	prepared, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(
		string(prepared),
		"selected_feature_standardization_v1",
	) || !strings.Contains(string(prepared), ",1\n") {
		t.Fatalf("unexpected materialized row:\n%s", prepared)
	}
	if _, err := os.Stat(manifestPath); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(stdout.String(), "tabular_materialization=PASS") {
		t.Fatalf("unexpected stdout: %s", stdout.String())
	}
}
