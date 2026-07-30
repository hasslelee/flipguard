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
			"flipguard-materialize-tabular: %v\n",
			err,
		)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-materialize-tabular",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	modelPath := flags.String(
		"model",
		"",
		"path to a supported FlipGuard model artifact",
	)
	dataPath := flags.String(
		"data",
		"",
		"path to held-out feature CSV",
	)
	dataSpace := flags.String(
		"data-space",
		"auto",
		"feature interpretation: auto, model, or raw",
	)
	outputPath := flags.String(
		"out",
		"",
		"canonical prepared validation CSV path",
	)
	manifestPath := flags.String(
		"manifest-out",
		"",
		"optional materialization manifest JSON path",
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
		"--model": *modelPath,
		"--data":  *dataPath,
		"--out":   *outputPath,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	materialization, err :=
		ckksplanner.MaterializeTabularValidationWithOptions(
			*modelPath,
			*dataPath,
			*outputPath,
			ckksplanner.TabularMaterializationOptions{
				DataSpace: ckksplanner.TabularDataSpace(
					strings.TrimSpace(*dataSpace),
				),
			},
		)
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(materialization, "", "  ")
	if err != nil {
		return fmt.Errorf(
			"marshal tabular materialization: %w",
			err,
		)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*manifestPath) != "" {
		if err := os.WriteFile(*manifestPath, encoded, 0o644); err != nil {
			return fmt.Errorf(
				"write materialization manifest %s: %w",
				*manifestPath,
				err,
			)
		}
	}
	fmt.Fprintf(
		stdout,
		"tabular_materialization=PASS rows=%d output=%s sha256=%s\n",
		materialization.Rows,
		materialization.ValidationPath,
		materialization.ValidationSHA256,
	)
	return nil
}
