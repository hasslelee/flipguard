package ckksplanner

// IndependentFacts deliberately cannot carry a decision threshold, margin,
// sensitivity, decision-derived budget, or a C candidate. It is the entire
// information boundary of the representative A/B candidate generator.
import (
	"encoding/json"
	"fmt"
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"github.com/hasslelee/flipguard/internal/tuner"
	"math"
	"os"
)

type IndependentFacts struct {
	ModelDigest     string  `json:"model_digest"`
	InputDigest     string  `json:"input_digest"`
	RequiredQPrimes int     `json:"required_q_primes"`
	RescaleLevels   int     `json:"rescale_levels"`
	RequiredSlots   int     `json:"required_slots"`
	MaxOutputAbs    float64 `json:"max_output_abs"`
}

// BuildIndependentFacts computes only graph scale demand and observed output
// magnitude. It never calls Synthesize, a contract builder, margin scope
// derivation, or sensitivity analysis. Tabular data is already materialized by
// the unchanged common preprocessing routine.
func BuildIndependentFacts(modelPath, dataPath string, multiclass bool) (IndependentFacts, error) {
	mb, e := os.ReadFile(modelPath)
	if e != nil {
		return IndependentFacts{}, e
	}
	db, e := os.ReadFile(dataPath)
	if e != nil {
		return IndependentFacts{}, e
	}
	f := IndependentFacts{ModelDigest: digestBytes(mb), InputDigest: digestBytes(db), RequiredSlots: 1}
	if multiclass {
		m, e := journalmnist.LoadModelArtifact(modelPath)
		if e != nil {
			return f, e
		}
		rows, e := journalmnist.LoadPartitionCSV(dataPath, "configuration_validation")
		if e != nil {
			return f, e
		}
		_, levels, _, q, e := journalMNISTGraphFacts(m.ModelType)
		if e != nil {
			return f, e
		}
		f.RequiredQPrimes = q
		f.RescaleLevels = levels
		f.RequiredSlots = len(rows)
		for _, r := range rows {
			z, e := m.Logits(r)
			if e != nil {
				return f, e
			}
			for _, v := range z {
				f.MaxOutputAbs = math.Max(f.MaxOutputAbs, math.Abs(v))
			}
		}
	} else {
		var m tabularModelArtifact
		if e = json.Unmarshal(mb, &m); e != nil {
			return f, e
		}
		g, e := buildTabularIRGraph(m)
		if e != nil {
			return f, e
		}
		d, e := analyzeLattigoRescaleDemand(g)
		if e != nil {
			return f, e
		}
		f.RequiredQPrimes = d.RequiredQPrimes
		f.RescaleLevels = d.LevelsConsumed
		rows, _, e := parseTabularValidation(db, m.InputDim)
		if e != nil {
			return f, e
		}
		for _, r := range rows {
			f.MaxOutputAbs = math.Max(f.MaxOutputAbs, math.Abs(r.PlainScore))
		}
	}
	return f, nil
}

// GenerateIndependentCandidate uses an explicitly requested scale. Backend
// rejection is returned, never repaired by a hidden decision-derived minimum.
// Q length follows the backend scale trace, not just multiplicative depth.
// Structural first-prime headroom and Q/QP admission reuse low-level helpers.
func GenerateIndependentCandidate(f IndependentFacts, scale, qGuard int) (SynthesizedCandidate, error) {
	var zero SynthesizedCandidate
	if scale < 18 || scale > 52 || qGuard < 0 || qGuard > 1 || f.RequiredQPrimes < 1 || f.RequiredSlots < 1 || !finite(f.MaxOutputAbs) || f.MaxOutputAbs < 0 {
		return zero, fmt.Errorf("GENERATION_REJECT: invalid independent facts or range")
	}
	bits := magnitudeBits(f.MaxOutputAbs)
	first := maxInt(18, scale+bits+3)
	if first > 60 {
		return zero, fmt.Errorf("GENERATION_REJECT: first prime %d exceeds60", first)
	}
	q := make([]int, f.RequiredQPrimes+qGuard)
	q[0] = first
	for i := 1; i < len(q); i++ {
		q[i] = scale
	}
	p := []int{maxInt(30, first)}
	envelope := DefaultSecurityEnvelope()
	n, _, e := admitLogN(sumInts(q)+sumInts(p), f.RequiredSlots, SynthesisPolicy{MinLogN: 12, MaxLogN: 15, SecurityEnvelope: envelope})
	if e != nil {
		return zero, fmt.Errorf("SECURITY_REJECT: %w", e)
	}
	spec := CKKSParameterLiteralSpec{LogN: n, LogQ: q, LogP: p, LogDefaultScale: scale}
	sec, e := AssessSecurity(spec, 128, envelope)
	if e != nil {
		return zero, fmt.Errorf("SECURITY_REJECT: %w", e)
	}
	b, _ := json.Marshal(spec)
	id := digestBytes(b)
	c := SynthesizedCandidate{ID: fmt.Sprintf("independent_S%d_Q%d_N%d_%s", scale, len(q), n, id[7:19]), Path: tuner.PathRescale, Parameters: spec, Security: sec, RequiredRescaleLevels: f.RescaleLevels, LevelGuard: qGuard, PrecisionTargetBits: scale, MessageMagnitudeBits: bits, AnalysisScaleBits: scale, BackendValidationAttempts: 1, GenerationKind: "independent_explicit_scale_v1", Reason: "graph scale trace and output magnitude only; fixed scale; no decision or sensitivity input"}
	if _, e = c.Profile(); e != nil {
		return c, fmt.Errorf("BACKEND_GENERATION_REJECT: %w", e)
	}
	return c, nil
}
