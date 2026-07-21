package certify

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"strings"
)

// AnalyticalInputScopeKind distinguishes an exact finite input set from a
// separately justified bounded domain and from merely observed empirical
// ranges.
type AnalyticalInputScopeKind string

const (
	// AnalyticalInputEnumeratedFiniteSet identifies an exact ordered input set
	// through SourceDigest and SampleCount. Any guarantee is limited to that
	// exact set.
	AnalyticalInputEnumeratedFiniteSet AnalyticalInputScopeKind = "ENUMERATED_FINITE_SET"

	// AnalyticalInputDeclaredBoxDomain identifies a feature-wise bounded domain
	// justified by an external data, preprocessing, or deployment contract.
	AnalyticalInputDeclaredBoxDomain AnalyticalInputScopeKind = "DECLARED_BOX_DOMAIN"

	// AnalyticalInputEmpiricalRangeOnly records observed feature minima and
	// maxima. It is useful for diagnostics but is not sufficient for issuing
	// an analytical certificate.
	AnalyticalInputEmpiricalRangeOnly AnalyticalInputScopeKind = "EMPIRICAL_RANGE_ONLY"
)

// AnalyticalFeatureBound defines one ordered feature interval.
//
// Index must be contiguous from zero so that the scope cannot silently reorder
// model inputs.
type AnalyticalFeatureBound struct {
	Index int    `json:"index"`
	Name  string `json:"name"`

	Lower float64 `json:"lower"`
	Upper float64 `json:"upper"`
}

// AnalyticalInputScope describes exactly which inputs an analytical derivation
// claims to cover.
type AnalyticalInputScope struct {
	Kind AnalyticalInputScopeKind `json:"kind"`

	// SourceDigest identifies the exact input-set artifact, domain
	// specification, preprocessing contract, or empirical range artifact.
	SourceDigest string `json:"source_digest"`

	// SampleCount is required only for ENUMERATED_FINITE_SET.
	SampleCount int `json:"sample_count"`

	// FeatureBounds is required for DECLARED_BOX_DOMAIN and
	// EMPIRICAL_RANGE_ONLY.
	FeatureBounds []AnalyticalFeatureBound `json:"feature_bounds,omitempty"`
}

// AnalyticalExecutionScope binds an analytical result to a model, input scope,
// CKKS profile, execution path, implementation, and decision rule.
type AnalyticalExecutionScope struct {
	SchemaVersion int `json:"schema_version"`

	WorkloadID string `json:"workload_id"`
	DatasetID  string `json:"dataset_id"`
	ModelID    string `json:"model_id"`
	ModelType  string `json:"model_type"`

	Formula   string  `json:"formula"`
	Threshold float64 `json:"threshold"`

	ModelArtifactDigest  string `json:"model_artifact_digest"`
	OperationGraphDigest string `json:"operation_graph_digest"`
	ProfileFactsDigest   string `json:"profile_facts_digest"`
	SourceCodeDigest     string `json:"source_code_digest"`

	ExecutionPath string `json:"execution_path"`

	LibraryModule  string `json:"library_module"`
	LibraryVersion string `json:"library_version"`

	Input AnalyticalInputScope `json:"input"`
}

// Validate checks that all analytical claim dimensions are explicit and
// reproducibly bound.
func (scope AnalyticalExecutionScope) Validate() error {
	if scope.SchemaVersion != 1 {
		return fmt.Errorf(
			"unsupported analytical scope schema version %d",
			scope.SchemaVersion,
		)
	}

	requiredStrings := []struct {
		name  string
		value string
	}{
		{"workload ID", scope.WorkloadID},
		{"dataset ID", scope.DatasetID},
		{"model ID", scope.ModelID},
		{"model type", scope.ModelType},
		{"formula", scope.Formula},
		{"execution path", scope.ExecutionPath},
		{"library module", scope.LibraryModule},
		{"library version", scope.LibraryVersion},
	}

	for _, field := range requiredStrings {
		if strings.TrimSpace(field.value) == "" {
			return fmt.Errorf(
				"analytical scope %s is empty",
				field.name,
			)
		}
	}

	if !finiteAnalyticalScopeValue(scope.Threshold) {
		return fmt.Errorf(
			"analytical scope threshold must be finite",
		)
	}

	digests := []struct {
		name  string
		value string
	}{
		{
			"model artifact",
			scope.ModelArtifactDigest,
		},
		{
			"operation graph",
			scope.OperationGraphDigest,
		},
		{
			"profile facts",
			scope.ProfileFactsDigest,
		},
		{
			"source code",
			scope.SourceCodeDigest,
		},
	}

	for _, digest := range digests {
		if err := validateAnalyticalProofDigest(
			digest.name,
			digest.value,
		); err != nil {
			return err
		}
	}

	if err := scope.Input.Validate(); err != nil {
		return fmt.Errorf(
			"validate analytical input scope: %w",
			err,
		)
	}

	return nil
}

// Validate checks the consistency and semantics of an analytical input scope.
func (scope AnalyticalInputScope) Validate() error {
	if err := validateAnalyticalProofDigest(
		"input source",
		scope.SourceDigest,
	); err != nil {
		return err
	}

	switch scope.Kind {
	case AnalyticalInputEnumeratedFiniteSet:
		if scope.SampleCount <= 0 {
			return fmt.Errorf(
				"enumerated finite set sample count must be positive",
			)
		}
		if len(scope.FeatureBounds) != 0 {
			return fmt.Errorf(
				"enumerated finite set must not substitute empirical feature bounds for the exact set digest",
			)
		}

	case AnalyticalInputDeclaredBoxDomain:
		if scope.SampleCount != 0 {
			return fmt.Errorf(
				"declared box domain must not carry a finite-set sample count",
			)
		}
		if err := validateAnalyticalFeatureBounds(
			scope.FeatureBounds,
		); err != nil {
			return fmt.Errorf(
				"declared box domain: %w",
				err,
			)
		}

	case AnalyticalInputEmpiricalRangeOnly:
		if scope.SampleCount != 0 {
			return fmt.Errorf(
				"empirical range scope must not carry a finite-set sample count",
			)
		}
		if err := validateAnalyticalFeatureBounds(
			scope.FeatureBounds,
		); err != nil {
			return fmt.Errorf(
				"empirical range scope: %w",
				err,
			)
		}

	default:
		return fmt.Errorf(
			"unsupported analytical input scope kind %q",
			scope.Kind,
		)
	}

	return nil
}

// CertificateEligible reports whether the input scope can support an
// analytical certificate.
//
// This does not mean that a valid error derivation already exists. It only means
// that the input scope itself is not merely an empirical diagnostic range.
func (scope AnalyticalInputScope) CertificateEligible() bool {
	switch scope.Kind {
	case AnalyticalInputEnumeratedFiniteSet,
		AnalyticalInputDeclaredBoxDomain:
		return true

	default:
		return false
	}
}

// CanonicalJSON returns the deterministic representation used for ScopeDigest.
func (scope AnalyticalExecutionScope) CanonicalJSON() (
	[]byte,
	error,
) {
	if err := scope.Validate(); err != nil {
		return nil, err
	}

	encoded, err := json.Marshal(scope)
	if err != nil {
		return nil, fmt.Errorf(
			"marshal analytical execution scope: %w",
			err,
		)
	}

	return encoded, nil
}

// Digest returns the SHA-256 digest suitable for AnalyticalBoundProof.ScopeDigest.
func (scope AnalyticalExecutionScope) Digest() (
	string,
	error,
) {
	canonical, err := scope.CanonicalJSON()
	if err != nil {
		return "", err
	}

	sum := sha256.Sum256(canonical)

	return "sha256:" +
			hex.EncodeToString(sum[:]),
		nil
}

func validateAnalyticalFeatureBounds(
	bounds []AnalyticalFeatureBound,
) error {
	if len(bounds) == 0 {
		return fmt.Errorf(
			"feature bounds are empty",
		)
	}

	names := make(
		map[string]struct{},
		len(bounds),
	)

	for expectedIndex, bound := range bounds {
		if bound.Index != expectedIndex {
			return fmt.Errorf(
				"feature bound index %d is not contiguous; expected %d",
				bound.Index,
				expectedIndex,
			)
		}

		name := strings.TrimSpace(
			bound.Name,
		)
		if name == "" {
			return fmt.Errorf(
				"feature %d name is empty",
				bound.Index,
			)
		}

		if _, exists := names[name]; exists {
			return fmt.Errorf(
				"duplicate feature name %q",
				name,
			)
		}
		names[name] = struct{}{}

		if !finiteAnalyticalScopeValue(
			bound.Lower,
		) || !finiteAnalyticalScopeValue(
			bound.Upper,
		) {
			return fmt.Errorf(
				"feature %d bounds must be finite",
				bound.Index,
			)
		}

		if bound.Lower > bound.Upper {
			return fmt.Errorf(
				"feature %d lower bound %.12g exceeds upper bound %.12g",
				bound.Index,
				bound.Lower,
				bound.Upper,
			)
		}
	}

	return nil
}

func finiteAnalyticalScopeValue(
	value float64,
) bool {
	return !math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
