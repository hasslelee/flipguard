package ckksbackend

import (
	"testing"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

func TestNewCKKSProfileFromLiteralAcceptsDirectParameters(t *testing.T) {
	literal := ckks.ParametersLiteral{
		LogN:            13,
		LogQ:            []int{35, 30, 30},
		LogP:            []int{50},
		LogDefaultScale: 30,
	}
	profile, err := NewCKKSProfileFromLiteral(
		"synthesized_test",
		"direct literal",
		literal,
	)
	if err != nil {
		t.Fatalf("create direct profile: %v", err)
	}

	if profile.Name != "synthesized_test" {
		t.Fatalf("unexpected profile name %q", profile.Name)
	}
	if profile.LogQCount() != 3 {
		t.Fatalf("expected 3 Q primes, got %d", profile.LogQCount())
	}
	if profile.LogQPSum() != 145 {
		t.Fatalf("expected declared logQP 145, got %d", profile.LogQPSum())
	}

	literal.LogQ[0] = 60
	if profile.LogQPSum() != 145 {
		t.Fatalf(
			"profile changed after source mutation: logQP=%d",
			profile.LogQPSum(),
		)
	}
}

func TestNewCKKSProfileFromLiteralRejectsInvalidLiteral(t *testing.T) {
	_, err := NewCKKSProfileFromLiteral(
		"invalid",
		"",
		ckks.ParametersLiteral{
			LogN:            13,
			LogDefaultScale: 30,
		},
	)
	if err == nil {
		t.Fatal("expected invalid direct literal to fail")
	}
}
