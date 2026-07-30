package benchmarks

import (
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	PolynomialRegressionThreshold = 0.0
)

// PolynomialRegressionCoefficients defines the fixed polynomial regression
// workload used by FlipGuard benchmark expansion.
//
// The model is intentionally deeper than linear_poly3:
//
//	y = c0 + c1*x + c2*x^2 + c3*x^3 + c4*x^4 + c5*x^5
//
// It is still small enough to inspect manually, but it exposes more
// multiplication levels and program points than the running example.
var PolynomialRegressionCoefficients = []float64{
	0.12,   // c0
	0.70,   // c1
	-0.25,  // c2
	0.11,   // c3
	-0.035, // c4
	0.006,  // c5
}

// PolynomialRegressionSample represents one scalar input sample.
type PolynomialRegressionSample struct {
	X float64
}

// Inputs converts the sample into an IR input map.
func (s PolynomialRegressionSample) Inputs() map[ir.NodeID]float64 {
	return map[ir.NodeID]float64{
		"x": s.X,
	}
}

// NewPolynomialRegressionGraph builds an explicit computation graph for:
//
//	y = 0.12 + 0.70*x - 0.25*x^2 + 0.11*x^3 - 0.035*x^4 + 0.006*x^5
//
// Powers are expanded into explicit program points:
//
//	x2 = x*x
//	x3 = x2*x
//	x4 = x2*x2
//	x5 = x4*x
//
// This explicit graph is better for FlipGuard than a single OpPoly node because
// it exposes intermediate nodes with different sensitivity and error-budget
// roles.
func NewPolynomialRegressionGraph() *ir.Graph {
	g := ir.NewGraph()

	g.MustAddNode(ir.NewInput("x", "x"))

	g.MustAddNode(ir.NewBinary("x2", "x^2", ir.OpMul, "x", "x"))
	g.MustAddNode(ir.NewBinary("x3", "x^3", ir.OpMul, "x2", "x"))
	g.MustAddNode(ir.NewBinary("x4", "x^4", ir.OpMul, "x2", "x2"))
	g.MustAddNode(ir.NewBinary("x5", "x^5", ir.OpMul, "x4", "x"))

	g.MustAddNode(ir.NewMulConst("t1", "0.70*x", "x", 0.70))
	g.MustAddNode(ir.NewMulConst("t2", "-0.25*x^2", "x2", -0.25))
	g.MustAddNode(ir.NewMulConst("t3", "0.11*x^3", "x3", 0.11))
	g.MustAddNode(ir.NewMulConst("t4", "-0.035*x^4", "x4", -0.035))
	g.MustAddNode(ir.NewMulConst("t5", "0.006*x^5", "x5", 0.006))

	g.MustAddNode(ir.NewConst("c0", "0.12", 0.12))

	g.MustAddNode(ir.NewBinary("s1", "c0+t1", ir.OpAdd, "c0", "t1"))
	g.MustAddNode(ir.NewBinary("s2", "s1+t2", ir.OpAdd, "s1", "t2"))
	g.MustAddNode(ir.NewBinary("s3", "s2+t3", ir.OpAdd, "s2", "t3"))
	g.MustAddNode(ir.NewBinary("s4", "s3+t4", ir.OpAdd, "s3", "t4"))
	g.MustAddNode(ir.NewBinary("y", "polynomial regression output", ir.OpAdd, "s4", "t5"))

	g.MustSetOutput("y")

	return g
}

// PolynomialRegressionScore evaluates the fixed polynomial over plaintext.
func PolynomialRegressionScore(s PolynomialRegressionSample) float64 {
	return EvalPolynomialRegressionPlain(s.X)
}

// EvalPolynomialRegressionPlain evaluates the fixed polynomial over x.
func EvalPolynomialRegressionPlain(x float64) float64 {
	coeffs := PolynomialRegressionCoefficients

	// Horner form for the reference plaintext evaluator.
	y := coeffs[len(coeffs)-1]
	for i := len(coeffs) - 2; i >= 0; i-- {
		y = y*x + coeffs[i]
	}

	if y == 0 || math.Abs(y) < 1e-18 {
		return 0
	}

	return y
}

// PolynomialRegressionMargin returns |score - threshold|.
func PolynomialRegressionMargin(s PolynomialRegressionSample, threshold float64) float64 {
	return math.Abs(PolynomialRegressionScore(s) - threshold)
}

// DefaultPolynomialRegressionSamples returns deterministic samples covering
// negative, near-boundary, and positive outputs.
func DefaultPolynomialRegressionSamples() []PolynomialRegressionSample {
	return []PolynomialRegressionSample{
		{X: -2.0},
		{X: -1.5},
		{X: -1.0},
		{X: -0.5},
		{X: -0.2},
		{X: 0.0},
		{X: 0.2},
		{X: 0.5},
		{X: 1.0},
		{X: 1.5},
		{X: 2.0},
	}
}

// PolynomialRegressionSampleGenOptions controls deterministic scalar sample
// generation.
type PolynomialRegressionSampleGenOptions struct {
	RangeMin float64
	RangeMax float64
	Step     float64

	Threshold float64
	Gamma     float64

	MaxBoundary    int
	MaxNonBoundary int
}

// DefaultPolynomialRegressionBoundaryOptions returns a deterministic sampling
// configuration with boundary and non-boundary examples.
func DefaultPolynomialRegressionBoundaryOptions() PolynomialRegressionSampleGenOptions {
	return PolynomialRegressionSampleGenOptions{
		RangeMin: -2.5,
		RangeMax: 2.5,
		Step:     0.001,

		Threshold: PolynomialRegressionThreshold,
		Gamma:     0.02,

		MaxBoundary:    100,
		MaxNonBoundary: 100,
	}
}

// GeneratePolynomialRegressionSamples generates deterministic boundary-focused
// samples.
//
// Boundary samples satisfy:
//
//	|f_plain(x) - threshold| <= gamma
func GeneratePolynomialRegressionSamples(opts PolynomialRegressionSampleGenOptions) []PolynomialRegressionSample {
	if opts.Step <= 0 {
		opts.Step = 0.01
	}
	if opts.RangeMax < opts.RangeMin {
		opts.RangeMin, opts.RangeMax = opts.RangeMax, opts.RangeMin
	}
	if opts.Gamma < 0 {
		opts.Gamma = math.Abs(opts.Gamma)
	}

	threshold := opts.Threshold

	boundary := make([]PolynomialRegressionSample, 0, opts.MaxBoundary)
	nonBoundary := make([]PolynomialRegressionSample, 0, opts.MaxNonBoundary)

	steps := int(math.Round((opts.RangeMax - opts.RangeMin) / opts.Step))

	for i := 0; i <= steps; i++ {
		x := roundPolynomialRegressionGrid(opts.RangeMin + float64(i)*opts.Step)
		sample := PolynomialRegressionSample{X: x}
		margin := PolynomialRegressionMargin(sample, threshold)

		if margin <= opts.Gamma {
			if len(boundary) < opts.MaxBoundary {
				boundary = append(boundary, sample)
			}
		} else {
			if len(nonBoundary) < opts.MaxNonBoundary {
				nonBoundary = append(nonBoundary, sample)
			}
		}

		if len(boundary) >= opts.MaxBoundary && len(nonBoundary) >= opts.MaxNonBoundary {
			return append(boundary, nonBoundary...)
		}
	}

	return append(boundary, nonBoundary...)
}

func roundPolynomialRegressionGrid(x float64) float64 {
	return math.Round(x*1e12) / 1e12
}
