package ckksbackend

import (
	"fmt"
	"math"
)

// FullLogRegBoundarySweepConfig defines dense boundary sweep settings.
type FullLogRegBoundarySweepConfig struct {
	MinTargetZ  float64
	MaxTargetZ  float64
	Points      int
	Repetitions int
}

// FullLogRegBoundarySweepRecord records one dense boundary sweep execution.
type FullLogRegBoundarySweepRecord struct {
	CaseIndex  int
	Repetition int

	BoundaryResult FullLogRegBoundaryResult
}

// FullLogRegBoundarySweepSummary summarizes dense boundary sweep execution.
type FullLogRegBoundarySweepSummary struct {
	Points      int
	Repetitions int
	Runs        int

	Flips          int
	StableFlips    int
	AmbiguousFlips int

	BoundaryRuns  int
	StableRuns    int
	AmbiguousRuns int

	MinMargin float64
	MaxMargin float64

	MaxZError  float64
	MeanZError float64
	MaxYError  float64
	MeanYError float64
}

// DefaultFullLogRegBoundarySweepConfig returns the current dense sweep config.
func DefaultFullLogRegBoundarySweepConfig() FullLogRegBoundarySweepConfig {
	return FullLogRegBoundarySweepConfig{
		MinTargetZ:  -0.05,
		MaxTargetZ:  0.05,
		Points:      101,
		Repetitions: 3,
	}
}

// RunFullLogRegBoundarySweepProbe runs dense CKKS boundary decision evaluation.
func (c Context) RunFullLogRegBoundarySweepProbe(
	config FullLogRegBoundarySweepConfig,
) ([]FullLogRegBoundarySweepRecord, FullLogRegBoundarySweepSummary, error) {
	if config.Points < 2 {
		return nil, FullLogRegBoundarySweepSummary{}, fmt.Errorf("points must be at least 2: %d", config.Points)
	}

	if config.Repetitions <= 0 {
		return nil, FullLogRegBoundarySweepSummary{}, fmt.Errorf("repetitions must be positive: %d", config.Repetitions)
	}

	if config.MaxTargetZ <= config.MinTargetZ {
		return nil, FullLogRegBoundarySweepSummary{}, fmt.Errorf(
			"max target z must be greater than min target z: min=%.10f max=%.10f",
			config.MinTargetZ,
			config.MaxTargetZ,
		)
	}

	boundaryConfig := DefaultFullLogRegBoundaryConfig()
	records := make([]FullLogRegBoundarySweepRecord, 0, config.Points*config.Repetitions)

	for rep := 0; rep < config.Repetitions; rep++ {
		for caseIndex := 0; caseIndex < config.Points; caseIndex++ {
			targetZ := targetZAtIndex(config, caseIndex)
			probeCase := FullLogRegBoundaryCase{
				TargetZ: targetZ,
				Input:   inputForTargetZ(targetZ),
			}

			result, err := c.RunFullLogRegProbeCase(FullLogRegProbeCase{
				Input: probeCase.Input,
			})
			if err != nil {
				return nil, FullLogRegBoundarySweepSummary{}, fmt.Errorf(
					"run boundary sweep case %d repetition %d: %w",
					caseIndex,
					rep,
					err,
				)
			}

			margin := math.Abs(result.PlainY - boundaryConfig.Threshold)
			boundary := margin <= boundaryConfig.Gamma
			ambiguous := margin <= boundaryConfig.MarginFloor
			stable := boundary && !ambiguous

			records = append(records, FullLogRegBoundarySweepRecord{
				CaseIndex:  caseIndex,
				Repetition: rep,
				BoundaryResult: FullLogRegBoundaryResult{
					Case: probeCase,

					Result: result,

					Margin:      margin,
					Boundary:    boundary,
					Ambiguous:   ambiguous,
					Stable:      stable,
					TargetError: math.Abs(result.PlainZ - probeCase.TargetZ),
				},
			})
		}
	}

	summary := summarizeFullLogRegBoundarySweep(records, config.Points, config.Repetitions)

	return records, summary, nil
}

func targetZAtIndex(config FullLogRegBoundarySweepConfig, index int) float64 {
	step := (config.MaxTargetZ - config.MinTargetZ) / float64(config.Points-1)
	return config.MinTargetZ + step*float64(index)
}

func summarizeFullLogRegBoundarySweep(
	records []FullLogRegBoundarySweepRecord,
	points int,
	repetitions int,
) FullLogRegBoundarySweepSummary {
	summary := FullLogRegBoundarySweepSummary{
		Points:      points,
		Repetitions: repetitions,
		Runs:        len(records),
		MinMargin:   math.Inf(1),
	}

	sumZError := 0.0
	sumYError := 0.0

	for _, record := range records {
		boundary := record.BoundaryResult
		result := boundary.Result

		sumZError += result.ZError
		sumYError += result.YError

		if boundary.Margin < summary.MinMargin {
			summary.MinMargin = boundary.Margin
		}

		if boundary.Margin > summary.MaxMargin {
			summary.MaxMargin = boundary.Margin
		}

		if result.ZError > summary.MaxZError {
			summary.MaxZError = result.ZError
		}

		if result.YError > summary.MaxYError {
			summary.MaxYError = result.YError
		}

		if boundary.Boundary {
			summary.BoundaryRuns++
		}

		if boundary.Stable {
			summary.StableRuns++
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
	}

	if len(records) > 0 {
		summary.MeanZError = sumZError / float64(len(records))
		summary.MeanYError = sumYError / float64(len(records))
	}

	if math.IsInf(summary.MinMargin, 1) {
		summary.MinMargin = 0
	}

	return summary
}
