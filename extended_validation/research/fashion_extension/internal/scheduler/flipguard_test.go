package scheduler

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestBuildFlipGuardSchedule(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()

	opts := benchmarks.DefaultBoundaryFocusedOptions()
	opts.MaxBoundary = 20
	opts.MaxNonBoundary = 20

	samples := benchmarks.GenerateLogRegSmallSamples(opts)
	inputs := make([]map[ir.NodeID]float64, 0, len(samples))

	for _, sample := range samples {
		inputs = append(inputs, sample.Inputs())
	}

	analysisResult, err := analysis.AnalyzeBoundsAndSensitivity(
		g,
		inputs,
		opts.Threshold,
		0.05,
	)
	if err != nil {
		t.Fatalf("AnalyzeBoundsAndSensitivity failed: %v", err)
	}

	fg, err := BuildFlipGuardSchedule(g, analysisResult, FlipGuardOptions{
		MinBits: runtime.PrecisionBits(0),
		MaxBits: runtime.PrecisionBits(12),

		GlobalTolerance:    0.02,
		SafetyFactor:       0.5,
		UseProtectedMargin: true,

		ScheduleOptions: DefaultIntermediateOptions(),
	})
	if err != nil {
		t.Fatalf("BuildFlipGuardSchedule failed: %v", err)
	}

	if len(fg.Schedule) == 0 {
		t.Fatalf("expected non-empty schedule")
	}

	if fg.Budget <= 0 {
		t.Fatalf("expected positive budget")
	}

	if !fg.Feasible {
		t.Fatalf("expected feasible schedule: estimated %.12f budget %.12f", fg.EstimatedError, fg.Budget)
	}

	if fg.EstimatedError > fg.Budget {
		t.Fatalf("estimated error exceeds budget: estimated %.12f budget %.12f", fg.EstimatedError, fg.Budget)
	}

	if _, ok := fg.Schedule[ir.NodeID("x1")]; ok {
		t.Fatalf("input node x1 should not be scheduled")
	}

	if _, ok := fg.Schedule[ir.NodeID("y")]; ok {
		t.Fatalf("output node y should not be scheduled")
	}
}
