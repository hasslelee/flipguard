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
)

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-sobel-autotune: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-sobel-autotune",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	modelPath := flags.String("model", "", "frozen Sobel model artifact")
	validationPath := flags.String(
		"validation",
		"",
		"configuration-validation Sobel patch CSV",
	)
	sourceArchivePath := flags.String(
		"source-archive",
		"",
		"digest-bound BSDS500 source archive",
	)
	splitID := flags.String("split-id", "", "stable split identifier")
	outputPath := flags.String("out", "", "result JSON path")
	planOnly := flags.Bool(
		"plan-only",
		false,
		"emit the static synthesis plan without CKKS execution",
	)
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf(
			"unexpected positional arguments: %v",
			flags.Args(),
		)
	}
	for name, value := range map[string]string{
		"--model":          *modelPath,
		"--validation":     *validationPath,
		"--source-archive": *sourceArchivePath,
		"--split-id":       *splitID,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}

	options := ckksplanner.DefaultPrimarySobelContractOptions()
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SourceArchivePath = *sourceArchivePath
	options.SplitID = *splitID
	contract, err := ckksplanner.BuildSobelWorkloadContract(options)
	if err != nil {
		return err
	}
	plan, err := ckksplanner.Synthesize(
		contract,
		ckksplanner.DefaultPrimarySynthesisPolicy(),
	)
	if err != nil {
		return err
	}
	var value any = plan
	if !*planOnly {
		result, err := ckksplanner.RunAdaptiveSobelAutotune(plan)
		if err != nil {
			return err
		}
		value = result
	}
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal Sobel result: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*outputPath) == "" {
		_, err = stdout.Write(encoded)
		return err
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write Sobel result: %w", err)
	}
	fmt.Fprintf(stdout, "sobel_result=%s\n", *outputPath)
	return nil
}
