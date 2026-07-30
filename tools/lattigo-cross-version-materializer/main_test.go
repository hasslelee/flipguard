package main

import "testing"

func TestHITCandidateMaterializesExactly(t *testing.T) {
	result, err := materialize(input{
		NumSlots:    8192,
		MaxCTLevel:  6,
		LogScale:    20,
		NumKSPrimes: 1,
	})
	if err != nil {
		t.Fatal(err)
	}
	if !result.ExactConcreteTranslation {
		t.Fatalf("translation is not exact: %+v", result)
	}
	if result.Derived.LogN != 14 ||
		len(result.Derived.LogQ) != 7 ||
		len(result.Derived.LogP) != 1 ||
		result.Derived.LogQ[0] != 60 ||
		result.Derived.LogP[0] != 61 {
		t.Fatalf("unexpected HIT formula: %+v", result.Derived)
	}
	if result.V6NativeLogError == "" {
		t.Fatal("expected native v6 LogQ materialization diagnostic")
	}
}

func TestRejectsNonPowerOfTwoSlots(t *testing.T) {
	_, err := materialize(input{
		NumSlots:    1000,
		MaxCTLevel:  6,
		LogScale:    20,
		NumKSPrimes: 1,
	})
	if err == nil {
		t.Fatal("expected invalid slot count")
	}
}
