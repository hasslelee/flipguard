package main

import (
	"fmt"
	"log"
	"math"

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

	sampleOpts := benchmarks.DefaultBoundaryFocusedOptions()
	samples := benchmarks.GenerateLogRegSmallSamples(sampleOpts)

	threshold := sampleOpts.Threshold
	gamma := sampleOpts.Gamma

	analysisInputs := make([]map[ir.NodeID]float64, 0, len(samples))
	for _, sample := range samples {
		analysisInputs = append(analysisInputs, sample.Inputs())
	}

	analysisP5, err := analysis.AnalyzeBoundsAndSensitivity(
		g,
		analysisInputs,
		threshold,
		0.05,
	)
	if err != nil {
		log.Fatalf("p5 analysis failed: %v", err)
	}

	analysisP1, err := analysis.AnalyzeBoundsAndSensitivity(
		g,
		analysisInputs,
		threshold,
		0.01,
	)
	if err != nil {
		log.Fatalf("p1 analysis failed: %v", err)
	}

	analysisMin := cloneAnalysisWithProtectedMargin(
		analysisP5,
		minPositiveMargin(analysisP5.Margins),
		0.0,
	)

	flipGuardP5, err := scheduler.BuildFlipGuardSchedule(
		g,
		analysisP5,
		scheduler.DefaultFlipGuardOptions(),
	)
	if err != nil {
		log.Fatalf("FlipGuard p5 scheduling failed: %v", err)
	}

	flipGuardP1, err := scheduler.BuildFlipGuardSchedule(
		g,
		analysisP1,
		scheduler.DefaultFlipGuardOptions(),
	)
	if err != nil {
		log.Fatalf("FlipGuard p1 scheduling failed: %v", err)
	}

	flipGuardMin, err := scheduler.BuildFlipGuardSchedule(
		g,
		analysisMin,
		scheduler.DefaultFlipGuardOptions(),
	)
	if err != nil {
		log.Fatalf("FlipGuard min scheduling failed: %v", err)
	}

	fmt.Println("FlipGuard demo: logreg_small decision-stability simulation")
	fmt.Printf("threshold=%.4f gamma=%.4f samples=%d\n", threshold, gamma, len(samples))
	fmt.Println()

	printFlipGuardResult("flipguard_p5", flipGuardP5, analysisP5)
	printFlipGuardResult("flipguard_p1", flipGuardP1, analysisP1)
	printFlipGuardResult("flipguard_min", flipGuardMin, analysisMin)

	methods := []method{
		{
			name:     "plain",
			schedule: nil,
		},
		{
			name:     "uniform_bits_12",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(12), scheduler.DefaultIntermediateOptions()),
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
		{
			name:     "flipguard_p5",
			schedule: flipGuardP5.Schedule,
		},
		{
			name:     "flipguard_p1",
			schedule: flipGuardP1.Schedule,
		},
		{
			name:     "flipguard_min",
			schedule: flipGuardMin.Schedule,
		},
	}

	fmt.Printf("%-16s %8s %8s %10s %10s %15s %15s %12s %10s\n",
		"method",
		"samples",
		"flips",
		"flip_rate",
		"boundary",
		"boundary_flips",
		"boundary_rate",
		"max_error",
		"avg_bits",
	)

	for _, m := range methods {
		stats, err := evaluateMethod(g, samples, threshold, gamma, m.schedule)
		if err != nil {
			log.Fatalf("method %s failed: %v", m.name, err)
		}

		fmt.Printf("%-16s %8d %8d %10.4f %10d %15d %15.4f %12.6f %10.2f\n",
			m.name,
			stats.Count,
			stats.FlipCount,
			stats.FlipRate,
			stats.BoundaryCount,
			stats.BoundaryFlipCount,
			stats.BoundaryFlipRate,
			stats.MaxError,
			averageBits(m.schedule),
		)
	}
}

func cloneAnalysisWithProtectedMargin(
	src *analysis.BoundSensitivityResult,
	protectedMargin float64,
	protectedPercentile float64,
) *analysis.BoundSensitivityResult {
	if src == nil {
		return nil
	}

	return &analysis.BoundSensitivityResult{
		Intervals:           src.Intervals,
		Sensitivity:         src.Sensitivity,
		Outputs:             src.Outputs,
		Margins:             src.Margins,
		ProtectedMargin:     protectedMargin,
		ProtectedPercentile: protectedPercentile,
	}
}

func minPositiveMargin(margins []float64) float64 {
	minMargin := math.Inf(1)

	for _, margin := range margins {
		if margin > 0 && margin < minMargin {
			minMargin = margin
		}
	}

	if math.IsInf(minMargin, 1) {
		return 0
	}

	return minMargin
}

func printFlipGuardResult(
	name string,
	result *scheduler.FlipGuardResult,
	analysisResult *analysis.BoundSensitivityResult,
) {
	fmt.Printf("%s budget=%.8f source=%s estimated_error=%.8f feasible=%v protected_margin=%.8f protected_percentile=%.4f avg_bits=%.2f\n",
		name,
		result.Budget,
		result.BudgetSource,
		result.EstimatedError,
		result.Feasible,
		analysisResult.ProtectedMargin,
		analysisResult.ProtectedPercentile,
		averageBits(result.Schedule),
	)

	printFlipGuardSchedule(result)
}

func printFlipGuardSchedule(result *scheduler.FlipGuardResult) {
	fmt.Println("Schedule:")
	fmt.Printf("%-8s %-12s %12s %6s %12s %12s %15s\n",
		"node",
		"op",
		"sensitivity",
		"bits",
		"step",
		"delta",
		"contribution",
	)

	totalBits := 0
	minBits := 1 << 30
	maxBits := -1

	for _, n := range result.Nodes {
		bits := int(n.Bits)
		totalBits += bits
		if bits < minBits {
			minBits = bits
		}
		if bits > maxBits {
			maxBits = bits
		}

		fmt.Printf("%-8s %-12s %12.6f %6d %12.8f %12.8f %15.8f\n",
			n.NodeID,
			n.Op,
			n.Sensitivity,
			bits,
			n.Step,
			n.Delta,
			n.Contribution,
		)
	}

	if len(result.Nodes) > 0 {
		avgBits := float64(totalBits) / float64(len(result.Nodes))
		fmt.Printf("Schedule summary: nodes=%d avg_bits=%.2f min_bits=%d max_bits=%d\n\n",
			len(result.Nodes),
			avgBits,
			minBits,
			maxBits,
		)
		return
	}

	fmt.Println()
}

func averageBits(schedule runtime.PrecisionSchedule) float64 {
	if len(schedule) == 0 {
		return 0
	}

	total := 0
	for _, bits := range schedule {
		total += int(bits)
	}

	return float64(total) / float64(len(schedule))
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
