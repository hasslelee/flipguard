package ckksplanner

import (
	"fmt"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
)

func TestSynthesizeProducesDirectExecutableProfile(t *testing.T) {
	contract := validContractFixture()

	plan, err := Synthesize(contract, DefaultSynthesisPolicy())
	if err != nil {
		t.Fatalf("synthesize: %v", err)
	}

	if len(plan.InitialCandidates) != 1 {
		t.Fatalf(
			"expected one initial candidate, got %d",
			len(plan.InitialCandidates),
		)
	}

	candidate := plan.InitialCandidates[0]
	if candidate.Parameters.LogN != 13 {
		t.Fatalf(
			"expected smallest admitted LogN 13, got %d",
			candidate.Parameters.LogN,
		)
	}
	if len(candidate.Parameters.LogQ) != 6 {
		t.Fatalf(
			"expected trace-derived 6-prime Q chain, got %d",
			len(candidate.Parameters.LogQ),
		)
	}
	if candidate.Security.AdmissionStatus !=
		"ADMITTED_BY_DECLARED_ENVELOPE" {
		t.Fatalf(
			"unexpected security status %q",
			candidate.Security.AdmissionStatus,
		)
	}

	profile, err := candidate.Profile()
	if err != nil {
		t.Fatalf("materialize direct profile: %v", err)
	}
	context, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		t.Fatalf("create context from direct profile: %v", err)
	}
	if context.ProfileName() != candidate.ID {
		t.Fatalf(
			"unexpected direct profile identity %q",
			context.ProfileName(),
		)
	}
	if strings.Contains(
		ckksbackend.DefaultCKKSProfileNames(),
		candidate.ID,
	) {
		t.Fatal("synthesized candidate unexpectedly came from built-in catalog")
	}
}

func TestSynthesizeRaisesLogNWhenModulusRequiresIt(t *testing.T) {
	contract := validContractFixture()
	contract.Graph.MultiplicativeDepth = 3
	contract.Graph.RescaleOps = 3
	contract.Deployment.RescaleLevelsConsumed = 9
	contract.Deployment.TerminalScaleExponent = 1
	contract.Deployment.RequiredQPrimes = 10

	policy := DefaultSynthesisPolicy()

	plan, err := Synthesize(contract, policy)
	if err != nil {
		t.Fatalf("synthesize: %v", err)
	}

	candidate := plan.InitialCandidates[0]
	if candidate.Parameters.LogN != 14 {
		t.Fatalf(
			"expected security admission to raise LogN to 14, got %d (logQP=%d)",
			candidate.Parameters.LogN,
			candidate.Parameters.DeclaredLogQPBits(),
		)
	}
	if candidate.Security.HeadroomBits < 0 {
		t.Fatalf(
			"candidate exceeded security envelope: %+v",
			candidate.Security,
		)
	}
}

func TestSynthesizeRecordsLowerExperimentalFloor(t *testing.T) {
	contract := validContractFixture()
	policy := DefaultSynthesisPolicy()
	policy.MinScaleBits = 18
	policy.MinPrimeBits = 18

	plan, err := Synthesize(contract, policy)
	if err != nil {
		t.Fatalf("synthesize with lower floor: %v", err)
	}

	candidate := plan.InitialCandidates[0]
	if plan.Policy.MinScaleBits != 18 ||
		plan.Policy.MinPrimeBits != 18 {
		t.Fatalf(
			"experimental policy was not recorded: %+v",
			plan.Policy,
		)
	}
	if candidate.Parameters.LogDefaultScale != 20 {
		t.Fatalf(
			"expected backend feasibility to lift scale to 20 bits, got %d",
			candidate.Parameters.LogDefaultScale,
		)
	}
	if candidate.AnalysisScaleBits != 18 ||
		candidate.BackendScaleLiftBits != 2 ||
		candidate.BackendValidationAttempts != 3 {
		t.Fatalf(
			"unexpected backend feasibility trace: %+v",
			candidate,
		)
	}
	if _, err := candidate.Profile(); err != nil {
		t.Fatalf("lower-floor candidate is not backend-valid: %v", err)
	}
}

func TestRetryablePrimeGenerationErrorIsNarrow(t *testing.T) {
	if !retryablePrimeGenerationError(
		fmt.Errorf("cannot GenModuli: failed to generate 5 primes"),
	) {
		t.Fatal("expected prime-generation exhaustion to be retryable")
	}
	if retryablePrimeGenerationError(
		fmt.Errorf("cannot NewParameters: invalid modulus"),
	) {
		t.Fatal("unexpected retry for unrelated backend error")
	}
}

func TestSynthesizeRejectsUnsupportedNonRescalePath(t *testing.T) {
	contract := validContractFixture()
	contract.Deployment.AllowedPaths = []tuner.ExecutionPath{
		tuner.PathNonRescale,
	}

	_, err := Synthesize(contract, DefaultSynthesisPolicy())
	if err == nil || !strings.Contains(err.Error(), "not implemented") {
		t.Fatalf("expected declared scope rejection, got %v", err)
	}
}

func TestSynthesizeRejectsConfigurationOutsideSecurityEnvelope(t *testing.T) {
	contract := validContractFixture()
	contract.Graph.MultiplicativeDepth = 20
	contract.Graph.RescaleOps = 20
	contract.Deployment.RescaleLevelsConsumed = 60
	contract.Deployment.TerminalScaleExponent = 1
	contract.Deployment.RequiredQPrimes = 61

	policy := DefaultSynthesisPolicy()
	policy.MaxLogN = 13

	_, err := Synthesize(contract, policy)
	if err == nil || !strings.Contains(err.Error(), "no admitted ring dimension") {
		t.Fatalf("expected security-envelope rejection, got %v", err)
	}
}
