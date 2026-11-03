package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

// WriteCKKSCertificateAuditSummaryCSV writes aggregate certificate audit results.
func WriteCKKSCertificateAuditSummaryCSV(path string, summary ckksbackend.CKKSCertificateAuditSummary) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS certificate audit summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"points",
		"repetitions",
		"runs",
		"safety_factor",
		"boundary_runs",
		"stable_runs",
		"ambiguous_runs",
		"flips",
		"stable_flips",
		"ambiguous_flips",
		"certified_runs",
		"stable_certified_runs",
		"stable_violations",
		"min_stable_margin",
		"max_y_error",
		"mean_y_error",
		"max_stable_usage",
		"mean_stable_usage",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS certificate audit summary header: %w", err)
	}

	row := []string{
		strconv.Itoa(summary.Points),
		strconv.Itoa(summary.Repetitions),
		strconv.Itoa(summary.Runs),
		formatFloat(summary.SafetyFactor),
		strconv.Itoa(summary.BoundaryRuns),
		strconv.Itoa(summary.StableRuns),
		strconv.Itoa(summary.AmbiguousRuns),
		strconv.Itoa(summary.Flips),
		strconv.Itoa(summary.StableFlips),
		strconv.Itoa(summary.AmbiguousFlips),
		strconv.Itoa(summary.CertifiedRuns),
		strconv.Itoa(summary.StableCertifiedRuns),
		strconv.Itoa(summary.StableViolations),
		formatFloat(summary.MinStableMargin),
		formatFloat(summary.MaxYError),
		formatFloat(summary.MeanYError),
		formatFloat(summary.MaxStableUsage),
		formatFloat(summary.MeanStableUsage),
	}

	if err := w.Write(row); err != nil {
		return fmt.Errorf("write CKKS certificate audit summary row: %w", err)
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS certificate audit summary csv: %w", err)
	}

	return nil
}

// WriteCKKSCertificateAuditRecordsCSV writes per-run certificate audit records.
func WriteCKKSCertificateAuditRecordsCSV(path string, records []ckksbackend.CKKSCertificateAuditRecord) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create CKKS certificate audit records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"case_index",
		"repetition",
		"target_z",
		"threshold",
		"plain_y",
		"ckks_y",
		"y_error",
		"margin",
		"error_budget",
		"budget_usage",
		"boundary",
		"ambiguous",
		"stable",
		"certified",
		"stable_certified",
		"plain_decision",
		"ckks_decision",
		"decision_flip",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write CKKS certificate audit records header: %w", err)
	}

	for _, record := range records {
		boundary := record.BoundaryResult
		result := boundary.Result

		row := []string{
			strconv.Itoa(record.CaseIndex),
			strconv.Itoa(record.Repetition),
			formatFloat(boundary.Case.TargetZ),
			formatFloat(result.Threshold),
			formatFloat(result.PlainY),
			formatFloat(result.CKKSY),
			formatFloat(result.YError),
			formatFloat(boundary.Margin),
			formatFloat(record.ErrorBudget),
			formatFloat(record.BudgetUsage),
			strconv.FormatBool(boundary.Boundary),
			strconv.FormatBool(boundary.Ambiguous),
			strconv.FormatBool(boundary.Stable),
			strconv.FormatBool(record.Certified),
			strconv.FormatBool(record.StableCertified),
			strconv.FormatBool(result.PlainDecision),
			strconv.FormatBool(result.CKKSDecision),
			strconv.FormatBool(result.DecisionFlip),
		}

		if err := w.Write(row); err != nil {
			return fmt.Errorf(
				"write CKKS certificate audit record case %d repetition %d: %w",
				record.CaseIndex,
				record.Repetition,
				err,
			)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush CKKS certificate audit records csv: %w", err)
	}

	return nil
}
