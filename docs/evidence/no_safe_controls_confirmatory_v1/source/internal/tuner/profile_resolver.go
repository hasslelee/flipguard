package tuner

import (
	"fmt"
	"math"
	"sort"
	"strings"
)

// AvailableProfile describes an executable CKKS parameter profile that can be
// matched against an analysis-derived planner candidate.
//
// The planner emits idealized candidates such as:
//
//	chain=5, scale=30, logN=14
//
// but the CKKS backend usually exposes a finite profile catalog such as:
//
//	default, scale40, short_chain_6_scale40, short_chain_5, ...
//
// The resolver bridges those two layers.
type AvailableProfile struct {
	Name        string
	Description string

	LogN        int
	Slots       int
	ChainLength int
	ScaleBits   int
	Family      string
}

// ProfileResolverPolicy controls how planned candidates are matched to
// available CKKS profiles.
type ProfileResolverPolicy struct {
	ChainWeight float64
	ScaleWeight float64
	LogNWeight  float64

	// Under-provisioning is riskier than over-provisioning. For example, mapping
	// planned chain=5 to profile chain=3 may be fast but likely unsafe.
	UnderChainPenalty float64
	UnderScalePenalty float64
	UnderLogNPenalty  float64

	// If false, profiles below the planned chain/scale/logN are excluded.
	// This is the paper-friendly default because the planner candidate is a
	// minimum feasible point.
	AllowUnderProvision bool

	// Number of closest profiles to keep per planned candidate.
	MaxMatchesPerCandidate int
}

// ResolvedProfileMatch maps one planner candidate to one available CKKS profile.
type ResolvedProfileMatch struct {
	Planned ExecutionConfiguration
	Profile AvailableProfile

	Rank     int
	Distance float64

	ChainGap int
	ScaleGap int
	LogNGap  int

	UnderProvisioned bool

	Reason string
}

// DefaultProfileResolverPolicy returns a conservative matching policy.
func DefaultProfileResolverPolicy() ProfileResolverPolicy {
	return ProfileResolverPolicy{
		ChainWeight: 10.0,
		ScaleWeight: 1.0,
		LogNWeight:  6.0,

		UnderChainPenalty: 100.0,
		UnderScalePenalty: 20.0,
		UnderLogNPenalty:  100.0,

		AllowUnderProvision: false,

		MaxMatchesPerCandidate: 3,
	}
}

// ResolveClosestProfiles maps each planned candidate to the closest available
// executable CKKS profiles.
//
// The function does not execute CKKS. It is a planning/resolution layer that
// narrows the validation set before measurement.
func ResolveClosestProfiles(
	planned []ExecutionConfiguration,
	profiles []AvailableProfile,
	policy ProfileResolverPolicy,
) ([]ResolvedProfileMatch, error) {
	policy = normalizeProfileResolverPolicy(policy)

	if len(planned) == 0 {
		return nil, fmt.Errorf("planned candidate list is empty")
	}
	if len(profiles) == 0 {
		return nil, fmt.Errorf("available profile list is empty")
	}

	matches := make([]ResolvedProfileMatch, 0, len(planned)*policy.MaxMatchesPerCandidate)

	for _, cfg := range planned {
		perCandidate := make([]ResolvedProfileMatch, 0, len(profiles))

		for _, profile := range profiles {
			match, ok := scoreProfileMatch(cfg, profile, policy)
			if !ok {
				continue
			}
			perCandidate = append(perCandidate, match)
		}

		if len(perCandidate) == 0 {
			return nil, fmt.Errorf("no available profile can satisfy planned candidate %s", cfg.Candidate.ID)
		}

		sort.SliceStable(perCandidate, func(i int, j int) bool {
			if perCandidate[i].Distance != perCandidate[j].Distance {
				return perCandidate[i].Distance < perCandidate[j].Distance
			}

			if perCandidate[i].Profile.ChainLength != perCandidate[j].Profile.ChainLength {
				return perCandidate[i].Profile.ChainLength < perCandidate[j].Profile.ChainLength
			}

			if perCandidate[i].Profile.ScaleBits != perCandidate[j].Profile.ScaleBits {
				return perCandidate[i].Profile.ScaleBits < perCandidate[j].Profile.ScaleBits
			}

			return perCandidate[i].Profile.Name < perCandidate[j].Profile.Name
		})

		limit := policy.MaxMatchesPerCandidate
		if limit > len(perCandidate) {
			limit = len(perCandidate)
		}

		for i := 0; i < limit; i++ {
			match := perCandidate[i]
			match.Rank = i + 1
			matches = append(matches, match)
		}
	}

	return matches, nil
}

func normalizeProfileResolverPolicy(policy ProfileResolverPolicy) ProfileResolverPolicy {
	defaults := DefaultProfileResolverPolicy()

	if policy.ChainWeight <= 0 {
		policy.ChainWeight = defaults.ChainWeight
	}
	if policy.ScaleWeight <= 0 {
		policy.ScaleWeight = defaults.ScaleWeight
	}
	if policy.LogNWeight <= 0 {
		policy.LogNWeight = defaults.LogNWeight
	}

	if policy.UnderChainPenalty <= 0 {
		policy.UnderChainPenalty = defaults.UnderChainPenalty
	}
	if policy.UnderScalePenalty <= 0 {
		policy.UnderScalePenalty = defaults.UnderScalePenalty
	}
	if policy.UnderLogNPenalty <= 0 {
		policy.UnderLogNPenalty = defaults.UnderLogNPenalty
	}

	if policy.MaxMatchesPerCandidate <= 0 {
		policy.MaxMatchesPerCandidate = defaults.MaxMatchesPerCandidate
	}

	return policy
}

func scoreProfileMatch(
	cfg ExecutionConfiguration,
	profile AvailableProfile,
	policy ProfileResolverPolicy,
) (ResolvedProfileMatch, bool) {
	planned := cfg.Candidate

	if planned.LogN <= 0 || planned.ChainLength <= 0 || planned.ScaleBits <= 0 {
		return ResolvedProfileMatch{}, false
	}
	if profile.LogN <= 0 || profile.ChainLength <= 0 || profile.ScaleBits <= 0 {
		return ResolvedProfileMatch{}, false
	}

	chainGap := profile.ChainLength - planned.ChainLength
	scaleGap := profile.ScaleBits - planned.ScaleBits
	logNGap := profile.LogN - planned.LogN

	underProvisioned := chainGap < 0 || scaleGap < 0 || logNGap < 0

	if underProvisioned && !policy.AllowUnderProvision {
		return ResolvedProfileMatch{}, false
	}

	distance := 0.0
	distance += policy.ChainWeight * math.Abs(float64(chainGap))
	distance += policy.ScaleWeight * math.Abs(float64(scaleGap))
	distance += policy.LogNWeight * math.Abs(float64(logNGap))

	if chainGap < 0 {
		distance += policy.UnderChainPenalty * math.Abs(float64(chainGap))
	}
	if scaleGap < 0 {
		distance += policy.UnderScalePenalty * math.Abs(float64(scaleGap))
	}
	if logNGap < 0 {
		distance += policy.UnderLogNPenalty * math.Abs(float64(logNGap))
	}

	reason := fmt.Sprintf(
		"planned(chain=%d,scale=%d,logN=%d,path=%s) profile(chain=%d,scale=%d,logN=%d) gaps(chain=%+d,scale=%+d,logN=%+d) distance=%.3f",
		planned.ChainLength,
		planned.ScaleBits,
		planned.LogN,
		cfg.Path,
		profile.ChainLength,
		profile.ScaleBits,
		profile.LogN,
		chainGap,
		scaleGap,
		logNGap,
		distance,
	)

	return ResolvedProfileMatch{
		Planned: cfg,
		Profile: profile,

		Distance: distance,

		ChainGap: chainGap,
		ScaleGap: scaleGap,
		LogNGap:  logNGap,

		UnderProvisioned: underProvisioned,

		Reason: reason,
	}, true
}

// DeduplicateResolvedProfiles returns one representative match per profile name.
// This is useful before executing CKKS, because several planned candidates may
// resolve to the same executable profile.
func DeduplicateResolvedProfiles(matches []ResolvedProfileMatch) []ResolvedProfileMatch {
	bestByProfile := make(map[string]ResolvedProfileMatch)

	for _, match := range matches {
		name := strings.TrimSpace(match.Profile.Name)
		if name == "" {
			continue
		}

		existing, ok := bestByProfile[name]
		if !ok || match.Distance < existing.Distance {
			bestByProfile[name] = match
		}
	}

	deduped := make([]ResolvedProfileMatch, 0, len(bestByProfile))
	for _, match := range bestByProfile {
		deduped = append(deduped, match)
	}

	sort.SliceStable(deduped, func(i int, j int) bool {
		if deduped[i].Distance != deduped[j].Distance {
			return deduped[i].Distance < deduped[j].Distance
		}

		return deduped[i].Profile.Name < deduped[j].Profile.Name
	})

	return deduped
}
