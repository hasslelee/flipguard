package ckksbackend

import "testing"

func TestEncodeEncryptDecryptDecodeVector(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	values := []float64{
		0.25,
		-0.5,
		1.125,
	}

	result, err := ctx.EncodeEncryptDecryptDecodeVector(values)
	if err != nil {
		t.Fatalf("EncodeEncryptDecryptDecodeVector failed: %v", err)
	}

	if result.UsedSlots != len(values) {
		t.Fatalf("expected used slots %d, got %d", len(values), result.UsedSlots)
	}

	if len(result.Got) != len(values) {
		t.Fatalf("expected decoded length %d, got %d", len(values), len(result.Got))
	}

	if result.MaxAbsError > 1e-3 {
		t.Fatalf(
			"input vector max error too large: max_abs_error %.10f mean_abs_error %.10f want=%v got=%v",
			result.MaxAbsError,
			result.MeanAbsError,
			result.Want,
			result.Got,
		)
	}

	t.Logf(
		"input vector roundtrip ok: want=%v got=%v max_abs_error=%.10f mean_abs_error=%.10f slots=%d used_slots=%d",
		result.Want,
		result.Got,
		result.MaxAbsError,
		result.MeanAbsError,
		result.Slots,
		result.UsedSlots,
	)
}

func TestEncodeEncryptDecryptDecodeVectorRejectsEmptyInput(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	if _, err := ctx.EncodeEncryptDecryptDecodeVector(nil); err == nil {
		t.Fatalf("expected empty input error")
	}
}

func TestEncodeEncryptDecryptDecodeLogRegSmallInput(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	input := LogRegSmallInput{
		X1: 0.8,
		X2: -0.3,
		X3: 0.1,
	}

	result, err := ctx.EncodeEncryptDecryptDecodeLogRegSmallInput(input)
	if err != nil {
		t.Fatalf("EncodeEncryptDecryptDecodeLogRegSmallInput failed: %v", err)
	}

	if result.UsedSlots != 3 {
		t.Fatalf("expected 3 used slots, got %d", result.UsedSlots)
	}

	if result.MaxAbsError > 1e-3 {
		t.Fatalf(
			"logreg_small input max error too large: max_abs_error %.10f want=%v got=%v",
			result.MaxAbsError,
			result.Want,
			result.Got,
		)
	}
}
