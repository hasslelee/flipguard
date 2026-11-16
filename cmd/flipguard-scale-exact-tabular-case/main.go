// Command flipguard-scale-exact-tabular-case re-runs configuration selection
// and the separate-input evaluation for one tabular case with a selectable
// constant-encoding scale. It writes to a new output root and never touches a
// frozen V17 evidence directory.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const schema = "flipguard_scale_exact_tabular_case_v1"

type summary struct {
	SchemaVersion    string `json:"schema_version"`
	DatasetID        string `json:"dataset_id"`
	ModelID          string `json:"model_id"`
	SplitID          string `json:"split_id"`
	ConstantEncoding string `json:"constant_encoding"`

	InitialCandidateID      string                  `json:"initial_candidate_id"`
	InitialScaleBits        int                     `json:"initial_scale_bits"`
	InitialLogN             int                     `json:"initial_log_n"`
	InitialStatus           certify.CandidateStatus `json:"initial_status"`
	InitialDecisionFlips    int                     `json:"initial_decision_flips"`
	InitialErrorViolations  int                     `json:"initial_error_violations"`
	InitialMaxObservedError float64                 `json:"initial_max_observed_error"`
	InitialMaxBudgetUsage   float64                 `json:"initial_max_error_budget_usage"`

	Outcome           string  `json:"outcome"`
	TrialsUsed        int     `json:"trials_used"`
	SelectedID        string  `json:"selected_candidate_id,omitempty"`
	SelectedScaleBits int     `json:"selected_scale_bits,omitempty"`
	SelectedLogN      int     `json:"selected_log_n,omitempty"`
	SelectedQPrimes   int     `json:"selected_q_primes,omitempty"`
	SelectedMeanMS    float64 `json:"selected_mean_total_ms,omitempty"`

	IndependentStatus          certify.CandidateStatus `json:"independent_status,omitempty"`
	IndependentDecisionFlips   int                     `json:"independent_decision_flips"`
	IndependentErrorViolations int                     `json:"independent_error_violations"`
	IndependentMaxBudgetUsage  float64                 `json:"independent_max_error_budget_usage"`
	IndependentVCert           int                     `json:"independent_v_cert"`
	IndependentVAmb            int                     `json:"independent_v_amb"`

	SelectionWallClockMS   float64 `json:"selection_wall_clock_ms"`
	IndependentWallClockMS float64 `json:"independent_wall_clock_ms"`
}

func main() {
	modelPath := flag.String("model", "", "trained model artifact")
	selectionPath := flag.String("selection", "", "configuration-selection feature CSV")
	independentPath := flag.String("independent", "", "independent-evaluation feature CSV")
	datasetID := flag.String("dataset", "", "dataset identity")
	modelID := flag.String("model-id", "", "model identity")
	splitID := flag.String("split-id", "", "outer-fold and training-seed identity")
	outRoot := flag.String("out-root", "", "case output directory")
	encoding := flag.String("constant-encoding", "ciphertext_scale", "default_scale or ciphertext_scale")
	frozenRoot := flag.String("frozen-root", "results/model_family_expansion_v17", "frozen evidence root that must not contain the output")
	flag.Parse()
	if *modelPath == "" || *selectionPath == "" || *independentPath == "" || *datasetID == "" || *modelID == "" || *splitID == "" || *outRoot == "" {
		fatalf("all flags are required")
	}
	mode, err := ckksbackend.ParseConstantEncodingMode(*encoding)
	if err != nil {
		fatalf("%v", err)
	}
	outAbs, err := filepath.Abs(*outRoot)
	if err != nil {
		fatalf("resolve output: %v", err)
	}
	frozenAbs, err := filepath.Abs(*frozenRoot)
	if err != nil {
		fatalf("resolve frozen root: %v", err)
	}
	if outAbs == frozenAbs || strings.HasPrefix(outAbs, frozenAbs+string(os.PathSeparator)) {
		fatalf("output %s is inside the frozen evidence root %s", outAbs, frozenAbs)
	}
	if _, err := os.Stat(filepath.Join(*outRoot, "case_summary.json")); err == nil {
		fmt.Printf("case already complete: %s\n", *outRoot)
		return
	}
	if err := os.MkdirAll(*outRoot, 0o755); err != nil {
		fatalf("create output: %v", err)
	}
	options := ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true, ConstantEncoding: mode}

	selectionPrepared := filepath.Join(*outRoot, "configuration_selection.prepared.csv")
	independentPrepared := filepath.Join(*outRoot, "independent_evaluation.prepared.csv")
	ensurePrepared(*modelPath, *selectionPath, selectionPrepared)
	selectionContract := buildContract(*modelPath, *selectionPath, selectionPrepared, *datasetID, *modelID, *splitID+"/configuration_selection")

	result := summary{SchemaVersion: schema, DatasetID: *datasetID, ModelID: *modelID, SplitID: *splitID, ConstantEncoding: *encoding}

	selectionFile := filepath.Join(*outRoot, "selection.json")
	var direct ckksplanner.AdaptiveAutotuneResult
	if !load(selectionFile, &direct) {
		started := time.Now()
		plan, err := ckksplanner.Synthesize(selectionContract, ckksplanner.DefaultPrimarySynthesisPolicy())
		if err != nil {
			fatalf("direct synthesis: %v", err)
		}
		direct, err = ckksplanner.RunAdaptiveTabularAutotuneWithOptions(plan, options)
		if err != nil {
			fatalf("direct selection: %v", err)
		}
		writeAtomic(selectionFile, direct)
		result.SelectionWallClockMS = float64(time.Since(started).Microseconds()) / 1000
	}
	if len(direct.Trials) == 0 {
		fatalf("selection produced no trial")
	}
	initial := direct.Trials[0]
	result.InitialCandidateID = initial.Candidate.ID
	result.InitialScaleBits = initial.Candidate.Parameters.LogDefaultScale
	result.InitialLogN = initial.Candidate.Parameters.LogN
	result.InitialStatus = initial.Status
	result.InitialDecisionFlips = initial.DecisionFlips
	result.InitialErrorViolations = initial.ErrorViolations
	result.InitialMaxObservedError = initial.MaxObservedError
	result.InitialMaxBudgetUsage = initial.MaxErrorBudgetUsage
	result.Outcome = direct.Outcome
	result.TrialsUsed = direct.TrialsUsed

	if direct.Selected != nil {
		result.SelectedID = direct.Selected.ID
		result.SelectedScaleBits = direct.Selected.Parameters.LogDefaultScale
		result.SelectedLogN = direct.Selected.Parameters.LogN
		result.SelectedQPrimes = len(direct.Selected.Parameters.LogQ)
		result.SelectedMeanMS = direct.Trials[len(direct.Trials)-1].MeanTotalMS

		ensurePrepared(*modelPath, *independentPath, independentPrepared)
		independentContract := buildContract(*modelPath, *independentPath, independentPrepared, *datasetID, *modelID, *splitID+"/independent_evaluation")
		auditFile := filepath.Join(*outRoot, "direct_independent_evaluation.json")
		var audit ckksplanner.TabularTrialResult
		if !load(auditFile, &audit) {
			started := time.Now()
			audit, err = ckksplanner.ExecuteTabularCandidateWithOptions(independentContract, *direct.Selected, 1, options)
			if err != nil {
				fatalf("independent evaluation: %v", err)
			}
			writeAtomic(auditFile, audit)
			result.IndependentWallClockMS = float64(time.Since(started).Microseconds()) / 1000
		}
		result.IndependentStatus = audit.Status
		result.IndependentDecisionFlips = audit.DecisionFlips
		result.IndependentErrorViolations = audit.ErrorViolations
		result.IndependentMaxBudgetUsage = audit.MaxErrorBudgetUsage
		result.IndependentVCert = audit.VCert
		result.IndependentVAmb = audit.VAmb
	}
	writeAtomic(filepath.Join(*outRoot, "case_summary.json"), result)
	fmt.Printf("case=%s/%s/%s encoding=%s initial=%s flips=%d violations=%d outcome=%s trials=%d selected_scale=%d independent=%s\n",
		*datasetID, *modelID, *splitID, *encoding, result.InitialStatus, result.InitialDecisionFlips, result.InitialErrorViolations,
		result.Outcome, result.TrialsUsed, result.SelectedScaleBits, result.IndependentStatus)
}

func ensurePrepared(model, source, target string) {
	if _, err := os.Stat(target); err == nil {
		return
	}
	_, err := ckksplanner.MaterializeTabularValidationWithOptions(model, source, target, ckksplanner.TabularMaterializationOptions{DataSpace: ckksplanner.TabularDataSpaceRaw})
	if err != nil {
		fatalf("materialize %s: %v", source, err)
	}
}

func buildContract(model, source, prepared, dataset, modelID, split string) ckksplanner.WorkloadContract {
	options := ckksplanner.DefaultPrimaryTabularContractOptions()
	options.ModelPath, options.SourceDataPath, options.ValidationPath = model, source, prepared
	options.SplitID = split
	options.AllowedPaths = []tuner.ExecutionPath{tuner.PathRescale}
	contract, err := ckksplanner.BuildTabularWorkloadContract(options)
	if err != nil {
		fatalf("build contract: %v", err)
	}
	if contract.DatasetID != dataset || contract.ModelID != modelID {
		fatalf("model identity mismatch: got %s/%s expected %s/%s", contract.DatasetID, contract.ModelID, dataset, modelID)
	}
	return contract
}

func load(path string, target any) bool {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return false
	}
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		fatalf("parse %s: %v", path, err)
	}
	return true
}

func writeAtomic(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatalf("marshal %s: %v", path, err)
	}
	data = append(data, '\n')
	temp := path + ".tmp"
	if err := os.WriteFile(temp, data, 0o644); err != nil {
		fatalf("write %s: %v", temp, err)
	}
	if err := os.Rename(temp, path); err != nil {
		fatalf("publish %s: %v", path, err)
	}
}

func fatalf(format string, args ...any) { fmt.Fprintf(os.Stderr, format+"\n", args...); os.Exit(1) }
