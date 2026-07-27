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
	"github.com/hasslelee/flipguard/internal/tuner"
)

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-autotune: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	defaults := ckksplanner.DefaultTabularContractOptions()
	synthesisDefaults := ckksplanner.DefaultSynthesisPolicy()

	flags := flag.NewFlagSet("flipguard-autotune", flag.ContinueOnError)
	flags.SetOutput(stdout)

	modelPath := flags.String(
		"model",
		"",
		"path to a supported FlipGuard model artifact",
	)
	validationPath := flags.String(
		"validation",
		"",
		"path to configuration-validation CSV",
	)
	splitID := flags.String(
		"split-id",
		"",
		"stable validation split identifier",
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
	securityBits := flags.Int(
		"security-bits",
		defaults.SecurityBits,
		"target classical security bits",
	)
	maxEncryptedTrials := flags.Int(
		"max-encrypted-trials",
		defaults.MaxEncryptedTrials,
		"maximum adaptive encrypted trials",
	)
	minScaleBits := flags.Int(
		"min-scale-bits",
		synthesisDefaults.MinScaleBits,
		"minimum initial CKKS scale bits",
	)
	minPrimeBits := flags.Int(
		"min-prime-bits",
		synthesisDefaults.MinPrimeBits,
		"minimum Q-prime bits",
	)
	specialPrimeBits := flags.Int(
		"special-prime-bits",
		synthesisDefaults.SpecialPrimeBits,
		"minimum P special-prime bits",
	)

	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments: %v", flags.Args())
	}
	if strings.TrimSpace(*modelPath) == "" {
		return errors.New("--model is required")
	}
	if strings.TrimSpace(*validationPath) == "" {
		return errors.New("--validation is required")
	}
	if strings.TrimSpace(*splitID) == "" {
		return errors.New("--split-id is required")
	}
	if *minScaleBits <= 0 {
		return errors.New("--min-scale-bits must be positive")
	}
	if *minPrimeBits <= 0 {
		return errors.New("--min-prime-bits must be positive")
	}
	if *specialPrimeBits <= 0 {
		return errors.New("--special-prime-bits must be positive")
	}

	options := defaults
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SplitID = *splitID
	options.MarginFloor = *marginFloor
	options.SafetyFactor = *safetyFactor
	options.SecurityBits = *securityBits
	options.MaxEncryptedTrials = *maxEncryptedTrials
	options.AllowedPaths = []tuner.ExecutionPath{
		tuner.PathRescale,
	}

	contract, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		return err
	}
	synthesisPolicy := synthesisDefaults
	synthesisPolicy.MinScaleBits = *minScaleBits
	synthesisPolicy.MinPrimeBits = *minPrimeBits
	synthesisPolicy.SpecialPrimeBits = *specialPrimeBits

	plan, err := ckksplanner.Synthesize(contract, synthesisPolicy)
	if err != nil {
		return err
	}
	result, err := ckksplanner.RunAdaptiveTabularAutotune(plan)
	if err != nil {
		return err
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal adaptive autotune result: %w", err)
	}
	encoded = append(encoded, '\n')

	if strings.TrimSpace(*outputPath) == "" {
		if _, err := stdout.Write(encoded); err != nil {
			return fmt.Errorf("write adaptive autotune result: %w", err)
		}
		return nil
	}

	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf(
			"write adaptive autotune result %s: %w",
			*outputPath,
			err,
		)
	}

	fmt.Fprintf(
		stdout,
		"adaptive_autotune=%s workload=%s trials=%d output=%s\n",
		result.Outcome,
		result.Plan.Contract.WorkloadID,
		result.TrialsUsed,
		*outputPath,
	)
	return nil
}
