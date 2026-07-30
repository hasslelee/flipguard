package scheduler

import (
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
)

// ScheduleOptions controls which nodes are quantized.
type ScheduleOptions struct {
	IncludeInputs    bool
	IncludeConstants bool
	IncludeOutput    bool
}

// DefaultIntermediateOptions quantizes intermediate computation nodes only.
//
// Inputs, constants, and the final output are excluded.
// This matches the first FlipGuard simulation setting.
func DefaultIntermediateOptions() ScheduleOptions {
	return ScheduleOptions{
		IncludeInputs:    false,
		IncludeConstants: false,
		IncludeOutput:    false,
	}
}

// UniformSchedule creates a schedule that assigns the same precision bits
// to all selected nodes.
func UniformSchedule(g *ir.Graph, bits runtime.PrecisionBits, opts ScheduleOptions) runtime.PrecisionSchedule {
	schedule := runtime.PrecisionSchedule{}

	if g == nil {
		return schedule
	}

	for _, n := range g.Nodes() {
		if !opts.IncludeInputs && n.Op == ir.OpInput {
			continue
		}
		if !opts.IncludeConstants && n.Op == ir.OpConst {
			continue
		}
		if !opts.IncludeOutput && n.ID == g.Output {
			continue
		}

		schedule[n.ID] = bits
	}

	return schedule
}
