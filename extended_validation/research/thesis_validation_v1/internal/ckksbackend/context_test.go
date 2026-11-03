package ckksbackend

import (
	"math"
	"testing"
)

func TestNewDefaultContext(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	if ctx.MaxSlots() <= 0 {
		t.Fatalf("expected positive max slots, got %d", ctx.MaxSlots())
	}

	if ctx.MaxLevel() <= 0 {
		t.Fatalf("expected positive max level, got %d", ctx.MaxLevel())
	}

	if ctx.LogDefaultScale() <= 0 {
		t.Fatalf("expected positive log default scale, got %d", ctx.LogDefaultScale())
	}
}

func TestContextEncodeEncryptDecryptDecode(t *testing.T) {
	ctx, err := NewDefaultContext()
	if err != nil {
		t.Fatalf("NewDefaultContext failed: %v", err)
	}

	want := -0.375

	got, err := ctx.EncodeEncryptDecryptDecode(want)
	if err != nil {
		t.Fatalf("EncodeEncryptDecryptDecode failed: %v", err)
	}

	absError := math.Abs(got - want)
	if absError > 1e-3 {
		t.Fatalf(
			"roundtrip error too large: want %.10f got %.10f abs_error %.10f",
			want,
			got,
			absError,
		)
	}
}
