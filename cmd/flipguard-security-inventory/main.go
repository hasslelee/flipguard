package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math/bits"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

type parameterRecord struct {
	CandidateSource string `json:"candidate_source"`
	CandidateID     string `json:"candidate_id"`
	Profile         string `json:"profile,omitempty"`
	Path            string `json:"path,omitempty"`
	DatasetID       string `json:"dataset_id,omitempty"`
	ModelID         string `json:"model_id,omitempty"`
	SplitSeed       int    `json:"split_seed,omitempty"`

	Parameters  ckksplanner.CKKSParameterLiteralSpec `json:"parameters"`
	ActualQ     []uint64                             `json:"actual_q_primes"`
	ActualP     []uint64                             `json:"actual_p_primes"`
	ActualLogQ  float64                              `json:"actual_log_q"`
	ActualLogP  float64                              `json:"actual_log_p"`
	ActualLogQP float64                              `json:"actual_log_qp"`
	ActualXs    string                               `json:"actual_xs"`
	ActualXe    string                               `json:"actual_xe"`

	OldSecurity ckksplanner.SecurityAssessment `json:"old_security"`
	V2Security  ckksplanner.SecurityAssessment `json:"v2_security"`
}

type inventory struct {
	SchemaVersion        int                                       `json:"schema_version"`
	SecurityPolicy       ckksplanner.SecurityEnvelope              `json:"security_policy"`
	SecurityPolicyDigest string                                    `json:"security_policy_digest"`
	DirectPolicy         ckksplanner.DirectSynthesisPolicyContract `json:"direct_policy"`
	DirectPolicyDigest   string                                    `json:"direct_policy_digest"`
	DirectSelected       []parameterRecord                         `json:"direct_selected"`
	CatalogProfiles      []parameterRecord                         `json:"catalog_profiles"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	flags := flag.NewFlagSet(
		"flipguard-security-inventory",
		flag.ContinueOnError,
	)
	directRoot := flags.String(
		"direct-results",
		"results/thesis_grade_protocol/direct_tabular_autotune_v1/full_floor18_keys3/results",
		"directory containing direct result JSON files",
	)
	output := flags.String("out", "", "output JSON path")
	if err := flags.Parse(os.Args[1:]); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments: %v", flags.Args())
	}

	securityPolicy := ckksplanner.DefaultSecurityEnvelope()
	securityDigest, err := ckksplanner.SecurityPolicyDigest(securityPolicy)
	if err != nil {
		return err
	}
	directPolicy := ckksplanner.DefaultDirectSynthesisPolicyContract()
	directDigest, err := ckksplanner.DirectSynthesisPolicyDigest(directPolicy)
	if err != nil {
		return err
	}

	direct, err := loadDirectSelected(*directRoot, securityPolicy)
	if err != nil {
		return err
	}
	catalog, err := loadCatalog(securityPolicy)
	if err != nil {
		return err
	}

	payload := inventory{
		SchemaVersion:        2,
		SecurityPolicy:       securityPolicy,
		SecurityPolicyDigest: securityDigest,
		DirectPolicy:         directPolicy,
		DirectPolicyDigest:   directDigest,
		DirectSelected:       direct,
		CatalogProfiles:      catalog,
	}
	encoded, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal inventory: %w", err)
	}
	encoded = append(encoded, '\n')
	if strings.TrimSpace(*output) == "" {
		_, err = os.Stdout.Write(encoded)
		return err
	}
	if err := os.WriteFile(*output, encoded, 0o644); err != nil {
		return fmt.Errorf("write inventory: %w", err)
	}
	return nil
}

func loadDirectSelected(
	root string,
	policy ckksplanner.SecurityEnvelope,
) ([]parameterRecord, error) {
	paths, err := filepath.Glob(filepath.Join(root, "*.json"))
	if err != nil {
		return nil, err
	}
	sort.Strings(paths)
	if len(paths) == 0 {
		return nil, fmt.Errorf("no direct result JSON files under %s", root)
	}
	records := make([]parameterRecord, 0, len(paths))
	for _, path := range paths {
		encoded, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		var result ckksplanner.AdaptiveAutotuneResult
		if err := json.Unmarshal(encoded, &result); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
		if result.Outcome != ckksplanner.AdaptiveOutcomeSelected ||
			result.Selected == nil {
			return nil, fmt.Errorf("%s: expected selected direct candidate", path)
		}
		selected := *result.Selected
		record, err := materializeRecord(
			"direct",
			selected.ID,
			"",
			string(selected.Path),
			selected.Parameters,
			selected.Security,
			policy,
		)
		if err != nil {
			return nil, fmt.Errorf("%s: %w", path, err)
		}
		record.DatasetID = result.Plan.Contract.DatasetID
		record.ModelID = result.Plan.Contract.ModelID
		if _, err := fmt.Sscanf(
			result.Plan.Contract.SplitID,
			"split_seed_%d",
			&record.SplitSeed,
		); err != nil {
			return nil, fmt.Errorf(
				"%s: parse split id %q: %w",
				path,
				result.Plan.Contract.SplitID,
				err,
			)
		}
		records = append(records, record)
	}
	return records, nil
}

func loadCatalog(
	policy ckksplanner.SecurityEnvelope,
) ([]parameterRecord, error) {
	profiles := ckksbackend.AllCKKSProfiles()
	records := make([]parameterRecord, 0, len(profiles))
	for _, profile := range profiles {
		context, err := ckksbackend.NewContextFromProfile(profile)
		if err != nil {
			return nil, err
		}
		spec := ckksplanner.CKKSParameterLiteralSpec{
			LogN:            context.Params.LogN(),
			LogQ:            literalBitSizes(profile.Literal.Q, profile.Literal.LogQ),
			LogP:            literalBitSizes(profile.Literal.P, profile.Literal.LogP),
			LogDefaultScale: context.Params.LogDefaultScale(),
		}
		old, err := ckksplanner.AssessSecurity(
			spec,
			128,
			ckksplanner.LegacySecurityEnvelope(),
		)
		if err != nil {
			return nil, err
		}
		record, err := materializeRecord(
			"catalog",
			profile.Name,
			profile.Name,
			"",
			spec,
			old,
			policy,
		)
		if err != nil {
			return nil, err
		}
		records = append(records, record)
	}
	return records, nil
}

func literalBitSizes(
	primes []uint64,
	declared []int,
) []int {
	if len(primes) > 0 {
		out := make([]int, len(primes))
		for index, prime := range primes {
			out[index] = bits.Len64(prime)
		}
		return out
	}
	return append([]int(nil), declared...)
}

func materializeRecord(
	source string,
	candidateID string,
	profileName string,
	path string,
	spec ckksplanner.CKKSParameterLiteralSpec,
	old ckksplanner.SecurityAssessment,
	policy ckksplanner.SecurityEnvelope,
) (parameterRecord, error) {
	profile, err := ckksbackend.NewCKKSProfileFromLiteral(
		candidateID,
		"static security re-attestation",
		specLiteral(spec),
	)
	if err != nil {
		return parameterRecord{}, err
	}
	context, err := ckksbackend.NewContextFromProfile(profile)
	if err != nil {
		return parameterRecord{}, err
	}
	v2, err := ckksplanner.AssessSecurity(spec, 128, policy)
	if err != nil {
		return parameterRecord{}, err
	}
	return parameterRecord{
		CandidateSource: source,
		CandidateID:     candidateID,
		Profile:         profileName,
		Path:            path,
		Parameters:      spec,
		ActualQ:         append([]uint64(nil), context.Params.Q()...),
		ActualP:         append([]uint64(nil), context.Params.P()...),
		ActualLogQ:      context.Params.LogQ(),
		ActualLogP:      context.Params.LogP(),
		ActualLogQP:     context.Params.LogQP(),
		ActualXs:        fmt.Sprintf("%T:%v", context.Params.Xs(), context.Params.Xs()),
		ActualXe:        fmt.Sprintf("%T:%v", context.Params.Xe(), context.Params.Xe()),
		OldSecurity:     old,
		V2Security:      v2,
	}, nil
}

func specLiteral(
	spec ckksplanner.CKKSParameterLiteralSpec,
) ckks.ParametersLiteral {
	return ckks.ParametersLiteral{
		LogN:            spec.LogN,
		LogQ:            append([]int(nil), spec.LogQ...),
		LogP:            append([]int(nil), spec.LogP...),
		LogDefaultScale: spec.LogDefaultScale,
	}
}
