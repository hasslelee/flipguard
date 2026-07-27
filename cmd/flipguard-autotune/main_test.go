package main

import (
	"bytes"
	"strings"
	"testing"
)

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
			"--min-scale-bits", "0",
		},
		output,
	)
	if err == nil || !strings.Contains(err.Error(), "--min-scale-bits") {
		t.Fatalf("expected invalid scale-floor error, got %v", err)
	}
}

func TestRunRejectsNonPositiveKeyRepeats(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(
		[]string{
			"--model", "model.json",
			"--validation", "validation.csv",
			"--split-id", "split",
			"--key-repeats", "0",
		},
		output,
	)
	if err == nil || !strings.Contains(err.Error(), "--key-repeats") {
		t.Fatalf("expected invalid key-repeat error, got %v", err)
	}
}
