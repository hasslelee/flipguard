package ckksbackend

import "testing"

func TestRunFullLogRegBoundaryRepeatProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	config := FullLogRegBoundaryRepeatConfig{
		Repetitions: 2,
	}

	records, summary, err := ctx.RunFullLogRegBoundaryRepeatProbe(config)
	if err != nil {
		t.Fatalf("RunFullLogRegBoundaryRepeatProbe failed: %v", err)
	}

	wantRuns := len(DefaultFullLogRegBoundaryCases()) * config.Repetitions
	if len(records) != wantRuns {
		t.Fatalf("expected %d records, got %d", wantRuns, len(records))
	}

	if summary.Runs != wantRuns {
		t.Fatalf("expected summary runs %d, got %d", wantRuns, summary.Runs)
	}

	if summary.Cases != len(DefaultFullLogRegBoundaryCases()) {
		t.Fatalf("unexpected case count: got %d", summary.Cases)
	}

	if summary.Repetitions != config.Repetitions {
		t.Fatalf("unexpected repetition count: got %d", summary.Repetitions)
	}

	if summary.Flips != 0 {
		t.Fatalf("expected zero flips, got %d", summary.Flips)
	}

	if summary.StableFlips != 0 {
		t.Fatalf("expected zero stable flips, got %d", summary.StableFlips)
	}

	if summary.StableRuns == 0 {
		t.Fatalf("expected at least one stable run")
	}

	if summary.AmbiguousRuns == 0 {
		t.Fatalf("expected at least one ambiguous run")
	}

	if summary.MaxYError > 1e-2 {
		t.Fatalf("max y error too large: %.10f", summary.MaxYError)
	}
}

func TestRunFullLogRegBoundaryRepeatProbeRejectsInvalidRepetitions(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	_, _, err = ctx.RunFullLogRegBoundaryRepeatProbe(FullLogRegBoundaryRepeatConfig{
		Repetitions: 0,
	})
	if err == nil {
		t.Fatalf("expected error for zero repetitions")
	}
}
