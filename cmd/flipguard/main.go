package main

import (
	"fmt"
	"log"
	"math"
	"path/filepath"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/hasslelee/flipguard/internal/ir"
	"github.com/hasslelee/flipguard/internal/report"
	"github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/scheduler"
)

type method struct {
	name     string
	schedule runtime.PrecisionSchedule
}

type flipGuardCase struct {
	name     string
	result   *scheduler.FlipGuardResult
	analysis *analysis.BoundSensitivityResult
}

func main() {
	g := benchmarks.NewLogRegSmallGraph()

	sampleOpts := benchmarks.DefaultBoundaryFocusedOptions()
	samples := benchmarks.GenerateLogRegSmallSamples(sampleOpts)

	threshold := sampleOpts.Threshold
	gamma := sampleOpts.Gamma
	marginFloor := 1e-4

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

	analysisMinFloor := cloneAnalysisWithProtectedMargin(
		analysisP5,
		minPositiveMarginAboveFloor(analysisP5.Margins, marginFloor),
		0.0,
	)

	flipGuardP5M12, err := buildFlipGuard(g, analysisP5, 12)
	if err != nil {
		log.Fatalf("FlipGuard p5 max12 scheduling failed: %v", err)
	}

	flipGuardP5M16, err := buildFlipGuard(g, analysisP5, 16)
	if err != nil {
		log.Fatalf("FlipGuard p5 max16 scheduling failed: %v", err)
	}

	flipGuardP1M16, err := buildFlipGuard(g, analysisP1, 16)
	if err != nil {
		log.Fatalf("FlipGuard p1 max16 scheduling failed: %v", err)
	}

	flipGuardMinM16, err := buildFlipGuard(g, analysisMinFloor, 16)
	if err != nil {
		log.Fatalf("FlipGuard min-floor max16 scheduling failed: %v", err)
	}

	flipCases := []flipGuardCase{
		{
			name:     "flipguard_p5_m12",
			result:   flipGuardP5M12,
			analysis: analysisP5,
		},
		{
			name:     "flipguard_p5_m16",
			result:   flipGuardP5M16,
			analysis: analysisP5,
		},
		{
			name:     "flipguard_p1_m16",
			result:   flipGuardP1M16,
			analysis: analysisP1,
		},
		{
			name:     "flipguard_minfloor_m16",
			result:   flipGuardMinM16,
			analysis: analysisMinFloor,
		},
	}

	fmt.Println("FlipGuard demo: logreg_small decision-stability simulation")
	fmt.Printf("threshold=%.4f gamma=%.4f margin_floor=%.6f samples=%d\n", threshold, gamma, marginFloor, len(samples))
	fmt.Println()

	for _, c := range flipCases {
		printFlipGuardResult(c.name, c.result, c.analysis)
	}

	methods := []method{
		{
			name:     "plain",
			schedule: nil,
		},
		{
			name:     "uniform_bits_16",
			schedule: scheduler.UniformSchedule(g, runtime.PrecisionBits(16), scheduler.DefaultIntermediateOptions()),
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
			name:     "flipguard_p5_m12",
			schedule: flipGuardP5M12.Schedule,
		},
		{
			name:     "flipguard_p5_m16",
			schedule: flipGuardP5M16.Schedule,
		},
		{
			name:     "flipguard_p1_m16",
			schedule: flipGuardP1M16.Schedule,
		},
		{
			name:     "flipguard_minfloor_m16",
			schedule: flipGuardMinM16.Schedule,
		},
	}

	fmt.Printf("%-24s %8s %8s %10s %10s %10s %15s %15s %15s %15s %12s %10s\n",
		"method",
		"samples",
		"flips",
		"flip_rate",
		"boundary",
		"ambig",
		"boundary_flips",
		"boundary_rate",
		"stable_b_flips",
		"stable_b_rate",
		"max_error",
		"avg_bits",
	)

	summaryRows := make([]report.SummaryRow, 0, len(methods))
	recordsByMethod := make(map[string][]analysis.DecisionRecord)

	for _, m := range methods {
		records, err := evaluateMethodRecords(g, samples, threshold, gamma, marginFloor, m.schedule)
		if err != nil {
			log.Fatalf("method %s failed: %v", m.name, err)
		}

		stats := analysis.SummarizeDecisions(records)
		row := report.NewSummaryRow(m.name, stats, m.schedule)

		summaryRows = append(summaryRows, row)
		recordsByMethod[m.name] = records

		fmt.Printf("%-24s %8d %8d %10.4f %10d %10d %15d %15.4f %15d %15.4f %12.6f %10.2f\n",
			row.Method,
			row.Samples,
			row.Flips,
			row.FlipRate,
			row.BoundaryCount,
			row.AmbiguousCount,
			row.BoundaryFlips,
			row.BoundaryRate,
			row.StableBoundaryFlips,
			row.StableBoundaryRate,
			row.MaxError,
			row.AvgBits,
		)
	}

	if err := exportResults("results/logreg_small", summaryRows, recordsByMethod, flipCases, threshold, gamma, marginFloor, len(samples)); err != nil {
		log.Fatalf("export results failed: %v", err)
	}

	fmt.Println()
	fmt.Println("Exported CSV and Markdown files to results/logreg_small/")
}

func exportResults(
	outputDir string,
	summaryRows []report.SummaryRow,
	recordsByMethod map[string][]analysis.DecisionRecord,
	flipCases []flipGuardCase,
	threshold float64,
	gamma float64,
	marginFloor float64,
	samples int,
) error {
	if err := report.WriteSummaryCSV(filepath.Join(outputDir, "summary.csv"), summaryRows); err != nil {
		return err
	}

	for _, c := range flipCases {
		path := filepath.Join(outputDir, fmt.Sprintf("schedule_%s.csv", c.name))
		if err := report.WriteScheduleCSV(path, c.result); err != nil {
			return err
		}
	}

	for method, records := range recordsByMethod {
		path := filepath.Join(outputDir, fmt.Sprintf("records_%s.csv", method))
		if err := report.WriteDecisionRecordsCSV(path, method, records); err != nil {
			return err
		}
	}

	scheduleSummaries := make([]report.ScheduleSummary, 0, len(flipCases))
	for _, c := range flipCases {
		scheduleSummaries = append(
			scheduleSummaries,
			report.NewScheduleSummary(c.name, c.result, c.analysis.ProtectedMargin),
		)
	}

	md := report.MarkdownReport{
		Title:             "FlipGuard logreg_small Experiment Report",
		Threshold:         threshold,
		Gamma:             gamma,
		MarginFloor:       marginFloor,
		Samples:           samples,
		SummaryRows:       summaryRows,
		ScheduleSummaries: scheduleSummaries,
	}

	if err := report.WriteMarkdownReport(filepath.Join(outputDir, "report.md"), md); err != nil {
		return err
	}

	return nil
}

func buildFlipGuard(
	g *ir.Graph,
	analysisResult *analysis.BoundSensitivityResult,
	maxBits runtime.PrecisionBits,
) (*scheduler.FlipGuardResult, error) {
	opts := scheduler.DefaultFlipGuardOptions()
	opts.MaxBits = maxBits
	opts.MinBits = 0
	opts.GlobalTolerance = 0.02
	opts.SafetyFactor = 0.5
	opts.UseProtectedMargin = true
	opts.ScheduleOptions = scheduler.DefaultIntermediateOptions()

	return scheduler.BuildFlipGuardSchedule(g, analysisResult, opts)
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

func minPositiveMarginAboveFloor(margins []float64, floor float64) float64 {
	minMargin := math.Inf(1)

	for _, margin := range margins {
		if margin > floor && margin < minMargin {
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
		report.AverageBits(result.Schedule),
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

func evaluateMethodRecords(
	g *ir.Graph,
	samples []benchmarks.LogRegSmallSample,
	threshold float64,
	gamma float64,
	marginFloor float64,
	schedule runtime.PrecisionSchedule,
) ([]analysis.DecisionRecord, error) {
	records := make([]analysis.DecisionRecord, 0, len(samples))

	for i, sample := range samples {
		plain, err := runtime.EvalPlain(g, sample.Inputs())
		if err != nil {
			return nil, err
		}

		approxScore := plain.Output
		if schedule != nil {
			quantized, err := runtime.EvalQuantized(g, sample.Inputs(), schedule)
			if err != nil {
				return nil, err
			}
			approxScore = quantized.Output
		}

		record := analysis.AnalyzeDecisionWithMarginFloor(
			i,
			plain.Output,
			approxScore,
			threshold,
			gamma,
			marginFloor,
		)
		records = append(records, record)
	}

	return records, nil
}
