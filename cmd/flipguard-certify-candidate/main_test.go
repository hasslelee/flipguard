package main

import (
	"bytes"
	"errors"
	"flag"
	"strings"
	"testing"
)

func TestRunRequiresProviderGateInputs(t *testing.T) {
	err := run(nil, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "--model is required") {
		t.Fatalf("expected required model error, got %v", err)
	}
}

func TestHelpPublishesProviderGateContract(t *testing.T) {
	output := &bytes.Buffer{}
	err := run([]string{"--help"}, output)
	if !errors.Is(err, flag.ErrHelp) {
		t.Fatalf("expected flag help, got %v", err)
	}
	for _, expected := range []string{
		"-candidate string",
		"-model string",
		"-validation string",
		"-split-id string",
		"-key-repeats int",
		"(default 3)",
	} {
		if !strings.Contains(output.String(), expected) {
			t.Fatalf(
				"help missing %q:\n%s",
				expected,
				output.String(),
			)
		}
	}
}

func TestRunRejectsNonPositiveKeyRepeatsBeforeIO(t *testing.T) {
	err := run(
		[]string{
			"--model", "model.json",
			"--validation", "validation.csv",
			"--split-id", "split",
			"--candidate", "candidate.json",
			"--key-repeats", "0",
		},
		&bytes.Buffer{},
	)
	if err == nil || !strings.Contains(err.Error(), "--key-repeats") {
		t.Fatalf("expected key-repeat error, got %v", err)
	}
}
