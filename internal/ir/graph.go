package ir

import (
	"fmt"
)

// Graph represents a computation graph for CKKS-based encrypted inference.
//
// Nodes are stored in insertion order. For the first prototype, we assume
// the graph is built in topological order.
type Graph struct {
	nodes  []*Node
	byID   map[NodeID]*Node
	Output NodeID
}

// NewGraph creates an empty graph.
func NewGraph() *Graph {
	return &Graph{
		nodes: make([]*Node, 0),
		byID:  make(map[NodeID]*Node),
	}
}

// AddNode adds a node to the graph.
func (g *Graph) AddNode(n *Node) error {
	if n == nil {
		return fmt.Errorf("cannot add nil node")
	}
	if n.ID == "" {
		return fmt.Errorf("node ID cannot be empty")
	}
	if _, exists := g.byID[n.ID]; exists {
		return fmt.Errorf("duplicate node ID: %s", n.ID)
	}

	g.nodes = append(g.nodes, n)
	g.byID[n.ID] = n
	return nil
}

// MustAddNode adds a node and panics if it fails.
// This is useful for small benchmark graph construction.
func (g *Graph) MustAddNode(n *Node) {
	if err := g.AddNode(n); err != nil {
		panic(err)
	}
}

// SetOutput sets the graph output node.
func (g *Graph) SetOutput(id NodeID) error {
	if _, exists := g.byID[id]; !exists {
		return fmt.Errorf("output node does not exist: %s", id)
	}
	g.Output = id
	return nil
}

// MustSetOutput sets the graph output node and panics if it fails.
func (g *Graph) MustSetOutput(id NodeID) {
	if err := g.SetOutput(id); err != nil {
		panic(err)
	}
}

// Node returns a node by ID.
func (g *Graph) Node(id NodeID) (*Node, bool) {
	n, ok := g.byID[id]
	return n, ok
}

// Nodes returns nodes in insertion order.
func (g *Graph) Nodes() []*Node {
	out := make([]*Node, len(g.nodes))
	copy(out, g.nodes)
	return out
}

// Len returns the number of nodes in the graph.
func (g *Graph) Len() int {
	return len(g.nodes)
}

// Validate checks basic graph consistency.
func (g *Graph) Validate() error {
	if len(g.nodes) == 0 {
		return fmt.Errorf("graph has no nodes")
	}
	if g.Output == "" {
		return fmt.Errorf("graph output is not set")
	}
	if _, exists := g.byID[g.Output]; !exists {
		return fmt.Errorf("output node does not exist: %s", g.Output)
	}

	for _, n := range g.nodes {
		switch n.Op {
		case OpInput, OpConst:
			if len(n.Inputs) != 0 {
				return fmt.Errorf("node %s (%s) should not have inputs", n.ID, n.Op)
			}

		case OpPow2, OpPow3, OpMulConst, OpPoly:
			if len(n.Inputs) != 1 {
				return fmt.Errorf("node %s (%s) should have exactly one input", n.ID, n.Op)
			}

		case OpAdd, OpSub, OpMul:
			if len(n.Inputs) != 2 {
				return fmt.Errorf("node %s (%s) should have exactly two inputs", n.ID, n.Op)
			}

		default:
			return fmt.Errorf("node %s has unsupported op: %s", n.ID, n.Op)
		}

		for _, inputID := range n.Inputs {
			if _, exists := g.byID[inputID]; !exists {
				return fmt.Errorf("node %s references missing input %s", n.ID, inputID)
			}
		}
	}

	return nil
}
