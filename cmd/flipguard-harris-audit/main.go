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
		fmt.Fprintf(os.Stderr, "flipguard-harris-audit: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-harris-audit",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	selectionPath := flags.String(
		"selection",
		"",
		"frozen Harris selection JSON",
	)
	auditPath := flags.String(
		"audit",
		"",
		"locked-audit Harris patch CSV",
	)
	sourceArchivePath := flags.String(
		"source-archive",
		"",
		"digest-bound BSDS500 source archive",
	)
	manifestPath := flags.String(
		"extraction-manifest",
		"",
		"frozen Harris extraction manifest",
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
		"--selection":           *selectionPath,
		"--audit":               *auditPath,
		"--source-archive":      *sourceArchivePath,
		"--extraction-manifest": *manifestPath,
		"--out":                 *outputPath,
	} {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	result, err := ckksplanner.RunLockedHarrisAudit(
		ckksplanner.HarrisLockedAuditOptions{
			SelectionResultPath:    *selectionPath,
			AuditPath:              *auditPath,
			SourceArchivePath:      *sourceArchivePath,
			ExtractionManifestPath: *manifestPath,
			KeyRepeats:             3,
		},
	)
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal Harris audit: %w", err)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write Harris audit: %w", err)
	}
	fmt.Fprintf(
		stdout,
		"harris_audit=%s outcome=%s\n",
		*outputPath,
		result.Outcome,
	)
	return nil
}
