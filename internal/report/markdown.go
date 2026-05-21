package report

import (
	"fmt"
	"os"

	"github.com/hasslelee/flipguard/internal/scheduler"
)

// ScheduleSummary summarizes one FlipGuard schedule for Markdown reporting.
type ScheduleSummary struct {
	Name string

	Budget          float64
	BudgetSource    string
	EstimatedError  float64
	Feasible        bool
	ProtectedMargin float64

	AvgBits float64
	MinBits int
	MaxBits int
	Nodes   int
}

// NewScheduleSummary creates a compact schedule summary from a FlipGuard result.
func NewScheduleSummary(name string, result *scheduler.FlipGuardResult, protectedMargin float64) ScheduleSummary {
	s := ScheduleSummary{
		Name:            name,
		Budget:          result.Budget,
		BudgetSource:    result.BudgetSource,
		EstimatedError:  result.EstimatedError,
		Feasible:        result.Feasible,
		ProtectedMargin: protectedMargin,
		AvgBits:         AverageBits(result.Schedule),
		MinBits:         0,
		MaxBits:         0,
		Nodes:           len(result.Nodes),
	}

	if len(result.Nodes) == 0 {
		return s
	}

	minBits := 1 << 30
	maxBits := -1

	for _, n := range result.Nodes {
		bits := int(n.Bits)
		if bits < minBits {
			minBits = bits
		}
		if bits > maxBits {
			maxBits = bits
		}
	}

	s.MinBits = minBits
	s.MaxBits = maxBits

	return s
}

// MarkdownReport contains the experiment summary rendered to report.md.
type MarkdownReport struct {
	Title string

	Threshold   float64
	Gamma       float64
	MarginFloor float64
	Samples     int

	SummaryRows       []SummaryRow
	ScheduleSummaries []ScheduleSummary
}

// WriteMarkdownReport writes a compact Markdown report for paper/table drafting.
func WriteMarkdownReport(path string, r MarkdownReport) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create markdown report: %w", err)
	}
	defer f.Close()

	title := r.Title
	if title == "" {
		title = "FlipGuard Experiment Report"
	}

	fmt.Fprintf(f, "# %s\n\n", title)

	fmt.Fprintf(f, "## Experiment Setting\n\n")
	fmt.Fprintf(f, "- Threshold: `%.6f`\n", r.Threshold)
	fmt.Fprintf(f, "- Boundary gamma: `%.6f`\n", r.Gamma)
	fmt.Fprintf(f, "- Ambiguous margin floor: `%.6f`\n", r.MarginFloor)
	fmt.Fprintf(f, "- Samples: `%d`\n\n", r.Samples)

	fmt.Fprintf(f, "## Summary\n\n")
	fmt.Fprintf(f, "| Method | Samples | Flips | Boundary Flips | Stable Boundary Flips | Max Error | Avg Bits |\n")
	fmt.Fprintf(f, "|---|---:|---:|---:|---:|---:|---:|\n")

	for _, row := range r.SummaryRows {
		fmt.Fprintf(
			f,
			"| %s | %d | %d | %d | %d | %.10f | %.2f |\n",
			row.Method,
			row.Samples,
			row.Flips,
			row.BoundaryFlips,
			row.StableBoundaryFlips,
			row.MaxError,
			row.AvgBits,
		)
	}

	fmt.Fprintf(f, "\n## FlipGuard Schedule Summary\n\n")
	fmt.Fprintf(f, "| Schedule | Feasible | Budget Source | Budget | Estimated Error | Protected Margin | Avg Bits | Min Bits | Max Bits |\n")
	fmt.Fprintf(f, "|---|---:|---|---:|---:|---:|---:|---:|---:|\n")

	for _, s := range r.ScheduleSummaries {
		fmt.Fprintf(
			f,
			"| %s | %t | %s | %.10f | %.10f | %.10f | %.2f | %d | %d |\n",
			s.Name,
			s.Feasible,
			s.BudgetSource,
			s.Budget,
			s.EstimatedError,
			s.ProtectedMargin,
			s.AvgBits,
			s.MinBits,
			s.MaxBits,
		)
	}

	fmt.Fprintf(f, "\n## Key Observations\n\n")
	fmt.Fprintf(f, "- `stable_boundary_flips` excludes ambiguous samples with margin less than or equal to the configured margin floor.\n")
	fmt.Fprintf(f, "- A remaining boundary flip with `ambiguous=true` indicates an inherently unstable near-threshold sample rather than a stable-region scheduling failure.\n")
	fmt.Fprintf(f, "- Compare `avg_bits` under the same `stable_boundary_flips` level to estimate precision-saving behavior.\n")

	return nil
}
