package ckksbackend

import "testing"

func TestRunCKKSCertificateAudit(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	config := CKKSCertificateAuditConfig{
		SafetyFactor: 0.5,
		SweepConfig: FullLogRegBoundarySweepConfig{
			MinTargetZ:  -0.01,
			MaxTargetZ:  0.01,
			Points:      11,
			Repetitions: 2,
		},
	}

	records, summary, err := ctx.RunCKKSCertificateAudit(config)
	if err != nil {
		t.Fatalf("RunCKKSCertificateAudit failed: %v", err)
	}

	wantRuns := config.SweepConfig.Points * config.SweepConfig.Repetitions
	if len(records) != wantRuns {
		t.Fatalf("expected %d records, got %d", wantRuns, len(records))
	}

	if summary.Runs != wantRuns {
		t.Fatalf("expected summary runs %d, got %d", wantRuns, summary.Runs)
	}

	if summary.StableRuns == 0 {
		t.Fatalf("expected at least one stable run")
	}

	if summary.AmbiguousRuns == 0 {
		t.Fatalf("expected at least one ambiguous run")
	}

	if summary.StableFlips != 0 {
		t.Fatalf("expected zero stable flips, got %d", summary.StableFlips)
	}

	if summary.StableViolations != 0 {
		t.Fatalf("expected zero stable certificate violations, got %d", summary.StableViolations)
	}

	if summary.MaxStableUsage >= 1.0 {
		t.Fatalf("expected max stable usage below 1, got %.10f", summary.MaxStableUsage)
	}
}

func TestRunCKKSCertificateAuditRejectsInvalidSafetyFactor(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	_, _, err = ctx.RunCKKSCertificateAudit(CKKSCertificateAuditConfig{
		SafetyFactor: 0,
		SweepConfig: FullLogRegBoundarySweepConfig{
			MinTargetZ:  -0.01,
			MaxTargetZ:  0.01,
			Points:      3,
			Repetitions: 1,
		},
	})
	if err == nil {
		t.Fatalf("expected error for invalid safety factor")
	}
}
