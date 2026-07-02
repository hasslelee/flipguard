package tuner

import "errors"

var ErrNoSafeCandidate = errors.New("no safe candidate found")

// SelectFastestSafe returns the lowest-latency candidate among candidates
// that satisfy failure=0, decision_flip=0, and error_violation=0.
func SelectFastestSafe(evals []CandidateEvaluation) (CandidateEvaluation, error) {
	var best CandidateEvaluation
	found := false

	for _, e := range evals {
		if !e.IsSafe() {
			continue
		}
		if !found || e.MeanTotalMS < best.MeanTotalMS {
			best = e
			found = true
		}
	}

	if !found {
		return CandidateEvaluation{}, ErrNoSafeCandidate
	}
	return best, nil
}

// SelectLatencyOnly returns the fastest candidate regardless of safety.
// This is useful as a comparison baseline.
func SelectLatencyOnly(evals []CandidateEvaluation) (CandidateEvaluation, error) {
	if len(evals) == 0 {
		return CandidateEvaluation{}, ErrNoSafeCandidate
	}

	best := evals[0]
	for _, e := range evals[1:] {
		if e.MeanTotalMS < best.MeanTotalMS {
			best = e
		}
	}
	return best, nil
}
