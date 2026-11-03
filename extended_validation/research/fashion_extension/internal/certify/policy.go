package certify

import "fmt"

// CertificationPolicy defines which evidence is required before a candidate
// may be labeled SAFE.
type CertificationPolicy struct {
	// SafetyFactor scales the minimum certified decision margin:
	//
	//	analytical_budget =
	//	    SafetyFactor * MinCertifiedMargin
	//
	// A value in (0, 1] is required.
	SafetyFactor float64

	// RequireObservedValidation requires actual validation evidence over V_cert.
	RequireObservedValidation bool

	// RequireAnalyticalBound requires a supplied analytical error bound that
	// satisfies the protected margin budget.
	RequireAnalyticalBound bool
}

// DefaultCertificationPolicy preserves the current FlipGuard validation-level
// claim: zero observed flips and violations over V_cert.
func DefaultCertificationPolicy() CertificationPolicy {
	return CertificationPolicy{
		SafetyFactor:              0.5,
		RequireObservedValidation: true,
		RequireAnalyticalBound:    false,
	}
}

// StrictHybridCertificationPolicy requires both observed validation and a
// sufficient analytical error bound.
func StrictHybridCertificationPolicy() CertificationPolicy {
	return CertificationPolicy{
		SafetyFactor:              0.5,
		RequireObservedValidation: true,
		RequireAnalyticalBound:    true,
	}
}

// Validate checks whether the policy defines a meaningful certificate.
func (p CertificationPolicy) Validate() error {
	if !isFinite(p.SafetyFactor) ||
		p.SafetyFactor <= 0 ||
		p.SafetyFactor > 1 {
		return fmt.Errorf(
			"safety factor must be finite and in (0, 1]: %.12g",
			p.SafetyFactor,
		)
	}

	if !p.RequireObservedValidation && !p.RequireAnalyticalBound {
		return fmt.Errorf(
			"certification policy must require observed validation, analytical bound, or both",
		)
	}

	return nil
}
