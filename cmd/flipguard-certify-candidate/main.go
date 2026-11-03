package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/providergate"
	"github.com/hasslelee/flipguard/internal/tuner"
)

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-certify-candidate: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	defaults := ckksplanner.DefaultPrimaryTabularContractOptions()
	flags := flag.NewFlagSet(
		"flipguard-certify-candidate",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)

	modelPath := flags.String(
		"model",
		"",
		"path to a supported FlipGuard model artifact",
	)
	validationPath := flags.String(
		"validation",
		"",
		"path to prepared configuration-validation CSV",
	)
	splitID := flags.String(
		"split-id",
		"",
		"stable validation split identifier",
	)
	candidatePath := flags.String(
		"candidate",
		"",
		"path to a provider candidate request JSON",
	)
	outputPath := flags.String(
		"out",
		"",
		"optional result JSON path; stdout when omitted",
	)
	marginFloor := flags.Float64(
		"margin-floor",
		defaults.MarginFloor,
		"ambiguous-region decision margin floor",
	)
	safetyFactor := flags.Float64(
		"safety-factor",
		defaults.SafetyFactor,
		"fraction of protected margin assigned to output error",
	)
	keyRepeats := flags.Int(
		"key-repeats",
		defaults.ValidationKeyRepeats,
		"independent fresh-key validation runs for the bound literal",
	)

	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments: %v", flags.Args())
	}
	for _, required := range []struct {
		name  string
		value string
	}{
		{"--model", *modelPath},
		{"--validation", *validationPath},
		{"--split-id", *splitID},
		{"--candidate", *candidatePath},
	} {
		if strings.TrimSpace(required.value) == "" {
			return fmt.Errorf("%s is required", required.name)
		}
	}
	if *keyRepeats <= 0 {
		return errors.New("--key-repeats must be positive")
	}

	request, _, err := providergate.LoadProviderCandidateRequest(
		*candidatePath,
	)
	if err != nil {
		return err
	}
	options := defaults
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SplitID = *splitID
	options.MarginFloor = *marginFloor
	options.SafetyFactor = *safetyFactor
	options.ValidationKeyRepeats = *keyRepeats
	options.AllowedPaths = []tuner.ExecutionPath{request.Path}

	contract, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		return err
	}
	bound, err := providergate.LoadAndBindProviderCandidate(
		contract,
		*candidatePath,
	)
	if err != nil {
		return err
	}
	result, err := providergate.RunProviderCandidateGate(contract, bound)
	if err != nil {
		return err
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal provider candidate gate result: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*outputPath) == "" {
		if _, err := stdout.Write(encoded); err != nil {
			return fmt.Errorf("write provider gate result: %w", err)
		}
		return nil
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf(
			"write provider gate result %s: %w",
			*outputPath,
			err,
		)
	}
	fmt.Fprintf(
		stdout,
		"provider_candidate_gate=%s provider=%s candidate=%s status=%s key_runs=%d output=%s\n",
		result.Outcome,
		result.BoundCandidate.Request.ProviderKind,
		result.BoundCandidate.Candidate.ID,
		result.Trial.Status,
		result.EncryptedKeyRuns,
		*outputPath,
	)
	return nil
}
