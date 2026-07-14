package benchmarks

import (
	"math"
	"sort"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	// MLPSquareThreshold is the fixed decision threshold for the small
	// square-activation MLP workload.
	MLPSquareThreshold = 0.15
)

// MLPSquareSample is one four-dimensional input for the square-activation MLP.
type MLPSquareSample struct {
	X1 float64
	X2 float64
	X3 float64
	X4 float64
}

// Inputs converts the sample into graph input values.
func (s MLPSquareSample) Inputs() map[ir.NodeID]float64 {
	return map[ir.NodeID]float64{
		"x1": s.X1,
		"x2": s.X2,
		"x3": s.X3,
		"x4": s.X4,
	}
}

// NewMLPSquareGraph builds a small CKKS-friendly MLP:
//
//	h = W1*x + b1
//	a = h^2
//	y = W2*a + b2
//
// The graph intentionally uses a square activation instead of ReLU/sigmoid so
// that it is directly evaluable with CKKS polynomial arithmetic.
func NewMLPSquareGraph() *ir.Graph {
	g := ir.NewGraph()

	g.MustAddNode(ir.NewInput("x1", "x1"))
	g.MustAddNode(ir.NewInput("x2", "x2"))
	g.MustAddNode(ir.NewInput("x3", "x3"))
	g.MustAddNode(ir.NewInput("x4", "x4"))

	// First affine layer: 4 -> 3.
	addAffine4(
		g,
		"h1",
		[4]float64{0.65, -0.35, 0.20, 0.10},
		0.10,
	)
	addAffine4(
		g,
		"h2",
		[4]float64{-0.20, 0.55, -0.15, 0.25},
		-0.05,
	)
	addAffine4(
		g,
		"h3",
		[4]float64{0.30, 0.10, 0.50, -0.40},
		0.00,
	)

	// Square activation.
	g.MustAddNode(ir.NewUnary("a1", "h1^2", ir.OpPow2, "h1"))
	g.MustAddNode(ir.NewUnary("a2", "h2^2", ir.OpPow2, "h2"))
	g.MustAddNode(ir.NewUnary("a3", "h3^2", ir.OpPow2, "h3"))

	// Output affine layer: 3 -> 1.
	g.MustAddNode(ir.NewMulConst("y_t1", "0.70*a1", "a1", 0.70))
	g.MustAddNode(ir.NewMulConst("y_t2", "-0.30*a2", "a2", -0.30))
	g.MustAddNode(ir.NewMulConst("y_t3", "0.20*a3", "a3", 0.20))
	g.MustAddNode(ir.NewBinary("y_s1", "y_t1+y_t2", ir.OpAdd, "y_t1", "y_t2"))
	g.MustAddNode(ir.NewBinary("y_s2", "y_s1+y_t3", ir.OpAdd, "y_s1", "y_t3"))
	g.MustAddNode(ir.NewConst("y_b", "-0.10", -0.10))
	g.MustAddNode(ir.NewBinary("y", "mlp_square_score", ir.OpAdd, "y_s2", "y_b"))

	g.MustSetOutput("y")

	return g
}

func addAffine4(
	g *ir.Graph,
	prefix string,
	weights [4]float64,
	bias float64,
) {
	t1 := ir.NodeID(prefix + "_t1")
	t2 := ir.NodeID(prefix + "_t2")
	t3 := ir.NodeID(prefix + "_t3")
	t4 := ir.NodeID(prefix + "_t4")
	s1 := ir.NodeID(prefix + "_s1")
	s2 := ir.NodeID(prefix + "_s2")
	s3 := ir.NodeID(prefix + "_s3")
	b := ir.NodeID(prefix + "_b")
	out := ir.NodeID(prefix)

	g.MustAddNode(ir.NewMulConst(t1, prefix+"_w1*x1", "x1", weights[0]))
	g.MustAddNode(ir.NewMulConst(t2, prefix+"_w2*x2", "x2", weights[1]))
	g.MustAddNode(ir.NewMulConst(t3, prefix+"_w3*x3", "x3", weights[2]))
	g.MustAddNode(ir.NewMulConst(t4, prefix+"_w4*x4", "x4", weights[3]))

	g.MustAddNode(ir.NewBinary(s1, prefix+"_t1+t2", ir.OpAdd, t1, t2))
	g.MustAddNode(ir.NewBinary(s2, prefix+"_s1+t3", ir.OpAdd, s1, t3))
	g.MustAddNode(ir.NewBinary(s3, prefix+"_s2+t4", ir.OpAdd, s2, t4))
	g.MustAddNode(ir.NewConst(b, prefix+"_bias", bias))
	g.MustAddNode(ir.NewBinary(out, prefix+"_affine", ir.OpAdd, s3, b))
}

func addAffine3(
	g *ir.Graph,
	prefix string,
	weights [3]float64,
	bias float64,
) {
	t1 := ir.NodeID(prefix + "_t1")
	t2 := ir.NodeID(prefix + "_t2")
	t3 := ir.NodeID(prefix + "_t3")
	s1 := ir.NodeID(prefix + "_s1")
	s2 := ir.NodeID(prefix + "_s2")
	b := ir.NodeID(prefix + "_b")
	out := ir.NodeID(prefix)

	g.MustAddNode(ir.NewMulConst(t1, prefix+"_w1*a1", "a1", weights[0]))
	g.MustAddNode(ir.NewMulConst(t2, prefix+"_w2*a2", "a2", weights[1]))
	g.MustAddNode(ir.NewMulConst(t3, prefix+"_w3*a3", "a3", weights[2]))

	g.MustAddNode(ir.NewBinary(s1, prefix+"_t1+t2", ir.OpAdd, t1, t2))
	g.MustAddNode(ir.NewBinary(s2, prefix+"_s1+t3", ir.OpAdd, s1, t3))
	g.MustAddNode(ir.NewConst(b, prefix+"_bias", bias))
	g.MustAddNode(ir.NewBinary(out, prefix+"_affine", ir.OpAdd, s2, b))
}

// MLPSquareScore evaluates the same fixed MLP in plain floating point.
func MLPSquareScore(sample MLPSquareSample) float64 {
	h1 := 0.65*sample.X1 - 0.35*sample.X2 + 0.20*sample.X3 + 0.10*sample.X4 + 0.10
	h2 := -0.20*sample.X1 + 0.55*sample.X2 - 0.15*sample.X3 + 0.25*sample.X4 - 0.05
	h3 := 0.30*sample.X1 + 0.10*sample.X2 + 0.50*sample.X3 - 0.40*sample.X4

	a1 := h1 * h1
	a2 := h2 * h2
	a3 := h3 * h3

	return 0.70*a1 - 0.30*a2 + 0.20*a3 - 0.10
}

// MLPSquareDecision returns the thresholded MLP decision.
func MLPSquareDecision(sample MLPSquareSample, threshold float64) bool {
	return MLPSquareScore(sample) >= threshold
}

// MLPSquareMargin returns the absolute decision margin.
func MLPSquareMargin(sample MLPSquareSample, threshold float64) float64 {
	return math.Abs(MLPSquareScore(sample) - threshold)
}

// DefaultMLPSquareSamples returns deterministic non-random samples containing
// both positive and negative decisions.
func DefaultMLPSquareSamples() []MLPSquareSample {
	return []MLPSquareSample{
		{X1: 0.0, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 1.0, X2: 0.0, X3: 0.0, X4: 0.0},
		{X1: 0.0, X2: 1.0, X3: 0.0, X4: 0.0},
		{X1: 0.0, X2: 0.0, X3: 1.0, X4: 0.0},
		{X1: 0.0, X2: 0.0, X3: 0.0, X4: 1.0},
		{X1: 1.0, X2: -1.0, X3: 1.0, X4: -1.0},
		{X1: -1.0, X2: 1.0, X3: -1.0, X4: 1.0},
		{X1: -0.5, X2: 0.5, X3: -0.25, X4: 0.25},
		{X1: 1.0, X2: 1.0, X3: 1.0, X4: 1.0},
		{X1: -1.0, X2: -1.0, X3: -1.0, X4: -1.0},
	}
}

// MLPSquareSampleGenOptions controls deterministic sample generation.
type MLPSquareSampleGenOptions struct {
	Grid []float64

	MaxBoundary    int
	MaxNonBoundary int

	Threshold float64
}

// DefaultMLPSquareSampleGenOptions returns a balanced deterministic generator
// configuration for boundary-focused and non-boundary samples.
func DefaultMLPSquareSampleGenOptions() MLPSquareSampleGenOptions {
	return MLPSquareSampleGenOptions{
		Grid: []float64{
			-1.0,
			-0.75,
			-0.50,
			-0.25,
			0.0,
			0.25,
			0.50,
			0.75,
			1.0,
		},
		MaxBoundary:    32,
		MaxNonBoundary: 32,
		Threshold:      MLPSquareThreshold,
	}
}

// GenerateMLPSquareSamples deterministically selects samples near and far from
// the threshold. Near-boundary samples stress decision stability, while far
// samples ensure both decision classes remain represented.
func GenerateMLPSquareSamples(opts MLPSquareSampleGenOptions) []MLPSquareSample {
	if len(opts.Grid) == 0 {
		opts.Grid = DefaultMLPSquareSampleGenOptions().Grid
	}
	if opts.Threshold == 0 {
		opts.Threshold = MLPSquareThreshold
	}
	if opts.MaxBoundary < 0 {
		opts.MaxBoundary = 0
	}
	if opts.MaxNonBoundary < 0 {
		opts.MaxNonBoundary = 0
	}

	type candidate struct {
		Sample MLPSquareSample
		Margin float64
		Score  float64
	}

	candidates := make([]candidate, 0, len(opts.Grid)*len(opts.Grid)*len(opts.Grid)*len(opts.Grid))

	for _, x1 := range opts.Grid {
		for _, x2 := range opts.Grid {
			for _, x3 := range opts.Grid {
				for _, x4 := range opts.Grid {
					sample := MLPSquareSample{
						X1: x1,
						X2: x2,
						X3: x3,
						X4: x4,
					}
					score := MLPSquareScore(sample)
					candidates = append(candidates, candidate{
						Sample: sample,
						Margin: math.Abs(score - opts.Threshold),
						Score:  score,
					})
				}
			}
		}
	}

	selected := make([]MLPSquareSample, 0, opts.MaxBoundary+opts.MaxNonBoundary)
	seen := make(map[MLPSquareSample]bool)

	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].Margin == candidates[j].Margin {
			return candidates[i].Score < candidates[j].Score
		}
		return candidates[i].Margin < candidates[j].Margin
	})

	for _, c := range candidates {
		if len(selected) >= opts.MaxBoundary {
			break
		}
		if seen[c.Sample] {
			continue
		}
		selected = append(selected, c.Sample)
		seen[c.Sample] = true
	}

	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].Margin == candidates[j].Margin {
			return candidates[i].Score > candidates[j].Score
		}
		return candidates[i].Margin > candidates[j].Margin
	})

	for _, c := range candidates {
		if opts.MaxNonBoundary > 0 && len(selected) >= opts.MaxBoundary+opts.MaxNonBoundary {
			break
		}
		if seen[c.Sample] {
			continue
		}
		selected = append(selected, c.Sample)
		seen[c.Sample] = true
	}

	return selected
}
