package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestFrozenMLPGraphOnlyPreflight(t *testing.T) {
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test path")
	}
	root := filepath.Clean(filepath.Join(filepath.Dir(filename), "..", ".."))
	data, err := os.ReadFile(filepath.Join(
		root,
		"results/journal_multiclass_extension_v1/preflight/mlp_configuration_validation.json",
	))
	if err != nil {
		t.Fatal(err)
	}
	var preflight preflightEnvelope
	if err := json.Unmarshal(data, &preflight); err != nil {
		t.Fatal(err)
	}
	if err := validatePreflight(preflight); err != nil {
		t.Fatal(err)
	}
	candidate := preflight.GraphOnlyFixedTolerancePlan.InitialCandidates[0]
	if candidate.Parameters.LogN != 13 || candidate.Parameters.LogDefaultScale != 32 {
		t.Fatalf("unexpected graph-only literal: %+v", candidate.Parameters)
	}
	if candidate.Security.LogQP != 212 || candidate.Security.HeadroomBits != 2 {
		t.Fatalf("unexpected security binding: %+v", candidate.Security)
	}
}
