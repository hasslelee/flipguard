package ckksbackend

import (
	"strings"
	"testing"
)

func TestValidateTabularPlainDecisionsUsesArtifactThreshold(
	t *testing.T,
) {
	rows := []tabularTestRow{
		{
			RowID:         0,
			PlainY:        0.60,
			PlainDecision: false,
		},
		{
			RowID:         1,
			PlainY:        0.80,
			PlainDecision: true,
		},
	}

	if err := validateTabularPlainDecisions(
		rows,
		0.70,
	); err != nil {
		t.Fatalf(
			"expected decisions to match threshold 0.70: %v",
			err,
		)
	}

	err := validateTabularPlainDecisions(
		rows,
		0.50,
	)
	if err == nil {
		t.Fatal(
			"expected decision mismatch at threshold 0.50",
		)
	}
	if !strings.Contains(
		err.Error(),
		"does not match",
	) {
		t.Fatalf(
			"unexpected validation error: %v",
			err,
		)
	}
}
