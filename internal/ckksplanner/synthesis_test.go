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
	if candidate.Parameters.LogN != 14 {
		t.Fatalf(
			"expected smallest V2-admitted LogN 14, got %d",
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
		SecurityAdmissionPass {
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

func TestSynthesizeMaximizesPrecisionWithinMinimumLogNTier(t *testing.T) {
	contract := validContractFixture()
	policy := DefaultSynthesisPolicy()
	policy.MinScaleBits = 18
	policy.MinPrimeBits = 18
	policy.PrecisionSlackMode =
		PrecisionSlackMaximizeWithinMinLogN

	plan, err := Synthesize(contract, policy)
	if err != nil {
		t.Fatalf("synthesize with same-tier precision: %v", err)
	}

	candidate := plan.InitialCandidates[0]
	if candidate.Parameters.LogN != 13 ||
		candidate.Parameters.LogDefaultScale != 29 {
		t.Fatalf(
			"expected V2-tier MLP candidate N13/scale29, got N%d/scale%d",
			candidate.Parameters.LogN,
			candidate.Parameters.LogDefaultScale,
		)
	}
	if candidate.AnalysisScaleBits != 18 ||
		candidate.BackendScaleLiftBits != 2 ||
		candidate.SameTierPrecisionGainBits != 9 {
		t.Fatalf(
			"unexpected same-tier trace: %+v",
			candidate,
		)
	}
}

func TestSynthesizeLinearSameTierCeilingIsScale26(t *testing.T) {
	contract := validContractFixture()
	contract.ModelType = "linear_poly3"
	contract.Graph.MultiplicativeDepth = 2
	contract.Graph.RescaleOps = 2
	contract.Deployment.RescaleLevelsConsumed = 6
	contract.Deployment.TerminalScaleExponent = 1
	contract.Deployment.RequiredQPrimes = 7

	policy := DefaultSynthesisPolicy()
	policy.MinScaleBits = 18
	policy.MinPrimeBits = 18
	policy.PrecisionSlackMode =
		PrecisionSlackMaximizeWithinMinLogN

	plan, err := Synthesize(contract, policy)
	if err != nil {
		t.Fatalf("synthesize linear same-tier precision: %v", err)
	}

	candidate := plan.InitialCandidates[0]
	if candidate.Parameters.LogN != 13 ||
		candidate.Parameters.LogDefaultScale != 25 {
		t.Fatalf(
			"expected V2-tier linear candidate N13/scale25, got N%d/scale%d",
			candidate.Parameters.LogN,
			candidate.Parameters.LogDefaultScale,
		)
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

func TestDefaultPrimarySynthesisPolicyMatchesEvaluatedProtocol(
	t *testing.T,
) {
	policy := DefaultPrimarySynthesisPolicy()
	if policy.MinScaleBits != 18 ||
		policy.MinPrimeBits != 18 ||
		policy.SpecialPrimeBits != 30 {
		t.Fatalf("unexpected primary policy: %+v", policy)
	}
}

func TestDefaultPrimaryContractPolicyMatchesEvaluatedProtocol(
	t *testing.T,
) {
	options := DefaultPrimaryTabularContractOptions()
	if options.ValidationKeyRepeats != 3 ||
		options.MarginFloor != 0.001 ||
		options.SafetyFactor != 0.5 {
		t.Fatalf("unexpected primary contract policy: %+v", options)
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
