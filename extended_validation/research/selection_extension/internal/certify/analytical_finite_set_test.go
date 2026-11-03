package certify

import (
	"math"
	"strings"
	"testing"
)

func TestAnalyticalFiniteSetDigestIsDeterministic(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()

	first, err := set.Digest()
	if err != nil {
		t.Fatalf(
			"first finite-set digest failed: %v",
			err,
		)
	}

	second, err := set.Digest()
	if err != nil {
		t.Fatalf(
			"second finite-set digest failed: %v",
			err,
		)
	}

	if first != second {
		t.Fatalf(
			"finite-set digest is not deterministic: %s != %s",
			first,
			second,
		)
	}

	scope, err := set.InputScope()
	if err != nil {
		t.Fatalf(
			"finite-set input scope failed: %v",
			err,
		)
	}

	if scope.Kind !=
		AnalyticalInputEnumeratedFiniteSet {
		t.Fatalf(
			"unexpected scope kind %q",
			scope.Kind,
		)
	}

	if scope.SourceDigest != first {
		t.Fatalf(
			"scope digest %q does not match set digest %q",
			scope.SourceDigest,
			first,
		)
	}

	if scope.SampleCount != len(set.Rows) {
		t.Fatalf(
			"scope sample count %d; expected %d",
			scope.SampleCount,
			len(set.Rows),
		)
	}
}

func TestAnalyticalFiniteSetDigestChangesWithRowOrder(
	t *testing.T,
) {
	first := testAnalyticalFiniteSet()
	second := testAnalyticalFiniteSet()

	second.Rows[0], second.Rows[1] =
		second.Rows[1], second.Rows[0]

	requireDifferentFiniteSetDigest(
		t,
		first,
		second,
		"row order",
	)
}

func TestAnalyticalFiniteSetDigestChangesWithFeatureOrder(
	t *testing.T,
) {
	first := testAnalyticalFiniteSet()
	second := testAnalyticalFiniteSet()

	second.FeatureNames[0],
		second.FeatureNames[1] =
		second.FeatureNames[1],
		second.FeatureNames[0]

	for rowIndex := range second.Rows {
		second.Rows[rowIndex].Values[0],
			second.Rows[rowIndex].Values[1] =
			second.Rows[rowIndex].Values[1],
			second.Rows[rowIndex].Values[0]
	}

	requireDifferentFiniteSetDigest(
		t,
		first,
		second,
		"feature order",
	)
}

func TestAnalyticalFiniteSetDigestChangesWithSampleID(
	t *testing.T,
) {
	first := testAnalyticalFiniteSet()
	second := testAnalyticalFiniteSet()

	second.Rows[0].SampleID = "row-0009"

	requireDifferentFiniteSetDigest(
		t,
		first,
		second,
		"sample ID",
	)
}

func TestAnalyticalFiniteSetDigestChangesWithFeatureValue(
	t *testing.T,
) {
	first := testAnalyticalFiniteSet()
	second := testAnalyticalFiniteSet()

	second.Rows[1].Values[2] += 1e-12

	requireDifferentFiniteSetDigest(
		t,
		first,
		second,
		"feature value",
	)
}

func TestAnalyticalFiniteSetNormalizesNegativeZero(
	t *testing.T,
) {
	positive := NewAnalyticalFiniteSet(
		[]string{"x_0"},
		[]AnalyticalFiniteSetRow{
			{
				SampleID: "0",
				Values:   []float64{0},
			},
		},
	)

	negative := NewAnalyticalFiniteSet(
		[]string{"x_0"},
		[]AnalyticalFiniteSetRow{
			{
				SampleID: "0",
				Values: []float64{
					math.Copysign(0, -1),
				},
			},
		},
	)

	positiveDigest, err := positive.Digest()
	if err != nil {
		t.Fatalf(
			"positive-zero digest failed: %v",
			err,
		)
	}

	negativeDigest, err := negative.Digest()
	if err != nil {
		t.Fatalf(
			"negative-zero digest failed: %v",
			err,
		)
	}

	if positiveDigest != negativeDigest {
		t.Fatalf(
			"positive and negative zero produced different digests: %s != %s",
			positiveDigest,
			negativeDigest,
		)
	}
}

func TestAnalyticalFiniteSetRejectsDuplicateSampleID(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()
	set.Rows[1].SampleID = set.Rows[0].SampleID

	err := set.Validate()
	if err == nil {
		t.Fatal(
			"expected duplicate sample ID to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"duplicate sample ID",
	) {
		t.Fatalf(
			"unexpected duplicate-sample error: %v",
			err,
		)
	}
}

func TestAnalyticalFiniteSetRejectsDuplicateFeatureName(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()
	set.FeatureNames[1] = set.FeatureNames[0]

	err := set.Validate()
	if err == nil {
		t.Fatal(
			"expected duplicate feature name to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"duplicate feature name",
	) {
		t.Fatalf(
			"unexpected duplicate-feature error: %v",
			err,
		)
	}
}

func TestAnalyticalFiniteSetRejectsDimensionMismatch(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()
	set.Rows[0].Values =
		set.Rows[0].Values[:2]

	err := set.Validate()
	if err == nil {
		t.Fatal(
			"expected feature dimension mismatch to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"expected 3",
	) {
		t.Fatalf(
			"unexpected dimension error: %v",
			err,
		)
	}
}

func TestAnalyticalFiniteSetRejectsNonFiniteValue(
	t *testing.T,
) {
	for _, value := range []float64{
		math.NaN(),
		math.Inf(1),
		math.Inf(-1),
	} {
		set := testAnalyticalFiniteSet()
		set.Rows[0].Values[0] = value

		err := set.Validate()
		if err == nil {
			t.Fatalf(
				"expected non-finite value %v to fail",
				value,
			)
		}

		if !strings.Contains(
			err.Error(),
			"must be finite",
		) {
			t.Fatalf(
				"unexpected non-finite error: %v",
				err,
			)
		}
	}
}

func TestAnalyticalFiniteSetRejectsWhitespaceIdentity(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()
	set.Rows[0].SampleID = " 0"

	err := set.Validate()
	if err == nil {
		t.Fatal(
			"expected sample ID whitespace to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"surrounding whitespace",
	) {
		t.Fatalf(
			"unexpected whitespace error: %v",
			err,
		)
	}
}

func testAnalyticalFiniteSet() AnalyticalFiniteSet {
	return NewAnalyticalFiniteSet(
		[]string{
			"variance_wavelet",
			"skewness_wavelet",
			"curtosis_wavelet",
		},
		[]AnalyticalFiniteSetRow{
			{
				SampleID: "0",
				Values: []float64{
					-0.75,
					1.25,
					0.5,
				},
			},
			{
				SampleID: "1",
				Values: []float64{
					0.125,
					-2.5,
					3.75,
				},
			},
		},
	)
}

func requireDifferentFiniteSetDigest(
	t *testing.T,
	first AnalyticalFiniteSet,
	second AnalyticalFiniteSet,
	changedField string,
) {
	t.Helper()

	firstDigest, err := first.Digest()
	if err != nil {
		t.Fatalf(
			"first digest for %s failed: %v",
			changedField,
			err,
		)
	}

	secondDigest, err := second.Digest()
	if err != nil {
		t.Fatalf(
			"second digest for %s failed: %v",
			changedField,
			err,
		)
	}

	if firstDigest == secondDigest {
		t.Fatalf(
			"%s change did not alter finite-set digest",
			changedField,
		)
	}
}

func TestAnalyticalFiniteSetDigestMatchesVersion1GoldenVector(
	t *testing.T,
) {
	set := testAnalyticalFiniteSet()

	got, err := set.Digest()
	if err != nil {
		t.Fatalf(
			"golden finite-set digest failed: %v",
			err,
		)
	}

	const expected = "sha256:" +
		"7033b79e9173b89f529e7a5feadfac10" +
		"680007ca8074da5ed89e2affca366ff3"

	if got != expected {
		t.Fatalf(
			"finite-set schema-v1 digest changed: got %s, expected %s",
			got,
			expected,
		)
	}
}

func TestNewAnalyticalFiniteSetDefensivelyCopiesInputs(
	t *testing.T,
) {
	featureNames := []string{
		"x_0",
		"x_1",
	}

	rows := []AnalyticalFiniteSetRow{
		{
			SampleID: "0",
			Values: []float64{
				1.25,
				-2.5,
			},
		},
	}

	set := NewAnalyticalFiniteSet(
		featureNames,
		rows,
	)

	before, err := set.Digest()
	if err != nil {
		t.Fatalf(
			"finite-set digest before mutation failed: %v",
			err,
		)
	}

	featureNames[0] = "mutated_feature"
	rows[0].SampleID = "mutated_sample"
	rows[0].Values[0] = 999

	after, err := set.Digest()
	if err != nil {
		t.Fatalf(
			"finite-set digest after source mutation failed: %v",
			err,
		)
	}

	if before != after {
		t.Fatalf(
			"source-slice mutation changed defensively copied set: %s != %s",
			before,
			after,
		)
	}

	if set.FeatureNames[0] != "x_0" {
		t.Fatalf(
			"feature name was not defensively copied: %q",
			set.FeatureNames[0],
		)
	}

	if set.Rows[0].SampleID != "0" {
		t.Fatalf(
			"sample ID was not defensively copied: %q",
			set.Rows[0].SampleID,
		)
	}

	if set.Rows[0].Values[0] != 1.25 {
		t.Fatalf(
			"feature value was not defensively copied: %.12g",
			set.Rows[0].Values[0],
		)
	}
}
