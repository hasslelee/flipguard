package ckksbackend

import "testing"

func TestRunRoundTripProbe(t *testing.T) {
	result, err := RunRoundTripProbe()
	if err != nil {
		t.Fatalf("RunRoundTripProbe failed: %v", err)
	}

	if result.MaxSlots <= 0 {
		t.Fatalf("expected positive max slots, got %d", result.MaxSlots)
	}

	if result.MaxLevel <= 0 {
		t.Fatalf("expected positive max level, got %d", result.MaxLevel)
	}

	if result.LogDefaultScale <= 0 {
		t.Fatalf("expected positive default scale, got %d", result.LogDefaultScale)
	}

	if result.AbsError > 1e-3 {
		t.Fatalf(
			"roundtrip error too large: want %.10f got %.10f abs_error %.10f",
			result.Want,
			result.Got,
			result.AbsError,
		)
	}

	t.Logf(
		"CKKS roundtrip ok: want=%.10f got=%.10f abs_error=%.10f max_slots=%d max_level=%d log_default_scale=%d",
		result.Want,
		result.Got,
		result.AbsError,
		result.MaxSlots,
		result.MaxLevel,
		result.LogDefaultScale,
	)
}
