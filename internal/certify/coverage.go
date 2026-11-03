package certify

import (
	"fmt"
	"math"
	"sort"
)

// ValidationCoverage summarizes the decision-margin partition of a validation
// set.
//
// A sample belongs to V_amb when:
//
//	|plainScore - threshold| <= marginFloor
//
// All remaining samples belong to V_cert.
type ValidationCoverage struct {
	Threshold   float64
	MarginFloor float64

	Total int

	VCert int
	VAmb  int

	CoverageRate float64

	// MinMargin is the minimum margin over the entire validation set.
	MinMargin float64

	// MinCertifiedMargin is the minimum margin over V_cert.
	// It is zero when V_cert is empty.
	MinCertifiedMargin float64

	// P5Margin is the nearest-rank fifth percentile of all margins.
	P5Margin float64
}

// AnalyzeValidationCoverage partitions plaintext validation scores into
// certifiable and ambiguous subsets.
func AnalyzeValidationCoverage(
	plainScores []float64,
	threshold float64,
	marginFloor float64,
) (ValidationCoverage, error) {
	if len(plainScores) == 0 {
		return ValidationCoverage{}, fmt.Errorf(
			"plain validation scores are empty",
		)
	}
	if !isFinite(threshold) {
		return ValidationCoverage{}, fmt.Errorf(
			"threshold must be finite",
		)
	}
	if !isFinite(marginFloor) || marginFloor < 0 {
		return ValidationCoverage{}, fmt.Errorf(
			"margin floor must be finite and non-negative: %.12g",
			marginFloor,
		)
	}

	margins := make([]float64, 0, len(plainScores))
	certifiedMargins := make([]float64, 0, len(plainScores))

	coverage := ValidationCoverage{
		Threshold:   threshold,
		MarginFloor: marginFloor,
		Total:       len(plainScores),
	}

	for i, score := range plainScores {
		if !isFinite(score) {
			return ValidationCoverage{}, fmt.Errorf(
				"plain validation score at index %d is not finite",
				i,
			)
		}

		margin := math.Abs(score - threshold)
		margins = append(margins, margin)

		if margin <= marginFloor {
			coverage.VAmb++
			continue
		}

		coverage.VCert++
		certifiedMargins = append(certifiedMargins, margin)
	}

	sort.Float64s(margins)
	sort.Float64s(certifiedMargins)

	coverage.CoverageRate =
		float64(coverage.VCert) / float64(coverage.Total)

	coverage.MinMargin = margins[0]
	coverage.P5Margin = nearestRankPercentile(margins, 0.05)

	if len(certifiedMargins) > 0 {
		coverage.MinCertifiedMargin = certifiedMargins[0]
	}

	return coverage, nil
}

// Validate checks internal consistency of a validation coverage summary.
func (c ValidationCoverage) Validate() error {
	if !isFinite(c.Threshold) {
		return fmt.Errorf("validation threshold must be finite")
	}
	if !isFinite(c.MarginFloor) || c.MarginFloor < 0 {
		return fmt.Errorf(
			"validation margin floor must be finite and non-negative",
		)
	}
	if c.Total <= 0 {
		return fmt.Errorf(
			"validation coverage total must be positive",
		)
	}
	if c.VCert < 0 {
		return fmt.Errorf("V_cert must be non-negative")
	}
	if c.VAmb < 0 {
		return fmt.Errorf("V_amb must be non-negative")
	}
	if c.VCert+c.VAmb != c.Total {
		return fmt.Errorf(
			"validation coverage mismatch: V_cert=%d V_amb=%d total=%d",
			c.VCert,
			c.VAmb,
			c.Total,
		)
	}
	if !isFinite(c.CoverageRate) ||
		c.CoverageRate < 0 ||
		c.CoverageRate > 1 {
		return fmt.Errorf(
			"coverage rate must be finite and in [0, 1]",
		)
	}
	if !isFinite(c.MinMargin) || c.MinMargin < 0 {
		return fmt.Errorf(
			"minimum margin must be finite and non-negative",
		)
	}
	if !isFinite(c.MinCertifiedMargin) ||
		c.MinCertifiedMargin < 0 {
		return fmt.Errorf(
			"minimum certified margin must be finite and non-negative",
		)
	}
	if !isFinite(c.P5Margin) || c.P5Margin < 0 {
		return fmt.Errorf(
			"p5 margin must be finite and non-negative",
		)
	}

	return nil
}

func nearestRankPercentile(
	sorted []float64,
	percentile float64,
) float64 {
	if len(sorted) == 0 {
		return 0
	}
	if percentile <= 0 {
		return sorted[0]
	}
	if percentile >= 1 {
		return sorted[len(sorted)-1]
	}

	rank := int(math.Ceil(
		percentile*float64(len(sorted)),
	)) - 1

	if rank < 0 {
		rank = 0
	}
	if rank >= len(sorted) {
		rank = len(sorted) - 1
	}

	return sorted[rank]
}

func isFinite(value float64) bool {
	return !math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
