package runtime

import (
	"fmt"
	"math"

	"github.com/hasslelee/flipguard/internal/ir"
)

// EvalResult contains all node values computed during plain evaluation.
type EvalResult struct {
	Values map[ir.NodeID]float64
	Output float64
}

// EvalPlain evaluates a computation graph over plain floating-point values.
//
// The graph is assumed to be in topological insertion order.
// Input values must be provided by input node ID.
func EvalPlain(g *ir.Graph, inputs map[ir.NodeID]float64) (*EvalResult, error) {
	if g == nil {
		return nil, fmt.Errorf("graph is nil")
	}
	if err := g.Validate(); err != nil {
		return nil, fmt.Errorf("invalid graph: %w", err)
	}

	values := make(map[ir.NodeID]float64)

	for _, n := range g.Nodes() {
		switch n.Op {
		case ir.OpInput:
			v, ok := inputs[n.ID]
			if !ok {
				return nil, fmt.Errorf("missing input value for node %s", n.ID)
			}
			values[n.ID] = v

		case ir.OpConst:
			values[n.ID] = n.Const

		case ir.OpAdd:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a + b

		case ir.OpSub:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a - b

		case ir.OpMul:
			a, b, err := get2(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a * b

		case ir.OpMulConst:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a * n.Const

		case ir.OpPow2:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a * a

		case ir.OpPow3:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = a * a * a

		case ir.OpPoly:
			a, err := get1(values, n)
			if err != nil {
				return nil, err
			}
			values[n.ID] = evalPoly(a, n.Coeffs)

		default:
			return nil, fmt.Errorf("unsupported op %s for node %s", n.Op, n.ID)
		}
	}

	out, ok := values[g.Output]
	if !ok {
		return nil, fmt.Errorf("missing output value for node %s", g.Output)
	}

	return &EvalResult{
		Values: values,
		Output: out,
	}, nil
}

func get1(values map[ir.NodeID]float64, n *ir.Node) (float64, error) {
	if len(n.Inputs) != 1 {
		return 0, fmt.Errorf("node %s expects 1 input, got %d", n.ID, len(n.Inputs))
	}

	v, ok := values[n.Inputs[0]]
	if !ok {
		return 0, fmt.Errorf("node %s input %s has not been evaluated", n.ID, n.Inputs[0])
	}

	return v, nil
}

func get2(values map[ir.NodeID]float64, n *ir.Node) (float64, float64, error) {
	if len(n.Inputs) != 2 {
		return 0, 0, fmt.Errorf("node %s expects 2 inputs, got %d", n.ID, len(n.Inputs))
	}

	a, ok := values[n.Inputs[0]]
	if !ok {
		return 0, 0, fmt.Errorf("node %s input %s has not been evaluated", n.ID, n.Inputs[0])
	}

	b, ok := values[n.Inputs[1]]
	if !ok {
		return 0, 0, fmt.Errorf("node %s input %s has not been evaluated", n.ID, n.Inputs[1])
	}

	return a, b, nil
}

func evalPoly(x float64, coeffs []float64) float64 {
	if len(coeffs) == 0 {
		return 0
	}

	// Horner's method.
	y := coeffs[len(coeffs)-1]
	for i := len(coeffs) - 2; i >= 0; i-- {
		y = y*x + coeffs[i]
	}

	// Avoid negative zero in reports.
	if y == 0 || math.Abs(y) < 1e-18 {
		return 0
	}

	return y
}
