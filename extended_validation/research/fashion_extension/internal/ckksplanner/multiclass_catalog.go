package ckksplanner

import (
	"fmt"
	"math/bits"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/tuner"
)

var JournalSecurityV2AdmittedCatalogProfiles = []string{
	"deep_chain_8_scale45",
	"deep_chain_9_scale45",
	"short_chain_3",
	"short_chain_5",
	"short_chain_6_scale38",
	"short_chain_6_scale40",
	"short_chain_6_scale42",
}

type MulticlassCatalogStaticEntry struct {
	ProfileName                string               `json:"profile_name"`
	Candidate                  SynthesizedCandidate `json:"candidate"`
	RequiredQPrimes            int                  `json:"required_q_primes"`
	AvailableQPrimes           int                  `json:"available_q_primes"`
	StaticStatus               string               `json:"static_status"`
	EncryptedExecutionRequired bool                 `json:"encrypted_execution_required"`
}

func BuildJournalMulticlassCatalog(contract WorkloadContract) ([]MulticlassCatalogStaticEntry, error) {
	if err := contract.Validate(); err != nil {
		return nil, err
	}
	entries := make([]MulticlassCatalogStaticEntry, 0, len(JournalSecurityV2AdmittedCatalogProfiles))
	for _, name := range JournalSecurityV2AdmittedCatalogProfiles {
		profile, err := ckksbackend.FindCKKSProfile(name)
		if err != nil {
			return nil, err
		}
		logQ := literalPrimeBits(profile.Literal.LogQ, profile.Literal.Q)
		logP := literalPrimeBits(profile.Literal.LogP, profile.Literal.P)
		spec := CKKSParameterLiteralSpec{
			LogN:            profile.Literal.LogN,
			LogQ:            logQ,
			LogP:            logP,
			Q:               append([]uint64(nil), profile.Literal.Q...),
			P:               append([]uint64(nil), profile.Literal.P...),
			LogDefaultScale: profile.Literal.LogDefaultScale,
		}
		security, err := AssessSecurity(spec, contract.Deployment.SecurityBits, DefaultSecurityEnvelope())
		if err != nil {
			return nil, fmt.Errorf("catalog profile %s security: %w", name, err)
		}
		if security.FinalAdmission != SecurityAdmissionPass {
			return nil, fmt.Errorf("catalog profile %s is not Security-V2 admitted", name)
		}
		candidate := SynthesizedCandidate{
			ID:                    "catalog_" + name + "__rescale",
			Path:                  tuner.PathRescale,
			Parameters:            spec,
			Security:              security,
			RequiredRescaleLevels: contract.Deployment.RescaleLevelsConsumed,
			GenerationKind:        "security_v2_bounded_catalog",
			Reason:                "exact built-in profile; Security-V2 admitted; evaluation-only bounded catalog",
		}
		status := "PLAN_OK"
		execute := true
		if len(logQ) < contract.Deployment.RequiredQPrimes {
			status = "PLAN_UNSUPPORTED_LEVELS"
			execute = false
		}
		entries = append(entries, MulticlassCatalogStaticEntry{
			ProfileName:                name,
			Candidate:                  candidate,
			RequiredQPrimes:            contract.Deployment.RequiredQPrimes,
			AvailableQPrimes:           len(logQ),
			StaticStatus:               status,
			EncryptedExecutionRequired: execute,
		})
	}
	return entries, nil
}

func literalPrimeBits(declared []int, concrete []uint64) []int {
	if len(concrete) > 0 {
		result := make([]int, len(concrete))
		for index, prime := range concrete {
			result[index] = bits.Len64(prime)
		}
		return result
	}
	return append([]int(nil), declared...)
}
