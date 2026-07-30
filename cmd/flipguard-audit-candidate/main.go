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
)

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(
			os.Stderr,
			"flipguard-audit-candidate: %v\n",
			err,
		)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-audit-candidate",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)

	selectionPath := flags.String(
		"selection",
		"",
		"path to a completed provider candidate gate result",
	)
	auditPath := flags.String(
		"audit",
		"",
		"path to the locked audit source feature CSV",
	)
	preparedAuditPath := flags.String(
		"prepared-audit-out",
		"",
		"optional canonical audit artifact materialized from --audit",
	)
	auditDataSpace := flags.String(
		"audit-data-space",
		"auto",
		"feature interpretation for materialized audit: auto, model, or raw",
	)
	manifestPath := flags.String(
		"manifest",
		"",
		"path to the split manifest",
	)
	keyRepeats := flags.Int(
		"key-repeats",
		3,
		"independent fresh-key audit runs",
	)
	outputPath := flags.String(
		"out",
		"",
		"optional locked audit result JSON path; stdout when omitted",
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
	for _, required := range []struct {
		name  string
		value string
	}{
		{"--selection", *selectionPath},
		{"--audit", *auditPath},
		{"--manifest", *manifestPath},
	} {
		if strings.TrimSpace(required.value) == "" {
			return fmt.Errorf("%s is required", required.name)
		}
	}
	if *keyRepeats <= 0 {
		return errors.New("--key-repeats must be positive")
	}
	hasPreparedAudit := strings.TrimSpace(*preparedAuditPath) != ""
	if !hasPreparedAudit &&
		strings.TrimSpace(*auditDataSpace) != "auto" {
		return errors.New(
			"--audit-data-space requires --prepared-audit-out",
		)
	}

	result, err := providergate.RunLockedProviderCandidateAudit(
		*selectionPath,
		ckksplanner.LockedAuditOptions{
			SelectionResultPath: *selectionPath,
			AuditPath:           *auditPath,
			PreparedAuditPath:   *preparedAuditPath,
			AuditDataSpace: ckksplanner.TabularDataSpace(
				strings.TrimSpace(*auditDataSpace),
			),
			SplitManifestPath: *manifestPath,
			KeyRepeats:        *keyRepeats,
		},
	)
	if err != nil {
		return err
	}

	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal provider locked audit result: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*outputPath) == "" {
		if _, err := stdout.Write(encoded); err != nil {
			return fmt.Errorf(
				"write provider locked audit result: %w",
				err,
			)
		}
		return nil
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf(
			"write provider locked audit result %s: %w",
			*outputPath,
			err,
		)
	}
	fmt.Fprintf(
		stdout,
		"provider_locked_audit=%s candidate=%s status=%s retuning=%t output=%s\n",
		result.Outcome,
		result.SelectedCandidate.ID,
		result.AuditTrial.Status,
		result.RetuningPerformed,
		*outputPath,
	)
	return nil
}
