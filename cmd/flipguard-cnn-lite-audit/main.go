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
			"flipguard-cnn-lite-audit: %v\n",
			err,
		)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-cnn-lite-audit",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	selectionPath := flags.String(
		"selection",
		"",
		"frozen CNN-lite selection JSON",
	)
	auditPath := flags.String(
		"audit",
		"",
		"locked-audit CNN-lite CSV",
	)
	sourcePath := flags.String(
		"source",
		"",
		"digest-bound MNIST ARFF source",
	)
	manifestPath := flags.String(
		"input-manifest",
		"",
		"frozen CNN-lite input manifest",
	)
	outputPath := flags.String("out", "", "audit JSON path")
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
		"--selection":      *selectionPath,
		"--audit":          *auditPath,
		"--source":         *sourcePath,
		"--input-manifest": *manifestPath,
		"--out":            *outputPath,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	result, err := ckksplanner.RunLockedCNNLiteAudit(
		ckksplanner.CNNLiteLockedAuditOptions{
			SelectionResultPath: *selectionPath,
			AuditPath:           *auditPath,
			SourcePath:          *sourcePath,
			ManifestPath:        *manifestPath,
			KeyRepeats:          3,
		},
	)
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return fmt.Errorf(
			"marshal CNN-lite audit: %w",
			err,
		)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf(
			"write CNN-lite audit: %w",
			err,
		)
	}
	fmt.Fprintf(
		stdout,
		"cnn_lite_audit=%s outcome=%s\n",
		*outputPath,
		result.Outcome,
	)
	return nil
}
