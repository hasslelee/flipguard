package tuner

import "errors"

var ErrNoSafeCandidate = errors.New("no safe candidate found")
var ErrNoSuccessfulCandidate = errors.New("no successful candidate found")

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

// SelectLatencyOnly returns the fastest successfully executed candidate,
// ignoring decision flips and error violations.
//
// Failed candidates are excluded because they do not represent usable
// configurations. This makes latency-only a meaningful unsafe baseline:
//
//   - it may choose a candidate with decision flips or error violations,
//   - but it must be a candidate that actually ran.
func SelectLatencyOnly(evals []CandidateEvaluation) (CandidateEvaluation, error) {
	var best CandidateEvaluation
	found := false

	for _, e := range evals {
		if e.FailedRuns > 0 {
			continue
		}
		if !found || e.MeanTotalMS < best.MeanTotalMS {
			best = e
			found = true
		}
	}

	if !found {
		return CandidateEvaluation{}, ErrNoSuccessfulCandidate
	}

	return best, nil
}
