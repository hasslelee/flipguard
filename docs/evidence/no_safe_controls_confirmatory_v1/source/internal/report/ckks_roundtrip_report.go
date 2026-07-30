package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSRoundTripSummaryCSV writes a CSV summary for a minimal CKKS
// encode-encrypt-decrypt-decode roundtrip.
func WriteCKKSRoundTripSummaryCSV(path string, result ckksbackend.RoundTripResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS roundtrip summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"want",
		"got",
		"abs_error",
		"max_slots",
		"max_level",
		"log_default_scale",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS roundtrip summary header: %w", err)
	}

	record := []string{
		formatFloat(result.Want),
		formatFloat(result.Got),
		formatFloat(result.AbsError),
		strconv.Itoa(result.MaxSlots),
		strconv.Itoa(result.MaxLevel),
		strconv.Itoa(result.LogDefaultScale),
	}

	if err := w.Write(record); err != nil {
		return fmt.Errorf("write CKKS roundtrip summary row: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS roundtrip summary csv: %w", err)
	}

	return nil
}

// WriteCKKSRoundTripMarkdown writes a Markdown report for a minimal CKKS
// roundtrip probe.
func WriteCKKSRoundTripMarkdown(path string, result ckksbackend.RoundTripResult) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS roundtrip markdown: %w", err)
	}
	defer f.Close()

	fmt.Fprintf(f, "# CKKS Roundtrip Probe\n\n")

	fmt.Fprintf(f, "## Overview\n\n")
	fmt.Fprintf(f, "This report summarizes a minimal Lattigo CKKS encode-encrypt-decrypt-decode roundtrip.\n\n")
	fmt.Fprintf(f, "The probe verifies that the repository can instantiate CKKS parameters, generate keys, encode a real value, encrypt it, decrypt it, decode it, and compare the decoded value with the original input.\n\n")
	fmt.Fprintf(f, "This is not a full FlipGuard encrypted inference experiment yet. It is a backend availability check before implementing encrypted `logreg_small` evaluation.\n\n")

	fmt.Fprintf(f, "## Result\n\n")
	fmt.Fprintf(f, "| Field | Value |\n")
	fmt.Fprintf(f, "|---|---:|\n")
	fmt.Fprintf(f, "| want | %.10f |\n", result.Want)
	fmt.Fprintf(f, "| got | %.10f |\n", result.Got)
	fmt.Fprintf(f, "| abs_error | %.10f |\n", result.AbsError)
	fmt.Fprintf(f, "| max_slots | %d |\n", result.MaxSlots)
	fmt.Fprintf(f, "| max_level | %d |\n", result.MaxLevel)
	fmt.Fprintf(f, "| log_default_scale | %d |\n", result.LogDefaultScale)

	return nil
}
