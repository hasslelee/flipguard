package ir

// OpType represents the operation type of an IR node.
type OpType string

const (
	OpInput    OpType = "input"
	OpConst    OpType = "const"
	OpAdd      OpType = "add"
	OpSub      OpType = "sub"
	OpMul      OpType = "mul"
	OpMulConst OpType = "mul_const"
	OpPow2     OpType = "pow2"
	OpPow3     OpType = "pow3"
	OpPoly     OpType = "poly"
)

func (op OpType) String() string {
	return string(op)
}
