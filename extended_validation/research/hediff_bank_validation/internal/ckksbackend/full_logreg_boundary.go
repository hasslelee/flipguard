package ckksbackend

import (
	"fmt"
	"math"
)

// FullLogRegBoundaryCase defines one boundary-focused full logreg input.
type FullLogRegBoundaryCase struct {
	TargetZ float64
	Input   LogRegSmallInput
}

// FullLogRegBoundaryResult records decision behavior near the threshold.
type FullLogRegBoundaryResult struct {
	Case FullLogRegBoundaryCase

	Result FullLogRegProbeResult

	Margin      float64
	Boundary    bool
	Ambiguous   bool
	Stable      bool
	TargetError float64
}

// FullLogRegBoundaryConfig defines the boundary decision analysis settings.
type FullLogRegBoundaryConfig struct {
	Threshold   float64
	Gamma       float64
	MarginFloor float64
}

// DefaultFullLogRegBoundaryConfig returns the current boundary analysis config.
func DefaultFullLogRegBoundaryConfig() FullLogRegBoundaryConfig {
	return FullLogRegBoundaryConfig{
		Threshold:   0.5,
		Gamma:       0.05,
		MarginFloor: 0.0001,
	}
}

// DefaultFullLogRegBoundaryCases returns deterministic samples around the
// decision boundary of the current polynomial approximation.
func DefaultFullLogRegBoundaryCases() []FullLogRegBoundaryCase {
	targetZValues := []float64{
		-0.0500,
		-0.0200,
		-0.0100,
		-0.0050,
		-0.0010,
		-0.0005,
		0.0005,
		0.0010,
		0.0050,
		0.0100,
		0.0200,
		0.0500,
	}

	cases := make([]FullLogRegBoundaryCase, 0, len(targetZValues))
	for _, targetZ := range targetZValues {
		cases = append(cases, FullLogRegBoundaryCase{
			TargetZ: targetZ,
			Input:   inputForTargetZ(targetZ),
		})
	}

	return cases
}

// RunFullLogRegBoundaryProbe runs CKKS end-to-end evaluation on boundary samples.
func (c Context) RunFullLogRegBoundaryProbe() ([]FullLogRegBoundaryResult, error) {
	config := DefaultFullLogRegBoundaryConfig()
	cases := DefaultFullLogRegBoundaryCases()

	results := make([]FullLogRegBoundaryResult, 0, len(cases))

	for i, probeCase := range cases {
		result, err := c.RunFullLogRegProbeCase(FullLogRegProbeCase{
			Input: probeCase.Input,
		})
		if err != nil {
			return nil, fmt.Errorf("run full logreg boundary case %d: %w", i, err)
		}

		margin := math.Abs(result.PlainY - config.Threshold)
		boundary := margin <= config.Gamma
		ambiguous := margin <= config.MarginFloor
		stable := boundary && !ambiguous

		results = append(results, FullLogRegBoundaryResult{
			Case: probeCase,

			Result: result,

			Margin:      margin,
			Boundary:    boundary,
			Ambiguous:   ambiguous,
			Stable:      stable,
			TargetError: math.Abs(result.PlainZ - probeCase.TargetZ),
		})
	}

	return results, nil
}

func inputForTargetZ(targetZ float64) LogRegSmallInput {
	return LogRegSmallInput{
		X1: (targetZ + 0.3) / 0.8,
		X2: 0,
		X3: 0,
	}
}
