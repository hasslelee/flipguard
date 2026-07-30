package experiment

import (
	"fmt"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/report"
)

const ckksCertificateAuditOutputDir = "results/ckks_certificate_audit"

// RunCKKSCertificateAudit runs observed-error decision certificate auditing.
func RunCKKSCertificateAudit() error {
	ctx, err := ckksbackend.NewDefaultContext()
	if err != nil {
		return fmt.Errorf("create CKKS context: %w", err)
	}

	config := CKKSCertificateAuditConfigFromRuntimeOptions()
	outputDir := CKKSResultDir(ckksCertificateAuditOutputDir)

	records, summary, err := ctx.RunCKKSCertificateAudit(config)
	if err != nil {
		return fmt.Errorf("run CKKS certificate audit: %w", err)
	}

	fmt.Println("FlipGuard CKKS observed-error certificate audit")
	fmt.Printf(
		"points=%d repetitions=%d runs=%d safety_factor=%.4f\n",
		summary.Points,
		summary.Repetitions,
		summary.Runs,
		summary.SafetyFactor,
	)
	fmt.Println()

	fmt.Printf(
		"stable_runs=%d stable_flips=%d stable_violations=%d max_stable_usage=%.10f max_y_error=%.10f\n",
		summary.StableRuns,
		summary.StableFlips,
		summary.StableViolations,
		summary.MaxStableUsage,
		summary.MaxYError,
	)

	if err := report.WriteCKKSCertificateAuditSummaryCSV(
		filepath.Join(outputDir, "summary.csv"),
		summary,
	); err != nil {
		return fmt.Errorf("write CKKS certificate audit summary CSV: %w", err)
	}

	if err := report.WriteCKKSCertificateAuditRecordsCSV(
		filepath.Join(outputDir, "records.csv"),
		records,
	); err != nil {
		return fmt.Errorf("write CKKS certificate audit records CSV: %w", err)
	}

	fmt.Println()
	fmt.Printf("Exported CKKS certificate audit files to %s/\n", outputDir)

	return nil
}
