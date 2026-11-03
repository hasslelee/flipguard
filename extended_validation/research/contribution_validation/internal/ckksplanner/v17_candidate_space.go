package ckksplanner

import (
	"errors"
	"fmt"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const V17DepthCompleteCandidateGeneratorID = "flipguard_v17_depth_complete_finite_set_v1"

const V17LegacyFiniteSetID = "flipguard_v17_legacy_security_v2_7_profiles_2_paths_v1"

type V17LegacyFiniteEntry struct {
	ProfileName                string               `json:"profile_name"`
	Candidate                  SynthesizedCandidate `json:"candidate"`
	RequiredQPrimes            int                  `json:"required_q_primes"`
	AvailableQPrimes           int                  `json:"available_q_primes"`
	StaticStatus               string               `json:"static_status"`
	EncryptedExecutionRequired bool                 `json:"encrypted_execution_required"`
}

func BuildV17FixedDefaultBaseline(contract WorkloadContract) (V17LegacyFiniteEntry, error) {
	profile, err := ckksbackend.FindCKKSProfile("default")
	if err != nil {
		return V17LegacyFiniteEntry{}, err
	}
	logQ := literalPrimeBits(profile.Literal.LogQ, profile.Literal.Q)
	logP := literalPrimeBits(profile.Literal.LogP, profile.Literal.P)
	spec := CKKSParameterLiteralSpec{
		LogN: profile.Literal.LogN, LogQ: logQ, LogP: logP,
		Q:               append([]uint64(nil), profile.Literal.Q...),
		P:               append([]uint64(nil), profile.Literal.P...),
		LogDefaultScale: profile.Literal.LogDefaultScale,
	}
	security, err := AssessSecurity(spec, contract.Deployment.SecurityBits, DefaultSecurityEnvelope())
	if err != nil {
		return V17LegacyFiniteEntry{}, err
	}
	candidate := SynthesizedCandidate{
		ID: "fixed_default__rescale", Path: tuner.PathRescale,
		Parameters: spec, Security: security,
		RequiredRescaleLevels: contract.Deployment.RescaleLevelsConsumed,
		GenerationKind:        "fixed_default_diagnostic",
		Reason:                "built-in fixed default; execution requires Security-V2 admission",
	}
	status := "PLAN_OK"
	execute := true
	if security.FinalAdmission != SecurityAdmissionPass {
		status, execute = "SECURITY_INADMISSIBLE", false
	} else if len(logQ) < contract.Deployment.RequiredQPrimes {
		status, execute = "PLAN_UNSUPPORTED_LEVELS", false
	}
	return V17LegacyFiniteEntry{
		ProfileName: "default", Candidate: candidate,
		RequiredQPrimes:  contract.Deployment.RequiredQPrimes,
		AvailableQPrimes: len(logQ), StaticStatus: status,
		EncryptedExecutionRequired: execute,
	}, nil
}

// BuildV17LegacyFiniteSet retains the historical seven Security-V2-admitted
// built-in profiles over the rescale and non-rescale paths. It is diagnostic
// B2 evidence and never replaces the graph-derived B3 finite reference.
func BuildV17LegacyFiniteSet(contract WorkloadContract) ([]V17LegacyFiniteEntry, error) {
	base, err := BuildJournalMulticlassCatalog(contract)
	if err != nil {
		return nil, err
	}
	entries := make([]V17LegacyFiniteEntry, 0, 2*len(base))
	for _, item := range base {
		for _, path := range []tuner.ExecutionPath{tuner.PathRescale, tuner.PathNonRescale} {
			candidate := item.Candidate
			candidate.ID = "legacy_" + item.ProfileName + "__" + string(path)
			candidate.Path = path
			candidate.GenerationKind = "security_v2_legacy_finite_reference"
			candidate.Reason = "exact built-in Security-V2-admitted profile; diagnostic legacy finite set"
			status, execute := item.StaticStatus, item.EncryptedExecutionRequired
			if path == tuner.PathNonRescale {
				status = "PLAN_OK_NON_RESCALE_DIAGNOSTIC"
				execute = true
			}
			entries = append(entries, V17LegacyFiniteEntry{
				ProfileName: item.ProfileName, Candidate: candidate,
				RequiredQPrimes:  item.RequiredQPrimes,
				AvailableQPrimes: item.AvailableQPrimes,
				StaticStatus:     status, EncryptedExecutionRequired: execute,
			})
		}
	}
	return entries, nil
}

// BuildV17DepthCompleteFiniteSet creates the predeclared B3 comparison set
// from graph facts alone. It is evaluation-only: it does not change the
// bounded direct optimizer, its four-trial budget, or its first-SAFE rule.
//
// The set contains scale offsets 0,+4,+8,+12 and level guards 0,+1 whenever
// those literals are backend-valid and Security-V2-admitted. Candidate
// identity is deduplicated because backend prime feasibility can lift two
// requested scale floors to the same literal.
func BuildV17DepthCompleteFiniteSet(
	contract WorkloadContract,
) (SynthesisPlan, []SynthesizedCandidate, error) {
	plan, err := Synthesize(contract, DefaultPrimarySynthesisPolicy())
	if err != nil {
		return SynthesisPlan{}, nil, err
	}
	if len(plan.InitialCandidates) != 1 {
		return SynthesisPlan{}, nil, fmt.Errorf(
			"V17 finite-set generator expected one initial candidate, got %d",
			len(plan.InitialCandidates),
		)
	}

	base := plan.InitialCandidates[0]
	scales := []SynthesizedCandidate{base}
	current := base
	for ordinal := 1; ordinal <= 3; ordinal++ {
		current, err = RepairCandidate(
			plan,
			current,
			RepairNumericalReject,
			ordinal,
		)
		if err != nil {
			if errors.Is(err, ErrRepairExhausted) {
				break
			}
			return SynthesisPlan{}, nil, fmt.Errorf(
				"V17 scale tier %d: %w",
				ordinal,
				err,
			)
		}
		scales = append(scales, current)
	}

	seen := make(map[string]struct{}, 8)
	candidates := make([]SynthesizedCandidate, 0, 8)
	appendCandidate := func(candidate SynthesizedCandidate) {
		if _, ok := seen[candidate.ID]; ok {
			return
		}
		seen[candidate.ID] = struct{}{}
		candidates = append(candidates, candidate)
	}
	for ordinal, candidate := range scales {
		appendCandidate(candidate)
		levelCandidate, levelErr := RepairCandidate(
			plan,
			candidate,
			RepairLevelFailure,
			ordinal+1,
		)
		if levelErr == nil {
			appendCandidate(levelCandidate)
		} else if !errors.Is(levelErr, ErrRepairExhausted) {
			return SynthesisPlan{}, nil, fmt.Errorf(
				"V17 level tier %d: %w",
				ordinal,
				levelErr,
			)
		}
	}
	if len(candidates) == 0 {
		return SynthesisPlan{}, nil, fmt.Errorf("V17 finite candidate set is empty")
	}
	return plan, candidates, nil
}
