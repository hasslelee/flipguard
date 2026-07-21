package certify

import (
	"strings"
	"testing"
)

const analyticalScopeTestDigest = "sha256:" +
	"22222222222222222222222222222222" +
	"22222222222222222222222222222222"

func TestAnalyticalExecutionScopeFiniteSetDigestIsDeterministic(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()

	first, err := scope.Digest()
	if err != nil {
		t.Fatalf(
			"first scope digest failed: %v",
			err,
		)
	}

	second, err := scope.Digest()
	if err != nil {
		t.Fatalf(
			"second scope digest failed: %v",
			err,
		)
	}

	if first != second {
		t.Fatalf(
			"scope digest is not deterministic: %s != %s",
			first,
			second,
		)
	}

	if !scope.Input.CertificateEligible() {
		t.Fatal(
			"enumerated finite set should be scope-eligible",
		)
	}
}

func TestAnalyticalExecutionScopeDigestChangesWithExecutionPath(
	t *testing.T,
) {
	baseline := testAnalyticalExecutionScope()

	baselineDigest, err := baseline.Digest()
	if err != nil {
		t.Fatalf(
			"baseline digest failed: %v",
			err,
		)
	}

	rescale := baseline
	rescale.ExecutionPath = "rescale_aware"

	rescaleDigest, err := rescale.Digest()
	if err != nil {
		t.Fatalf(
			"rescale digest failed: %v",
			err,
		)
	}

	if baselineDigest == rescaleDigest {
		t.Fatal(
			"execution-path change did not alter scope digest",
		)
	}
}

func TestAnalyticalExecutionScopeDigestChangesWithProfile(
	t *testing.T,
) {
	first := testAnalyticalExecutionScope()

	firstDigest, err := first.Digest()
	if err != nil {
		t.Fatalf(
			"first digest failed: %v",
			err,
		)
	}

	second := first
	second.ProfileFactsDigest = "sha256:" +
		"33333333333333333333333333333333" +
		"33333333333333333333333333333333"

	secondDigest, err := second.Digest()
	if err != nil {
		t.Fatalf(
			"second digest failed: %v",
			err,
		)
	}

	if firstDigest == secondDigest {
		t.Fatal(
			"profile change did not alter scope digest",
		)
	}
}

func TestDeclaredBoxDomainIsScopeEligible(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()

	scope.Input = AnalyticalInputScope{
		Kind: AnalyticalInputDeclaredBoxDomain,

		SourceDigest: analyticalScopeTestDigest,

		FeatureBounds: []AnalyticalFeatureBound{
			{
				Index: 0,
				Name:  "x_0",
				Lower: -2,
				Upper: 2,
			},
			{
				Index: 1,
				Name:  "x_1",
				Lower: -4,
				Upper: 4,
			},
		},
	}

	if err := scope.Validate(); err != nil {
		t.Fatalf(
			"valid box scope rejected: %v",
			err,
		)
	}

	if !scope.Input.CertificateEligible() {
		t.Fatal(
			"declared box domain should be scope-eligible",
		)
	}
}

func TestEmpiricalRangeIsNotCertificateEligible(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()

	scope.Input = AnalyticalInputScope{
		Kind: AnalyticalInputEmpiricalRangeOnly,

		SourceDigest: analyticalScopeTestDigest,

		FeatureBounds: []AnalyticalFeatureBound{
			{
				Index: 0,
				Name:  "x_0",
				Lower: -1.5,
				Upper: 2.7,
			},
		},
	}

	if err := scope.Validate(); err != nil {
		t.Fatalf(
			"valid empirical scope rejected: %v",
			err,
		)
	}

	if scope.Input.CertificateEligible() {
		t.Fatal(
			"empirical ranges must not be certificate eligible",
		)
	}
}

func TestEnumeratedFiniteSetRejectsFeatureRangeSubstitution(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()

	scope.Input.FeatureBounds =
		[]AnalyticalFeatureBound{
			{
				Index: 0,
				Name:  "x_0",
				Lower: -1,
				Upper: 1,
			},
		}

	err := scope.Validate()
	if err == nil {
		t.Fatal(
			"expected finite-set scope with feature bounds to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"must not substitute empirical feature bounds",
	) {
		t.Fatalf(
			"unexpected finite-set scope error: %v",
			err,
		)
	}
}

func TestDeclaredBoxDomainRejectsNonContiguousFeatureOrder(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()

	scope.Input = AnalyticalInputScope{
		Kind: AnalyticalInputDeclaredBoxDomain,

		SourceDigest: analyticalScopeTestDigest,

		FeatureBounds: []AnalyticalFeatureBound{
			{
				Index: 1,
				Name:  "x_1",
				Lower: -1,
				Upper: 1,
			},
		},
	}

	err := scope.Validate()
	if err == nil {
		t.Fatal(
			"expected non-contiguous feature order to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"not contiguous",
	) {
		t.Fatalf(
			"unexpected feature-order error: %v",
			err,
		)
	}
}

func TestAnalyticalExecutionScopeRejectsInvalidDigest(
	t *testing.T,
) {
	scope := testAnalyticalExecutionScope()
	scope.ModelArtifactDigest = "not-a-digest"

	err := scope.Validate()
	if err == nil {
		t.Fatal(
			"expected invalid model digest to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"model artifact digest",
	) {
		t.Fatalf(
			"unexpected digest error: %v",
			err,
		)
	}
}

func testAnalyticalExecutionScope() AnalyticalExecutionScope {
	return AnalyticalExecutionScope{
		SchemaVersion: 1,

		WorkloadID: "banknote__linear_poly3",
		DatasetID:  "banknote",
		ModelID:    "linear_poly3",
		ModelType:  "linear_poly3",

		Formula:   "0.5 + 0.197*z - 0.004*z^3",
		Threshold: 0.5,

		ModelArtifactDigest:  analyticalScopeTestDigest,
		OperationGraphDigest: analyticalScopeTestDigest,
		ProfileFactsDigest:   analyticalScopeTestDigest,
		SourceCodeDigest:     analyticalScopeTestDigest,

		ExecutionPath: "baseline_non_rescale",

		LibraryModule:  "github.com/tuneinsight/lattigo/v6",
		LibraryVersion: "v6.2.0",

		Input: AnalyticalInputScope{
			Kind: AnalyticalInputEnumeratedFiniteSet,

			SourceDigest: analyticalScopeTestDigest,
			SampleCount:  412,
		},
	}
}
