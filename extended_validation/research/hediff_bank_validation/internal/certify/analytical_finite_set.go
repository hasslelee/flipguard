package certify

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"math"
	"strings"
)

const analyticalFiniteSetSchemaVersion = 1

const analyticalFiniteSetCanonicalMagic = "flipguard:analytical-finite-set:v1"

// AnalyticalFiniteSetRow contains one model-ready input vector.
//
// SampleID binds the vector to the stable row identity used by observed
// evidence. Values must be ordered exactly as FeatureNames.
type AnalyticalFiniteSetRow struct {
	SampleID string
	Values   []float64
}

// AnalyticalFiniteSet describes an exact ordered collection of model-ready
// inputs.
//
// The set intentionally excludes labels, plaintext outputs, decisions, and
// CKKS results. Those values are not inputs to the encrypted computation.
// Preprocessing and model semantics are bound separately through the model
// artifact digest in AnalyticalExecutionScope.
type AnalyticalFiniteSet struct {
	SchemaVersion int

	FeatureNames []string
	Rows         []AnalyticalFiniteSetRow
}

// NewAnalyticalFiniteSet creates a versioned finite-set value with defensive
// copies of all supplied slices.
func NewAnalyticalFiniteSet(
	featureNames []string,
	rows []AnalyticalFiniteSetRow,
) AnalyticalFiniteSet {
	copiedFeatures := append(
		[]string(nil),
		featureNames...,
	)

	copiedRows := make(
		[]AnalyticalFiniteSetRow,
		len(rows),
	)

	for index, row := range rows {
		copiedRows[index] = AnalyticalFiniteSetRow{
			SampleID: row.SampleID,
			Values: append(
				[]float64(nil),
				row.Values...,
			),
		}
	}

	return AnalyticalFiniteSet{
		SchemaVersion: analyticalFiniteSetSchemaVersion,
		FeatureNames:  copiedFeatures,
		Rows:          copiedRows,
	}
}

// Validate rejects ambiguous, incomplete, or non-finite finite-set
// descriptions.
func (set AnalyticalFiniteSet) Validate() error {
	if set.SchemaVersion !=
		analyticalFiniteSetSchemaVersion {
		return fmt.Errorf(
			"unsupported analytical finite-set schema version %d",
			set.SchemaVersion,
		)
	}

	if len(set.FeatureNames) == 0 {
		return fmt.Errorf(
			"analytical finite set has no features",
		)
	}

	seenFeatures := make(
		map[string]struct{},
		len(set.FeatureNames),
	)

	for index, name := range set.FeatureNames {
		if name == "" {
			return fmt.Errorf(
				"analytical finite-set feature %d name is empty",
				index,
			)
		}

		if strings.TrimSpace(name) != name {
			return fmt.Errorf(
				"analytical finite-set feature %d name %q has surrounding whitespace",
				index,
				name,
			)
		}

		if _, exists := seenFeatures[name]; exists {
			return fmt.Errorf(
				"analytical finite set has duplicate feature name %q",
				name,
			)
		}

		seenFeatures[name] = struct{}{}
	}

	if len(set.Rows) == 0 {
		return fmt.Errorf(
			"analytical finite set has no rows",
		)
	}

	seenSamples := make(
		map[string]struct{},
		len(set.Rows),
	)

	for rowIndex, row := range set.Rows {
		if row.SampleID == "" {
			return fmt.Errorf(
				"analytical finite-set row %d sample ID is empty",
				rowIndex,
			)
		}

		if strings.TrimSpace(row.SampleID) !=
			row.SampleID {
			return fmt.Errorf(
				"analytical finite-set row %d sample ID %q has surrounding whitespace",
				rowIndex,
				row.SampleID,
			)
		}

		if _, exists := seenSamples[row.SampleID]; exists {
			return fmt.Errorf(
				"analytical finite set has duplicate sample ID %q",
				row.SampleID,
			)
		}

		seenSamples[row.SampleID] = struct{}{}

		if len(row.Values) != len(set.FeatureNames) {
			return fmt.Errorf(
				"analytical finite-set row %d sample %q has %d values; expected %d",
				rowIndex,
				row.SampleID,
				len(row.Values),
				len(set.FeatureNames),
			)
		}

		for featureIndex, value := range row.Values {
			if math.IsNaN(value) ||
				math.IsInf(value, 0) {
				return fmt.Errorf(
					"analytical finite-set row %d sample %q feature %d must be finite",
					rowIndex,
					row.SampleID,
					featureIndex,
				)
			}
		}
	}

	return nil
}

// CanonicalBytes returns the deterministic binary representation used by
// Digest.
//
// Encoding:
//   - fixed schema magic
//   - ordered UTF-8 feature names
//   - ordered sample IDs
//   - ordered IEEE-754 binary64 feature values
//
// All lengths and binary64 values use unsigned 64-bit big-endian encoding.
// Negative zero is normalized to positive zero because both values have the
// same arithmetic meaning for the supported real-valued CKKS input path.
func (set AnalyticalFiniteSet) CanonicalBytes() (
	[]byte,
	error,
) {
	if err := set.Validate(); err != nil {
		return nil, err
	}

	var buffer bytes.Buffer

	writeAnalyticalFiniteSetString(
		&buffer,
		analyticalFiniteSetCanonicalMagic,
	)

	writeAnalyticalFiniteSetUint64(
		&buffer,
		uint64(len(set.FeatureNames)),
	)

	for _, name := range set.FeatureNames {
		writeAnalyticalFiniteSetString(
			&buffer,
			name,
		)
	}

	writeAnalyticalFiniteSetUint64(
		&buffer,
		uint64(len(set.Rows)),
	)

	for _, row := range set.Rows {
		writeAnalyticalFiniteSetString(
			&buffer,
			row.SampleID,
		)

		writeAnalyticalFiniteSetUint64(
			&buffer,
			uint64(len(row.Values)),
		)

		for _, value := range row.Values {
			if value == 0 {
				value = 0
			}

			writeAnalyticalFiniteSetUint64(
				&buffer,
				math.Float64bits(value),
			)
		}
	}

	return buffer.Bytes(), nil
}

// Digest returns the canonical exact-input-set SHA-256 digest.
func (set AnalyticalFiniteSet) Digest() (
	string,
	error,
) {
	canonical, err := set.CanonicalBytes()
	if err != nil {
		return "", err
	}

	sum := sha256.Sum256(canonical)

	return "sha256:" +
		hex.EncodeToString(sum[:]), nil
}

// InputScope returns the ENUMERATED_FINITE_SET scope represented by this exact
// input collection.
func (set AnalyticalFiniteSet) InputScope() (
	AnalyticalInputScope,
	error,
) {
	digest, err := set.Digest()
	if err != nil {
		return AnalyticalInputScope{}, err
	}

	scope := AnalyticalInputScope{
		Kind: AnalyticalInputEnumeratedFiniteSet,

		SourceDigest: digest,
		SampleCount:  len(set.Rows),
	}

	if err := scope.Validate(); err != nil {
		return AnalyticalInputScope{}, fmt.Errorf(
			"validate generated analytical finite-set scope: %w",
			err,
		)
	}

	return scope, nil
}

func writeAnalyticalFiniteSetString(
	buffer *bytes.Buffer,
	value string,
) {
	writeAnalyticalFiniteSetUint64(
		buffer,
		uint64(len([]byte(value))),
	)

	_, _ = buffer.WriteString(value)
}

func writeAnalyticalFiniteSetUint64(
	buffer *bytes.Buffer,
	value uint64,
) {
	var encoded [8]byte

	binary.BigEndian.PutUint64(
		encoded[:],
		value,
	)

	_, _ = buffer.Write(encoded[:])
}
