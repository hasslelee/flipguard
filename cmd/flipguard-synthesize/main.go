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
		fmt.Fprintf(os.Stderr, "flipguard-synthesize: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	defaults := ckksplanner.DefaultTabularContractOptions()
	synthesisDefaults := ckksplanner.DefaultSynthesisPolicy()

	flags := flag.NewFlagSet("flipguard-synthesize", flag.ContinueOnError)
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
		"optional output JSON path; stdout when omitted",
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
	keyRepeats := flags.Int(
		"key-repeats",
		defaults.ValidationKeyRepeats,
		"independent fresh-key validation runs per configuration trial",
	)
	executionPath := flags.String(
		"path",
		string(tuner.PathRescale),
		"execution path; direct synthesis v1 supports rescale",
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
	precisionSlackMode := flags.String(
		"precision-slack-mode",
		synthesisDefaults.PrecisionSlackMode,
		"static precision policy: none or maximize_within_min_log_n",
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
	if *keyRepeats <= 0 {
		return errors.New("--key-repeats must be positive")
	}

	path, err := parseExecutionPath(*executionPath)
	if err != nil {
		return err
	}

	options := defaults
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SplitID = *splitID
	options.MarginFloor = *marginFloor
	options.SafetyFactor = *safetyFactor
	options.SecurityBits = *securityBits
	options.MaxEncryptedTrials = *maxEncryptedTrials
	options.ValidationKeyRepeats = *keyRepeats
	options.AllowedPaths = []tuner.ExecutionPath{path}

	contract, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		return err
	}
	synthesisPolicy := synthesisDefaults
	synthesisPolicy.MinScaleBits = *minScaleBits
	synthesisPolicy.MinPrimeBits = *minPrimeBits
	synthesisPolicy.SpecialPrimeBits = *specialPrimeBits
	synthesisPolicy.PrecisionSlackMode = strings.TrimSpace(
		*precisionSlackMode,
	)

	plan, err := ckksplanner.Synthesize(contract, synthesisPolicy)
	if err != nil {
		return err
	}

	encoded, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal synthesis plan: %w", err)
	}
	encoded = append(encoded, '\n')

	if strings.TrimSpace(*outputPath) == "" {
		if _, err := stdout.Write(encoded); err != nil {
			return fmt.Errorf("write synthesis plan: %w", err)
		}
		return nil
	}

	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write synthesis plan %s: %w", *outputPath, err)
	}

	fmt.Fprintf(
		stdout,
		"synthesis_plan=PASS workload=%s candidates=%d output=%s\n",
		plan.Contract.WorkloadID,
		len(plan.InitialCandidates),
		*outputPath,
	)
	return nil
}

func parseExecutionPath(raw string) (tuner.ExecutionPath, error) {
	switch strings.TrimSpace(strings.ToLower(raw)) {
	case "rescale", "rescale_aware":
		return tuner.PathRescale, nil
	case "non-rescale", "non_rescale", "baseline_non_rescale":
		return tuner.PathNonRescale, nil
	default:
		return "", fmt.Errorf("unsupported execution path %q", raw)
	}
}
