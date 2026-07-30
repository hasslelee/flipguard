package report

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/hasslelee/flipguard/internal/tuner"
)

// TunerSelectionRecord stores one selected candidate under a named policy.
// Example policies include:
//
//   - fastest_safe
//   - latency_only
//   - reference
//
// The policy name is report-facing and can be used directly in paper tables.
type TunerSelectionRecord struct {
	Policy     string
	Evaluation tuner.CandidateEvaluation
}

// ExportTunerCandidateEvaluations writes all evaluated tuner candidates to CSV.
//
// The output CSV is intended to become the raw artifact behind paper tables.
// Each row is one CKKS execution configuration and its observed validation
// result.
func ExportTunerCandidateEvaluations(
	outDir string,
	filename string,
	evals []tuner.CandidateEvaluation,
) (string, error) {
	if err := os.MkdirAll(outDir, 0755); err != nil {
		return "", err
	}

	path := filepath.Join(outDir, normalizeCSVFilename(filename, "tuner_candidates.csv"))

	f, err := os.Create(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"candidate_id",
		"path",
		"logN",
		"slots",
		"chain_length",
		"scale_bits",
		"family",
		"is_reference",
		"status",
		"success_runs",
		"failed_runs",
		"decision_flips",
		"error_violations",
		"max_output_error",
		"mean_total_ms",
	}

	if err := w.Write(header); err != nil {
		return "", err
	}

	for _, e := range evals {
		if err := w.Write(candidateEvaluationRow(e)); err != nil {
			return "", err
		}
	}

	if err := w.Error(); err != nil {
		return "", err
	}

	return path, nil
}

// ExportTunerSelectionRecords writes the final selected candidates under one or
// more selection policies.
//
// This is useful for compact tables such as:
//
//   - fastest safe configuration selected by FlipGuard
//   - fastest latency-only configuration used as an unsafe baseline
//   - conservative reference configuration
func ExportTunerSelectionRecords(
	outDir string,
	filename string,
	records []TunerSelectionRecord,
) (string, error) {
	if err := os.MkdirAll(outDir, 0755); err != nil {
		return "", err
	}

	path := filepath.Join(outDir, normalizeCSVFilename(filename, "tuner_selection.csv"))

	f, err := os.Create(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	header := []string{
		"policy",
		"candidate_id",
		"path",
		"logN",
		"slots",
		"chain_length",
		"scale_bits",
		"family",
		"is_reference",
		"status",
		"success_runs",
		"failed_runs",
		"decision_flips",
		"error_violations",
		"max_output_error",
		"mean_total_ms",
	}

	if err := w.Write(header); err != nil {
		return "", err
	}

	for _, r := range records {
		policy := r.Policy
		if policy == "" {
			policy = "unspecified"
		}

		row := append([]string{policy}, candidateEvaluationRow(r.Evaluation)...)
		if err := w.Write(row); err != nil {
			return "", err
		}
	}

	if err := w.Error(); err != nil {
		return "", err
	}

	return path, nil
}

func candidateEvaluationRow(e tuner.CandidateEvaluation) []string {
	c := e.Config.Candidate

	return []string{
		c.ID,
		string(e.Config.Path),
		strconv.Itoa(c.LogN),
		strconv.Itoa(c.Slots),
		strconv.Itoa(c.ChainLength),
		strconv.Itoa(c.ScaleBits),
		c.Family,
		strconv.FormatBool(c.IsReference),
		e.Status(),
		strconv.Itoa(e.SuccessRuns),
		strconv.Itoa(e.FailedRuns),
		strconv.Itoa(e.DecisionFlips),
		strconv.Itoa(e.ErrorViolations),
		formatTunerFloat(e.MaxOutputError),
		formatTunerFloat(e.MeanTotalMS),
	}
}

func normalizeCSVFilename(filename string, fallback string) string {
	if filename == "" {
		filename = fallback
	}
	if filepath.Ext(filename) == "" {
		filename = fmt.Sprintf("%s.csv", filename)
	}
	return filename
}

func formatTunerFloat(v float64) string {
	return fmt.Sprintf("%.12g", v)
}
