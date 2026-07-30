package ckksplanner

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
)

const (
	DirectSynthesisPolicyV2ID          = "flipguard_direct_synthesis_policy_v2"
	DirectSynthesisAlgorithmV2         = "flipguard_direct_synthesis_v2"
	DirectSynthesisPolicySchemaVersion = 2
)

type SupportedModelFormula struct {
	ModelType string `json:"model_type"`
	Formula   string `json:"formula"`
}

type PredeclaredAblation struct {
	ID                    string `json:"id"`
	CandidateSynthesis    string `json:"candidate_synthesis"`
	EncryptedValidation   bool   `json:"encrypted_validation"`
	AdaptiveRepair        bool   `json:"adaptive_repair"`
	DecisionIntegrityGate bool   `json:"decision_integrity_gate"`
}

type DirectSynthesisPolicyContract struct {
	SchemaVersion       int                     `json:"schema_version"`
	PolicyID            string                  `json:"policy_id"`
	AlgorithmID         string                  `json:"algorithm_id"`
	AlgorithmVersion    string                  `json:"algorithm_version"`
	GraphContractSchema int                     `json:"graph_contract_schema"`
	SupportedModels     []SupportedModelFormula `json:"supported_models"`
	ScaleTraceVersion   string                  `json:"scale_trace_version"`

	PrimaryAlpha        float64 `json:"primary_alpha"`
	PrimaryMarginFloor  float64 `json:"primary_margin_floor"`
	MinScaleBits        int     `json:"min_scale_bits"`
	MinPrimeBits        int     `json:"min_prime_bits"`
	MaxScaleBits        int     `json:"max_scale_bits"`
	MaxPrimeBits        int     `json:"max_prime_bits"`
	ScaleGuardBits      int     `json:"scale_guard_bits"`
	FirstPrimeGuardBits int     `json:"first_prime_guard_bits"`
	SpecialPrimeBits    int     `json:"special_prime_bits"`

	NumericalRepairScaleBits int    `json:"numerical_repair_scale_bits"`
	LevelRepairQPrimes       int    `json:"level_repair_q_primes"`
	MaxAdditionalLevels      int    `json:"max_additional_levels"`
	StaticNTTPrimeRetryRule  string `json:"static_ntt_prime_retry_rule"`
	MaxEncryptedTrials       int    `json:"max_encrypted_trials"`
	ErrorClassifier          string `json:"error_classifier"`

	SecurityPolicyID      string                `json:"security_policy_id"`
	PackingScope          string                `json:"packing_scope"`
	RequiredSlotRule      string                `json:"required_slot_rule"`
	FirstSAFEStoppingRule string                `json:"first_safe_stopping_rule"`
	NoSAFERule            string                `json:"no_safe_rule"`
	PredeclaredAblations  []PredeclaredAblation `json:"predeclared_ablations"`
}

// DefaultDirectSynthesisPolicyContract is the immutable primary V2 contract.
func DefaultDirectSynthesisPolicyContract() DirectSynthesisPolicyContract {
	return DirectSynthesisPolicyContract{
		SchemaVersion:       DirectSynthesisPolicySchemaVersion,
		PolicyID:            DirectSynthesisPolicyV2ID,
		AlgorithmID:         DirectSynthesisAlgorithmV2,
		AlgorithmVersion:    "2.0.0",
		GraphContractSchema: WorkloadContractSchemaVersion,
		SupportedModels: []SupportedModelFormula{
			{
				ModelType: "linear_poly3",
				Formula:   "poly3(linear(x))",
			},
			{
				ModelType: "mlp_square_linear_score",
				Formula:   "linear(square(linear(x)))",
			},
			{
				ModelType: "mlp_square_poly3",
				Formula:   "poly3(linear(square(linear(x))))",
			},
		},
		ScaleTraceVersion:        LattigoRescaleScaleTraceV1,
		PrimaryAlpha:             0.5,
		PrimaryMarginFloor:       0.001,
		MinScaleBits:             18,
		MinPrimeBits:             18,
		MaxScaleBits:             50,
		MaxPrimeBits:             60,
		ScaleGuardBits:           3,
		FirstPrimeGuardBits:      2,
		SpecialPrimeBits:         30,
		NumericalRepairScaleBits: 4,
		LevelRepairQPrimes:       1,
		MaxAdditionalLevels:      2,
		StaticNTTPrimeRetryRule:  "increment_scale_one_bit_until_backend_literal_is_valid_or_max_scale",
		MaxEncryptedTrials:       4,
		ErrorClassifier:          "LEVEL_FAILURE=>level_repair; encrypted_success_with_flip_or_error_violation=>numerical_repair; otherwise_failed",
		SecurityPolicyID:         SecurityPolicyV2ID,
		PackingScope:             ScalarReplicatedPackingV1,
		RequiredSlotRule:         "required_slots_must_not_exceed_N/2",
		FirstSAFEStoppingRule:    "stop_at_first_encrypted_candidate_certified_SAFE",
		NoSAFERule:               "return_NO_SAFE_when_trial_budget_or_monotone_repairs_are_exhausted",
		PredeclaredAblations: []PredeclaredAblation{
			{
				ID:                    "graph_only_fixed_tolerance",
				CandidateSynthesis:    "graph_fixed_tolerance:0.001",
				EncryptedValidation:   true,
				AdaptiveRepair:        true,
				DecisionIntegrityGate: true,
			},
			{
				ID:                    "one_shot_direct",
				CandidateSynthesis:    "graph_plus_decision_contract",
				EncryptedValidation:   true,
				AdaptiveRepair:        false,
				DecisionIntegrityGate: true,
			},
			{
				ID:                    "full_flipguard",
				CandidateSynthesis:    "graph_plus_decision_contract",
				EncryptedValidation:   true,
				AdaptiveRepair:        true,
				DecisionIntegrityGate: true,
			},
			{
				ID:                    "latency_only_no_certification",
				CandidateSynthesis:    "bounded_catalog_fastest_executable",
				EncryptedValidation:   true,
				AdaptiveRepair:        false,
				DecisionIntegrityGate: false,
			},
		},
	}
}

func DirectSynthesisPolicyDigest(
	policy DirectSynthesisPolicyContract,
) (string, error) {
	encoded, err := canonicalPolicyJSON(policy)
	if err != nil {
		return "", fmt.Errorf("marshal direct synthesis policy: %w", err)
	}
	sum := sha256.Sum256(encoded)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func canonicalPolicyJSON(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(buffer.Bytes(), []byte{'\n'}), nil
}

func MustDefaultDirectSynthesisPolicyDigest() string {
	digest, err := DirectSynthesisPolicyDigest(
		DefaultDirectSynthesisPolicyContract(),
	)
	if err != nil {
		panic(err)
	}
	return digest
}
