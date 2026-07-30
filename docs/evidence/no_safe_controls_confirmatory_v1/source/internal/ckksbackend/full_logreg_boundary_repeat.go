package ckksbackend

import (
	"fmt"
	"math"
)

// FullLogRegBoundaryRepeatConfig defines repeated boundary evaluation settings.
type FullLogRegBoundaryRepeatConfig struct {
	Repetitions int
}

// FullLogRegBoundaryRepeatRecord records one repeated boundary execution.
type FullLogRegBoundaryRepeatRecord struct {
	CaseIndex  int
	Repetition int

	BoundaryResult FullLogRegBoundaryResult
}

// FullLogRegBoundaryRepeatSummary summarizes repeated boundary execution.
type FullLogRegBoundaryRepeatSummary struct {
	Cases       int
	Repetitions int
	Runs        int

	Flips         int
	StableFlips   int
	AmbiguousRuns int
	StableRuns    int
	BoundaryRuns  int

	MaxZError  float64
	MaxYError  float64
	MeanZError float64
	MeanYError float64
}

// DefaultFullLogRegBoundaryRepeatConfig returns the current repeated boundary config.
func DefaultFullLogRegBoundaryRepeatConfig() FullLogRegBoundaryRepeatConfig {
	return FullLogRegBoundaryRepeatConfig{
		Repetitions: 5,
	}
}

// RunFullLogRegBoundaryRepeatProbe runs repeated CKKS boundary decision evaluation.
func (c Context) RunFullLogRegBoundaryRepeatProbe(
	config FullLogRegBoundaryRepeatConfig,
) ([]FullLogRegBoundaryRepeatRecord, FullLogRegBoundaryRepeatSummary, error) {
	if config.Repetitions <= 0 {
		return nil, FullLogRegBoundaryRepeatSummary{}, fmt.Errorf("repetitions must be positive: %d", config.Repetitions)
	}

	boundaryConfig := DefaultFullLogRegBoundaryConfig()
	cases := DefaultFullLogRegBoundaryCases()

	records := make([]FullLogRegBoundaryRepeatRecord, 0, len(cases)*config.Repetitions)

	for rep := 0; rep < config.Repetitions; rep++ {
		for caseIndex, probeCase := range cases {
			result, err := c.RunFullLogRegProbeCase(FullLogRegProbeCase{
				Input: probeCase.Input,
			})
			if err != nil {
				return nil, FullLogRegBoundaryRepeatSummary{}, fmt.Errorf(
					"run boundary repeat case %d repetition %d: %w",
					caseIndex,
					rep,
					err,
				)
			}

			margin := math.Abs(result.PlainY - boundaryConfig.Threshold)
			boundary := margin <= boundaryConfig.Gamma
			ambiguous := margin <= boundaryConfig.MarginFloor
			stable := boundary && !ambiguous

			records = append(records, FullLogRegBoundaryRepeatRecord{
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

	summary := summarizeFullLogRegBoundaryRepeat(records, len(cases), config.Repetitions)

	return records, summary, nil
}

func summarizeFullLogRegBoundaryRepeat(
	records []FullLogRegBoundaryRepeatRecord,
	cases int,
	repetitions int,
) FullLogRegBoundaryRepeatSummary {
	summary := FullLogRegBoundaryRepeatSummary{
		Cases:       cases,
		Repetitions: repetitions,
		Runs:        len(records),
	}

	sumZError := 0.0
	sumYError := 0.0

	for _, record := range records {
		result := record.BoundaryResult.Result

		sumZError += result.ZError
		sumYError += result.YError

		if result.ZError > summary.MaxZError {
			summary.MaxZError = result.ZError
		}

		if result.YError > summary.MaxYError {
			summary.MaxYError = result.YError
		}

		if record.BoundaryResult.Boundary {
			summary.BoundaryRuns++
		}

		if record.BoundaryResult.Ambiguous {
			summary.AmbiguousRuns++
		}

		if record.BoundaryResult.Stable {
			summary.StableRuns++
		}

		if result.DecisionFlip {
			summary.Flips++
		}

		if record.BoundaryResult.Stable && result.DecisionFlip {
			summary.StableFlips++
		}
	}

	if len(records) > 0 {
		summary.MeanZError = sumZError / float64(len(records))
		summary.MeanYError = sumYError / float64(len(records))
	}

	return summary
}
