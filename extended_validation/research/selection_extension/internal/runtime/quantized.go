package runtime

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

// PrecisionBits is the number of fractional bits used for dyadic quantization.
//
// A value b means:
//
//	step = 2^{-b}
//
// For example:
//   - b = 4  -> step = 1/16
//   - b = 8  -> step = 1/256
//   - b = 16 -> step = 1/65536
type PrecisionBits int

// PrecisionSchedule maps node IDs to precision bits.
//
// If a node is absent from the schedule, its value is not quantized.
type PrecisionSchedule map[ir.NodeID]PrecisionBits

// QuantizedEvalResult contains all node values computed during quantized evaluation.
type QuantizedEvalResult struct {
	Values map[ir.NodeID]float64
	Output float64

	Schedule PrecisionSchedule
}

// StepFromBits returns the dyadic quantization step Δ = 2^{-bits}.
func StepFromBits(bits PrecisionBits) float64 {
	return math.Pow(2, -float64(bits))
}

// QuantizeToBits quantizes x to the nearest dyadic grid point with the given bits.
//
// Q_Δ(x) = Δ * round(x / Δ)
func QuantizeToBits(x float64, bits PrecisionBits) float64 {
	step := StepFromBits(bits)
	if step <= 0 {
		return x
	}

	q := step * math.Round(x/step)

	if q == 0 || math.Abs(q) < 1e-18 {
		return 0
	}

	return q
}

// EvalQuantized evaluates a graph and applies node-wise dyadic quantization.
//
// The graph is evaluated in topological insertion order.
// If schedule contains a node ID, that node's computed value is quantized.
func EvalQuantized(g *ir.Graph, inputs map[ir.NodeID]float64, schedule PrecisionSchedule) (*QuantizedEvalResult, error) {
	if g == nil {
		return nil, fmt.Errorf("graph is nil")
	}
	if err := g.Validate(); err != nil {
		return nil, fmt.Errorf("invalid graph: %w", err)
	}
	if schedule == nil {
		schedule = PrecisionSchedule{}
	}

	values := make(map[ir.NodeID]float64)

	for _, n := range g.Nodes() {
		var value float64

		switch n.Op {
		case ir.OpInput:
			v, ok := inputs[n.ID]
			if !ok {
				return nil, fmt.Errorf("missing input value for node %s", n.ID)
			}
			value = v

		case ir.OpConst:
			value = n.Const

		case ir.OpAdd:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			value = a + b

		case ir.OpSub:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			value = a - b

		case ir.OpMul:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			value = a * b

		case ir.OpMulConst:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			value = a * n.Const

		case ir.OpPow2:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			value = a * a

		case ir.OpPow3:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			value = a * a * a

		case ir.OpPoly:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			value = evalPoly(a, n.Coeffs)

		default:
			return nil, fmt.Errorf("unsupported op %s for node %s", n.Op, n.ID)
		}

		if bits, ok := schedule[n.ID]; ok {
			value = QuantizeToBits(value, bits)
		}

		values[n.ID] = value
	}

	out, ok := values[g.Output]
	if !ok {
		return nil, fmt.Errorf("missing output value for node %s", g.Output)
	}

	return &QuantizedEvalResult{
		Values:   values,
		Output:   out,
		Schedule: schedule,
	}, nil
}
