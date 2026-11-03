package ckksplanner

// These wrappers expose the already implemented optional policy. The original
// Synthesize, RepairCandidate, admission policy and acceptance code are unchanged.
import (
	"fmt"
	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
	"time"
)

func ThesisInitialPlan(c WorkloadContract, slack bool) (SynthesisPlan, error) {
	p := DefaultPrimarySynthesisPolicy()
	if slack {
		p.PrecisionSlackMode = PrecisionSlackMaximizeWithinMinLogN
	}
	plan, e := Synthesize(c, p)
	if e != nil || !slack {
		return plan, e
	}
	base, e := Synthesize(c, DefaultPrimarySynthesisPolicy())
	if e != nil {
		return plan, e
	}
	if len(plan.InitialCandidates) != 1 || len(base.InitialCandidates) != 1 {
		return plan, fmt.Errorf("STRUCTURE_INELIGIBLE: expected one initial candidate")
	}
	if !ThesisSameStructure(base.InitialCandidates[0], plan.InitialCandidates[0]) {
		return plan, fmt.Errorf("STRUCTURE_INELIGIBLE: Cprime changed N/Q/P/path/levels")
	}
	return plan, nil
}

func ThesisSameStructure(a, b SynthesizedCandidate) bool {
	return a.Parameters.LogN == b.Parameters.LogN && len(a.Parameters.LogQ) == len(b.Parameters.LogQ) && len(a.Parameters.LogP) == len(b.Parameters.LogP) && a.Path == b.Path && a.RequiredRescaleLevels == b.RequiredRescaleLevels && a.LevelGuard == b.LevelGuard
}

// B+slack receives IndependentFacts only. It does not call a margin contract or
// the C-specific helper. This is a separately labelled, one-bit static analogue.
func ThesisIndependentSlack(f IndependentFacts, base SynthesizedCandidate) (SynthesizedCandidate, []map[string]any, error) {
	best := base
	attempts := []map[string]any{}
	for scale := base.Parameters.LogDefaultScale + 1; scale <= 50; scale++ {
		start := time.Now()
		c, e := GenerateIndependentCandidate(f, scale, base.LevelGuard)
		rec := map[string]any{"scale": scale, "ms": float64(time.Since(start).Nanoseconds()) / 1e6, "encrypted": false}
		if e != nil {
			rec["failure"] = e.Error()
			attempts = append(attempts, rec)
			continue
		}
		rec["same_structure"] = ThesisSameStructure(base, c)
		attempts = append(attempts, rec)
		if !ThesisSameStructure(base, c) {
			break
		}
		best = c
	}
	best.GenerationKind = "independent_same_N_precision_slack_aux_v1"
	best.SameTierPrecisionGainBits = best.Parameters.LogDefaultScale - base.Parameters.LogDefaultScale
	return best, attempts, nil
}

// Public primes/distributions only. No key material is generated or recorded.
func ThesisConcreteRecord(c SynthesizedCandidate) (map[string]any, error) {
	start := time.Now()
	profile, e := c.Profile()
	if e != nil {
		return nil, e
	}
	params, e := ckks.NewParametersFromLiteral(profile.Literal)
	if e != nil {
		return nil, e
	}
	concrete := CKKSParameterLiteralSpec{LogN: c.Parameters.LogN, Q: params.Q(), P: params.P(), LogDefaultScale: c.Parameters.LogDefaultScale}
	sec, e := AssessConcreteSecurity(concrete, 128, DefaultSecurityEnvelope())
	if e != nil {
		return nil, e
	}
	if sec.FinalAdmission != SecurityAdmissionPass {
		return nil, fmt.Errorf("CONCRETE_SECURITY_REJECT: %+v", sec)
	}
	return map[string]any{"candidate_id": c.ID, "declared": c.Parameters, "concrete": concrete, "actual_security": sec, "Xs": fmt.Sprintf("%+v", params.Xs()), "Xe": fmt.Sprintf("%+v", params.Xe()), "static_parameter_ms": float64(time.Since(start).Nanoseconds()) / 1e6, "backend_valid": true, "interpretation": "frozen 128-bit policy admission and Lattigo validity; not a per-instance attack-cost estimate"}, nil
}
