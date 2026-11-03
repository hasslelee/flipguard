package ckksbackend

import (
	"fmt"
	"math"
)

// CKKSCertificateAuditConfig defines observed-error certification settings.
type CKKSCertificateAuditConfig struct {
	SafetyFactor float64
	SweepConfig  FullLogRegBoundarySweepConfig
}

// CKKSCertificateAuditRecord records one observed-error certificate check.
type CKKSCertificateAuditRecord struct {
	CaseIndex  int
	Repetition int

	BoundaryResult FullLogRegBoundaryResult

	ErrorBudget float64
	BudgetUsage float64

	Certified       bool
	StableCertified bool
}

// CKKSCertificateAuditSummary summarizes observed-error certificate checks.
type CKKSCertificateAuditSummary struct {
	Points      int
	Repetitions int
	Runs        int

	SafetyFactor float64

	BoundaryRuns  int
	StableRuns    int
	AmbiguousRuns int

	Flips          int
	StableFlips    int
	AmbiguousFlips int

	CertifiedRuns       int
	StableCertifiedRuns int
	StableViolations    int

	MinStableMargin float64

	MaxYError  float64
	MeanYError float64

	MaxStableUsage  float64
	MeanStableUsage float64
}

// DefaultCKKSCertificateAuditConfig returns the default certificate audit config.
func DefaultCKKSCertificateAuditConfig() CKKSCertificateAuditConfig {
	return CKKSCertificateAuditConfig{
		SafetyFactor: 0.5,
		SweepConfig:  DefaultFullLogRegBoundarySweepConfig(),
	}
}

// RunCKKSCertificateAudit runs a dense boundary sweep and checks observed-error certificates.
func (c Context) RunCKKSCertificateAudit(
	config CKKSCertificateAuditConfig,
) ([]CKKSCertificateAuditRecord, CKKSCertificateAuditSummary, error) {
	if config.SafetyFactor <= 0 {
		return nil, CKKSCertificateAuditSummary{}, fmt.Errorf("safety factor must be positive: %.10f", config.SafetyFactor)
	}

	sweepRecords, _, err := c.RunFullLogRegBoundarySweepProbe(config.SweepConfig)
	if err != nil {
		return nil, CKKSCertificateAuditSummary{}, fmt.Errorf("run boundary sweep: %w", err)
	}

	auditRecords := make([]CKKSCertificateAuditRecord, 0, len(sweepRecords))

	for _, sweepRecord := range sweepRecords {
		boundary := sweepRecord.BoundaryResult
		errorBudget := config.SafetyFactor * boundary.Margin

		usage := 0.0
		if errorBudget > 0 {
			usage = boundary.Result.YError / errorBudget
		}

		certified := false
		stableCertified := false

		if boundary.Boundary && !boundary.Ambiguous && boundary.Result.YError <= errorBudget {
			certified = true
		}

		if boundary.Stable && boundary.Result.YError <= errorBudget {
			stableCertified = true
		}

		auditRecords = append(auditRecords, CKKSCertificateAuditRecord{
			CaseIndex:  sweepRecord.CaseIndex,
			Repetition: sweepRecord.Repetition,

			BoundaryResult: boundary,

			ErrorBudget: errorBudget,
			BudgetUsage: usage,

			Certified:       certified,
			StableCertified: stableCertified,
		})
	}

	summary := summarizeCKKSCertificateAudit(auditRecords, config)

	return auditRecords, summary, nil
}

func summarizeCKKSCertificateAudit(
	records []CKKSCertificateAuditRecord,
	config CKKSCertificateAuditConfig,
) CKKSCertificateAuditSummary {
	summary := CKKSCertificateAuditSummary{
		Points:          config.SweepConfig.Points,
		Repetitions:     config.SweepConfig.Repetitions,
		Runs:            len(records),
		SafetyFactor:    config.SafetyFactor,
		MinStableMargin: math.Inf(1),
	}

	sumYError := 0.0
	sumStableUsage := 0.0

	for _, record := range records {
		boundary := record.BoundaryResult
		result := boundary.Result

		sumYError += result.YError

		if result.YError > summary.MaxYError {
			summary.MaxYError = result.YError
		}

		if boundary.Boundary {
			summary.BoundaryRuns++
		}

		if boundary.Stable {
			summary.StableRuns++

			if boundary.Margin < summary.MinStableMargin {
				summary.MinStableMargin = boundary.Margin
			}

			sumStableUsage += record.BudgetUsage

			if record.BudgetUsage > summary.MaxStableUsage {
				summary.MaxStableUsage = record.BudgetUsage
			}
		}

		if boundary.Ambiguous {
			summary.AmbiguousRuns++
		}

		if result.DecisionFlip {
			summary.Flips++
		}

		if boundary.Stable && result.DecisionFlip {
			summary.StableFlips++
		}

		if boundary.Ambiguous && result.DecisionFlip {
			summary.AmbiguousFlips++
		}

		if record.Certified {
			summary.CertifiedRuns++
		}

		if record.StableCertified {
			summary.StableCertifiedRuns++
		}
	}

	summary.StableViolations = summary.StableRuns - summary.StableCertifiedRuns

	if len(records) > 0 {
		summary.MeanYError = sumYError / float64(len(records))
	}

	if summary.StableRuns > 0 {
		summary.MeanStableUsage = sumStableUsage / float64(summary.StableRuns)
	}

	if math.IsInf(summary.MinStableMargin, 1) {
		summary.MinStableMargin = 0
	}

	return summary
}
