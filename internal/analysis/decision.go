package analysis

import "math"

// Decision represents a binary threshold decision.
type Decision int

const (
	DecisionNegative Decision = 0
	DecisionPositive Decision = 1
)

// Classify returns a binary decision using score >= threshold.
func Classify(score float64, threshold float64) Decision {
	if score >= threshold {
		return DecisionPositive
	}
	return DecisionNegative
}

// DecisionRecord stores decision-stability information for one sample.
type DecisionRecord struct {
	Index int

	PlainScore  float64
	ApproxScore float64
	Threshold   float64
	Gamma       float64

	Margin      float64
	OutputError float64

	PlainDecision  Decision
	ApproxDecision Decision

	Flip     bool
	Boundary bool
}

// AnalyzeDecision compares a reference plaintext score and an approximate score.
//
// Boundary is defined by:
//
//	|plain_score - threshold| <= gamma
//
// Flip is defined by:
//
//	Classify(plain_score, threshold) != Classify(approx_score, threshold)
func AnalyzeDecision(index int, plainScore float64, approxScore float64, threshold float64, gamma float64) DecisionRecord {
	margin := math.Abs(plainScore - threshold)
	outputError := math.Abs(approxScore - plainScore)

	plainDecision := Classify(plainScore, threshold)
	approxDecision := Classify(approxScore, threshold)

	return DecisionRecord{
		Index: index,

		PlainScore:  plainScore,
		ApproxScore: approxScore,
		Threshold:   threshold,
		Gamma:       gamma,

		Margin:      margin,
		OutputError: outputError,

		PlainDecision:  plainDecision,
		ApproxDecision: approxDecision,

		Flip:     plainDecision != approxDecision,
		Boundary: margin <= gamma,
	}
}

// DecisionStats summarizes decision-stability results over multiple samples.
type DecisionStats struct {
	Count int

	FlipCount int
	FlipRate  float64

	BoundaryCount int

	BoundaryFlipCount int
	BoundaryFlipRate  float64

	MaxError float64
	P95Error float64
	P99Error float64
}

// SummarizeDecisions computes aggregate decision-stability statistics.
func SummarizeDecisions(records []DecisionRecord) DecisionStats {
	stats := DecisionStats{
		Count: len(records),
	}

	if len(records) == 0 {
		return stats
	}

	errors := make([]float64, 0, len(records))

	for _, r := range records {
		if r.Flip {
			stats.FlipCount++
		}
		if r.Boundary {
			stats.BoundaryCount++
			if r.Flip {
				stats.BoundaryFlipCount++
			}
		}
		if r.OutputError > stats.MaxError {
			stats.MaxError = r.OutputError
		}
		errors = append(errors, r.OutputError)
	}

	stats.FlipRate = float64(stats.FlipCount) / float64(stats.Count)

	if stats.BoundaryCount > 0 {
		stats.BoundaryFlipRate = float64(stats.BoundaryFlipCount) / float64(stats.BoundaryCount)
	}

	sortFloat64s(errors)
	stats.P95Error = percentileSorted(errors, 0.95)
	stats.P99Error = percentileSorted(errors, 0.99)

	return stats
}

// sortFloat64s sorts values in ascending order.
// Kept local to avoid exposing implementation details.
func sortFloat64s(values []float64) {
	for i := 1; i < len(values); i++ {
		key := values[i]
		j := i - 1
		for j >= 0 && values[j] > key {
			values[j+1] = values[j]
			j--
		}
		values[j+1] = key
	}
}

// percentileSorted returns a nearest-rank percentile from a sorted slice.
//
// p should be in [0,1]. For p=0.95, this returns the 95th percentile.
func percentileSorted(sorted []float64, p float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	if p <= 0 {
		return sorted[0]
	}
	if p >= 1 {
		return sorted[len(sorted)-1]
	}

	rank := int(math.Ceil(p*float64(len(sorted)))) - 1
	if rank < 0 {
		rank = 0
	}
	if rank >= len(sorted) {
		rank = len(sorted) - 1
	}

	return sorted[rank]
}
