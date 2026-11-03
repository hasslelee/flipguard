package ckksplanner

import "testing"

func TestBuildV17DepthCompleteFiniteSetIsGraphDerivedAndBounded(t *testing.T) {
	contract := validContractFixture()
	contract.Graph.MultiplicativeDepth = 2
	contract.Graph.RescaleOps = 2
	contract.Deployment.RescaleLevelsConsumed = 4
	contract.Deployment.TerminalScaleExponent = 1
	contract.Deployment.RequiredQPrimes = 5

	plan, candidates, err := BuildV17DepthCompleteFiniteSet(contract)
	if err != nil {
		t.Fatal(err)
	}
	if plan.DirectPolicyDigest == "" || plan.SecurityPolicyDigest == "" {
		t.Fatalf("missing frozen policy binding: %+v", plan)
	}
	if len(candidates) < 4 || len(candidates) > 8 {
		t.Fatalf("unexpected finite set size %d", len(candidates))
	}
	seen := map[string]bool{}
	for _, candidate := range candidates {
		if seen[candidate.ID] {
			t.Fatalf("duplicate candidate %s", candidate.ID)
		}
		seen[candidate.ID] = true
		if candidate.Security.FinalAdmission != "PASS" {
			t.Fatalf("inadmissible candidate: %+v", candidate.Security)
		}
		if candidate.Parameters.QPrimeCount() < contract.Deployment.RequiredQPrimes {
			t.Fatalf("depth-incomplete candidate: %+v", candidate.Parameters)
		}
	}
}

func TestBuildV17LegacyFiniteSetKeepsSevenProfilesAndTwoPaths(t *testing.T) {
	contract := validContractFixture()
	entries, err := BuildV17LegacyFiniteSet(contract)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 14 {
		t.Fatalf("legacy finite entries=%d, want 14", len(entries))
	}
	identities := make(map[string]bool, len(entries))
	for _, entry := range entries {
		if entry.Candidate.Security.FinalAdmission != SecurityAdmissionPass {
			t.Fatalf("legacy candidate %s is not Security-V2 admitted", entry.Candidate.ID)
		}
		identities[entry.Candidate.ID] = true
	}
	if len(identities) != 14 {
		t.Fatalf("legacy candidate identities=%d, want 14", len(identities))
	}
}

func TestBuildV17FixedDefaultFailsClosedUnderSecurityV2(t *testing.T) {
	entry, err := BuildV17FixedDefaultBaseline(validContractFixture())
	if err != nil {
		t.Fatal(err)
	}
	if entry.StaticStatus != "SECURITY_INADMISSIBLE" || entry.EncryptedExecutionRequired {
		t.Fatalf("fixed default did not fail closed: %+v", entry)
	}
	if entry.Candidate.Security.FinalAdmission != SecurityAdmissionFail {
		t.Fatalf("fixed default unexpectedly admitted: %+v", entry.Candidate.Security)
	}
}
