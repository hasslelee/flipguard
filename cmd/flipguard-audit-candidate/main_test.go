package main

import (
	"bytes"
	"errors"
	"flag"
	"strings"
	"testing"
)

func TestRunRequiresProviderAuditInputs(t *testing.T) {
	err := run(nil, &bytes.Buffer{})
	if err == nil ||
		!strings.Contains(err.Error(), "--selection is required") {
		t.Fatalf("expected required selection error, got %v", err)
	}
}

func TestHelpPublishesProviderAuditContract(t *testing.T) {
	output := &bytes.Buffer{}
	err := run([]string{"--help"}, output)
	if !errors.Is(err, flag.ErrHelp) {
		t.Fatalf("expected flag help, got %v", err)
	}
	for _, expected := range []string{
		"-selection string",
		"-audit string",
		"-manifest string",
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
			"--selection", "selection.json",
			"--audit", "audit.csv",
			"--manifest", "split.json",
			"--key-repeats", "0",
		},
		&bytes.Buffer{},
	)
	if err == nil || !strings.Contains(err.Error(), "--key-repeats") {
		t.Fatalf("expected key-repeat error, got %v", err)
	}
}
