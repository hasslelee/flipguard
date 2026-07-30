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
		fmt.Fprintf(
			os.Stderr,
			"flipguard-cnn-lite-autotune: %v\n",
			err,
		)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-cnn-lite-autotune",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	modelPath := flags.String(
		"model",
		"",
		"frozen CNN-lite model artifact",
	)
	validationPath := flags.String(
		"validation",
		"",
		"configuration-validation CNN-lite CSV",
	)
	sourcePath := flags.String(
		"source",
		"",
		"digest-bound MNIST ARFF source",
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
		"--model":      *modelPath,
		"--validation": *validationPath,
		"--source":     *sourcePath,
		"--split-id":   *splitID,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	options := ckksplanner.DefaultPrimaryCNNLiteContractOptions()
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SourcePath = *sourcePath
	options.SplitID = *splitID
	contract, err := ckksplanner.BuildCNNLiteWorkloadContract(options)
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
		result, err := ckksplanner.RunAdaptiveCNNLiteAutotune(plan)
		if err != nil {
			return err
		}
		value = result
	}
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal CNN-lite result: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*outputPath) == "" {
		_, err = stdout.Write(encoded)
		return err
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write CNN-lite result: %w", err)
	}
	fmt.Fprintf(stdout, "cnn_lite_result=%s\n", *outputPath)
	return nil
}
