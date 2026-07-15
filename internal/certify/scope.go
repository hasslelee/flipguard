package certify

import (
	"encoding/hex"
	"fmt"
	"strings"
)

// ClaimScope identifies the exact validation domain covered by a certificate.
//
// It prevents a validation-set result from being presented as a guarantee over
// a different dataset, model, split, threshold, or margin policy.
type ClaimScope struct {
	WorkloadID string
	DatasetID  string
	ModelID    string
	SplitID    string

	// ValidationDigest binds the claim to the ordered set of validation
	// sample identifiers and plaintext scores used to build the certificate.
	ValidationDigest string

	Threshold    float64
	MarginFloor  float64
	SafetyFactor float64

	SampleCount int

	SuccessfulRuns int
	FailedRuns     int
}

// Validate checks whether the certificate claim scope is explicit and
// internally meaningful.
func (s ClaimScope) Validate() error {
	if strings.TrimSpace(s.WorkloadID) == "" {
		return fmt.Errorf("claim scope workload ID is empty")
	}
	if strings.TrimSpace(s.DatasetID) == "" {
		return fmt.Errorf("claim scope dataset ID is empty")
	}
	if strings.TrimSpace(s.ModelID) == "" {
		return fmt.Errorf("claim scope model ID is empty")
	}
	if strings.TrimSpace(s.SplitID) == "" {
		return fmt.Errorf("claim scope split ID is empty")
	}

	const digestPrefix = "sha256:"
	if !strings.HasPrefix(s.ValidationDigest, digestPrefix) {
		return fmt.Errorf(
			"claim scope validation digest must use sha256 prefix",
		)
	}

	digestHex := strings.TrimPrefix(
		s.ValidationDigest,
		digestPrefix,
	)
	decodedDigest, err := hex.DecodeString(digestHex)
	if err != nil {
		return fmt.Errorf(
			"claim scope validation digest is invalid: %w",
			err,
		)
	}
	if len(decodedDigest) != 32 {
		return fmt.Errorf(
			"claim scope validation digest must contain 32 bytes",
		)
	}

	if !isFinite(s.Threshold) {
		return fmt.Errorf("claim scope threshold must be finite")
	}
	if !isFinite(s.MarginFloor) || s.MarginFloor < 0 {
		return fmt.Errorf(
			"claim scope margin floor must be finite and non-negative",
		)
	}
	if !isFinite(s.SafetyFactor) ||
		s.SafetyFactor <= 0 ||
		s.SafetyFactor > 1 {
		return fmt.Errorf(
			"claim scope safety factor must be finite and in (0, 1]",
		)
	}
	if s.SampleCount <= 0 {
		return fmt.Errorf(
			"claim scope sample count must be positive",
		)
	}
	if s.SuccessfulRuns < 0 {
		return fmt.Errorf(
			"claim scope successful runs must be non-negative",
		)
	}
	if s.FailedRuns < 0 {
		return fmt.Errorf(
			"claim scope failed runs must be non-negative",
		)
	}
	if s.SuccessfulRuns+s.FailedRuns <= 0 {
		return fmt.Errorf(
			"claim scope must contain at least one attempted run",
		)
	}

	return nil
}
