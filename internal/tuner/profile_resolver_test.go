package tuner

import "testing"

func TestResolveClosestProfilesFindsNearestNonUnderProvisionedProfile(t *testing.T) {
	planned := []ExecutionConfiguration{
		{
			Candidate: ParameterCandidate{
				ID:          "planner_min_feasible_chain5_scale30_N14_non_rescale",
				LogN:        14,
				Slots:       8192,
				ChainLength: 5,
				ScaleBits:   30,
				Family:      "planner_min_feasible",
			},
			Path: PathNonRescale,
		},
	}

	profiles := []AvailableProfile{
		{
			Name:        "short_chain_3",
			LogN:        14,
			Slots:       8192,
			ChainLength: 3,
			ScaleBits:   35,
			Family:      "short_chain",
		},
		{
			Name:        "short_chain_5",
			LogN:        14,
			Slots:       8192,
			ChainLength: 5,
			ScaleBits:   35,
			Family:      "short_chain",
		},
		{
			Name:        "short_chain_6_scale40",
			LogN:        14,
			Slots:       8192,
			ChainLength: 6,
			ScaleBits:   40,
			Family:      "short_chain",
		},
	}

	matches, err := ResolveClosestProfiles(planned, profiles, DefaultProfileResolverPolicy())
	if err != nil {
		t.Fatalf("ResolveClosestProfiles failed: %v", err)
	}

	if len(matches) == 0 {
		t.Fatal("expected at least one match")
	}

	if got := matches[0].Profile.Name; got != "short_chain_5" {
		t.Fatalf("expected short_chain_5 as nearest profile, got %s", got)
	}

	if matches[0].UnderProvisioned {
		t.Fatal("default policy should not under-provision")
	}
}

func TestResolveClosestProfilesRejectsUnderProvisioningByDefault(t *testing.T) {
	planned := []ExecutionConfiguration{
		{
			Candidate: ParameterCandidate{
				ID:          "planner_chain5_scale40",
				LogN:        14,
				ChainLength: 5,
				ScaleBits:   40,
				Family:      "planner_min_feasible",
			},
			Path: PathNonRescale,
		},
	}

	profiles := []AvailableProfile{
		{
			Name:        "too_short",
			LogN:        14,
			ChainLength: 3,
			ScaleBits:   45,
		},
		{
			Name:        "too_low_scale",
			LogN:        14,
			ChainLength: 6,
			ScaleBits:   35,
		},
	}

	_, err := ResolveClosestProfiles(planned, profiles, DefaultProfileResolverPolicy())
	if err == nil {
		t.Fatal("expected no satisfying profile error")
	}
}

func TestResolveClosestProfilesCanAllowUnderProvisioning(t *testing.T) {
	planned := []ExecutionConfiguration{
		{
			Candidate: ParameterCandidate{
				ID:          "planner_chain5_scale40",
				LogN:        14,
				ChainLength: 5,
				ScaleBits:   40,
				Family:      "planner_min_feasible",
			},
			Path: PathNonRescale,
		},
	}

	profiles := []AvailableProfile{
		{
			Name:        "under_but_available",
			LogN:        14,
			ChainLength: 4,
			ScaleBits:   38,
		},
	}

	policy := DefaultProfileResolverPolicy()
	policy.AllowUnderProvision = true

	matches, err := ResolveClosestProfiles(planned, profiles, policy)
	if err != nil {
		t.Fatalf("ResolveClosestProfiles failed: %v", err)
	}

	if len(matches) != 1 {
		t.Fatalf("expected one match, got %d", len(matches))
	}

	if !matches[0].UnderProvisioned {
		t.Fatal("expected under-provisioned match")
	}
}

func TestDeduplicateResolvedProfilesKeepsBestDistance(t *testing.T) {
	matches := []ResolvedProfileMatch{
		{
			Profile: AvailableProfile{
				Name: "profile_a",
			},
			Distance: 10,
		},
		{
			Profile: AvailableProfile{
				Name: "profile_a",
			},
			Distance: 3,
		},
		{
			Profile: AvailableProfile{
				Name: "profile_b",
			},
			Distance: 5,
		},
	}

	deduped := DeduplicateResolvedProfiles(matches)

	if len(deduped) != 2 {
		t.Fatalf("expected 2 deduped profiles, got %d", len(deduped))
	}

	if deduped[0].Profile.Name != "profile_a" {
		t.Fatalf("expected best profile_a first, got %s", deduped[0].Profile.Name)
	}

	if deduped[0].Distance != 3 {
		t.Fatalf("expected profile_a distance 3, got %.3f", deduped[0].Distance)
	}
}
