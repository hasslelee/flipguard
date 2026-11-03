package main

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

func TestAccumulateTimingStabilityUsesFrozenStrictBudget(t *testing.T) {
	records := []ckksbackend.PairedTabularLatencyRecord{
		{ArmID: "direct", PlainY: 0.6, YError: 0.049},
		{ArmID: "finite_fastest_safe", PlainY: 0.6, YError: 0.05, DecisionFlip: true},
		{ArmID: "direct", PlainY: 0.5005, YError: 1},
	}
	flips := map[string]int{"direct": 0, "finite_fastest_safe": 0}
	violations := map[string]int{"direct": 0, "finite_fastest_safe": 0}
	accumulateTimingStability(records, 0.5, 0.001, 0.5, flips, violations)
	if flips["finite_fastest_safe"] != 1 || flips["direct"] != 0 {
		t.Fatalf("unexpected flip counts: %#v", flips)
	}
	if violations["finite_fastest_safe"] != 1 || violations["direct"] != 0 {
		t.Fatalf("unexpected violation counts: %#v", violations)
	}
}
