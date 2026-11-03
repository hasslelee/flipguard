package ir

// NodeID is a stable identifier for a node in the computation graph.
type NodeID string

// Node represents a program point in the encrypted inference computation graph.
//
// The fields are intentionally simple at this stage.
//   - Input nodes use OpInput and no inputs.
//   - Const nodes use OpConst and Const.
//   - MulConst nodes use one input and Const.
//   - Poly nodes use one input and Coeffs, where
//     Coeffs[i] is the coefficient for x^i.
type Node struct {
	ID     NodeID
	Name   string
	Op     OpType
	Inputs []NodeID
	Const  float64
	Coeffs []float64
}

// NewInput creates an input node.
func NewInput(id NodeID, name string) *Node {
	return &Node{
		ID:   id,
		Name: name,
		Op:   OpInput,
	}
}

// NewConst creates a constant node.
func NewConst(id NodeID, name string, value float64) *Node {
	return &Node{
		ID:    id,
		Name:  name,
		Op:    OpConst,
		Const: value,
	}
}

// NewUnary creates a unary operation node.
func NewUnary(id NodeID, name string, op OpType, input NodeID) *Node {
	return &Node{
		ID:     id,
		Name:   name,
		Op:     op,
		Inputs: []NodeID{input},
	}
}

// NewBinary creates a binary operation node.
func NewBinary(id NodeID, name string, op OpType, left NodeID, right NodeID) *Node {
	return &Node{
		ID:     id,
		Name:   name,
		Op:     op,
		Inputs: []NodeID{left, right},
	}
}

// NewMulConst creates a multiplication-by-constant node.
func NewMulConst(id NodeID, name string, input NodeID, c float64) *Node {
	return &Node{
		ID:     id,
		Name:   name,
		Op:     OpMulConst,
		Inputs: []NodeID{input},
		Const:  c,
	}
}

// NewPoly creates a polynomial node.
//
// For example,
//
//	c0 + c1*x + c2*x^2 + c3*x^3
//
// is represented as:
//
//	Coeffs = []float64{c0, c1, c2, c3}
func NewPoly(id NodeID, name string, input NodeID, coeffs []float64) *Node {
	copied := make([]float64, len(coeffs))
	copy(copied, coeffs)

	return &Node{
		ID:     id,
		Name:   name,
		Op:     OpPoly,
		Inputs: []NodeID{input},
		Coeffs: copied,
	}
}
