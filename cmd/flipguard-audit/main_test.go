package main

import (
	"io"
	"strings"
	"testing"
)

func TestRunRejectsAuditDataSpaceWithoutPreparedOutput(
	t *testing.T,
) {
	err := run(
		[]string{
			"--selection", "selection.json",
			"--audit", "audit.csv",
			"--manifest", "manifest.json",
			"--audit-data-space", "raw",
		},
		io.Discard,
	)
	if err == nil ||
		!strings.Contains(
			err.Error(),
			"--audit-data-space requires --prepared-audit-out",
		) {
		t.Fatalf("expected audit materialization flag error, got %v", err)
	}
}
