package ckksbackend

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"math/bits"
	"runtime/debug"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const (
	lattigoModulePath = "github.com/tuneinsight/lattigo/v6"

	// Update this value deliberately when the dependency is upgraded.
	expectedLattigoVersion = "v6.2.0"
)

// CKKSProfileBoundSemantics records what the extracted numerical values mean.
//
// These facts are not themselves an analytical certificate. In particular,
// fresh-noise values are standard deviations and must not be treated as hard
// absolute bounds.
type CKKSProfileBoundSemantics struct {
	NoiseBoundMeaning string `json:"noise_bound_meaning"`

	FreshPublicKeyNoiseMeaning string `json:"fresh_public_key_noise_meaning"`
	FreshSecretKeyNoiseMeaning string `json:"fresh_secret_key_noise_meaning"`

	PrecisionStatsMeaning string `json:"precision_stats_meaning"`

	DirectEndToEndAbsoluteBoundAvailable bool `json:"direct_end_to_end_absolute_bound_available"`
	DirectFailureProbabilityAvailable    bool `json:"direct_failure_probability_available"`
	CertificateEligible                  bool `json:"certificate_eligible"`
}

// CKKSProfileBoundFacts is the reproducible parameter input to a later
// primitive-noise derivation.
//
// It deliberately separates:
//   - distribution truncation bounds,
//   - fresh-encryption standard deviations,
//   - modulus and scale parameters.
//
// No field in this structure is an end-to-end score error bound.
type CKKSProfileBoundFacts struct {
	SchemaVersion int `json:"schema_version"`

	ProfileName        string `json:"profile_name"`
	ProfileDescription string `json:"profile_description"`

	LibraryModule  string `json:"library_module"`
	LibraryVersion string `json:"library_version"`

	LogN     int `json:"log_n"`
	RingN    int `json:"ring_n"`
	MaxSlots int `json:"max_slots"`

	MaxLevel                  int     `json:"max_level"`
	LevelsConsumedPerRescale  int     `json:"levels_consumed_per_rescale"`
	LogDefaultScale           int     `json:"log_default_scale"`
	EncoderPrecisionBits      uint    `json:"encoder_precision_bits"`
	SecretHammingWeight       int     `json:"secret_hamming_weight"`
	NoiseDistributionAbsBound float64 `json:"noise_distribution_abs_bound"`

	FreshPublicKeyNoiseStdDev float64 `json:"fresh_public_key_noise_stddev"`
	FreshSecretKeyNoiseStdDev float64 `json:"fresh_secret_key_noise_stddev"`

	QPrimes     []uint64 `json:"q_primes"`
	PPrimes     []uint64 `json:"p_primes"`
	QPrimeBits  []int    `json:"q_prime_bits"`
	PPrimeBits  []int    `json:"p_prime_bits"`
	TotalQBits  int      `json:"total_q_bits"`
	TotalPBits  int      `json:"total_p_bits"`
	TotalQPBits int      `json:"total_qp_bits"`

	ErrorDistributionType string `json:"error_distribution_type"`
	ErrorDistributionJSON string `json:"error_distribution_json"`

	SecretDistributionType string `json:"secret_distribution_type"`
	SecretDistributionJSON string `json:"secret_distribution_json"`

	Semantics CKKSProfileBoundSemantics `json:"semantics"`
}

// BuildCKKSProfileBoundFacts extracts exact profile parameters and explicitly
// records the limited semantics of Lattigo's noise helper values.
func BuildCKKSProfileBoundFacts(
	profile CKKSProfile,
) (
	facts CKKSProfileBoundFacts,
	digest string,
	err error,
) {
	params, err := ckks.NewParametersFromLiteral(
		profile.Literal,
	)
	if err != nil {
		return CKKSProfileBoundFacts{}, "", fmt.Errorf(
			"construct CKKS parameters for profile %s: %w",
			profile.Name,
			err,
		)
	}

	errorDistribution := params.Xe()
	secretDistribution := params.Xs()

	errorDistributionJSON, err := json.Marshal(
		errorDistribution,
	)
	if err != nil {
		return CKKSProfileBoundFacts{}, "", fmt.Errorf(
			"marshal error distribution for profile %s: %w",
			profile.Name,
			err,
		)
	}

	secretDistributionJSON, err := json.Marshal(
		secretDistribution,
	)
	if err != nil {
		return CKKSProfileBoundFacts{}, "", fmt.Errorf(
			"marshal secret distribution for profile %s: %w",
			profile.Name,
			err,
		)
	}

	qPrimes := append(
		[]uint64(nil),
		params.Q()...,
	)
	pPrimes := append(
		[]uint64(nil),
		params.P()...,
	)

	qPrimeBits := primeBitLengths(qPrimes)
	pPrimeBits := primeBitLengths(pPrimes)

	facts = CKKSProfileBoundFacts{
		SchemaVersion: 1,

		ProfileName:        profile.Name,
		ProfileDescription: profile.Description,

		LibraryModule:  lattigoModulePath,
		LibraryVersion: resolvedLattigoVersion(),

		LogN:     params.LogN(),
		RingN:    params.N(),
		MaxSlots: params.MaxSlots(),

		MaxLevel:                  params.MaxLevel(),
		LevelsConsumedPerRescale:  params.LevelsConsumedPerRescaling(),
		LogDefaultScale:           params.LogDefaultScale(),
		EncoderPrecisionBits:      params.EncodingPrecision(),
		SecretHammingWeight:       params.XsHammingWeight(),
		NoiseDistributionAbsBound: params.NoiseBound(),

		FreshPublicKeyNoiseStdDev: params.NoiseFreshPK(),
		FreshSecretKeyNoiseStdDev: params.NoiseFreshSK(),

		QPrimes:    qPrimes,
		PPrimes:    pPrimes,
		QPrimeBits: qPrimeBits,
		PPrimeBits: pPrimeBits,
		TotalQBits: sumPrimeBits(
			qPrimeBits,
		),
		TotalPBits: sumPrimeBits(
			pPrimeBits,
		),
		TotalQPBits: sumPrimeBits(qPrimeBits) +
			sumPrimeBits(pPrimeBits),

		ErrorDistributionType: fmt.Sprintf(
			"%T",
			errorDistribution,
		),
		ErrorDistributionJSON: string(errorDistributionJSON),

		SecretDistributionType: fmt.Sprintf(
			"%T",
			secretDistribution,
		),
		SecretDistributionJSON: string(secretDistributionJSON),

		Semantics: CKKSProfileBoundSemantics{
			NoiseBoundMeaning: "coefficient truncation bound of the configured error distribution",

			FreshPublicKeyNoiseMeaning: "standard deviation estimate for a fresh public-key encryption",

			FreshSecretKeyNoiseMeaning: "standard deviation of the configured fresh secret-key encryption error",

			PrecisionStatsMeaning: "post-decryption empirical comparison utility, not an analytical bound",

			DirectEndToEndAbsoluteBoundAvailable: false,
			DirectFailureProbabilityAvailable:    false,
			CertificateEligible:                  false,
		},
	}

	if err := facts.Validate(); err != nil {
		return CKKSProfileBoundFacts{}, "", fmt.Errorf(
			"validate CKKS bound facts for profile %s: %w",
			profile.Name,
			err,
		)
	}

	canonical, err := facts.CanonicalJSON()
	if err != nil {
		return CKKSProfileBoundFacts{}, "", err
	}

	sum := sha256.Sum256(canonical)

	return facts,
		"sha256:" + hex.EncodeToString(sum[:]),
		nil
}

// CanonicalJSON returns the deterministic JSON representation used for the
// profile-facts digest.
func (f CKKSProfileBoundFacts) CanonicalJSON() (
	[]byte,
	error,
) {
	encoded, err := json.Marshal(f)
	if err != nil {
		return nil, fmt.Errorf(
			"marshal CKKS profile bound facts: %w",
			err,
		)
	}

	return encoded, nil
}

// Validate prevents parameter facts from accidentally being presented as an
// end-to-end analytical certificate.
func (f CKKSProfileBoundFacts) Validate() error {
	if f.SchemaVersion != 1 {
		return fmt.Errorf(
			"unsupported schema version %d",
			f.SchemaVersion,
		)
	}
	if f.ProfileName == "" {
		return fmt.Errorf(
			"profile name is empty",
		)
	}
	if f.LibraryModule != lattigoModulePath {
		return fmt.Errorf(
			"unexpected Lattigo module %q",
			f.LibraryModule,
		)
	}
	if f.LibraryVersion == "" {
		return fmt.Errorf(
			"Lattigo version is empty",
		)
	}
	if f.LogN <= 0 ||
		f.RingN != 1<<f.LogN {
		return fmt.Errorf(
			"invalid ring dimensions: logN=%d N=%d",
			f.LogN,
			f.RingN,
		)
	}
	if f.MaxSlots <= 0 ||
		f.MaxSlots > f.RingN {
		return fmt.Errorf(
			"invalid maximum slot count %d",
			f.MaxSlots,
		)
	}
	if len(f.QPrimes) == 0 {
		return fmt.Errorf(
			"Q modulus chain is empty",
		)
	}
	if f.MaxLevel != len(f.QPrimes)-1 {
		return fmt.Errorf(
			"maximum level %d does not match Q-prime count %d",
			f.MaxLevel,
			len(f.QPrimes),
		)
	}
	if f.LevelsConsumedPerRescale <= 0 {
		return fmt.Errorf(
			"levels consumed per rescale must be positive",
		)
	}
	if f.LogDefaultScale <= 0 {
		return fmt.Errorf(
			"default scale must be positive",
		)
	}
	if f.NoiseDistributionAbsBound <= 0 ||
		!finiteProfileFact(
			f.NoiseDistributionAbsBound,
		) {
		return fmt.Errorf(
			"noise-distribution bound must be finite and positive",
		)
	}
	if f.FreshPublicKeyNoiseStdDev <= 0 ||
		!finiteProfileFact(
			f.FreshPublicKeyNoiseStdDev,
		) {
		return fmt.Errorf(
			"fresh public-key noise standard deviation must be finite and positive",
		)
	}
	if f.FreshSecretKeyNoiseStdDev <= 0 ||
		!finiteProfileFact(
			f.FreshSecretKeyNoiseStdDev,
		) {
		return fmt.Errorf(
			"fresh secret-key noise standard deviation must be finite and positive",
		)
	}
	if f.Semantics.
		DirectEndToEndAbsoluteBoundAvailable {
		return fmt.Errorf(
			"profile facts must not claim a direct end-to-end absolute bound",
		)
	}
	if f.Semantics.
		DirectFailureProbabilityAvailable {
		return fmt.Errorf(
			"profile facts must not claim a direct failure probability",
		)
	}
	if f.Semantics.CertificateEligible {
		return fmt.Errorf(
			"profile facts alone must not be certificate eligible",
		)
	}

	return nil
}

func resolvedLattigoVersion() string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return expectedLattigoVersion
	}

	for _, dependency := range info.Deps {
		if dependency.Path != lattigoModulePath {
			continue
		}

		version := dependency.Version

		if dependency.Replace != nil &&
			dependency.Replace.Version != "" {
			version =
				dependency.Replace.Version
		}

		if version != "" &&
			version != "(devel)" {
			return version
		}
	}

	return expectedLattigoVersion
}

func primeBitLengths(
	primes []uint64,
) []int {
	result := make(
		[]int,
		len(primes),
	)

	for index, prime := range primes {
		result[index] = bits.Len64(prime)
	}

	return result
}

func sumPrimeBits(
	values []int,
) int {
	total := 0

	for _, value := range values {
		total += value
	}

	return total
}

func finiteProfileFact(
	value float64,
) bool {
	return !math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
