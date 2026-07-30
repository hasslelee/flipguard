package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/hasslelee/flipguard/internal/externaladapter"
)

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-audit-orion-candidate: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, stdout io.Writer) error {
	flags := flag.NewFlagSet(
		"flipguard-audit-orion-candidate",
		flag.ContinueOnError,
	)
	flags.SetOutput(stdout)
	configPath := flags.String("config", "", "path to pinned Orion YAML")
	repositoryURL := flags.String(
		"repository-url",
		"",
		"upstream Orion repository URL",
	)
	commit := flags.String("commit", "", "full upstream Orion commit SHA")
	upstreamPath := flags.String(
		"upstream-path",
		"",
		"path of the config within the upstream repository",
	)
	sourceSHA := flags.String(
		"source-sha256",
		"",
		"expected sha256-prefixed digest of the Orion YAML",
	)
	backendModule := flags.String(
		"backend-module",
		"github.com/baahl-nyu/lattigo/v6",
		"concrete Lattigo module selected by Orion",
	)
	backendVersion := flags.String(
		"backend-version",
		"v6.2.0",
		"concrete Lattigo version selected by Orion",
	)
	backendCommit := flags.String(
		"backend-commit",
		"",
		"full concrete Orion Lattigo backend commit SHA",
	)
	outputPath := flags.String(
		"out",
		"",
		"optional audit report JSON path; stdout when omitted",
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
		{"--config", *configPath},
		{"--repository-url", *repositoryURL},
		{"--commit", *commit},
		{"--upstream-path", *upstreamPath},
		{"--source-sha256", *sourceSHA},
		{"--backend-module", *backendModule},
		{"--backend-version", *backendVersion},
		{"--backend-commit", *backendCommit},
	} {
		if strings.TrimSpace(required.value) == "" {
			return fmt.Errorf("%s is required", required.name)
		}
	}

	report, err := externaladapter.AuditOrionConfig(
		*configPath,
		externaladapter.OrionAdapterInput{
			Source: externaladapter.ExternalSourceBinding{
				RepositoryURL: *repositoryURL,
				Commit:        *commit,
				Path:          *upstreamPath,
				SHA256:        *sourceSHA,
			},
			Backend: externaladapter.OrionBackendBinding{
				Module:  *backendModule,
				Version: *backendVersion,
				Commit:  *backendCommit,
			},
		},
	)
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal Orion adapter report: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*outputPath) == "" {
		_, err = stdout.Write(encoded)
		return err
	}
	if err := os.WriteFile(*outputPath, encoded, 0o644); err != nil {
		return fmt.Errorf("write Orion adapter report: %w", err)
	}
	fmt.Fprintf(
		stdout,
		"orion_adapter=%s status=%s encrypted_execution=%t output=%s\n",
		report.AdapterID,
		report.Status,
		report.EncryptedExecution,
		*outputPath,
	)
	return nil
}
