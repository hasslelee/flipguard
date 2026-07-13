package benchmarks

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	// HarrisCornerK is the standard empirical Harris response constant.
	HarrisCornerK = 0.04

	// HarrisCornerThreshold is used for a deterministic corner/non-corner
	// decision in the benchmark suite.
	HarrisCornerThreshold = 100.0
)

// HarrisCornerWindowSample represents a 5x5 image window.
//
// The Harris response is computed over the inner 3x3 positions. At each inner
// position, a 3x3 Sobel stencil is used to compute local gradients Ix and Iy.
// The benchmark then accumulates:
//
//	Sxx = sum Ix^2
//	Syy = sum Iy^2
//	Sxy = sum Ix*Iy
//
// and returns:
//
//	R = Sxx*Syy - Sxy^2 - k*(Sxx+Syy)^2
//
// This is a windowed Harris corner-response microbenchmark rather than a full
// image-level detector with non-maximum suppression.
type HarrisCornerWindowSample struct {
	Pixels [5][5]float64
}

// HarrisCornerComponents stores plaintext Harris response components.
type HarrisCornerComponents struct {
	SXX   float64
	SYY   float64
	SXY   float64
	Det   float64
	Trace float64
	Score float64
}

// NewHarrisCornerResponseGraph builds an IR graph for one 5x5-window Harris
// corner response.
//
// The graph intentionally mirrors the standard Harris response polynomial. It
// is useful as a vision workload that is deeper than the Sobel edge score:
//
//	Sobel score:  Gx^2 + Gy^2
//	Harris score: Sxx*Syy - Sxy^2 - k(Sxx+Syy)^2
func NewHarrisCornerResponseGraph() *ir.Graph {
	g := ir.NewGraph()

	for r := 0; r < 5; r++ {
		for c := 0; c < 5; c++ {
			id := harrisPixelID(r, c)
			g.MustAddNode(ir.NewInput(id, string(id)))
		}
	}

	sxxTerms := make([]ir.NodeID, 0, 9)
	syyTerms := make([]ir.NodeID, 0, 9)
	sxyTerms := make([]ir.NodeID, 0, 9)

	for r := 1; r <= 3; r++ {
		for c := 1; c <= 3; c++ {
			prefix := fmt.Sprintf("g%d%d", r, c)

			gx := addHarrisSobelGX(g, prefix, r, c)
			gy := addHarrisSobelGY(g, prefix, r, c)

			gx2 := ir.NodeID(prefix + "_gx2")
			gy2 := ir.NodeID(prefix + "_gy2")
			gxy := ir.NodeID(prefix + "_gxy")

			g.MustAddNode(ir.NewBinary(gx2, "Ix^2", ir.OpMul, gx, gx))
			g.MustAddNode(ir.NewBinary(gy2, "Iy^2", ir.OpMul, gy, gy))
			g.MustAddNode(ir.NewBinary(gxy, "Ix*Iy", ir.OpMul, gx, gy))

			sxxTerms = append(sxxTerms, gx2)
			syyTerms = append(syyTerms, gy2)
			sxyTerms = append(sxyTerms, gxy)
		}
	}

	sxx := addHarrisTermChain(g, "sxx", sxxTerms)
	syy := addHarrisTermChain(g, "syy", syyTerms)
	sxy := addHarrisTermChain(g, "sxy", sxyTerms)

	g.MustAddNode(ir.NewBinary("det_pos", "Sxx*Syy", ir.OpMul, sxx, syy))
	g.MustAddNode(ir.NewBinary("sxy2", "Sxy^2", ir.OpMul, sxy, sxy))
	g.MustAddNode(ir.NewMulConst("neg_sxy2", "-Sxy^2", "sxy2", -1.0))
	g.MustAddNode(ir.NewBinary("det", "Sxx*Syy - Sxy^2", ir.OpAdd, "det_pos", "neg_sxy2"))

	g.MustAddNode(ir.NewBinary("trace", "Sxx+Syy", ir.OpAdd, sxx, syy))
	g.MustAddNode(ir.NewBinary("trace2", "(Sxx+Syy)^2", ir.OpMul, "trace", "trace"))
	g.MustAddNode(ir.NewMulConst("neg_k_trace2", "-k*(Sxx+Syy)^2", "trace2", -HarrisCornerK))

	g.MustAddNode(ir.NewBinary("score", "Harris corner response", ir.OpAdd, "det", "neg_k_trace2"))
	g.MustSetOutput("score")

	return g
}

// Inputs converts the sample into an IR input map.
func (s HarrisCornerWindowSample) Inputs() map[ir.NodeID]float64 {
	inputs := make(map[ir.NodeID]float64, 25)

	for r := 0; r < 5; r++ {
		for c := 0; c < 5; c++ {
			inputs[harrisPixelID(r, c)] = s.Pixels[r][c]
		}
	}

	return inputs
}

// HarrisCornerResponse evaluates the windowed Harris response directly over
// plaintext values.
func HarrisCornerResponse(s HarrisCornerWindowSample) HarrisCornerComponents {
	sxx := 0.0
	syy := 0.0
	sxy := 0.0

	for r := 1; r <= 3; r++ {
		for c := 1; c <= 3; c++ {
			gx, gy := harrisSobelAt(s, r, c)

			sxx += gx * gx
			syy += gy * gy
			sxy += gx * gy
		}
	}

	det := sxx*syy - sxy*sxy
	trace := sxx + syy
	score := det - HarrisCornerK*trace*trace

	return HarrisCornerComponents{
		SXX:   sxx,
		SYY:   syy,
		SXY:   sxy,
		Det:   det,
		Trace: trace,
		Score: score,
	}
}

// HarrisCornerScore returns the scalar Harris response R.
func HarrisCornerScore(s HarrisCornerWindowSample) float64 {
	return HarrisCornerResponse(s).Score
}

// HarrisCornerDecision returns true when the Harris response is above threshold.
func HarrisCornerDecision(s HarrisCornerWindowSample, threshold float64) bool {
	return HarrisCornerScore(s) >= threshold
}

// HarrisCornerMargin returns |R - threshold|.
func HarrisCornerMargin(s HarrisCornerWindowSample, threshold float64) float64 {
	return math.Abs(HarrisCornerScore(s) - threshold)
}

// DefaultHarrisCornerSamples returns deterministic 5x5 windows containing flat
// patches, edges, corners, diagonal structures, and checkerboard-like patterns.
func DefaultHarrisCornerSamples() []HarrisCornerWindowSample {
	return []HarrisCornerWindowSample{
		newHarrisWindow(func(r, c int) float64 {
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			return 1.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if c >= 3 {
				return 1.0
			}
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if r >= 3 {
				return 1.0
			}
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if r >= 2 && c >= 2 {
				return 1.0
			}
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if r <= 2 && c <= 2 {
				return 1.0
			}
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if r+c >= 4 {
				return 1.0
			}
			return 0.0
		}),
		newHarrisWindow(func(r, c int) float64 {
			if (r+c)%2 == 0 {
				return 1.0
			}
			return 0.0
		}),
		scaleHarrisWindow(
			newHarrisWindow(func(r, c int) float64 {
				if r >= 2 && c >= 2 {
					return 1.0
				}
				return 0.0
			}),
			0.75,
		),
		scaleHarrisWindow(
			newHarrisWindow(func(r, c int) float64 {
				if r >= 2 && c >= 2 {
					return 1.0
				}
				return 0.0
			}),
			1.25,
		),
	}
}

// HarrisCornerSampleGenOptions controls deterministic Harris sample expansion.
type HarrisCornerSampleGenOptions struct {
	Scales []float64

	Threshold float64
	Gamma     float64

	MaxBoundary    int
	MaxNonBoundary int
}

// DefaultHarrisCornerSampleGenOptions returns a deterministic sample-generation
// policy for the Harris response benchmark.
func DefaultHarrisCornerSampleGenOptions() HarrisCornerSampleGenOptions {
	return HarrisCornerSampleGenOptions{
		Scales: []float64{
			0.75,
			1.0,
			1.25,
		},

		Threshold: HarrisCornerThreshold,
		Gamma:     10.0,

		MaxBoundary:    32,
		MaxNonBoundary: 32,
	}
}

// GenerateHarrisCornerSamples expands the default samples across a small set of
// intensity scales and returns both near-threshold and non-boundary cases.
func GenerateHarrisCornerSamples(opts HarrisCornerSampleGenOptions) []HarrisCornerWindowSample {
	if len(opts.Scales) == 0 {
		opts.Scales = []float64{0.75, 1.0, 1.25}
	}
	if opts.Threshold == 0 {
		opts.Threshold = HarrisCornerThreshold
	}
	if opts.Gamma <= 0 {
		opts.Gamma = 10.0
	}
	if opts.MaxBoundary <= 0 {
		opts.MaxBoundary = 32
	}
	if opts.MaxNonBoundary <= 0 {
		opts.MaxNonBoundary = 32
	}

	base := DefaultHarrisCornerSamples()

	boundary := make([]HarrisCornerWindowSample, 0, opts.MaxBoundary)
	nonBoundary := make([]HarrisCornerWindowSample, 0, opts.MaxNonBoundary)

	for _, sample := range base {
		for _, scale := range opts.Scales {
			scaled := scaleHarrisWindow(sample, scale)
			margin := HarrisCornerMargin(scaled, opts.Threshold)

			if margin <= opts.Gamma {
				if len(boundary) < opts.MaxBoundary {
					boundary = append(boundary, scaled)
				}
			} else {
				if len(nonBoundary) < opts.MaxNonBoundary {
					nonBoundary = append(nonBoundary, scaled)
				}
			}
		}
	}

	return append(boundary, nonBoundary...)
}

func addHarrisSobelGX(g *ir.Graph, prefix string, r int, c int) ir.NodeID {
	terms := []struct {
		id    ir.NodeID
		input ir.NodeID
		coef  float64
	}{
		{ir.NodeID(prefix + "_gx_t00"), harrisPixelID(r-1, c-1), -1.0},
		{ir.NodeID(prefix + "_gx_t02"), harrisPixelID(r-1, c+1), 1.0},
		{ir.NodeID(prefix + "_gx_t10"), harrisPixelID(r, c-1), -2.0},
		{ir.NodeID(prefix + "_gx_t12"), harrisPixelID(r, c+1), 2.0},
		{ir.NodeID(prefix + "_gx_t20"), harrisPixelID(r+1, c-1), -1.0},
		{ir.NodeID(prefix + "_gx_t22"), harrisPixelID(r+1, c+1), 1.0},
	}

	termIDs := make([]ir.NodeID, 0, len(terms))
	for _, term := range terms {
		g.MustAddNode(ir.NewMulConst(term.id, string(term.id), term.input, term.coef))
		termIDs = append(termIDs, term.id)
	}

	return addHarrisTermChain(g, ir.NodeID(prefix+"_gx"), termIDs)
}

func addHarrisSobelGY(g *ir.Graph, prefix string, r int, c int) ir.NodeID {
	terms := []struct {
		id    ir.NodeID
		input ir.NodeID
		coef  float64
	}{
		{ir.NodeID(prefix + "_gy_t00"), harrisPixelID(r-1, c-1), -1.0},
		{ir.NodeID(prefix + "_gy_t01"), harrisPixelID(r-1, c), -2.0},
		{ir.NodeID(prefix + "_gy_t02"), harrisPixelID(r-1, c+1), -1.0},
		{ir.NodeID(prefix + "_gy_t20"), harrisPixelID(r+1, c-1), 1.0},
		{ir.NodeID(prefix + "_gy_t21"), harrisPixelID(r+1, c), 2.0},
		{ir.NodeID(prefix + "_gy_t22"), harrisPixelID(r+1, c+1), 1.0},
	}

	termIDs := make([]ir.NodeID, 0, len(terms))
	for _, term := range terms {
		g.MustAddNode(ir.NewMulConst(term.id, string(term.id), term.input, term.coef))
		termIDs = append(termIDs, term.id)
	}

	return addHarrisTermChain(g, ir.NodeID(prefix+"_gy"), termIDs)
}

func addHarrisTermChain(g *ir.Graph, finalID ir.NodeID, terms []ir.NodeID) ir.NodeID {
	if len(terms) == 0 {
		panic("cannot add empty Harris term chain")
	}
	if len(terms) == 1 {
		return terms[0]
	}

	current := terms[0]
	for i := 1; i < len(terms); i++ {
		nodeID := ir.NodeID(fmt.Sprintf("%s_s%d", finalID, i))
		if i == len(terms)-1 {
			nodeID = finalID
		}

		g.MustAddNode(ir.NewBinary(nodeID, string(nodeID), ir.OpAdd, current, terms[i]))
		current = nodeID
	}

	return current
}

func harrisPixelID(r int, c int) ir.NodeID {
	return ir.NodeID(fmt.Sprintf("p%d%d", r, c))
}

func harrisSobelAt(s HarrisCornerWindowSample, r int, c int) (gx float64, gy float64) {
	p := s.Pixels

	gx = -p[r-1][c-1] + p[r-1][c+1] -
		2.0*p[r][c-1] + 2.0*p[r][c+1] -
		p[r+1][c-1] + p[r+1][c+1]

	gy = -p[r-1][c-1] - 2.0*p[r-1][c] - p[r-1][c+1] +
		p[r+1][c-1] + 2.0*p[r+1][c] + p[r+1][c+1]

	return gx, gy
}

func newHarrisWindow(fn func(r int, c int) float64) HarrisCornerWindowSample {
	var sample HarrisCornerWindowSample

	for r := 0; r < 5; r++ {
		for c := 0; c < 5; c++ {
			sample.Pixels[r][c] = fn(r, c)
		}
	}

	return sample
}

func scaleHarrisWindow(sample HarrisCornerWindowSample, scale float64) HarrisCornerWindowSample {
	var out HarrisCornerWindowSample

	for r := 0; r < 5; r++ {
		for c := 0; c < 5; c++ {
			out.Pixels[r][c] = sample.Pixels[r][c] * scale
		}
	}

	return out
}
