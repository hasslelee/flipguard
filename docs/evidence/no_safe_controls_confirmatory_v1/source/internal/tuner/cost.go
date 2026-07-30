package tuner

import "math"

// RelativeCostEstimate is a lightweight relative-cost model.
// It is not a replacement for measurement; it is used to prioritize candidates.
type RelativeCostEstimate struct {
	Config       ExecutionConfiguration
	RelativeCost float64
	Reason       string
}

// EstimateRelativeCost estimates CKKS cost using the main computational drivers:
// ring dimension N, chain length, and expensive operations such as multiplication,
// rotation, and rescale.
func EstimateRelativeCost(graph GraphSummary, cfg ExecutionConfiguration) RelativeCostEstimate {
	n := float64(uint64(1) << cfg.Candidate.LogN)
	nttFactor := n * math.Log2(n)
	chain := float64(cfg.Candidate.ChainLength)

	mulCost := float64(maxInt(graph.MulOps, 1)) * chain * nttFactor
	rotCost := float64(graph.RotOps) * chain * nttFactor
	rescaleCost := float64(graph.RescaleOps) * chain * n

	pathFactor := 1.0
	if cfg.Path == PathNonRescale {
		pathFactor = 0.92
	}

	cost := (mulCost + rotCost + rescaleCost) * pathFactor
	if cost <= 0 {
		cost = chain * nttFactor
	}

	return RelativeCostEstimate{
		Config:       cfg,
		RelativeCost: cost,
		Reason:       "cost ~= chain_length * N log N with operation weights",
	}
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
