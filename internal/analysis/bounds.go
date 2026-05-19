package analysis

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
)

// Interval represents an observed value range for one node.
type Interval struct {
	Low  float64
	High float64
}

// MaxAbs returns max(|Low|, |High|).
func (iv Interval) MaxAbs() float64 {
	a := math.Abs(iv.Low)
	b := math.Abs(iv.High)
	if a > b {
		return a
	}
	return b
}

// Width returns High - Low.
func (iv Interval) Width() float64 {
	return iv.High - iv.Low
}

// BoundSensitivityResult stores interval bounds and output sensitivities.
type BoundSensitivityResult struct {
	Intervals   map[ir.NodeID]Interval
	Sensitivity map[ir.NodeID]float64

	Outputs []float64
	Margins []float64

	ProtectedMargin     float64
	ProtectedPercentile float64
}

// AnalyzeBoundsAndSensitivity computes observed node intervals from samples
// and propagates interval-based output sensitivity over the computation graph.
//
// The samples are plaintext calibration inputs.
// Sensitivity S_v is an upper bound on how much a local error at node v
// can affect the final output.
func AnalyzeBoundsAndSensitivity(
	g *ir.Graph,
	samples []map[ir.NodeID]float64,
	threshold float64,
	protectedPercentile float64,
) (*BoundSensitivityResult, error) {
	if g == nil {
		return nil, fmt.Errorf("graph is nil")
	}
	if err := g.Validate(); err != nil {
		return nil, fmt.Errorf("invalid graph: %w", err)
	}
	if len(samples) == 0 {
		return nil, fmt.Errorf("samples are empty")
	}
	if protectedPercentile <= 0 || protectedPercentile > 1 {
		protectedPercentile = 0.05
	}

	intervals := make(map[ir.NodeID]Interval)
	outputs := make([]float64, 0, len(samples))
	margins := make([]float64, 0, len(samples))

	for _, sample := range samples {
		result, err := fgruntime.EvalPlain(g, sample)
		if err != nil {
			return nil, fmt.Errorf("plain evaluation failed: %w", err)
		}

		outputs = append(outputs, result.Output)
		margins = append(margins, math.Abs(result.Output-threshold))

		for id, value := range result.Values {
			updateInterval(intervals, id, value)
		}
	}

	sortedMargins := make([]float64, len(margins))
	copy(sortedMargins, margins)
	sortFloat64s(sortedMargins)

	protectedMargin := percentileSorted(sortedMargins, protectedPercentile)

	sensitivity, err := propagateSensitivity(g, intervals)
	if err != nil {
		return nil, err
	}

	return &BoundSensitivityResult{
		Intervals:           intervals,
		Sensitivity:         sensitivity,
		Outputs:             outputs,
		Margins:             margins,
		ProtectedMargin:     protectedMargin,
		ProtectedPercentile: protectedPercentile,
	}, nil
}

func updateInterval(intervals map[ir.NodeID]Interval, id ir.NodeID, value float64) {
	iv, ok := intervals[id]
	if !ok {
		intervals[id] = Interval{
			Low:  value,
			High: value,
		}
		return
	}

	if value < iv.Low {
		iv.Low = value
	}
	if value > iv.High {
		iv.High = value
	}
	intervals[id] = iv
}

func propagateSensitivity(g *ir.Graph, intervals map[ir.NodeID]Interval) (map[ir.NodeID]float64, error) {
	sensitivity := make(map[ir.NodeID]float64)

	for _, n := range g.Nodes() {
		sensitivity[n.ID] = 0
	}

	sensitivity[g.Output] = 1.0

	nodes := g.Nodes()
	for i := len(nodes) - 1; i >= 0; i-- {
		n := nodes[i]
		sOut := sensitivity[n.ID]

		if sOut == 0 {
			continue
		}

		switch n.Op {
		case ir.OpInput, ir.OpConst:
			// Leaf nodes do not propagate sensitivity further.

		case ir.OpAdd:
			a := n.Inputs[0]
			b := n.Inputs[1]
			sensitivity[a] += sOut
			sensitivity[b] += sOut

		case ir.OpSub:
			a := n.Inputs[0]
			b := n.Inputs[1]
			sensitivity[a] += sOut
			sensitivity[b] += sOut

		case ir.OpMulConst:
			a := n.Inputs[0]
			sensitivity[a] += math.Abs(n.Const) * sOut

		case ir.OpMul:
			a := n.Inputs[0]
			b := n.Inputs[1]

			ivA, ok := intervals[a]
			if !ok {
				return nil, fmt.Errorf("missing interval for node %s", a)
			}
			ivB, ok := intervals[b]
			if !ok {
				return nil, fmt.Errorf("missing interval for node %s", b)
			}

			sensitivity[a] += ivB.MaxAbs() * sOut
			sensitivity[b] += ivA.MaxAbs() * sOut

		case ir.OpPow2:
			a := n.Inputs[0]

			ivA, ok := intervals[a]
			if !ok {
				return nil, fmt.Errorf("missing interval for node %s", a)
			}

			sensitivity[a] += 2.0 * ivA.MaxAbs() * sOut

		case ir.OpPow3:
			a := n.Inputs[0]

			ivA, ok := intervals[a]
			if !ok {
				return nil, fmt.Errorf("missing interval for node %s", a)
			}

			maxAbs := ivA.MaxAbs()
			sensitivity[a] += 3.0 * maxAbs * maxAbs * sOut

		case ir.OpPoly:
			a := n.Inputs[0]

			ivA, ok := intervals[a]
			if !ok {
				return nil, fmt.Errorf("missing interval for node %s", a)
			}

			derivBound := maxAbsPolyDerivative(n.Coeffs, ivA)
			sensitivity[a] += derivBound * sOut

		default:
			return nil, fmt.Errorf("unsupported op for sensitivity propagation: %s", n.Op)
		}
	}

	return sensitivity, nil
}

func maxAbsPolyDerivative(coeffs []float64, iv Interval) float64 {
	if len(coeffs) <= 1 {
		return 0
	}

	candidates := []float64{
		iv.Low,
		iv.High,
	}

	// For cubic polynomial c0 + c1*x + c2*x^2 + c3*x^3,
	// derivative is c1 + 2*c2*x + 3*c3*x^2.
	// Its critical point is x = -c2 / (3*c3), if c3 != 0.
	if len(coeffs) == 4 {
		c2 := coeffs[2]
		c3 := coeffs[3]
		if c3 != 0 {
			x := -c2 / (3.0 * c3)
			if x >= iv.Low && x <= iv.High {
				candidates = append(candidates, x)
			}
		}
	} else if len(coeffs) > 4 {
		// Generic fallback for higher-degree polynomials.
		// This is conservative enough for the first prototype but can be
		// replaced by a tighter interval polynomial derivative bound later.
		const grid = 64
		width := iv.High - iv.Low
		if width > 0 {
			for i := 1; i < grid; i++ {
				x := iv.Low + width*float64(i)/float64(grid)
				candidates = append(candidates, x)
			}
		}
	}

	maxAbs := 0.0
	for _, x := range candidates {
		v := math.Abs(evalPolyDerivative(coeffs, x))
		if v > maxAbs {
			maxAbs = v
		}
	}

	return maxAbs
}

func evalPolyDerivative(coeffs []float64, x float64) float64 {
	if len(coeffs) <= 1 {
		return 0
	}

	sum := 0.0
	pow := 1.0

	for i := 1; i < len(coeffs); i++ {
		sum += float64(i) * coeffs[i] * pow
		pow *= x
	}

	return sum
}
