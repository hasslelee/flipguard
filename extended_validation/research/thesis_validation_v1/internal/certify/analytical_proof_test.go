package certify

import (
	"strings"
	"testing"
)

const analyticalProofTestDigest = "sha256:" +
	"11111111111111111111111111111111" +
	"11111111111111111111111111111111"

func TestAnalyticalBoundProofValidateDeterministic(
	t *testing.T,
) {
	proof := AnalyticalBoundProof{
		Method:  "symbolic-ckks-envelope",
		Version: "v1",

		Guarantee: AnalyticalGuaranteeDeterministic,

		ScopeDigest:      analyticalProofTestDigest,
		DerivationDigest: analyticalProofTestDigest,

		MaxErrorBound: 0.001,
	}

	if err := proof.Validate(); err != nil {
		t.Fatalf(
			"valid deterministic proof rejected: %v",
			err,
		)
	}
}

func TestAnalyticalBoundProofValidateProbabilistic(
	t *testing.T,
) {
	proof := AnalyticalBoundProof{
		Method:  "ckks-tail-envelope",
		Version: "v1",

		Guarantee: AnalyticalGuaranteeProbabilistic,

		ScopeDigest:      analyticalProofTestDigest,
		DerivationDigest: analyticalProofTestDigest,

		MaxErrorBound:      0.001,
		FailureProbability: 1e-12,
	}

	if err := proof.Validate(); err != nil {
		t.Fatalf(
			"valid probabilistic proof rejected: %v",
			err,
		)
	}
}

func TestAnalyticalBoundProofRejectsUnscopedBound(
	t *testing.T,
) {
	proof := AnalyticalBoundProof{
		Method:  "unscoped",
		Version: "v1",

		Guarantee: AnalyticalGuaranteeDeterministic,

		DerivationDigest: analyticalProofTestDigest,

		MaxErrorBound: 0.001,
	}

	err := proof.Validate()
	if err == nil {
		t.Fatal(
			"expected proof without scope digest to fail",
		)
	}
	if !strings.Contains(
		err.Error(),
		"scope digest",
	) {
		t.Fatalf(
			"unexpected unscoped-proof error: %v",
			err,
		)
	}
}

func TestAnalyticalBoundProofRejectsProbabilisticZeroDelta(
	t *testing.T,
) {
	proof := AnalyticalBoundProof{
		Method:  "invalid-tail-envelope",
		Version: "v1",

		Guarantee: AnalyticalGuaranteeProbabilistic,

		ScopeDigest:      analyticalProofTestDigest,
		DerivationDigest: analyticalProofTestDigest,

		MaxErrorBound: 0.001,
	}

	err := proof.Validate()
	if err == nil {
		t.Fatal(
			"expected zero-delta probabilistic proof to fail",
		)
	}
	if !strings.Contains(
		err.Error(),
		"failure probability",
	) {
		t.Fatalf(
			"unexpected probabilistic-proof error: %v",
			err,
		)
	}
}
