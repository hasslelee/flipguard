package ckksbackend

import (
	"math"
	"testing"
)

func TestRunFullLogRegBoundarySweepProbe(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	config := FullLogRegBoundarySweepConfig{
		MinTargetZ:  -0.01,
		MaxTargetZ:  0.01,
		Points:      11,
		Repetitions: 2,
	}

	records, summary, err := ctx.RunFullLogRegBoundarySweepProbe(config)
	if err != nil {
		t.Fatalf("RunFullLogRegBoundarySweepProbe failed: %v", err)
	}

	wantRuns := config.Points * config.Repetitions
	if len(records) != wantRuns {
		t.Fatalf("expected %d records, got %d", wantRuns, len(records))
	}

	if summary.Runs != wantRuns {
		t.Fatalf("expected summary runs %d, got %d", wantRuns, summary.Runs)
	}

	if summary.Points != config.Points {
		t.Fatalf("unexpected point count: got %d", summary.Points)
	}

	if summary.Repetitions != config.Repetitions {
		t.Fatalf("unexpected repetition count: got %d", summary.Repetitions)
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

	if summary.MaxYError > 1e-2 {
		t.Fatalf("max y error too large: %.10f", summary.MaxYError)
	}
}

func TestRunFullLogRegBoundarySweepProbeRejectsInvalidConfig(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	_, _, err = ctx.RunFullLogRegBoundarySweepProbe(FullLogRegBoundarySweepConfig{
		MinTargetZ:  -0.01,
		MaxTargetZ:  0.01,
		Points:      1,
		Repetitions: 1,
	})
	if err == nil {
		t.Fatalf("expected error for invalid points")
	}

	_, _, err = ctx.RunFullLogRegBoundarySweepProbe(FullLogRegBoundarySweepConfig{
		MinTargetZ:  -0.01,
		MaxTargetZ:  0.01,
		Points:      3,
		Repetitions: 0,
	})
	if err == nil {
		t.Fatalf("expected error for invalid repetitions")
	}

	_, _, err = ctx.RunFullLogRegBoundarySweepProbe(FullLogRegBoundarySweepConfig{
		MinTargetZ:  0.01,
		MaxTargetZ:  -0.01,
		Points:      3,
		Repetitions: 1,
	})
	if err == nil {
		t.Fatalf("expected error for invalid target range")
	}
}

func TestTargetZAtIndex(t *testing.T) {
	config := FullLogRegBoundarySweepConfig{
		MinTargetZ:  -0.05,
		MaxTargetZ:  0.05,
		Points:      101,
		Repetitions: 1,
	}

	first := targetZAtIndex(config, 0)
	middle := targetZAtIndex(config, 50)
	last := targetZAtIndex(config, 100)

	if math.Abs(first-(-0.05)) > 1e-12 {
		t.Fatalf("unexpected first target: %.16f", first)
	}

	if math.Abs(middle) > 1e-12 {
		t.Fatalf("unexpected middle target: %.16f", middle)
	}

	if math.Abs(last-0.05) > 1e-12 {
		t.Fatalf("unexpected last target: %.16f", last)
	}
}
