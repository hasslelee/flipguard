package main

import (
	"fmt"
	"log"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/scheduler"
)

type method struct {
	name     string
	schedule runtime.PrecisionSchedule
}

func main() {
	g := benchmarks.NewLogRegSmallGraph()
	samples := benchmarks.DefaultLogRegSmallSamples()

	threshold := benchmarks.LogRegSmallThreshold
	gamma := 0.05

	methods := []method{
		{
			name:     "plain",
			schedule: nil,
		},
		{
			name:     "uniform_bits_8",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(8), scheduler.DefaultIntermediateOptions()),
		},
		{
			name:     "uniform_bits_4",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(4), scheduler.DefaultIntermediateOptions()),
		},
		{
			name:     "uniform_bits_2",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(2), scheduler.DefaultIntermediateOptions()),
		},
		{
			name:     "uniform_bits_0",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(0), scheduler.DefaultIntermediateOptions()),
		},
	}

	fmt.Println("FlipGuard demo: logreg_small decision-stability simulation")
	fmt.Printf("threshold=%.4f gamma=%.4f samples=%d\n\n", threshold, gamma, len(samples))

	fmt.Printf("%-16s %8s %8s %10s %10s %15s %15s %12s\n",
		"method",
		"samples",
		"flips",
		"flip_rate",
		"boundary",
		"boundary_flips",
		"boundary_rate",
		"max_error",
	)

	for _, m := range methods {
		stats, err := evaluateMethod(g, samples, threshold, gamma, m.schedule)
		if err != nil {
			log.Fatalf("method %s failed: %v", m.name, err)
		}

		fmt.Printf("%-16s %8d %8d %10.4f %10d %15d %15.4f %12.6f\n",
			m.name,
			stats.Count,
			stats.FlipCount,
			stats.FlipRate,
			stats.BoundaryCount,
			stats.BoundaryFlipCount,
			stats.BoundaryFlipRate,
			stats.MaxError,
		)
	}
}

func evaluateMethod(
	g *ir.Graph,
	samples []benchmarks.LogRegSmallSample,
	threshold float64,
	gamma float64,
	schedule runtime.PrecisionSchedule,
) (analysis.DecisionStats, error) {
	records := make([]analysis.DecisionRecord, 0, len(samples))

	for i, sample := range samples {
		plain, err := runtime.EvalPlain(g, sample.Inputs())
		if err != nil {
			return analysis.DecisionStats{}, err
		}

		approxScore := plain.Output
		if schedule != nil {
			quantized, err := runtime.EvalQuantized(g, sample.Inputs(), schedule)
			if err != nil {
				return analysis.DecisionStats{}, err
			}
			approxScore = quantized.Output
		}

		record := analysis.AnalyzeDecision(
			i,
			plain.Output,
			approxScore,
			threshold,
			gamma,
		)
		records = append(records, record)
	}

	return analysis.SummarizeDecisions(records), nil
}
