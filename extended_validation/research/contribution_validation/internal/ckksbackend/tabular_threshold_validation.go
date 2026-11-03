package ckksbackend

import (
	"fmt"
	"math"
)

// validateTabularDecisionThreshold rejects non-finite decision thresholds.
func validateTabularDecisionThreshold(
	threshold float64,
) error {
	if math.IsNaN(threshold) ||
		math.IsInf(threshold, 0) {
		return fmt.Errorf(
			"tabular decision threshold must be finite",
		)
	}

	return nil
}

// validateTabularPlainDecisions verifies that the plaintext decisions stored
// in test.csv were generated using the model artifact's decision threshold.
func validateTabularPlainDecisions(
	rows []tabularTestRow,
	threshold float64,
) error {
	if err := validateTabularDecisionThreshold(
		threshold,
	); err != nil {
		return err
	}

	for _, row := range rows {
		expectedDecision := row.PlainY >= threshold

		if row.PlainDecision != expectedDecision {
			return fmt.Errorf(
				"tabular row %d plaintext decision %t does not match score %.12g at threshold %.12g",
				row.RowID,
				row.PlainDecision,
				row.PlainY,
				threshold,
			)
		}
	}

	return nil
}
