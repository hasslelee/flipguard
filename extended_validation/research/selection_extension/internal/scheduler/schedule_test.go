package scheduler

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

func TestUniformScheduleDefaultIntermediateOptions(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()

	s := UniformSchedule(g, runtime.PrecisionBits(4), DefaultIntermediateOptions())

	if _, ok := s[ir.NodeID("x1")]; ok {
		t.Fatalf("input node x1 should not be scheduled")
	}
	if _, ok := s[ir.NodeID("bias")]; ok {
		t.Fatalf("constant node bias should not be scheduled")
	}
	if _, ok := s[ir.NodeID("y")]; ok {
		t.Fatalf("output node y should not be scheduled by default")
	}

	if bits, ok := s[ir.NodeID("z")]; !ok {
		t.Fatalf("intermediate node z should be scheduled")
	} else if bits != runtime.PrecisionBits(4) {
		t.Fatalf("unexpected bits for z: got %d", bits)
	}
}

func TestUniformScheduleIncludeOutput(t *testing.T) {
	g := benchmarks.NewLogRegSmallGraph()

	opts := DefaultIntermediateOptions()
	opts.IncludeOutput = true

	s := UniformSchedule(g, runtime.PrecisionBits(8), opts)

	if bits, ok := s[ir.NodeID("y")]; !ok {
		t.Fatalf("output node y should be scheduled")
	} else if bits != runtime.PrecisionBits(8) {
		t.Fatalf("unexpected bits for y: got %d", bits)
	}
}
