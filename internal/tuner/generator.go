package tuner

import (
	"fmt"
	"sort"
)

const (
	minChainLength = 3
	minScaleBits   = 20
	minLogN        = 12
)

// DefaultCandidateGenerationOptions returns a small local search space around
// the conservative reference configuration.
//
// The search intentionally includes both smaller and larger candidates so that
// experiments can compare:
//   - reference-safe but potentially expensive configurations,
//   - cheaper candidate configurations,
//   - rejected fastest-only configurations.
func DefaultCandidateGenerationOptions() CandidateGenerationOptions {
	return CandidateGenerationOptions{
		ChainDeltas: []int{-3, -2, -1, 0, 1},
		ScaleDeltas: []int{-10, -5, 0, 5},
		LogNDeltas:  []int{0},
		Paths:       []ExecutionPath{PathRescale, PathNonRescale},
	}
}

// BuildReferenceConfiguration constructs a conservative parameter candidate
// from a workload graph summary.
//
// For leveled CKKS workloads, the required chain length is primarily driven by
// multiplicative depth. We add ChainMargin to leave room for conservative
// reference execution. This function does not claim optimality; it provides a
// stable paper-facing reference configuration around which local candidates are
// generated.
func BuildReferenceConfiguration(graph GraphSummary, policy ReferencePolicy) ParameterCandidate {
	scaleBits := policy.InitialScaleBits
	if scaleBits <= 0 {
		scaleBits = 45
	}

	chainMargin := policy.ChainMargin
	if chainMargin < 0 {
		chainMargin = 0
	}

	chainLength := graph.MultiplicativeDepth + chainMargin
	if chainLength < minChainLength {
		chainLength = minChainLength
	}

	logN := policy.MinLogN
	if logN <= 0 {
		logN = 14
	}
	if logN < minLogN {
		logN = minLogN
	}
	if policy.MaxLogN > 0 && logN > policy.MaxLogN {
		logN = policy.MaxLogN
	}

	return ParameterCandidate{
		ID:          candidateID("reference", chainLength, scaleBits, logN),
		LogN:        logN,
		Slots:       slotsFromLogN(logN),
		ChainLength: chainLength,
		ScaleBits:   scaleBits,
		Family:      "reference",
		IsReference: true,
	}
}

// GenerateAroundReference expands a reference parameter candidate into concrete
// execution configurations by applying local deltas to chain length, scale bits,
// and logN, and pairing each parameter candidate with each execution path.
func GenerateAroundReference(
	reference ParameterCandidate,
	options CandidateGenerationOptions,
) []ExecutionConfiguration {
	normalizeCandidateGenerationOptions(&options)

	seen := map[string]bool{}
	configs := make([]ExecutionConfiguration, 0)

	for _, chainDelta := range options.ChainDeltas {
		for _, scaleDelta := range options.ScaleDeltas {
			for _, logNDelta := range options.LogNDeltas {
				candidate := ParameterCandidate{
					LogN:        reference.LogN + logNDelta,
					ChainLength: reference.ChainLength + chainDelta,
					ScaleBits:   reference.ScaleBits + scaleDelta,
					Family:      "local",
					IsReference: false,
				}

				if candidate.LogN < minLogN {
					continue
				}
				if candidate.ChainLength < minChainLength {
					continue
				}
				if candidate.ScaleBits < minScaleBits {
					continue
				}

				candidate.Slots = slotsFromLogN(candidate.LogN)

				if candidate.LogN == reference.LogN &&
					candidate.ChainLength == reference.ChainLength &&
					candidate.ScaleBits == reference.ScaleBits {
					candidate.Family = reference.Family
					candidate.IsReference = reference.IsReference
					candidate.ID = reference.ID
				} else {
					candidate.ID = candidateID("candidate", candidate.ChainLength, candidate.ScaleBits, candidate.LogN)
				}

				for _, path := range options.Paths {
					if path == "" {
						continue
					}

					config := ExecutionConfiguration{
						Candidate: candidate,
						Path:      path,
					}

					key := configKey(config)
					if seen[key] {
						continue
					}
					seen[key] = true
					configs = append(configs, config)
				}
			}
		}
	}

	sort.Slice(configs, func(i, j int) bool {
		ci := configs[i]
		cj := configs[j]

		if ci.Candidate.IsReference != cj.Candidate.IsReference {
			return ci.Candidate.IsReference
		}
		if ci.Candidate.LogN != cj.Candidate.LogN {
			return ci.Candidate.LogN < cj.Candidate.LogN
		}
		if ci.Candidate.ChainLength != cj.Candidate.ChainLength {
			return ci.Candidate.ChainLength < cj.Candidate.ChainLength
		}
		if ci.Candidate.ScaleBits != cj.Candidate.ScaleBits {
			return ci.Candidate.ScaleBits < cj.Candidate.ScaleBits
		}
		return ci.Path < cj.Path
	})

	return configs
}

func normalizeCandidateGenerationOptions(options *CandidateGenerationOptions) {
	if len(options.ChainDeltas) == 0 {
		options.ChainDeltas = []int{0}
	}
	if len(options.ScaleDeltas) == 0 {
		options.ScaleDeltas = []int{0}
	}
	if len(options.LogNDeltas) == 0 {
		options.LogNDeltas = []int{0}
	}
	if len(options.Paths) == 0 {
		options.Paths = []ExecutionPath{PathRescale}
	}
}

func slotsFromLogN(logN int) int {
	if logN <= 1 {
		return 1
	}
	return 1 << (logN - 1)
}

func candidateID(prefix string, chainLength int, scaleBits int, logN int) string {
	return fmt.Sprintf("%s_chain%d_scale%d_N%d", prefix, chainLength, scaleBits, logN)
}

func configKey(config ExecutionConfiguration) string {
	return fmt.Sprintf(
		"%s|%s|%d|%d|%d",
		config.Candidate.ID,
		config.Path,
		config.Candidate.LogN,
		config.Candidate.ChainLength,
		config.Candidate.ScaleBits,
	)
}
