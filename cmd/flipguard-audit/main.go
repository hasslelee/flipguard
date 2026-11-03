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
		fmt.Fprintf(os.Stderr, "flipguard-audit: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet("flipguard-audit", flag.ContinueOnError)
	flags.SetOutput(stdout)

	selectionPath := flags.String(
		"selection",
		"",
		"path to a completed adaptive selection result",
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
	if strings.TrimSpace(*selectionPath) == "" {
		return errors.New("--selection is required")
	}
	if strings.TrimSpace(*auditPath) == "" {
		return errors.New("--audit is required")
	}
	if strings.TrimSpace(*manifestPath) == "" {
		return errors.New("--manifest is required")
	}
	if *keyRepeats <= 0 {
		return errors.New("--key-repeats must be positive")
	}
	hasPreparedAudit :=
		strings.TrimSpace(*preparedAuditPath) != ""
	if !hasPreparedAudit &&
		strings.TrimSpace(*auditDataSpace) != "auto" {
		return errors.New(
			"--audit-data-space requires --prepared-audit-out",
		)
	}

	result, err := ckksplanner.RunLockedTabularAudit(
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
		return fmt.Errorf("marshal locked audit result: %w", err)
	}
	encoded = append(encoded, '\n')

	if strings.TrimSpace(*outputPath) == "" {
		if _, err := stdout.Write(encoded); err != nil {
			return fmt.Errorf("write locked audit result: %w", err)
		}
		return nil
	}

	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf(
			"write locked audit result %s: %w",
			*outputPath,
			err,
		)
	}

	fmt.Fprintf(
		stdout,
		"locked_audit=%s workload=%s status=%s keys=%d output=%s\n",
		result.Outcome,
		result.SelectionWorkloadID,
		result.AuditTrial.Status,
		result.AuditTrial.KeyRepeatsCompleted,
		*outputPath,
	)
	return nil
}
