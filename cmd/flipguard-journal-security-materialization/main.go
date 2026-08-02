package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const schemaVersion = "flipguard_journal_multiclass_security_materialization_v1"

type candidate struct {
	ID         string                               `json:"id"`
	Path       string                               `json:"path"`
	Parameters ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`
	Security   ckksplanner.SecurityAssessment       `json:"security"`
}

type selectionEnvelope struct {
	Result struct {
		Selected *candidate `json:"selected"`
	} `json:"result"`
}

type comparatorEnvelope struct {
	Candidate candidate `json:"candidate"`
}

type catalogTrial struct {
	Status      string  `json:"status"`
	MeanTotalMS float64 `json:"mean_total_ms"`
}

type catalogEntry struct {
	Static struct {
		ProfileName string    `json:"profile_name"`
		Candidate   candidate `json:"candidate"`
	} `json:"static"`
	Trial *catalogTrial `json:"trial"`
}

type catalogEnvelope struct {
	FastestSafeProfile string         `json:"fastest_safe_profile"`
	Entries            []catalogEntry `json:"entries"`
}

type sourceCandidate struct {
	ModelID string
	Arm     string
	Profile string
	Value   candidate
}

type materializedCandidate struct {
	ModelID         string                               `json:"model_id"`
	Arm             string                               `json:"arm"`
	CandidateID     string                               `json:"candidate_id"`
	Profile         string                               `json:"profile,omitempty"`
	Path            string                               `json:"path"`
	Parameters      ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`
	ExactQPrimes    []uint64                             `json:"exact_q_primes"`
	ExactPPrimes    []uint64                             `json:"exact_p_primes"`
	ActualLogQ      float64                              `json:"actual_log_q"`
	ActualLogP      float64                              `json:"actual_log_p"`
	ActualLogQP     float64                              `json:"actual_log_qp"`
	ActualXs        string                               `json:"actual_xs"`
	ActualXe        string                               `json:"actual_xe"`
	SecurityPolicy  ckksplanner.SecurityAssessment       `json:"security_policy_v2"`
	RequiredObjects map[string]any                       `json:"required_objects"`
}

type output struct {
	SchemaVersion        string                  `json:"schema_version"`
	SourceCommit         string                  `json:"source_commit"`
	LattigoModule        string                  `json:"lattigo_module"`
	LattigoVersion       string                  `json:"lattigo_version"`
	SecurityPolicyID     string                  `json:"security_policy_id"`
	SecurityPolicyDigest string                  `json:"security_policy_digest"`
	PolicyRetuning       int                     `json:"policy_retuning"`
	Candidates           []materializedCandidate `json:"candidates"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	flags := flag.NewFlagSet("flipguard-journal-security-materialization", flag.ContinueOnError)
	mlpSelection := flags.String("mlp-selection", "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/selection_result.json", "frozen MLP selection")
	lenetSelection := flags.String("lenet-selection", "results/journal_multiclass_extension_v1/encrypted/mnist_lenet5_small_square_v1/selection_result.json", "frozen LeNet selection")
	graphOnly := flags.String("graph-only", "results/journal_multiclass_extension_v1/comparators/mlp_graph_only_fixed_logit_tolerance_v1/result.json", "frozen graph-only comparator")
	catalog := flags.String("catalog", "results/journal_multiclass_extension_v1/encrypted/mnist_mlp_square_784_100_10_v1/catalog_result.json", "frozen MLP catalog")
	sourceCommit := flags.String("source-commit", "", "full source commit for the materializer")
	out := flags.String("out", "", "exclusive output JSON path")
	if err := flags.Parse(os.Args[1:]); err != nil {
		return err
	}
	if strings.TrimSpace(*sourceCommit) == "" || strings.TrimSpace(*out) == "" {
		return fmt.Errorf("-source-commit and -out are required")
	}
	if _, err := os.Stat(*out); err == nil {
		return fmt.Errorf("refusing to overwrite %s", *out)
	} else if !os.IsNotExist(err) {
		return err
	}

	mlp, err := loadSelected(*mlpSelection)
	if err != nil {
		return err
	}
	lenet, err := loadSelected(*lenetSelection)
	if err != nil {
		return err
	}
	graph, err := loadComparator(*graphOnly)
	if err != nil {
		return err
	}
	profile, catalogCandidate, err := loadFastestSafeCatalog(*catalog)
	if err != nil {
		return err
	}

	policy := ckksplanner.DefaultSecurityEnvelope()
	policyDigest, err := ckksplanner.SecurityPolicyDigest(policy)
	if err != nil {
		return err
	}
	sources := []sourceCandidate{
		{ModelID: "mnist_mlp_square_784_100_10_v1", Arm: "gap_aware_direct", Value: mlp},
		{ModelID: "mnist_mlp_square_784_100_10_v1", Arm: "graph_only_fixed_tolerance", Value: graph},
		{ModelID: "mnist_mlp_square_784_100_10_v1", Arm: "bounded_catalog_fastest_safe", Profile: profile, Value: catalogCandidate},
		{ModelID: "mnist_lenet5_small_square_v1", Arm: "gap_aware_direct", Value: lenet},
	}
	materialized := make([]materializedCandidate, 0, len(sources))
	for _, source := range sources {
		record, err := materialize(source, policy)
		if err != nil {
			return fmt.Errorf("%s/%s: %w", source.ModelID, source.Arm, err)
		}
		materialized = append(materialized, record)
	}
	sort.Slice(materialized, func(i, j int) bool {
		if materialized[i].ModelID == materialized[j].ModelID {
			return materialized[i].Arm < materialized[j].Arm
		}
		return materialized[i].ModelID < materialized[j].ModelID
	})
	payload := output{
		SchemaVersion:        schemaVersion,
		SourceCommit:         *sourceCommit,
		LattigoModule:        "github.com/tuneinsight/lattigo/v6",
		LattigoVersion:       "v6.2.0",
		SecurityPolicyID:     policy.ID,
		SecurityPolicyDigest: policyDigest,
		PolicyRetuning:       0,
		Candidates:           materialized,
	}
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	return os.WriteFile(*out, encoded, 0o644)
}

func loadJSON(path string, destination any) error {
	encoded, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if err := json.Unmarshal(encoded, destination); err != nil {
		return fmt.Errorf("parse %s: %w", path, err)
	}
	return nil
}

func loadSelected(path string) (candidate, error) {
	var envelope selectionEnvelope
	if err := loadJSON(path, &envelope); err != nil {
		return candidate{}, err
	}
	if envelope.Result.Selected == nil {
		return candidate{}, fmt.Errorf("%s: selected candidate missing", path)
	}
	return *envelope.Result.Selected, nil
}

func loadComparator(path string) (candidate, error) {
	var envelope comparatorEnvelope
	if err := loadJSON(path, &envelope); err != nil {
		return candidate{}, err
	}
	if envelope.Candidate.ID == "" {
		return candidate{}, fmt.Errorf("%s: comparator candidate missing", path)
	}
	return envelope.Candidate, nil
}

func loadFastestSafeCatalog(path string) (string, candidate, error) {
	var envelope catalogEnvelope
	if err := loadJSON(path, &envelope); err != nil {
		return "", candidate{}, err
	}
	var selected *catalogEntry
	for index := range envelope.Entries {
		entry := &envelope.Entries[index]
		if entry.Trial == nil || entry.Trial.Status != "SAFE" {
			continue
		}
		if selected == nil || entry.Trial.MeanTotalMS < selected.Trial.MeanTotalMS {
			selected = entry
		}
	}
	if selected == nil {
		return "", candidate{}, fmt.Errorf("%s: no frozen SAFE catalog arm", path)
	}
	if selected.Static.ProfileName != envelope.FastestSafeProfile {
		return "", candidate{}, fmt.Errorf("%s: fastest-safe identity mismatch", path)
	}
	return selected.Static.ProfileName, selected.Static.Candidate, nil
}

func materialize(source sourceCandidate, policy ckksplanner.SecurityEnvelope) (materializedCandidate, error) {
	literal := ckks.ParametersLiteral{
		LogN:            source.Value.Parameters.LogN,
		LogQ:            append([]int(nil), source.Value.Parameters.LogQ...),
		LogP:            append([]int(nil), source.Value.Parameters.LogP...),
		LogDefaultScale: source.Value.Parameters.LogDefaultScale,
	}
	params, err := ckks.NewParametersFromLiteral(literal)
	if err != nil {
		return materializedCandidate{}, err
	}
	security, err := ckksplanner.AssessSecurity(source.Value.Parameters, 128, policy)
	if err != nil {
		return materializedCandidate{}, err
	}
	if security.FinalAdmission != "PASS" || source.Value.Security.FinalAdmission != "PASS" {
		return materializedCandidate{}, fmt.Errorf("candidate is not Security-V2 admitted")
	}
	return materializedCandidate{
		ModelID:        source.ModelID,
		Arm:            source.Arm,
		CandidateID:    source.Value.ID,
		Profile:        source.Profile,
		Path:           source.Value.Path,
		Parameters:     source.Value.Parameters,
		ExactQPrimes:   append([]uint64(nil), params.Q()...),
		ExactPPrimes:   append([]uint64(nil), params.P()...),
		ActualLogQ:     params.LogQ(),
		ActualLogP:     params.LogP(),
		ActualLogQP:    params.LogQP(),
		ActualXs:       fmt.Sprintf("%T:%v", params.Xs(), params.Xs()),
		ActualXe:       fmt.Sprintf("%T:%v", params.Xe(), params.Xe()),
		SecurityPolicy: security,
		RequiredObjects: map[string]any{
			"ciphertext_q":           true,
			"relinearization_key_qp": true,
			"rotation_key_qp":        false,
			"evaluation_key_modulus": "QP",
		},
	}, nil
}
