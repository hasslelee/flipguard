package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/tuner"
)

func TestParseExecutionPath(t *testing.T) {
	path, err := parseExecutionPath("rescale_aware")
	if err != nil {
		t.Fatalf("parse rescale path: %v", err)
	}
	if path != tuner.PathRescale {
		t.Fatalf("unexpected path %q", path)
	}
}

func TestRunRequiresUserInputs(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(nil, output)
	if err == nil || !strings.Contains(err.Error(), "--model is required") {
		t.Fatalf("expected required model error, got %v", err)
	}
}

func TestRunRejectsNonPositivePolicyFloor(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(
		[]string{
			"--model", "model.json",
			"--validation", "validation.csv",
			"--split-id", "split",
			"--min-prime-bits", "-1",
		},
		output,
	)
	if err == nil || !strings.Contains(err.Error(), "--min-prime-bits") {
		t.Fatalf("expected invalid prime-floor error, got %v", err)
	}
}
