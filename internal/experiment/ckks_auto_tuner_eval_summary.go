package experiment

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/hasslelee/flipguard/internal/tuner"
)

type ckksAutoTunerEvalSummaryInput struct {
	OutputDir string

	ProfileCount   int
	ModeCount      int
	CandidateCount int
	SafeCount      int
	RejectedCount  int
	FailedCount    int

	ScoreErrorBudget float64
	WarmupRuns       int
	MeasurementRuns  int

	Reference   tuner.CandidateEvaluation
	FastestSafe tuner.CandidateEvaluation
	LatencyOnly tuner.CandidateEvaluation
}

func writeCKKSAutoTunerEvalSummary(input ckksAutoTunerEvalSummaryInput) (string, error) {
	if err := os.MkdirAll(input.OutputDir, 0755); err != nil {
		return "", err
	}

	path := filepath.Join(input.OutputDir, "selection_summary.md")

	var b strings.Builder

	b.WriteString("# CKKS Auto-Tuner Evaluation Summary\n\n")

	b.WriteString("## Experiment Overview\n\n")
	b.WriteString("| Item | Value |\n")
	b.WriteString("|---|---:|\n")
	b.WriteString(fmt.Sprintf("| Profiles | %d |\n", input.ProfileCount))
	b.WriteString(fmt.Sprintf("| Modes | %d |\n", input.ModeCount))
	b.WriteString(fmt.Sprintf("| Candidate configurations | %d |\n", input.CandidateCount))
	b.WriteString(fmt.Sprintf("| SAFE candidates | %d |\n", input.SafeCount))
	b.WriteString(fmt.Sprintf("| REJECTED candidates | %d |\n", input.RejectedCount))
	b.WriteString(fmt.Sprintf("| FAILED candidates | %d |\n", input.FailedCount))
	b.WriteString(fmt.Sprintf("| Score error budget | %.10f |\n", input.ScoreErrorBudget))
	b.WriteString(fmt.Sprintf("| Warmup runs | %d |\n", input.WarmupRuns))
	b.WriteString(fmt.Sprintf("| Measurement runs | %d |\n", input.MeasurementRuns))
	b.WriteString("\n")

	b.WriteString("## Selected Configurations\n\n")
	b.WriteString("| Policy | Candidate | Path | Status | Chain | Scale | Mean total ms | Max output error | Flips | Violations | Failures |\n")
	b.WriteString("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
	b.WriteString(selectionMarkdownRow("reference", input.Reference))
	b.WriteString(selectionMarkdownRow("fastest_safe", input.FastestSafe))
	b.WriteString(selectionMarkdownRow("latency_only", input.LatencyOnly))
	b.WriteString("\n")

	b.WriteString("## Relative Performance\n\n")
	b.WriteString("| Comparison | Value |\n")
	b.WriteString("|---|---:|\n")
	b.WriteString(fmt.Sprintf(
		"| Fastest-safe speedup vs reference | %.2f%% |\n",
		percentFaster(input.Reference.MeanTotalMS, input.FastestSafe.MeanTotalMS),
	))
	b.WriteString(fmt.Sprintf(
		"| Latency-only speedup vs reference | %.2f%% |\n",
		percentFaster(input.Reference.MeanTotalMS, input.LatencyOnly.MeanTotalMS),
	))
	b.WriteString(fmt.Sprintf(
		"| Fastest-safe overhead vs latency-only | %.2f%% |\n",
		percentSlower(input.LatencyOnly.MeanTotalMS, input.FastestSafe.MeanTotalMS),
	))
	b.WriteString("\n")

	b.WriteString("## Interpretation\n\n")
	b.WriteString("- `reference` is the conservative baseline configuration.\n")
	b.WriteString("- `latency_only` selects the fastest successfully executed candidate without checking decision flips or output-error violations.\n")
	b.WriteString("- `fastest_safe` selects the lowest-latency candidate among configurations with zero failures, zero decision flips, and zero error violations.\n\n")

	if input.LatencyOnly.IsSafe() {
		b.WriteString("In this run, the latency-only candidate was also SAFE. This means the selected workload/profile set did not expose a safety-efficiency trade-off for the fastest executable candidate.\n")
	} else {
		b.WriteString("In this run, the latency-only candidate was not SAFE. This supports the FlipGuard design choice: configuration selection should first restrict candidates to the certified/safe region and then minimize latency within that region.\n")
	}

	b.WriteString("\n")

	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		return "", err
	}

	return path, nil
}

func selectionMarkdownRow(policy string, evaluation tuner.CandidateEvaluation) string {
	c := evaluation.Config.Candidate

	return fmt.Sprintf(
		"| %s | `%s` | `%s` | %s | %d | %d | %.6f | %.10f | %d | %d | %d |\n",
		policy,
		c.ID,
		evaluation.Config.Path,
		evaluation.Status(),
		c.ChainLength,
		c.ScaleBits,
		evaluation.MeanTotalMS,
		evaluation.MaxOutputError,
		evaluation.DecisionFlips,
		evaluation.ErrorViolations,
		evaluation.FailedRuns,
	)
}

func percentFaster(referenceMS float64, candidateMS float64) float64 {
	if referenceMS <= 0 || candidateMS <= 0 {
		return 0
	}

	return (1.0 - candidateMS/referenceMS) * 100.0
}

func percentSlower(referenceMS float64, candidateMS float64) float64 {
	if referenceMS <= 0 || candidateMS <= 0 {
		return 0
	}

	return (candidateMS/referenceMS - 1.0) * 100.0
}
