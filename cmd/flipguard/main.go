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

const safetyFactor = 0.5

type method struct {
	name     string
	schedule runtime.PrecisionSchedule
}

type scheduleCase struct {
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

	accuracyOnlyTol002M12, err := buildAccuracyOnly(g, analysisP5, 12, 0.02)
	if err != nil {
		log.Fatalf("accuracy-only tol0.02 max12 scheduling failed: %v", err)
	}

	accuracyOnlyTol002M16, err := buildAccuracyOnly(g, analysisP5, 16, 0.02)
	if err != nil {
		log.Fatalf("accuracy-only tol0.02 max16 scheduling failed: %v", err)
	}

	accuracyOnlyTol0005M16, err := buildAccuracyOnly(g, analysisP5, 16, 0.005)
	if err != nil {
		log.Fatalf("accuracy-only tol0.005 max16 scheduling failed: %v", err)
	}

	scheduleCases := []scheduleCase{
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
		{
			name:     "accuracy_only_tol002_m12",
			result:   accuracyOnlyTol002M12,
			analysis: analysisP5,
		},
		{
			name:     "accuracy_only_tol002_m16",
			result:   accuracyOnlyTol002M16,
			analysis: analysisP5,
		},
		{
			name:     "accuracy_only_tol0005_m16",
			result:   accuracyOnlyTol0005M16,
			analysis: analysisP5,
		},
	}

	fmt.Println("FlipGuard demo: logreg_small decision-stability simulation")
	fmt.Printf("threshold=%.4f gamma=%.4f margin_floor=%.6f samples=%d\n", threshold, gamma, marginFloor, len(samples))
	fmt.Printf("p5_budget=%.8f p1_budget=%.8f safety_factor=%.2f\n\n",
		certBudget(analysisP5),
		certBudget(analysisP1),
		safetyFactor,
	)

	for _, c := range scheduleCases {
		printScheduleResult(c.name, c.result, c.analysis)
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
			name:     "accuracy_only_tol002_m12",
			schedule: accuracyOnlyTol002M12.Schedule,
		},
		{
			name:     "accuracy_only_tol002_m16",
			schedule: accuracyOnlyTol002M16.Schedule,
		},
		{
			name:     "accuracy_only_tol0005_m16",
			schedule: accuracyOnlyTol0005M16.Schedule,
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

	fmt.Printf("%-28s %8s %8s %10s %15s %15s %12s %8s %8s %10s %10s %10s\n",
		"method",
		"samples",
		"flips",
		"flip_rate",
		"stable_b_flips",
		"stable_b_rate",
		"est_error",
		"p5_cert",
		"p1_cert",
		"avg_bits",
		"save_u12",
		"save_u16",
	)

	summaryRows := make([]report.SummaryRow, 0, len(methods))
	recordsByMethod := make(map[string][]analysis.DecisionRecord)

	for _, m := range methods {
		records, err := evaluateMethodRecords(g, samples, threshold, gamma, marginFloor, m.schedule)
		if err != nil {
			log.Fatalf("method %s failed: %v", m.name, err)
		}

		stats := analysis.SummarizeDecisions(records)
		cert := certifySchedule(analysisP5, analysisP1, m.schedule)
		row := report.NewSummaryRow(m.name, stats, m.schedule, cert)

		summaryRows = append(summaryRows, row)
		recordsByMethod[m.name] = records
	}

	summaryRows = attachSavingRates(summaryRows)

	for _, row := range summaryRows {
		fmt.Printf("%-28s %8d %8d %10.4f %15d %15.4f %12.6f %8t %8t %10.2f %10.2f %10.2f\n",
			row.Method,
			row.Samples,
			row.Flips,
			row.FlipRate,
			row.StableBoundaryFlips,
			row.StableBoundaryRate,
			row.EstimatedError,
			row.P5Certified,
			row.P1Certified,
			row.AvgBits,
			row.SavingVsUniform12Pct,
			row.SavingVsUniform16Pct,
		)
	}

	if err := exportResults("results/logreg_small", summaryRows, recordsByMethod, scheduleCases, threshold, gamma, marginFloor, len(samples)); err != nil {
		log.Fatalf("export results failed: %v", err)
	}

	fmt.Println()
	fmt.Println("Exported CSV and Markdown files to results/logreg_small/")
}

func exportResults(
	outputDir string,
	summaryRows []report.SummaryRow,
	recordsByMethod map[string][]analysis.DecisionRecord,
	scheduleCases []scheduleCase,
	threshold float64,
	gamma float64,
	marginFloor float64,
	samples int,
) error {
	if err := report.WriteSummaryCSV(filepath.Join(outputDir, "summary.csv"), summaryRows); err != nil {
		return err
	}

	for _, c := range scheduleCases {
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

	scheduleSummaries := make([]report.ScheduleSummary, 0, len(scheduleCases))
	for _, c := range scheduleCases {
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

	if err := report.WritePaperTableMarkdown(
		filepath.Join(outputDir, "paper_table.md"),
		"Paper-Ready FlipGuard Result Table",
		summaryRows,
	); err != nil {
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
	opts.SafetyFactor = safetyFactor
	opts.UseProtectedMargin = true
	opts.ScheduleOptions = scheduler.DefaultIntermediateOptions()

	return scheduler.BuildFlipGuardSchedule(g, analysisResult, opts)
}

func buildAccuracyOnly(
	g *ir.Graph,
	analysisResult *analysis.BoundSensitivityResult,
	maxBits runtime.PrecisionBits,
	globalTolerance float64,
) (*scheduler.FlipGuardResult, error) {
	opts := scheduler.DefaultFlipGuardOptions()
	opts.MaxBits = maxBits
	opts.MinBits = 0
	opts.GlobalTolerance = globalTolerance
	opts.SafetyFactor = safetyFactor
	opts.UseProtectedMargin = false
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

func certBudget(r *analysis.BoundSensitivityResult) float64 {
	if r == nil || r.ProtectedMargin <= 0 {
		return 0
	}

	return safetyFactor * r.ProtectedMargin
}

func certifySchedule(
	p5 *analysis.BoundSensitivityResult,
	p1 *analysis.BoundSensitivityResult,
	schedule runtime.PrecisionSchedule,
) report.Certification {
	estimated := estimateScheduleError(p5, schedule)

	p5Budget := certBudget(p5)
	p1Budget := certBudget(p1)

	return report.Certification{
		EstimatedError: estimated,

		P5Budget:    p5Budget,
		P5Certified: p5Budget > 0 && estimated <= p5Budget,

		P1Budget:    p1Budget,
		P1Certified: p1Budget > 0 && estimated <= p1Budget,
	}
}

func estimateScheduleError(
	analysisResult *analysis.BoundSensitivityResult,
	schedule runtime.PrecisionSchedule,
) float64 {
	if analysisResult == nil || len(schedule) == 0 {
		return 0
	}

	sum := 0.0

	for nodeID, bits := range schedule {
		sensitivity := analysisResult.Sensitivity[nodeID]
		if sensitivity <= 0 {
			continue
		}

		step := runtime.StepFromBits(bits)
		delta := step / 2.0

		sum += sensitivity * delta
	}

	return sum
}

func attachSavingRates(rows []report.SummaryRow) []report.SummaryRow {
	uniform12 := findAvgBits(rows, "uniform_bits_12")
	uniform16 := findAvgBits(rows, "uniform_bits_16")

	for i := range rows {
		rows[i].SavingVsUniform12Pct = savingPercent(rows[i].AvgBits, uniform12)
		rows[i].SavingVsUniform16Pct = savingPercent(rows[i].AvgBits, uniform16)
	}

	return rows
}

func findAvgBits(rows []report.SummaryRow, method string) float64 {
	for _, row := range rows {
		if row.Method == method {
			return row.AvgBits
		}
	}

	return 0
}

func savingPercent(avgBits float64, baselineBits float64) float64 {
	if avgBits <= 0 || baselineBits <= 0 {
		return 0
	}

	return (baselineBits - avgBits) / baselineBits * 100.0
}

func printScheduleResult(
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

	printSchedule(result)
}

func printSchedule(result *scheduler.FlipGuardResult) {
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
