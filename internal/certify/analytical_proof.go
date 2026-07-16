package certify

import (
	"encoding/hex"
	"fmt"
	"strings"
)

// AnalyticalGuaranteeKind states whether a bound is deterministic or carries
// an explicit failure probability.
type AnalyticalGuaranteeKind string

const (
	// AnalyticalGuaranteeDeterministic means that the stated scope is covered
	// without a probabilistic tail event.
	AnalyticalGuaranteeDeterministic AnalyticalGuaranteeKind = "DETERMINISTIC"

	// AnalyticalGuaranteeProbabilistic means that the bound holds except with
	// the explicitly recorded FailureProbability.
	AnalyticalGuaranteeProbabilistic AnalyticalGuaranteeKind = "PROBABILISTIC"
)

// AnalyticalBoundProof binds a scalar error bound to its derivation and exact
// claim scope.
//
// ScopeDigest must bind at least the model graph, model parameters, supported
// input domain, candidate CKKS parameters, and execution path.
//
// DerivationDigest identifies the machine-readable derivation or bound artifact
// from which MaxErrorBound was obtained.
type AnalyticalBoundProof struct {
	Method  string
	Version string

	Guarantee AnalyticalGuaranteeKind

	ScopeDigest      string
	DerivationDigest string

	MaxErrorBound float64

	// FailureProbability is zero for deterministic guarantees and must lie in
	// (0, 1) for probabilistic guarantees.
	FailureProbability float64
}

// Validate checks that an analytical bound is explicit, scoped, reproducible,
// and honest about deterministic versus probabilistic semantics.
func (p AnalyticalBoundProof) Validate() error {
	if strings.TrimSpace(p.Method) == "" {
		return fmt.Errorf(
			"analytical proof method is empty",
		)
	}
	if strings.TrimSpace(p.Version) == "" {
		return fmt.Errorf(
			"analytical proof version is empty",
		)
	}

	switch p.Guarantee {
	case AnalyticalGuaranteeDeterministic:
		if p.FailureProbability != 0 {
			return fmt.Errorf(
				"deterministic analytical proof must have zero failure probability",
			)
		}

	case AnalyticalGuaranteeProbabilistic:
		if !isFinite(p.FailureProbability) ||
			p.FailureProbability <= 0 ||
			p.FailureProbability >= 1 {
			return fmt.Errorf(
				"probabilistic analytical proof failure probability must be finite and in (0, 1): %.12g",
				p.FailureProbability,
			)
		}

	default:
		return fmt.Errorf(
			"unsupported analytical guarantee kind %q",
			p.Guarantee,
		)
	}

	if !isNonNegativeFinite(p.MaxErrorBound) {
		return fmt.Errorf(
			"analytical proof maximum error bound must be finite and non-negative",
		)
	}

	if err := validateAnalyticalProofDigest(
		"scope",
		p.ScopeDigest,
	); err != nil {
		return err
	}

	if err := validateAnalyticalProofDigest(
		"derivation",
		p.DerivationDigest,
	); err != nil {
		return err
	}

	return nil
}

func validateAnalyticalProofDigest(
	name string,
	value string,
) error {
	const prefix = "sha256:"

	if !strings.HasPrefix(value, prefix) {
		return fmt.Errorf(
			"analytical proof %s digest must use sha256 prefix",
			name,
		)
	}

	encoded := strings.TrimPrefix(
		value,
		prefix,
	)

	decoded, err := hex.DecodeString(encoded)
	if err != nil {
		return fmt.Errorf(
			"analytical proof %s digest is invalid: %w",
			name,
			err,
		)
	}

	if len(decoded) != 32 {
		return fmt.Errorf(
			"analytical proof %s digest must contain 32 bytes",
			name,
		)
	}

	return nil
}

func cloneAnalyticalBoundProof(
	proof *AnalyticalBoundProof,
) *AnalyticalBoundProof {
	if proof == nil {
		return nil
	}

	cloned := *proof
	return &cloned
}
