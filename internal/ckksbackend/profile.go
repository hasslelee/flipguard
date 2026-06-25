package ckksbackend

import (
	"fmt"
	"math/bits"
	"strings"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

// CKKSProfile describes one CKKS parameter profile used by FlipGuard experiments.
type CKKSProfile struct {
	Name        string
	Description string
	Literal     ckks.ParametersLiteral
}

// DefaultCKKSProfileNames returns the default profile ladder.
func DefaultCKKSProfileNames() string {
	return "default,scale42,scale40,scale38,deep_chain_8_scale45,deep_chain_9_scale45,short_chain_6_scale42,short_chain_6_scale40,short_chain_6_scale38,short_chain_5,short_chain_3"
}

// AllCKKSProfiles returns all built-in CKKS profiles.
func AllCKKSProfiles() []CKKSProfile {
	defaultLiteral := copyCKKSParametersLiteral(ckks.ExampleParameters128BitLogN14LogQP438)

	return []CKKSProfile{
		{
			Name:        "default",
			Description: "Lattigo example parameter set LogN14 LogQP438 with default scale",
			Literal:     copyCKKSParametersLiteral(defaultLiteral),
		},
		ckksProfileWithScale(
			"scale42",
			"Default modulus chain with log scale 42",
			defaultLiteral,
			42,
		),
		ckksProfileWithScale(
			"scale40",
			"Default modulus chain with log scale 40",
			defaultLiteral,
			40,
		),
		ckksProfileWithScale(
			"scale38",
			"Default modulus chain with log scale 38",
			defaultLiteral,
			38,
		),
		ckksProfileWithDeepChain(
			"deep_chain_8_scale45",
			"LogN15 modulus chain with eight Q primes and log scale 45",
			defaultLiteral,
			15,
			8,
			45,
		),
		ckksProfileWithDeepChain(
			"deep_chain_9_scale45",
			"LogN15 modulus chain with nine Q primes and log scale 45",
			defaultLiteral,
			15,
			9,
			45,
		),
		ckksProfileWithShortChain(
			"short_chain_6_scale42",
			"Short Q modulus chain with six Q primes and log scale 42",
			defaultLiteral,
			6,
			42,
		),
		ckksProfileWithShortChain(
			"short_chain_6_scale40",
			"Short Q modulus chain with six Q primes and log scale 40",
			defaultLiteral,
			6,
			40,
		),
		ckksProfileWithShortChain(
			"short_chain_6_scale38",
			"Short Q modulus chain with six Q primes and log scale 38",
			defaultLiteral,
			6,
			38,
		),
		ckksProfileWithShortChain(
			"short_chain_5",
			"Short Q modulus chain with five Q primes and log scale 40",
			defaultLiteral,
			5,
			40,
		),
		ckksProfileWithShortChain(
			"short_chain_3",
			"Short Q modulus chain with three Q primes and log scale 35",
			defaultLiteral,
			3,
			35,
		),
	}
}

// SelectCKKSProfiles returns profiles selected by a comma-separated name list.
func SelectCKKSProfiles(names string) ([]CKKSProfile, error) {
	if strings.TrimSpace(names) == "" {
		names = DefaultCKKSProfileNames()
	}

	available := make(map[string]CKKSProfile)
	for _, profile := range AllCKKSProfiles() {
		available[profile.Name] = profile
	}

	selected := make([]CKKSProfile, 0)

	for _, rawName := range strings.Split(names, ",") {
		name := strings.TrimSpace(rawName)
		if name == "" {
			continue
		}

		profile, ok := available[name]
		if !ok {
			return nil, fmt.Errorf("unknown CKKS profile %q", name)
		}

		selected = append(selected, profile)
	}

	if len(selected) == 0 {
		return nil, fmt.Errorf("no CKKS profiles selected")
	}

	return selected, nil
}

// FindCKKSProfile returns a built-in CKKS profile by name.
func FindCKKSProfile(name string) (CKKSProfile, error) {
	profiles, err := SelectCKKSProfiles(name)
	if err != nil {
		return CKKSProfile{}, err
	}

	if len(profiles) != 1 {
		return CKKSProfile{}, fmt.Errorf("expected exactly one CKKS profile, got %d", len(profiles))
	}

	return profiles[0], nil
}

// LogQCount returns the number of Q primes in the profile literal.
func (p CKKSProfile) LogQCount() int {
	if len(p.Literal.Q) > 0 {
		return len(p.Literal.Q)
	}

	return len(p.Literal.LogQ)
}

// LogPCount returns the number of P primes in the profile literal.
func (p CKKSProfile) LogPCount() int {
	if len(p.Literal.P) > 0 {
		return len(p.Literal.P)
	}

	return len(p.Literal.LogP)
}

// LogQSum returns the sum of Q prime bit sizes in the profile literal.
func (p CKKSProfile) LogQSum() int {
	if len(p.Literal.Q) > 0 {
		return sumUint64BitLengths(p.Literal.Q)
	}

	return sumInts(p.Literal.LogQ)
}

// LogPSum returns the sum of P prime bit sizes in the profile literal.
func (p CKKSProfile) LogPSum() int {
	if len(p.Literal.P) > 0 {
		return sumUint64BitLengths(p.Literal.P)
	}

	return sumInts(p.Literal.LogP)
}

// LogQPSum returns the sum of Q and P prime bit sizes in the profile literal.
func (p CKKSProfile) LogQPSum() int {
	return p.LogQSum() + p.LogPSum()
}

// LogDefaultScale returns the profile literal default scale.
func (p CKKSProfile) LogDefaultScale() int {
	return p.Literal.LogDefaultScale
}

func ckksProfileWithScale(
	name string,
	description string,
	base ckks.ParametersLiteral,
	logDefaultScale int,
) CKKSProfile {
	literal := copyCKKSParametersLiteral(base)
	literal.LogDefaultScale = logDefaultScale

	return CKKSProfile{
		Name:        name,
		Description: description,
		Literal:     literal,
	}
}

func ckksProfileWithDeepChain(
	name string,
	description string,
	base ckks.ParametersLiteral,
	logN int,
	qCount int,
	logDefaultScale int,
) CKKSProfile {
	literal := copyCKKSParametersLiteral(base)

	logQ := extendInts(logQBitSizes(literal), qCount, logDefaultScale)
	logP := logPBitSizes(literal)

	literal.LogN = logN
	literal.Q = nil
	literal.P = nil
	literal.LogQ = logQ
	literal.LogP = logP
	literal.LogDefaultScale = logDefaultScale

	return CKKSProfile{
		Name:        name,
		Description: description,
		Literal:     literal,
	}
}

func ckksProfileWithShortChain(
	name string,
	description string,
	base ckks.ParametersLiteral,
	qCount int,
	logDefaultScale int,
) CKKSProfile {
	literal := copyCKKSParametersLiteral(base)

	if len(literal.Q) > 0 {
		literal.Q = trimUint64s(literal.Q, qCount)
	}

	if len(literal.LogQ) > 0 {
		literal.LogQ = trimInts(literal.LogQ, qCount)
	}

	literal.LogDefaultScale = logDefaultScale

	return CKKSProfile{
		Name:        name,
		Description: description,
		Literal:     literal,
	}
}

func copyCKKSParametersLiteral(literal ckks.ParametersLiteral) ckks.ParametersLiteral {
	copied := literal
	copied.Q = append([]uint64(nil), literal.Q...)
	copied.P = append([]uint64(nil), literal.P...)
	copied.LogQ = append([]int(nil), literal.LogQ...)
	copied.LogP = append([]int(nil), literal.LogP...)

	return copied
}

func logQBitSizes(literal ckks.ParametersLiteral) []int {
	if len(literal.LogQ) > 0 {
		return append([]int(nil), literal.LogQ...)
	}

	return uint64BitLengths(literal.Q)
}

func logPBitSizes(literal ckks.ParametersLiteral) []int {
	if len(literal.LogP) > 0 {
		return append([]int(nil), literal.LogP...)
	}

	return uint64BitLengths(literal.P)
}

func uint64BitLengths(values []uint64) []int {
	out := make([]int, 0, len(values))
	for _, value := range values {
		out = append(out, bits.Len64(value))
	}

	return out
}

func trimInts(values []int, limit int) []int {
	if limit <= 0 || limit >= len(values) {
		return append([]int(nil), values...)
	}

	return append([]int(nil), values[:limit]...)
}

func extendInts(values []int, limit int, fillValue int) []int {
	if limit <= 0 {
		return append([]int(nil), values...)
	}

	out := append([]int(nil), values...)

	if len(out) == 0 {
		out = append(out, fillValue+10)
	}

	for len(out) < limit {
		out = append(out, fillValue)
	}

	if len(out) > limit {
		out = out[:limit]
	}

	return out
}

func trimUint64s(values []uint64, limit int) []uint64 {
	if limit <= 0 || limit >= len(values) {
		return append([]uint64(nil), values...)
	}

	return append([]uint64(nil), values[:limit]...)
}

func sumInts(values []int) int {
	sum := 0
	for _, value := range values {
		sum += value
	}

	return sum
}

func sumUint64BitLengths(values []uint64) int {
	sum := 0
	for _, value := range values {
		sum += bits.Len64(value)
	}

	return sum
}
