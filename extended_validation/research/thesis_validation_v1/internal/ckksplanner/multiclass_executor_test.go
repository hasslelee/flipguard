package ckksplanner

import "testing"

func TestMulticlassRoleForSplit(t *testing.T) {
	if got := multiclassRoleForSplit("mnist_sha_rank_validation_500_v1"); got != "configuration_validation" {
		t.Fatalf("unexpected validation role %q", got)
	}
	if got := multiclassRoleForSplit("mnist_sha_rank_locked_audit_500_v1"); got != "locked_audit" {
		t.Fatalf("unexpected audit role %q", got)
	}
}

func TestEqualFloatVectorsUsesExactBits(t *testing.T) {
	if !equalFloatVectors([]float64{1, 2}, []float64{1, 2}) {
		t.Fatal("identical vectors should match")
	}
	if equalFloatVectors([]float64{1, 2}, []float64{1, 2.000000000000001}) {
		t.Fatal("changed full-precision vector should fail")
	}
}
