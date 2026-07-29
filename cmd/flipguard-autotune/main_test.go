package main

import (
	"bytes"
	"errors"
	"flag"
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

func TestHelpPublishesPrimaryUserInputPolicy(t *testing.T) {
	output := &bytes.Buffer{}
	err := run([]string{"--help"}, output)
	if !errors.Is(err, flag.ErrHelp) {
		t.Fatalf("expected flag help, got %v", err)
	}
	for _, expected := range []string{
		"-data string",
		"-data-space string",
		"(default \"auto\")",
		"-key-repeats int",
		"(default 3)",
		"-min-prime-bits int",
		"-min-scale-bits int",
		"(default 18)",
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

func TestRunRejectsDataSpaceWithoutData(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(
		[]string{
			"--model", "model.json",
			"--validation", "validation.csv",
			"--data-space", "raw",
			"--split-id", "split",
		},
		output,
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"--data-space is valid only with --data",
	) {
		t.Fatalf("expected data-space scope error, got %v", err)
	}
}

func TestRunRequiresExactlyOneDataInput(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(
		[]string{
			"--model", "model.json",
			"--split-id", "split",
		},
		output,
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"exactly one of --validation or --data",
	) {
		t.Fatalf("expected missing data input error, got %v", err)
	}

	err = run(
		[]string{
			"--model", "model.json",
			"--validation", "validation.csv",
			"--data", "data.csv",
			"--split-id", "split",
		},
		output,
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"exactly one of --validation or --data",
	) {
		t.Fatalf("expected conflicting data input error, got %v", err)
	}
}

func TestRunRequiresPersistentMaterializationForData(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(
		[]string{
			"--model", "model.json",
			"--data", "data.csv",
			"--split-id", "split",
		},
		output,
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"--data requires --out or --prepared-validation-out",
	) {
		t.Fatalf(
			"expected persistent materialization error, got %v",
			err,
		)
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
