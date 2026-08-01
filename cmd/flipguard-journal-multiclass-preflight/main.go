package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const schemaVersion = "flipguard_journal_multiclass_preflight_v1"

type runtimeEstimate struct {
	Method                  string  `json:"method"`
	ArithmeticPrimitives    int     `json:"arithmetic_primitives_per_key_run"`
	AssumedMSPerPrimitiveLo float64 `json:"assumed_ms_per_primitive_low"`
	AssumedMSPerPrimitiveHi float64 `json:"assumed_ms_per_primitive_high"`
	SecondsPerKeyRunLow     float64 `json:"seconds_per_key_run_low"`
	SecondsPerKeyRunHigh    float64 `json:"seconds_per_key_run_high"`
	SecondsPerTrialLow      float64 `json:"seconds_per_trial_low"`
	SecondsPerTrialHigh     float64 `json:"seconds_per_trial_high"`
	Caveat                  string  `json:"caveat"`
}

type preflightReport struct {
	SchemaVersion string `json:"schema_version"`
	GeneratedAt   string `json:"generated_at"`
	SourceCommit  string `json:"source_commit"`
	Role          string `json:"role"`

	Contract            ckksplanner.WorkloadContract               `json:"contract"`
	PlaintextScope      ckksplanner.MulticlassPlaintextScope       `json:"plaintext_scope"`
	DecisionAwarePlan   ckksplanner.SynthesisPlan                  `json:"decision_aware_plan"`
	GraphOnlyPlan       ckksplanner.SynthesisPlan                  `json:"graph_only_fixed_tolerance_plan"`
	InitialLiteralEqual bool                                       `json:"initial_literal_equal"`
	Catalog             []ckksplanner.MulticlassCatalogStaticEntry `json:"security_v2_bounded_catalog"`
	CatalogDenominator  int                                        `json:"catalog_denominator"`
	CatalogExecutable   int                                        `json:"catalog_encrypted_execution_count"`
	RuntimeEstimate     runtimeEstimate                            `json:"runtime_estimate"`
	DiskBudget          map[string]any                             `json:"disk_budget"`
	StaticStatus        string                                     `json:"static_status"`
	PolicyRetuning      int                                        `json:"policy_retuning"`
}

func main() {
	modelPath := flag.String("model", "", "frozen journal MNIST model artifact")
	validationPath := flag.String("data", "", "frozen configuration-validation CSV")
	sourcePath := flag.String("source", "results/source_datasets/mnist/mnist_784.arff.gz", "byte-pinned MNIST source")
	role := flag.String("role", "configuration_validation", "configuration_validation only; audit cannot synthesize")
	splitID := flag.String("split-id", "", "frozen partition identity")
	output := flag.String("output", "", "exclusive JSON output path")
	sourceCommit := flag.String("source-commit", "", "full execution-critical source commit")
	flag.Parse()
	if *modelPath == "" || *validationPath == "" || *output == "" ||
		len(*sourceCommit) != 40 {
		fatalf("--model, --data, --output, and a full --source-commit are required")
	}
	currentCommit, err := currentGitCommit()
	if err != nil {
		fatalf("resolve current Git commit: %v", err)
	}
	if *sourceCommit != currentCommit {
		fatalf("--source-commit %s does not match current HEAD %s", *sourceCommit, currentCommit)
	}
	if *role != "configuration_validation" {
		fatalf("preflight synthesis accepts configuration_validation only; locked audit replays a selected literal")
	}
	if strings.TrimSpace(*splitID) == "" {
		*splitID = *role
	}
	options := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = *modelPath
	options.ValidationPath = *validationPath
	options.SourcePath = *sourcePath
	options.ExpectedRole = *role
	options.SplitID = *splitID
	contract, scope, err := ckksplanner.BuildJournalMNISTMulticlassContract(options)
	if err != nil {
		fatalf("build multiclass contract: %v", err)
	}
	decisionPolicy := ckksplanner.DefaultPrimarySynthesisPolicy()
	decisionPlan, err := ckksplanner.Synthesize(contract, decisionPolicy)
	if err != nil {
		fatalf("decision-aware synthesis preflight: %v", err)
	}
	graphPolicy := ckksplanner.DefaultPrimarySynthesisPolicy()
	graphPolicy.SynthesisBudgetMode = ckksplanner.SynthesisBudgetGraphFixedTolerance
	graphPolicy.FixedOutputErrorBudget = 0.001
	graphPlan, err := ckksplanner.Synthesize(contract, graphPolicy)
	if err != nil {
		fatalf("graph-only synthesis preflight: %v", err)
	}
	catalog, err := ckksplanner.BuildJournalMulticlassCatalog(contract)
	if err != nil {
		fatalf("build Security-V2 bounded catalog: %v", err)
	}
	catalogExecutable := 0
	for _, entry := range catalog {
		if entry.EncryptedExecutionRequired {
			catalogExecutable++
		}
	}
	decisionLiteral, err := canonicalJSON(decisionPlan.InitialCandidates[0].Parameters)
	if err != nil {
		fatalf("encode decision literal: %v", err)
	}
	graphLiteral, err := canonicalJSON(graphPlan.InitialCandidates[0].Parameters)
	if err != nil {
		fatalf("encode graph-only literal: %v", err)
	}
	primitives := contract.Graph.AddOps + contract.Graph.MulOps + contract.Graph.RotOps
	estimate := runtimeEstimate{
		Method:                  "static_arithmetic_inventory_times_declared_0.5_to_5ms_per_primitive_bracket_v1",
		ArithmeticPrimitives:    primitives,
		AssumedMSPerPrimitiveLo: 0.5,
		AssumedMSPerPrimitiveHi: 5,
		SecondsPerKeyRunLow:     float64(primitives) * 0.5 / 1000,
		SecondsPerKeyRunHigh:    float64(primitives) * 5 / 1000,
		SecondsPerTrialLow:      float64(primitives*contract.Deployment.ValidationKeyRepeats) * 0.5 / 1000,
		SecondsPerTrialHigh:     float64(primitives*contract.Deployment.ValidationKeyRepeats) * 5 / 1000,
		Caveat:                  "static planning bracket only; it is not measured latency and excludes encode/encrypt/decrypt/key generation",
	}
	report := preflightReport{
		SchemaVersion:       schemaVersion,
		GeneratedAt:         time.Now().UTC().Format(time.RFC3339),
		SourceCommit:        *sourceCommit,
		Role:                *role,
		Contract:            contract,
		PlaintextScope:      scope,
		DecisionAwarePlan:   decisionPlan,
		GraphOnlyPlan:       graphPlan,
		InitialLiteralEqual: bytes.Equal(decisionLiteral, graphLiteral),
		Catalog:             catalog,
		CatalogDenominator:  len(catalog),
		CatalogExecutable:   catalogExecutable,
		RuntimeEstimate:     estimate,
		DiskBudget: map[string]any{
			"available_bytes_checked_by_orchestrator": true,
			"raw_observation_rows_per_trial":          len(scope.SampleIDs) * contract.Deployment.ValidationKeyRepeats,
			"logits_per_observation":                  10,
			"ciphertexts_persisted":                   0,
			"checkpoint_resume_required":              true,
		},
		StaticStatus:   "PLAN_OK_SECURITY_ADMITTED",
		PolicyRetuning: 0,
	}
	for key, value := range adapterResourceBudget(contract, decisionPlan.InitialCandidates[0]) {
		report.DiskBudget[key] = value
	}
	if err := writeExclusiveJSON(*output, report); err != nil {
		fatalf("write preflight: %v", err)
	}
	fmt.Printf(
		"status=%s model=%s role=%s logN=%d logQP=%d headroom=%d vcert=%d vamb=%d literal_equal=%t\n",
		report.StaticStatus,
		contract.ModelID,
		*role,
		decisionPlan.InitialCandidates[0].Parameters.LogN,
		decisionPlan.InitialCandidates[0].Security.LogQP,
		decisionPlan.InitialCandidates[0].Security.EvaluationKeyHeadroomBits,
		scope.VCert,
		scope.VAmb,
		report.InitialLiteralEqual,
	)
}

func adapterResourceBudget(
	contract ckksplanner.WorkloadContract,
	candidate ckksplanner.SynthesizedCandidate,
) map[string]any {
	result := map[string]any{
		"adapter_strategy":      "in_memory_feature_ciphertext_samples",
		"estimated_spool_bytes": int64(0),
	}
	if contract.ModelType != "lenet5_small_square_multiclass" {
		return result
	}
	qCount := candidate.Parameters.QPrimeCount()
	n := int64(1 << candidate.Parameters.LogN)
	bytesPerPrimeCiphertext := int64(2*8) * n
	p1PrimeCount := qCount - 3
	p2PrimeCount := qCount - 8
	spoolBytes := int64(1176*p1PrimeCount) * bytesPerPrimeCiphertext
	groupPeak := int64(400*p1PrimeCount+196*p1PrimeCount+300*p2PrimeCount) * bytesPerPrimeCiphertext
	stripePeak := int64(168*qCount) * bytesPerPrimeCiphertext
	peak := groupPeak
	if stripePeak > peak {
		peak = stripePeak
	}
	result["adapter_strategy"] = "six_row_c1_stripes_disk_spool_four_channel_c2_groups_v1"
	result["estimated_spool_bytes"] = spoolBytes
	result["estimated_peak_ciphertext_payload_bytes"] = peak
	result["minimum_free_disk_bytes"] = spoolBytes + 5*1024*1024*1024
	result["memory_estimate_caveat"] = "payload estimate excludes Go object, evaluator, key, allocator, and OS cache overhead"
	return result
}

func canonicalJSON(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(buffer.Bytes(), []byte{'\n'}), nil
}

func writeExclusiveJSON(path string, value any) error {
	if _, err := os.Stat(path); err == nil {
		return fmt.Errorf("refusing to overwrite existing preflight %s", path)
	} else if !os.IsNotExist(err) {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	temporary := path + ".tmp"
	if err := os.WriteFile(temporary, data, 0o644); err != nil {
		return err
	}
	return os.Rename(temporary, path)
}

func fatalf(format string, values ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", values...)
	os.Exit(1)
}

func currentGitCommit() (string, error) {
	command := exec.Command("git", "rev-parse", "HEAD")
	output, err := command.Output()
	if err != nil {
		return "", err
	}
	commit := strings.TrimSpace(string(output))
	if len(commit) != 40 {
		return "", fmt.Errorf("unexpected Git commit %q", commit)
	}
	return commit, nil
}
