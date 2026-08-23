package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

type completeResult struct {
	ckksplanner.V17DepthLadderResult
	FiniteGeneratorID      string                            `json:"finite_generator_id"`
	FiniteDenominator      int                               `json:"finite_denominator"`
	FiniteEntries          []ckksplanner.TabularTrialResult  `json:"finite_entries"`
	FiniteSafe             int                               `json:"finite_safe"`
	FiniteRejected         int                               `json:"finite_rejected"`
	FiniteFailed           int                               `json:"finite_failed"`
	FastestSafe            *ckksplanner.SynthesizedCandidate `json:"fastest_safe,omitempty"`
	FastestSafeMeanTotalMS float64                           `json:"fastest_safe_mean_total_ms,omitempty"`
	SelectedSafeRank       int                               `json:"selected_safe_rank,omitempty"`
	LatencyRegret          float64                           `json:"latency_regret,omitempty"`
	FalseNoSafe            bool                              `json:"false_no_safe"`
}

func main() {
	depth := flag.Int("depth", 0, "predeclared repeated-square depth")
	model := flag.String("model", "", "depth-ladder model artifact")
	data := flag.String("data", "", "depth-ladder configuration-selection data")
	out := flag.String("out", "", "result JSON")
	flag.Parse()
	if *depth <= 0 || *model == "" || *data == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "--depth, --model, --data, and --out are required")
		os.Exit(2)
	}
	contract, err := ckksplanner.BuildV17DepthLadderContract(ckksplanner.V17DepthLadderOptions{
		ModelPath: *model, DataPath: *data, SplitID: fmt.Sprintf("v17_depth_ladder_D%d", *depth), Depth: *depth,
	})
	if err != nil {
		fail(err)
	}
	plan, err := ckksplanner.Synthesize(contract, ckksplanner.DefaultPrimarySynthesisPolicy())
	if err != nil {
		payload := map[string]any{"schema_version": 1, "depth": *depth, "outcome": "BACKEND_DEPTH_UNSUPPORTED", "reason": err.Error(), "contract": contract}
		write(*out, payload)
		fmt.Printf("depth=%d outcome=BACKEND_DEPTH_UNSUPPORTED output=%s\n", *depth, *out)
		return
	}
	result, err := ckksplanner.RunAdaptiveV17DepthLadderAutotune(plan, *depth)
	if err != nil {
		fail(err)
	}
	_, candidates, err := ckksplanner.BuildV17DepthCompleteFiniteSet(contract)
	if err != nil {
		fail(err)
	}
	complete := completeResult{
		V17DepthLadderResult: result,
		FiniteGeneratorID:    ckksplanner.V17DepthCompleteCandidateGeneratorID,
		FiniteDenominator:    len(candidates),
		FiniteEntries:        make([]ckksplanner.TabularTrialResult, 0, len(candidates)),
	}
	for index, candidate := range candidates {
		trial, executeErr := ckksplanner.ExecuteV17DepthLadderCandidate(contract, candidate, *depth, index+1)
		if executeErr != nil {
			fail(executeErr)
		}
		complete.FiniteEntries = append(complete.FiniteEntries, trial)
		switch trial.Status {
		case certify.StatusSafe:
			complete.FiniteSafe++
			if complete.FastestSafe == nil || trial.MeanTotalMS < complete.FastestSafeMeanTotalMS {
				copy := candidate
				complete.FastestSafe = &copy
				complete.FastestSafeMeanTotalMS = trial.MeanTotalMS
			}
		case certify.StatusRejected:
			complete.FiniteRejected++
		default:
			complete.FiniteFailed++
		}
	}
	complete.FalseNoSafe = result.Outcome == ckksplanner.AdaptiveOutcomeNoSafe && complete.FiniteSafe > 0
	if result.Selected != nil && complete.FastestSafeMeanTotalMS > 0 {
		selectedLatency := math.NaN()
		for _, trial := range result.Trials {
			if trial.Status == certify.StatusSafe && trial.Candidate.ID == result.Selected.ID {
				selectedLatency = trial.MeanTotalMS
				break
			}
		}
		if !math.IsNaN(selectedLatency) {
			complete.LatencyRegret = (selectedLatency - complete.FastestSafeMeanTotalMS) / complete.FastestSafeMeanTotalMS
			type ranked struct {
				id      string
				latency float64
			}
			ranking := make([]ranked, 0, complete.FiniteSafe)
			for _, trial := range complete.FiniteEntries {
				if trial.Status == certify.StatusSafe {
					ranking = append(ranking, ranked{id: trial.Candidate.ID, latency: trial.MeanTotalMS})
				}
			}
			sort.SliceStable(ranking, func(i, j int) bool { return ranking[i].latency < ranking[j].latency })
			for index, item := range ranking {
				if item.id == result.Selected.ID {
					complete.SelectedSafeRank = index + 1
					break
				}
			}
		}
	}
	write(*out, complete)
	fmt.Printf("depth=%d outcome=%s trials=%d finite=%d safe=%d output=%s\n", *depth, result.Outcome, result.TrialsUsed, complete.FiniteDenominator, complete.FiniteSafe, *out)
}

func write(path string, value any) {
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fail(err)
	}
	encoded = append(encoded, '\n')
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		fail(err)
	}
	if err := os.WriteFile(path, encoded, 0o644); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
