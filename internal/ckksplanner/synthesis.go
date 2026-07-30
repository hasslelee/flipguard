package ckksplanner

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const (
	SynthesisPlanSchemaVersion = 1

	PrecisionSlackNone                  = "none"
	PrecisionSlackMaximizeWithinMinLogN = "maximize_within_min_log_n"

	SynthesisBudgetDecisionContract    = "decision_contract"
	SynthesisBudgetGraphFixedTolerance = "graph_fixed_tolerance"
)

var ErrRepairExhausted = errors.New("adaptive repair exhausted")

// RepairSignal classifies the only two v1 failures with a monotone repair.
type RepairSignal string

const (
	RepairLevelFailure    RepairSignal = "LEVEL_FAILURE"
	RepairNumericalReject RepairSignal = "NUMERICAL_REJECT"
)

// SecurityLimit is one maximum declared log2(QP) for a ring dimension.
type SecurityLimit struct {
	LogN         int `json:"log_n"`
	MaxLogQPBits int `json:"max_log_qp_bits"`
}

// SecurityEnvelope records the external table used to admit synthesized
// parameters.
type SecurityEnvelope struct {
	ID                 string              `json:"id"`
	SchemaVersion      int                 `json:"schema_version,omitempty"`
	PolicyVersion      string              `json:"policy_version,omitempty"`
	Source             string              `json:"source"`
	PaperTitle         string              `json:"paper_title,omitempty"`
	DOI                string              `json:"doi,omitempty"`
	PublicationDate    string              `json:"publication_date,omitempty"`
	TableNumber        string              `json:"table_number,omitempty"`
	TargetCategory     string              `json:"target_security_category,omitempty"`
	EstimatorCommit    string              `json:"estimator_commit,omitempty"`
	CostModel          string              `json:"cost_model,omitempty"`
	LattigoModule      string              `json:"lattigo_module,omitempty"`
	LattigoVersion     string              `json:"lattigo_version,omitempty"`
	SecurityBits       int                 `json:"security_bits"`
	SecretDistribution string              `json:"secret_distribution"`
	ErrorSigma         float64             `json:"error_sigma"`
	TableErrorSigma    float64             `json:"table_error_sigma,omitempty"`
	RuntimeXs          RuntimeDistribution `json:"runtime_xs,omitempty"`
	RuntimeXe          RuntimeDistribution `json:"runtime_xe,omitempty"`
	ModulusSemantics   ModulusSemantics    `json:"modulus_semantics,omitempty"`
	AdmissionCaveat    string              `json:"admission_caveat,omitempty"`

	Limits []SecurityLimit `json:"limits"`
}

// SynthesisPolicy contains explicit search guards. None of these values is a
// certificate: they only control the first candidate and adaptive repair.
type SynthesisPolicy struct {
	MinLogN int `json:"min_log_n"`
	MaxLogN int `json:"max_log_n"`

	MinScaleBits int `json:"min_scale_bits"`
	MaxScaleBits int `json:"max_scale_bits"`

	MinPrimeBits int `json:"min_prime_bits"`
	MaxPrimeBits int `json:"max_prime_bits"`

	ScaleGuardBits      int `json:"scale_guard_bits"`
	FirstPrimeGuardBits int `json:"first_prime_guard_bits"`
	LevelGuard          int `json:"level_guard"`
	SpecialPrimeBits    int `json:"special_prime_bits"`

	RepairScaleStepBits int `json:"repair_scale_step_bits"`
	MaxRepairLevels     int `json:"max_repair_levels"`

	PrecisionSlackMode     string  `json:"precision_slack_mode"`
	SynthesisBudgetMode    string  `json:"synthesis_budget_mode"`
	FixedOutputErrorBudget float64 `json:"fixed_output_error_budget,omitempty"`

	SecurityEnvelope SecurityEnvelope `json:"security_envelope"`
}

// CKKSParameterLiteralSpec is a JSON-safe direct CKKS parameter literal.
type CKKSParameterLiteralSpec struct {
	LogN            int      `json:"log_n"`
	LogQ            []int    `json:"log_q,omitempty"`
	LogP            []int    `json:"log_p,omitempty"`
	Q               []uint64 `json:"q,omitempty"`
	P               []uint64 `json:"p,omitempty"`
	LogDefaultScale int      `json:"log_default_scale"`
}

// DeclaredLogQPBits returns the conservative sum used by the security envelope.
func (spec CKKSParameterLiteralSpec) DeclaredLogQPBits() int {
	return sumInts(spec.LogQ) + sumInts(spec.LogP)
}

// QPrimeCount returns the number of ciphertext-modulus primes represented by
// either a concrete or logarithmic literal.
func (spec CKKSParameterLiteralSpec) QPrimeCount() int {
	if len(spec.Q) > 0 {
		return len(spec.Q)
	}
	return len(spec.LogQ)
}

// SecurityAssessment records why a candidate was admitted.
type SecurityAssessment struct {
	EnvelopeID      string `json:"envelope_id"`
	TargetBits      int    `json:"target_bits"`
	DeclaredLogQP   int    `json:"declared_log_qp"`
	MaxAllowedLogQP int    `json:"max_allowed_log_qp"`
	HeadroomBits    int    `json:"headroom_bits"`
	AdmissionStatus string `json:"admission_status"`
	Measurement     string `json:"measurement,omitempty"`

	LogQ  int `json:"log_q,omitempty"`
	LogP  int `json:"log_p,omitempty"`
	LogQP int `json:"log_qp,omitempty"`

	CiphertextQAdmission      string `json:"ciphertext_q_admission,omitempty"`
	EvaluationKeyQPAdmission  string `json:"evaluation_key_qp_admission,omitempty"`
	FinalAdmission            string `json:"final_admission,omitempty"`
	CiphertextHeadroomBits    int    `json:"ciphertext_headroom_bits,omitempty"`
	EvaluationKeyHeadroomBits int    `json:"evaluation_key_headroom_bits,omitempty"`
	AdmissionReason           string `json:"admission_reason,omitempty"`
}

// SynthesizedCandidate is an executable parameter set generated from a
// workload contract rather than selected from a built-in profile catalog.
type SynthesizedCandidate struct {
	ID   string              `json:"id"`
	Path tuner.ExecutionPath `json:"path"`

	Parameters CKKSParameterLiteralSpec `json:"parameters"`
	Security   SecurityAssessment       `json:"security"`

	RequiredRescaleLevels int `json:"required_rescale_levels"`
	LevelGuard            int `json:"level_guard"`
	PrecisionTargetBits   int `json:"precision_target_bits"`
	MessageMagnitudeBits  int `json:"message_magnitude_bits"`

	AnalysisScaleBits         int `json:"analysis_scale_bits"`
	BackendScaleLiftBits      int `json:"backend_scale_lift_bits"`
	BackendValidationAttempts int `json:"backend_validation_attempts"`

	SameTierPrecisionGainBits     int `json:"same_tier_precision_gain_bits"`
	SameTierStaticCandidatesTried int `json:"same_tier_static_candidates_tried"`

	GenerationKind string `json:"generation_kind"`
	Reason         string `json:"reason"`
}

// AdaptiveRepairPolicy is consumed only after an encrypted trial fails or is
// rejected. It avoids eagerly executing a hand-authored neighborhood.
type AdaptiveRepairPolicy struct {
	OnLevelFailure      string `json:"on_level_failure"`
	OnNumericalReject   string `json:"on_numerical_reject"`
	ScaleStepBits       int    `json:"scale_step_bits"`
	MaxAdditionalLevels int    `json:"max_additional_levels"`
	MaxEncryptedTrials  int    `json:"max_encrypted_trials"`
}

// SynthesisPlan is the first-party planner output. InitialCandidates normally
// contains one candidate. Additional candidates are derived on demand through
// the recorded repair policy.
type SynthesisPlan struct {
	SchemaVersion        int    `json:"schema_version"`
	AlgorithmID          string `json:"algorithm_id,omitempty"`
	AlgorithmVersion     string `json:"algorithm_version,omitempty"`
	DirectPolicyID       string `json:"direct_policy_id,omitempty"`
	DirectPolicyDigest   string `json:"direct_policy_digest,omitempty"`
	SecurityPolicyDigest string `json:"security_policy_digest,omitempty"`

	Contract       WorkloadContract `json:"contract"`
	ContractDigest string           `json:"contract_digest"`

	Policy SynthesisPolicy `json:"policy"`

	InitialCandidates []SynthesizedCandidate `json:"initial_candidates"`
	RepairPolicy      AdaptiveRepairPolicy   `json:"repair_policy"`

	PlannerAssurance string `json:"planner_assurance"`
}

// DefaultSecurityEnvelope returns the updated standard table for uniform
// ternary secrets, Gaussian error sigma about 3.2, and classical 128-bit
// security.
func DefaultSecurityEnvelope() SecurityEnvelope {
	return SecurityEnvelope{
		ID:                 SecurityPolicyV2ID,
		SchemaVersion:      2,
		PolicyVersion:      "2.0.0",
		Source:             "https://doi.org/10.62056/anxra69p1",
		PaperTitle:         "Security Guidelines for Implementing Homomorphic Encryption",
		DOI:                "10.62056/anxra69p1",
		PublicationDate:    "2025-01-13",
		TableNumber:        "Table 5.2",
		TargetCategory:     "Category 128",
		EstimatorCommit:    "8f1ff7e",
		CostModel:          "classical lattice reduction; ring operations",
		LattigoModule:      "github.com/tuneinsight/lattigo/v6",
		LattigoVersion:     "v6.2.0",
		SecurityBits:       128,
		SecretDistribution: "uniform_ternary",
		ErrorSigma:         3.2,
		TableErrorSigma:    3.19,
		RuntimeXs: RuntimeDistribution{
			ConcreteType: "ring.Ternary",
			P:            2.0 / 3.0,
		},
		RuntimeXe: RuntimeDistribution{
			ConcreteType: "ring.DiscreteGaussian",
			Sigma:        3.2,
			Bound:        19.2,
		},
		ModulusSemantics: ModulusSemantics{
			CiphertextObject:    "check Q against the Table 5.2 q cap",
			EvaluationKeyObject: "check QP against the Table 5.2 q cap because hybrid key-switching objects use the extended modulus",
			FinalAdmission:      "PASS only when every required object passes",
		},
		AdmissionCaveat: "Table 5.2 assumes Gaussian error sigma=3.19; the Lattigo v6.2.0 runtime uses discrete Gaussian sigma=3.2, bound=19.2. The table is used as a conservative admission reference, not as an exact-distribution proof.",
		Limits: []SecurityLimit{
			{LogN: 12, MaxLogQPBits: 106},
			{LogN: 13, MaxLogQPBits: 214},
			{LogN: 14, MaxLogQPBits: 430},
			{LogN: 15, MaxLogQPBits: 868},
		},
	}
}

// DefaultSynthesisPolicy returns a direct-generation policy for the current
// non-bootstrapped Lattigo backend.
func DefaultSynthesisPolicy() SynthesisPolicy {
	direct := DefaultDirectSynthesisPolicyContract()
	return SynthesisPolicy{
		MinLogN: 12,
		MaxLogN: 15,

		MinScaleBits: 30,
		MaxScaleBits: direct.MaxScaleBits,

		MinPrimeBits: 30,
		MaxPrimeBits: direct.MaxPrimeBits,

		ScaleGuardBits:      direct.ScaleGuardBits,
		FirstPrimeGuardBits: direct.FirstPrimeGuardBits,
		LevelGuard:          0,
		SpecialPrimeBits:    direct.SpecialPrimeBits,

		RepairScaleStepBits: direct.NumericalRepairScaleBits,
		MaxRepairLevels:     direct.MaxAdditionalLevels,

		PrecisionSlackMode:  PrecisionSlackNone,
		SynthesisBudgetMode: SynthesisBudgetDecisionContract,

		SecurityEnvelope: DefaultSecurityEnvelope(),
	}
}

// DefaultPrimarySynthesisPolicy returns the policy evaluated by the primary
// direct-synthesis experiments. Backend admission may raise these lower bounds.
func DefaultPrimarySynthesisPolicy() SynthesisPolicy {
	direct := DefaultDirectSynthesisPolicyContract()
	policy := DefaultSynthesisPolicy()
	policy.MinScaleBits = direct.MinScaleBits
	policy.MinPrimeBits = direct.MinPrimeBits
	return policy
}

// Synthesize creates the first directly executable CKKS configuration for a
// workload. It does not run CKKS and therefore cannot label a candidate SAFE.
func Synthesize(
	contract WorkloadContract,
	policy SynthesisPolicy,
) (SynthesisPlan, error) {
	if err := contract.Validate(); err != nil {
		return SynthesisPlan{}, fmt.Errorf(
			"invalid workload contract: %w",
			err,
		)
	}

	policy = normalizeSynthesisPolicy(policy)
	if err := validateSynthesisPolicy(policy, contract); err != nil {
		return SynthesisPlan{}, err
	}

	contractDigest, err := digestContract(contract)
	if err != nil {
		return SynthesisPlan{}, err
	}
	directPolicy := DefaultDirectSynthesisPolicyContract()
	directPolicyDigest, err := DirectSynthesisPolicyDigest(directPolicy)
	if err != nil {
		return SynthesisPlan{}, err
	}
	securityPolicyDigest, err := SecurityPolicyDigest(
		policy.SecurityEnvelope,
	)
	if err != nil {
		return SynthesisPlan{}, err
	}

	candidates := make(
		[]SynthesizedCandidate,
		0,
		len(contract.Deployment.AllowedPaths),
	)
	for _, path := range contract.Deployment.AllowedPaths {
		if path != tuner.PathRescale {
			return SynthesisPlan{}, fmt.Errorf(
				"direct synthesis for execution path %q is not implemented; rescale is the declared v1 scope",
				path,
			)
		}

		candidate, err := synthesizeBackendValidRescaleCandidate(
			contract,
			policy,
			contractDigest,
			"analysis_minimum",
			0,
			0,
			true,
		)
		if err != nil {
			return SynthesisPlan{}, err
		}
		candidates = append(candidates, candidate)
	}

	return SynthesisPlan{
		SchemaVersion:        SynthesisPlanSchemaVersion,
		AlgorithmID:          directPolicy.AlgorithmID,
		AlgorithmVersion:     directPolicy.AlgorithmVersion,
		DirectPolicyID:       directPolicy.PolicyID,
		DirectPolicyDigest:   directPolicyDigest,
		SecurityPolicyDigest: securityPolicyDigest,

		Contract:       contract,
		ContractDigest: contractDigest,
		Policy:         policy,

		InitialCandidates: candidates,
		RepairPolicy: AdaptiveRepairPolicy{
			OnLevelFailure:      "append_one_scale_sized_q_prime_then_readmit_security",
			OnNumericalReject:   "increase_all_scale_primes_then_readmit_security",
			ScaleStepBits:       policy.RepairScaleStepBits,
			MaxAdditionalLevels: policy.MaxRepairLevels,
			MaxEncryptedTrials:  contract.Deployment.MaxEncryptedTrials,
		},

		PlannerAssurance: "PREDICTED_FEASIBLE_ONLY; SAFE requires encrypted validation certification",
	}, nil
}

// Profile converts a synthesized candidate into a backend profile without
// consulting the built-in profile catalog.
func (candidate SynthesizedCandidate) Profile() (
	ckksbackend.CKKSProfile,
	error,
) {
	literal := ckks.ParametersLiteral{
		LogN: candidate.Parameters.LogN,
		Q: append(
			[]uint64(nil),
			candidate.Parameters.Q...,
		),
		P: append(
			[]uint64(nil),
			candidate.Parameters.P...,
		),
		LogQ: append(
			[]int(nil),
			candidate.Parameters.LogQ...,
		),
		LogP: append(
			[]int(nil),
			candidate.Parameters.LogP...,
		),
		LogDefaultScale: candidate.Parameters.LogDefaultScale,
	}

	return ckksbackend.NewCKKSProfileFromLiteral(
		candidate.ID,
		candidate.Reason,
		literal,
	)
}

// RepairCandidate derives one new candidate from observed feedback. It never
// enumerates a neighborhood and never weakens a prior configuration.
func RepairCandidate(
	plan SynthesisPlan,
	current SynthesizedCandidate,
	signal RepairSignal,
	repairOrdinal int,
) (SynthesizedCandidate, error) {
	if plan.SchemaVersion != SynthesisPlanSchemaVersion {
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported synthesis plan schema version %d",
			plan.SchemaVersion,
		)
	}
	if repairOrdinal <= 0 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"repair ordinal must be positive",
		)
	}
	if current.Path != tuner.PathRescale {
		return SynthesizedCandidate{}, fmt.Errorf(
			"cannot repair unsupported path %q",
			current.Path,
		)
	}
	if len(plan.InitialCandidates) == 0 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"synthesis plan has no initial candidate",
		)
	}

	minimumScaleBits := current.Parameters.LogDefaultScale
	extraLevels := current.LevelGuard - plan.Policy.LevelGuard

	generationKind := ""
	switch signal {
	case RepairLevelFailure:
		extraLevels++
		if extraLevels > plan.Policy.MaxRepairLevels {
			return SynthesizedCandidate{}, fmt.Errorf(
				"%w: level repair %d exceeds maximum %d",
				ErrRepairExhausted,
				extraLevels,
				plan.Policy.MaxRepairLevels,
			)
		}
		generationKind = fmt.Sprintf(
			"repair_level_%d",
			repairOrdinal,
		)

	case RepairNumericalReject:
		minimumScaleBits += plan.Policy.RepairScaleStepBits
		generationKind = fmt.Sprintf(
			"repair_scale_%d",
			repairOrdinal,
		)

	default:
		return SynthesizedCandidate{}, fmt.Errorf(
			"unsupported repair signal %q",
			signal,
		)
	}

	candidate, err := synthesizeBackendValidRescaleCandidate(
		plan.Contract,
		plan.Policy,
		plan.ContractDigest,
		generationKind,
		minimumScaleBits,
		extraLevels,
		false,
	)
	if err != nil {
		return SynthesizedCandidate{}, fmt.Errorf(
			"%w: %v",
			ErrRepairExhausted,
			err,
		)
	}
	return candidate, nil
}

func synthesizeBackendValidRescaleCandidate(
	contract WorkloadContract,
	policy SynthesisPolicy,
	contractDigest string,
	generationKind string,
	minimumScaleBits int,
	extraLevels int,
	allowPrecisionSlack bool,
) (SynthesizedCandidate, error) {
	analysisScaleBits := -1
	attempts := 0
	nextMinimumScaleBits := minimumScaleBits

	for {
		attempts++
		candidate, err := synthesizeRescaleCandidate(
			contract,
			policy,
			contractDigest,
			generationKind,
			nextMinimumScaleBits,
			extraLevels,
		)
		if err != nil {
			return SynthesizedCandidate{}, err
		}
		if analysisScaleBits < 0 {
			analysisScaleBits =
				candidate.Parameters.LogDefaultScale
		}

		if _, err := candidate.Profile(); err == nil {
			candidate.AnalysisScaleBits = analysisScaleBits
			candidate.BackendScaleLiftBits =
				candidate.Parameters.LogDefaultScale -
					analysisScaleBits
			candidate.BackendValidationAttempts = attempts
			if allowPrecisionSlack &&
				policy.PrecisionSlackMode ==
					PrecisionSlackMaximizeWithinMinLogN {
				candidate, err =
					maximizePrecisionWithinMinLogNTier(
						contract,
						policy,
						contractDigest,
						generationKind,
						extraLevels,
						candidate,
					)
				if err != nil {
					return SynthesizedCandidate{}, err
				}
			}
			return annotateStaticFeasibility(candidate), nil
		} else if !retryablePrimeGenerationError(err) {
			return SynthesizedCandidate{}, fmt.Errorf(
				"static backend validation for candidate %s: %w",
				candidate.ID,
				err,
			)
		}

		currentScaleBits :=
			candidate.Parameters.LogDefaultScale
		if currentScaleBits >= policy.MaxScaleBits {
			return SynthesizedCandidate{}, fmt.Errorf(
				"static backend prime generation failed through maximum scale %d after %d attempts",
				policy.MaxScaleBits,
				attempts,
			)
		}
		nextMinimumScaleBits = currentScaleBits + 1
	}
}

func maximizePrecisionWithinMinLogNTier(
	contract WorkloadContract,
	policy SynthesisPolicy,
	contractDigest string,
	generationKind string,
	extraLevels int,
	minimumCandidate SynthesizedCandidate,
) (SynthesizedCandidate, error) {
	best := minimumCandidate
	minimumScaleBits :=
		minimumCandidate.Parameters.LogDefaultScale
	targetLogN := minimumCandidate.Parameters.LogN
	staticCandidatesTried := 1

	for scaleBits := minimumScaleBits + 1; scaleBits <= policy.MaxScaleBits; scaleBits++ {
		candidate, err := synthesizeRescaleCandidate(
			contract,
			policy,
			contractDigest,
			generationKind,
			scaleBits,
			extraLevels,
		)
		if err != nil {
			return SynthesizedCandidate{}, fmt.Errorf(
				"same-tier precision synthesis at scale %d: %w",
				scaleBits,
				err,
			)
		}
		if candidate.Parameters.LogN != targetLogN {
			break
		}

		staticCandidatesTried++
		if _, err := candidate.Profile(); err != nil {
			if retryablePrimeGenerationError(err) {
				continue
			}
			return SynthesizedCandidate{}, fmt.Errorf(
				"same-tier backend validation for candidate %s: %w",
				candidate.ID,
				err,
			)
		}
		best = candidate
	}

	best.AnalysisScaleBits =
		minimumCandidate.AnalysisScaleBits
	best.BackendScaleLiftBits =
		minimumCandidate.BackendScaleLiftBits
	best.BackendValidationAttempts =
		minimumCandidate.BackendValidationAttempts
	best.SameTierPrecisionGainBits =
		best.Parameters.LogDefaultScale -
			minimumScaleBits
	best.SameTierStaticCandidatesTried =
		staticCandidatesTried

	return best, nil
}

func annotateStaticFeasibility(
	candidate SynthesizedCandidate,
) SynthesizedCandidate {
	candidate.Reason = fmt.Sprintf(
		"%s analysis_scale_bits=%d backend_scale_lift_bits=%d backend_validation_attempts=%d same_tier_precision_gain_bits=%d same_tier_static_candidates_tried=%d",
		candidate.Reason,
		candidate.AnalysisScaleBits,
		candidate.BackendScaleLiftBits,
		candidate.BackendValidationAttempts,
		candidate.SameTierPrecisionGainBits,
		candidate.SameTierStaticCandidatesTried,
	)
	return candidate
}

func retryablePrimeGenerationError(err error) bool {
	if err == nil {
		return false
	}
	return strings.Contains(
		err.Error(),
		"cannot GenModuli: failed to generate",
	)
}

func synthesizeRescaleCandidate(
	contract WorkloadContract,
	policy SynthesisPolicy,
	contractDigest string,
	generationKind string,
	minimumScaleBits int,
	extraLevels int,
) (SynthesizedCandidate, error) {
	outputErrorBudget := contract.Decision.OutputErrorBudget
	if policy.SynthesisBudgetMode == SynthesisBudgetGraphFixedTolerance {
		outputErrorBudget = policy.FixedOutputErrorBudget
	}
	unitBudget := outputErrorBudget /
		contract.Calibration.AggregateSensitivity
	if !finite(unitBudget) || unitBudget <= 0 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"invalid unit error budget %.12g",
			unitBudget,
		)
	}

	precisionBits := 0
	if unitBudget < 1 {
		precisionBits = int(math.Ceil(-math.Log2(unitBudget)))
	}

	scaleBits := precisionBits +
		policy.ScaleGuardBits
	scaleBits = maxInt(scaleBits, policy.MinScaleBits)
	scaleBits = maxInt(scaleBits, minimumScaleBits)
	if scaleBits > policy.MaxScaleBits {
		return SynthesizedCandidate{}, fmt.Errorf(
			"required scale %d exceeds declared maximum %d",
			scaleBits,
			policy.MaxScaleBits,
		)
	}

	messageBits := magnitudeBits(
		contract.Calibration.MaxPlaintextOutputAbs,
	)
	firstPrimeBits := scaleBits +
		messageBits +
		1 +
		policy.FirstPrimeGuardBits
	firstPrimeBits = maxInt(firstPrimeBits, policy.MinPrimeBits)
	if firstPrimeBits > policy.MaxPrimeBits {
		return SynthesizedCandidate{}, fmt.Errorf(
			"required first-prime size %d exceeds declared maximum %d",
			firstPrimeBits,
			policy.MaxPrimeBits,
		)
	}

	qCount := contract.Deployment.RequiredQPrimes +
		policy.LevelGuard +
		extraLevels
	if qCount <= 0 {
		return SynthesizedCandidate{}, fmt.Errorf(
			"derived Q-prime count %d is invalid",
			qCount,
		)
	}

	logQ := make([]int, qCount)
	logQ[0] = firstPrimeBits
	for index := 1; index < len(logQ); index++ {
		logQ[index] = scaleBits
	}

	specialPrimeBits := maxInt(
		policy.SpecialPrimeBits,
		firstPrimeBits,
	)
	if specialPrimeBits > policy.MaxPrimeBits {
		return SynthesizedCandidate{}, fmt.Errorf(
			"required special-prime size %d exceeds declared maximum %d",
			specialPrimeBits,
			policy.MaxPrimeBits,
		)
	}
	logP := []int{specialPrimeBits}

	declaredLogQP := sumInts(logQ) + sumInts(logP)
	logN, _, err := admitLogN(
		declaredLogQP,
		contract.Deployment.RequiredSlots,
		policy,
	)
	if err != nil {
		return SynthesizedCandidate{}, err
	}

	digestSuffix := strings.TrimPrefix(contractDigest, "sha256:")
	if len(digestSuffix) > 12 {
		digestSuffix = digestSuffix[:12]
	}

	spec := CKKSParameterLiteralSpec{
		LogN:            logN,
		LogQ:            logQ,
		LogP:            logP,
		LogDefaultScale: scaleBits,
	}

	security, err := AssessSecurity(
		spec,
		contract.Deployment.SecurityBits,
		policy.SecurityEnvelope,
	)
	if err != nil {
		return SynthesizedCandidate{}, err
	}

	candidate := SynthesizedCandidate{
		ID: fmt.Sprintf(
			"synth_%s_%s_N%d_Q%d_S%d_%s",
			generationKind,
			tuner.PathRescale,
			logN,
			qCount,
			scaleBits,
			digestSuffix,
		),
		Path: tuner.PathRescale,

		Parameters: spec,
		Security:   security,

		RequiredRescaleLevels: contract.Deployment.RescaleLevelsConsumed,
		LevelGuard:            policy.LevelGuard + extraLevels,
		PrecisionTargetBits:   precisionBits,
		MessageMagnitudeBits:  messageBits,

		AnalysisScaleBits:         scaleBits,
		BackendScaleLiftBits:      0,
		BackendValidationAttempts: 1,

		SameTierPrecisionGainBits:     0,
		SameTierStaticCandidatesTried: 1,

		GenerationKind: generationKind,
		Reason: fmt.Sprintf(
			"budget=%.6g aggregate_sensitivity=%.6g unit_budget=%.6g precision_bits=%d rescale_levels=%d terminal_scale_exponent=%d q_primes=%d level_guard=%d declared_logQP=%d",
			outputErrorBudget,
			contract.Calibration.AggregateSensitivity,
			unitBudget,
			precisionBits,
			contract.Deployment.RescaleLevelsConsumed,
			contract.Deployment.TerminalScaleExponent,
			contract.Deployment.RequiredQPrimes,
			policy.LevelGuard+extraLevels,
			declaredLogQP,
		),
	}

	return candidate, nil
}

func normalizeSynthesisPolicy(policy SynthesisPolicy) SynthesisPolicy {
	defaults := DefaultSynthesisPolicy()

	if policy.MinLogN <= 0 {
		policy.MinLogN = defaults.MinLogN
	}
	if policy.MaxLogN <= 0 {
		policy.MaxLogN = defaults.MaxLogN
	}
	if policy.MinScaleBits <= 0 {
		policy.MinScaleBits = defaults.MinScaleBits
	}
	if policy.MaxScaleBits <= 0 {
		policy.MaxScaleBits = defaults.MaxScaleBits
	}
	if policy.MinPrimeBits <= 0 {
		policy.MinPrimeBits = defaults.MinPrimeBits
	}
	if policy.MaxPrimeBits <= 0 {
		policy.MaxPrimeBits = defaults.MaxPrimeBits
	}
	if policy.ScaleGuardBits < 0 {
		policy.ScaleGuardBits = defaults.ScaleGuardBits
	}
	if policy.FirstPrimeGuardBits < 0 {
		policy.FirstPrimeGuardBits = defaults.FirstPrimeGuardBits
	}
	if policy.LevelGuard < 0 {
		policy.LevelGuard = defaults.LevelGuard
	}
	if policy.SpecialPrimeBits <= 0 {
		policy.SpecialPrimeBits = defaults.SpecialPrimeBits
	}
	if policy.RepairScaleStepBits <= 0 {
		policy.RepairScaleStepBits = defaults.RepairScaleStepBits
	}
	if policy.MaxRepairLevels < 0 {
		policy.MaxRepairLevels = defaults.MaxRepairLevels
	}
	if strings.TrimSpace(policy.PrecisionSlackMode) == "" {
		policy.PrecisionSlackMode = defaults.PrecisionSlackMode
	}
	if strings.TrimSpace(policy.SynthesisBudgetMode) == "" {
		policy.SynthesisBudgetMode = defaults.SynthesisBudgetMode
	}
	if strings.TrimSpace(policy.SecurityEnvelope.ID) == "" {
		policy.SecurityEnvelope = defaults.SecurityEnvelope
	}

	return policy
}

func validateSynthesisPolicy(
	policy SynthesisPolicy,
	contract WorkloadContract,
) error {
	if policy.MaxLogN < policy.MinLogN {
		return fmt.Errorf("synthesis max LogN is below min LogN")
	}
	if policy.MaxScaleBits < policy.MinScaleBits {
		return fmt.Errorf("synthesis max scale is below min scale")
	}
	if policy.MaxPrimeBits < policy.MinPrimeBits {
		return fmt.Errorf("synthesis max prime size is below min prime size")
	}
	switch policy.PrecisionSlackMode {
	case PrecisionSlackNone,
		PrecisionSlackMaximizeWithinMinLogN:
	default:
		return fmt.Errorf(
			"unsupported precision slack mode %q",
			policy.PrecisionSlackMode,
		)
	}
	switch policy.SynthesisBudgetMode {
	case SynthesisBudgetDecisionContract:
		if policy.FixedOutputErrorBudget != 0 {
			return fmt.Errorf(
				"fixed output error budget is valid only in graph_fixed_tolerance mode",
			)
		}
	case SynthesisBudgetGraphFixedTolerance:
		if !finite(policy.FixedOutputErrorBudget) ||
			policy.FixedOutputErrorBudget <= 0 {
			return fmt.Errorf(
				"graph-fixed synthesis requires a positive fixed output error budget",
			)
		}
	default:
		return fmt.Errorf(
			"unsupported synthesis budget mode %q",
			policy.SynthesisBudgetMode,
		)
	}
	if policy.SecurityEnvelope.SecurityBits !=
		contract.Deployment.SecurityBits {
		return fmt.Errorf(
			"security envelope target %d does not match deployment target %d",
			policy.SecurityEnvelope.SecurityBits,
			contract.Deployment.SecurityBits,
		)
	}
	if !finite(policy.SecurityEnvelope.ErrorSigma) ||
		policy.SecurityEnvelope.ErrorSigma <= 0 {
		return fmt.Errorf("security envelope error sigma is invalid")
	}
	if strings.TrimSpace(policy.SecurityEnvelope.Source) == "" {
		return fmt.Errorf("security envelope source is empty")
	}
	if len(policy.SecurityEnvelope.Limits) == 0 {
		return fmt.Errorf("security envelope has no limits")
	}

	seen := map[int]bool{}
	for _, limit := range policy.SecurityEnvelope.Limits {
		if limit.LogN <= 0 || limit.MaxLogQPBits <= 0 {
			return fmt.Errorf("security envelope contains invalid limit")
		}
		if seen[limit.LogN] {
			return fmt.Errorf(
				"security envelope contains duplicate LogN %d",
				limit.LogN,
			)
		}
		seen[limit.LogN] = true
	}
	return nil
}

func admitLogN(
	declaredLogQP int,
	requiredSlots int,
	policy SynthesisPolicy,
) (int, SecurityLimit, error) {
	requiredLogN := ceilLog2(requiredSlots) + 1
	requiredLogN = maxInt(requiredLogN, policy.MinLogN)

	var selected SecurityLimit
	found := false
	for _, limit := range policy.SecurityEnvelope.Limits {
		if limit.LogN < requiredLogN ||
			limit.LogN > policy.MaxLogN ||
			declaredLogQP > limit.MaxLogQPBits {
			continue
		}
		if !found || limit.LogN < selected.LogN {
			selected = limit
			found = true
		}
	}

	if !found {
		return 0, SecurityLimit{}, fmt.Errorf(
			"no admitted ring dimension for declared logQP=%d required_slots=%d within LogN=[%d,%d]",
			declaredLogQP,
			requiredSlots,
			policy.MinLogN,
			policy.MaxLogN,
		)
	}
	return selected.LogN, selected, nil
}

func digestContract(contract WorkloadContract) (string, error) {
	encoded, err := json.Marshal(contract)
	if err != nil {
		return "", fmt.Errorf("marshal workload contract: %w", err)
	}
	sum := sha256.Sum256(encoded)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func magnitudeBits(maxAbs float64) int {
	if maxAbs <= 1 {
		return 0
	}
	return int(math.Ceil(math.Log2(maxAbs)))
}

func sumInts(values []int) int {
	total := 0
	for _, value := range values {
		total += value
	}
	return total
}
