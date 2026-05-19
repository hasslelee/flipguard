package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/scheduler"
)

// SummaryRow represents one row in the experiment summary CSV.
type SummaryRow struct {
	Method string

	Samples int

	Flips    int
	FlipRate float64

	BoundaryCount int

	AmbiguousCount int

	BoundaryFlips int
	BoundaryRate  float64

	StableBoundaryFlips int
	StableBoundaryRate  float64

	MaxError float64
	P95Error float64
	P99Error float64

	AvgBits float64
}

// NewSummaryRow creates a summary row from decision statistics.
func NewSummaryRow(method string, stats analysis.DecisionStats, schedule runtime.PrecisionSchedule) SummaryRow {
	return SummaryRow{
		Method: method,

		Samples: stats.Count,

		Flips:    stats.FlipCount,
		FlipRate: stats.FlipRate,

		BoundaryCount: stats.BoundaryCount,

		AmbiguousCount: stats.AmbiguousCount,

		BoundaryFlips: stats.BoundaryFlipCount,
		BoundaryRate:  stats.BoundaryFlipRate,

		StableBoundaryFlips: stats.StableBoundaryFlipCount,
		StableBoundaryRate:  stats.StableBoundaryFlipRate,

		MaxError: stats.MaxError,
		P95Error: stats.P95Error,
		P99Error: stats.P99Error,

		AvgBits: AverageBits(schedule),
	}
}

// AverageBits returns the average precision bits in a schedule.
func AverageBits(schedule runtime.PrecisionSchedule) float64 {
	if len(schedule) == 0 {
		return 0
	}

	total := 0
	for _, bits := range schedule {
		total += int(bits)
	}

	return float64(total) / float64(len(schedule))
}

// WriteSummaryCSV writes experiment summary rows to a CSV file.
func WriteSummaryCSV(path string, rows []SummaryRow) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create summary csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"method",
		"samples",
		"flips",
		"flip_rate",
		"boundary_count",
		"ambiguous_count",
		"boundary_flips",
		"boundary_rate",
		"stable_boundary_flips",
		"stable_boundary_rate",
		"max_error",
		"p95_error",
		"p99_error",
		"avg_bits",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write summary header: %w", err)
	}

	for _, row := range rows {
		record := []string{
			row.Method,
			strconv.Itoa(row.Samples),
			strconv.Itoa(row.Flips),
			formatFloat(row.FlipRate),
			strconv.Itoa(row.BoundaryCount),
			strconv.Itoa(row.AmbiguousCount),
			strconv.Itoa(row.BoundaryFlips),
			formatFloat(row.BoundaryRate),
			strconv.Itoa(row.StableBoundaryFlips),
			formatFloat(row.StableBoundaryRate),
			formatFloat(row.MaxError),
			formatFloat(row.P95Error),
			formatFloat(row.P99Error),
			formatFloat(row.AvgBits),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write summary row for %s: %w", row.Method, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush summary csv: %w", err)
	}

	return nil
}

// WriteScheduleCSV writes a FlipGuard schedule report to a CSV file.
func WriteScheduleCSV(path string, result *scheduler.FlipGuardResult) error {
	if result == nil {
		return fmt.Errorf("schedule result is nil")
	}

	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create schedule csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"node_id",
		"name",
		"op",
		"sensitivity",
		"bits",
		"step",
		"delta",
		"contribution",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write schedule header: %w", err)
	}

	for _, n := range result.Nodes {
		record := []string{
			string(n.NodeID),
			n.Name,
			string(n.Op),
			formatFloat(n.Sensitivity),
			strconv.Itoa(int(n.Bits)),
			formatFloat(n.Step),
			formatFloat(n.Delta),
			formatFloat(n.Contribution),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write schedule row for %s: %w", n.NodeID, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush schedule csv: %w", err)
	}

	return nil
}

// WriteDecisionRecordsCSV writes sample-level decision records for one method.
func WriteDecisionRecordsCSV(path string, method string, records []analysis.DecisionRecord) error {
	if err := ensureParentDir(path); err != nil {
		return err
	}

	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create decision records csv: %w", err)
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"method",
		"index",
		"plain_score",
		"approx_score",
		"threshold",
		"gamma",
		"margin_floor",
		"margin",
		"output_error",
		"plain_decision",
		"approx_decision",
		"flip",
		"boundary",
		"ambiguous",
	}

	if err := w.Write(header); err != nil {
		return fmt.Errorf("write decision records header: %w", err)
	}

	for _, r := range records {
		record := []string{
			method,
			strconv.Itoa(r.Index),
			formatFloat(r.PlainScore),
			formatFloat(r.ApproxScore),
			formatFloat(r.Threshold),
			formatFloat(r.Gamma),
			formatFloat(r.MarginFloor),
			formatFloat(r.Margin),
			formatFloat(r.OutputError),
			strconv.Itoa(int(r.PlainDecision)),
			strconv.Itoa(int(r.ApproxDecision)),
			strconv.FormatBool(r.Flip),
			strconv.FormatBool(r.Boundary),
			strconv.FormatBool(r.Ambiguous),
		}

		if err := w.Write(record); err != nil {
			return fmt.Errorf("write decision record for method %s index %d: %w", method, r.Index, err)
		}
	}

	if err := w.Error(); err != nil {
		return fmt.Errorf("flush decision records csv: %w", err)
	}

	return nil
}

func ensureParentDir(path string) error {
	dir := filepath.Dir(path)
	if dir == "." || dir == "" {
		return nil
	}

	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create parent directory %s: %w", dir, err)
	}

	return nil
}

func formatFloat(v float64) string {
	return strconv.FormatFloat(v, 'f', 10, 64)
}
