package ckksplanner

import (
	"encoding/hex"
	"fmt"
	"math"
	"strings"

	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	// WorkloadContractSchemaVersion is incremented whenever a field changes
	// meaning. A configuration is scoped to one validated contract version.
	WorkloadContractSchemaVersion = 1

	// EmpiricalIntervalDAGSensitivityV1 records that the planner sensitivity is
	// derived from interval propagation over the exact validation inputs. It is
	// a planning signal, not an analytical CKKS error certificate.
	EmpiricalIntervalDAGSensitivityV1 = "empirical_interval_dag_sum_v1"

	// ScalarReplicatedPackingV1 matches the current tabular backend: each
	// feature is encrypted in its own ciphertext and replicated over slots.
	ScalarReplicatedPackingV1 = "scalar_replicated_per_ciphertext_v1"

	// LattigoRescaleScaleTraceV1 symbolically tracks the scale growth caused by
	// ciphertext multiplications and Lattigo's non-integer scalar encoding. It
	// derives both consumed levels and the terminal modulus capacity.
	LattigoRescaleScaleTraceV1 = "lattigo_v6_rescale_scale_trace_v1"
)

// ArtifactBinding binds a planner input to exact bytes.
type ArtifactBinding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

// DecisionStabilityContract defines the observed-validation decision claim
// that candidate execution must satisfy.
type DecisionStabilityContract struct {
	Threshold    float64 `json:"threshold"`
	MarginFloor  float64 `json:"margin_floor"`
	SafetyFactor float64 `json:"safety_factor"`

	ProtectedMargin   float64 `json:"protected_margin"`
	OutputErrorBudget float64 `json:"output_error_budget"`

	ValidationDigest string `json:"validation_digest"`

	ValidationSamples  int `json:"validation_samples"`
	CertifiableSamples int `json:"certifiable_samples"`
	AmbiguousSamples   int `json:"ambiguous_samples"`
}

// NumericalCalibration contains data-derived signals used only to propose the
// first CKKS configuration. The final SAFE decision always requires encrypted
// validation evidence.
type NumericalCalibration struct {
	MaxInputAbs           float64 `json:"max_input_abs"`
	MaxPlaintextOutputAbs float64 `json:"max_plaintext_output_abs"`

	AggregateSensitivity float64 `json:"aggregate_sensitivity"`
	SensitivityMethod    string  `json:"sensitivity_method"`
	CalibrationScope     string  `json:"calibration_scope"`
}

// DeploymentContract records the non-negotiable execution constraints.
type DeploymentContract struct {
	SecurityBits       int `json:"security_bits"`
	RequiredSlots      int `json:"required_slots"`
	MaxEncryptedTrials int `json:"max_encrypted_trials"`

	PackingStrategy string                `json:"packing_strategy"`
	AllowedPaths    []tuner.ExecutionPath `json:"allowed_paths"`

	ScaleTraceMethod      string `json:"scale_trace_method"`
	RescaleLevelsConsumed int    `json:"rescale_levels_consumed"`
	TerminalScaleExponent int    `json:"terminal_scale_exponent"`
	RequiredQPrimes       int    `json:"required_q_primes"`
}

// WorkloadContract is the normalized input to the first-party CKKS planner.
//
// Model and dataset files are user-facing inputs. A builder parses them and
// produces this explicit, digest-bound contract before any CKKS parameter is
// synthesized.
type WorkloadContract struct {
	SchemaVersion int `json:"schema_version"`

	WorkloadID string `json:"workload_id"`
	DatasetID  string `json:"dataset_id"`
	ModelID    string `json:"model_id"`
	ModelType  string `json:"model_type"`
	SplitID    string `json:"split_id"`

	ModelArtifact  ArtifactBinding `json:"model_artifact"`
	ValidationData ArtifactBinding `json:"validation_data"`

	Graph       tuner.GraphSummary        `json:"graph"`
	Decision    DecisionStabilityContract `json:"decision"`
	Calibration NumericalCalibration      `json:"calibration"`
	Deployment  DeploymentContract        `json:"deployment"`
}

// Validate rejects incomplete contracts before parameter synthesis.
func (contract WorkloadContract) Validate() error {
	if contract.SchemaVersion != WorkloadContractSchemaVersion {
		return fmt.Errorf(
			"unsupported workload contract schema version %d",
			contract.SchemaVersion,
		)
	}

	required := []struct {
		name  string
		value string
	}{
		{"workload ID", contract.WorkloadID},
		{"dataset ID", contract.DatasetID},
		{"model ID", contract.ModelID},
		{"model type", contract.ModelType},
		{"split ID", contract.SplitID},
	}
	for _, field := range required {
		if strings.TrimSpace(field.value) == "" {
			return fmt.Errorf("workload contract %s is empty", field.name)
		}
	}

	if err := contract.ModelArtifact.validate("model artifact"); err != nil {
		return err
	}
	if err := contract.ValidationData.validate("validation data"); err != nil {
		return err
	}
	if err := validateGraphSummary(contract.Graph); err != nil {
		return err
	}
	if err := contract.Decision.validate(); err != nil {
		return err
	}
	if err := contract.Calibration.validate(); err != nil {
		return err
	}
	if err := contract.Deployment.validate(); err != nil {
		return err
	}

	return nil
}

func (binding ArtifactBinding) validate(label string) error {
	if strings.TrimSpace(binding.Path) == "" {
		return fmt.Errorf("%s path is empty", label)
	}
	if err := validateSHA256(binding.SHA256); err != nil {
		return fmt.Errorf("%s digest: %w", label, err)
	}
	return nil
}

func (decision DecisionStabilityContract) validate() error {
	if !finite(decision.Threshold) {
		return fmt.Errorf("decision threshold must be finite")
	}
	if !finite(decision.MarginFloor) || decision.MarginFloor < 0 {
		return fmt.Errorf("decision margin floor must be finite and non-negative")
	}
	if !finite(decision.SafetyFactor) ||
		decision.SafetyFactor <= 0 ||
		decision.SafetyFactor > 1 {
		return fmt.Errorf("decision safety factor must be in (0, 1]")
	}
	if !finite(decision.ProtectedMargin) || decision.ProtectedMargin <= 0 {
		return fmt.Errorf("decision protected margin must be positive")
	}
	if decision.ProtectedMargin <= decision.MarginFloor {
		return fmt.Errorf(
			"decision protected margin %.12g must exceed margin floor %.12g",
			decision.ProtectedMargin,
			decision.MarginFloor,
		)
	}
	if !finite(decision.OutputErrorBudget) ||
		decision.OutputErrorBudget <= 0 {
		return fmt.Errorf("decision output error budget must be positive")
	}

	maxBudget := decision.SafetyFactor * decision.ProtectedMargin
	if decision.OutputErrorBudget > maxBudget &&
		!closeFloat(decision.OutputErrorBudget, maxBudget) {
		return fmt.Errorf(
			"decision output error budget %.12g exceeds safety-factor margin %.12g",
			decision.OutputErrorBudget,
			maxBudget,
		)
	}

	if err := validateSHA256(decision.ValidationDigest); err != nil {
		return fmt.Errorf("decision validation digest: %w", err)
	}
	if decision.ValidationSamples <= 0 {
		return fmt.Errorf("decision validation sample count must be positive")
	}
	if decision.CertifiableSamples <= 0 {
		return fmt.Errorf("decision contract has no certifiable samples")
	}
	if decision.AmbiguousSamples < 0 {
		return fmt.Errorf("decision ambiguous sample count is negative")
	}
	if decision.CertifiableSamples+decision.AmbiguousSamples !=
		decision.ValidationSamples {
		return fmt.Errorf(
			"decision partition mismatch: certifiable=%d ambiguous=%d total=%d",
			decision.CertifiableSamples,
			decision.AmbiguousSamples,
			decision.ValidationSamples,
		)
	}

	return nil
}

func (calibration NumericalCalibration) validate() error {
	if !finite(calibration.MaxInputAbs) || calibration.MaxInputAbs < 0 {
		return fmt.Errorf("calibration max input magnitude is invalid")
	}
	if !finite(calibration.MaxPlaintextOutputAbs) ||
		calibration.MaxPlaintextOutputAbs < 0 {
		return fmt.Errorf("calibration max output magnitude is invalid")
	}
	if !finite(calibration.AggregateSensitivity) ||
		calibration.AggregateSensitivity <= 0 {
		return fmt.Errorf("calibration aggregate sensitivity must be positive")
	}
	if calibration.SensitivityMethod != EmpiricalIntervalDAGSensitivityV1 {
		return fmt.Errorf(
			"unsupported calibration sensitivity method %q",
			calibration.SensitivityMethod,
		)
	}
	if strings.TrimSpace(calibration.CalibrationScope) == "" {
		return fmt.Errorf("calibration scope is empty")
	}
	return nil
}

func (deployment DeploymentContract) validate() error {
	if deployment.SecurityBits != 128 {
		return fmt.Errorf(
			"unsupported security target %d; current synthesis envelope supports 128",
			deployment.SecurityBits,
		)
	}
	if deployment.RequiredSlots <= 0 {
		return fmt.Errorf("deployment required slots must be positive")
	}
	if deployment.MaxEncryptedTrials <= 0 {
		return fmt.Errorf("deployment max encrypted trials must be positive")
	}
	if deployment.PackingStrategy != ScalarReplicatedPackingV1 {
		return fmt.Errorf(
			"unsupported deployment packing strategy %q",
			deployment.PackingStrategy,
		)
	}
	if deployment.ScaleTraceMethod != LattigoRescaleScaleTraceV1 {
		return fmt.Errorf(
			"unsupported deployment scale trace method %q",
			deployment.ScaleTraceMethod,
		)
	}
	if deployment.RescaleLevelsConsumed < 0 {
		return fmt.Errorf("deployment rescale level demand is negative")
	}
	if deployment.TerminalScaleExponent <= 0 {
		return fmt.Errorf(
			"deployment terminal scale exponent must be positive",
		)
	}
	if deployment.RequiredQPrimes !=
		deployment.RescaleLevelsConsumed+
			deployment.TerminalScaleExponent {
		return fmt.Errorf(
			"deployment Q-prime demand mismatch: required=%d levels=%d terminal_exponent=%d",
			deployment.RequiredQPrimes,
			deployment.RescaleLevelsConsumed,
			deployment.TerminalScaleExponent,
		)
	}
	if len(deployment.AllowedPaths) == 0 {
		return fmt.Errorf("deployment allowed paths are empty")
	}

	seen := map[tuner.ExecutionPath]bool{}
	for _, path := range deployment.AllowedPaths {
		switch path {
		case tuner.PathRescale, tuner.PathNonRescale:
		default:
			return fmt.Errorf("unsupported deployment execution path %q", path)
		}
		if seen[path] {
			return fmt.Errorf("duplicate deployment execution path %q", path)
		}
		seen[path] = true
	}

	return nil
}

func validateGraphSummary(graph tuner.GraphSummary) error {
	if graph.MultiplicativeDepth < 0 ||
		graph.AddOps < 0 ||
		graph.MulOps < 0 ||
		graph.RotOps < 0 ||
		graph.RescaleOps < 0 {
		return fmt.Errorf("workload graph contains negative operation counts")
	}
	if graph.RescaleOps < graph.MultiplicativeDepth {
		return fmt.Errorf(
			"workload graph rescale count %d is below multiplicative depth %d",
			graph.RescaleOps,
			graph.MultiplicativeDepth,
		)
	}
	return nil
}

func validateSHA256(value string) error {
	const prefix = "sha256:"
	if !strings.HasPrefix(value, prefix) {
		return fmt.Errorf("digest must use sha256 prefix")
	}
	decoded, err := hex.DecodeString(strings.TrimPrefix(value, prefix))
	if err != nil {
		return fmt.Errorf("invalid sha256 digest: %w", err)
	}
	if len(decoded) != 32 {
		return fmt.Errorf("sha256 digest must contain 32 bytes")
	}
	return nil
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}

func closeFloat(left float64, right float64) bool {
	scale := math.Max(1, math.Max(math.Abs(left), math.Abs(right)))
	return math.Abs(left-right) <= 1e-12*scale
}
