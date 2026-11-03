package main

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

func TestMaterializeExactModuli(t *testing.T) {
	policy := ckksplanner.DefaultSecurityEnvelope()
	source := sourceCandidate{
		ModelID: "test",
		Arm:     "direct",
		Value: candidate{
			ID:   "test-candidate",
			Path: "rescale",
			Parameters: ckksplanner.CKKSParameterLiteralSpec{
				LogN:            13,
				LogQ:            []int{39, 29, 29, 29, 29},
				LogP:            []int{39},
				LogDefaultScale: 29,
			},
		},
	}
	security, err := ckksplanner.AssessSecurity(source.Value.Parameters, 128, policy)
	if err != nil {
		t.Fatal(err)
	}
	source.Value.Security = security
	record, err := materialize(source, policy)
	if err != nil {
		t.Fatal(err)
	}
	if len(record.ExactQPrimes) != 5 || len(record.ExactPPrimes) != 1 {
		t.Fatalf("unexpected exact modulus lengths: Q=%d P=%d", len(record.ExactQPrimes), len(record.ExactPPrimes))
	}
	if record.ActualLogQP <= record.ActualLogQ {
		t.Fatalf("QP must exceed Q: Q=%f QP=%f", record.ActualLogQ, record.ActualLogQP)
	}
	if record.SecurityPolicy.FinalAdmission != "PASS" {
		t.Fatalf("expected Security-V2 PASS, got %s", record.SecurityPolicy.FinalAdmission)
	}
}

func TestMaterializePreservesConcretePrimes(t *testing.T) {
	policy := ckksplanner.DefaultSecurityEnvelope()
	source := sourceCandidate{
		ModelID: "test",
		Arm:     "catalog",
		Value: candidate{
			ID:   "concrete-candidate",
			Path: "rescale",
			Parameters: ckksplanner.CKKSParameterLiteralSpec{
				LogN:            13,
				Q:               []uint64{549755731969, 536903681},
				P:               []uint64{549756026881},
				LogDefaultScale: 29,
			},
		},
	}
	security, err := ckksplanner.AssessConcreteSecurity(source.Value.Parameters, 128, policy)
	if err != nil {
		t.Fatal(err)
	}
	source.Value.Security = security
	record, err := materialize(source, policy)
	if err != nil {
		t.Fatal(err)
	}
	if record.ExactQPrimes[0] != source.Value.Parameters.Q[0] || record.ExactPPrimes[0] != source.Value.Parameters.P[0] {
		t.Fatalf("concrete primes changed: Q=%v P=%v", record.ExactQPrimes, record.ExactPPrimes)
	}
	if record.SecurityPolicy.Measurement != "ceil_log2_concrete_modulus_product" {
		t.Fatalf("unexpected measurement: %s", record.SecurityPolicy.Measurement)
	}
}
