package benchmarks

import (
	"fmt"

	"github.com/hasslelee/flipguard/internal/ir"
)

const (
	CNNLiteInputSide  = 4
	CNNLiteFilterSide = 2
	CNNLiteFilters    = 4
	CNNLiteConvSide   = 3
)

// CNNLiteSquareModel is the learned scalar graph used by the predeclared
// MNIST 0-vs-1 holdout. Pooling is input materialization, not part of the
// encrypted graph.
type CNNLiteSquareModel struct {
	FilterWeights [CNNLiteFilters][CNNLiteFilterSide][CNNLiteFilterSide]float64
	FilterBias    [CNNLiteFilters]float64
	OutputWeights [CNNLiteFilters][CNNLiteConvSide][CNNLiteConvSide]float64
	OutputBias    float64
}

// CNNLiteSquareSample contains one 4x4 mean-pooled MNIST image.
type CNNLiteSquareSample struct {
	Pixels [CNNLiteInputSide][CNNLiteInputSide]float64
}

// Inputs returns the stable IR input mapping.
func (s CNNLiteSquareSample) Inputs() map[ir.NodeID]float64 {
	values := make(
		map[ir.NodeID]float64,
		CNNLiteInputSide*CNNLiteInputSide,
	)
	for row := 0; row < CNNLiteInputSide; row++ {
		for column := 0; column < CNNLiteInputSide; column++ {
			id := ir.NodeID(fmt.Sprintf("pool%d%d", row, column))
			values[id] = s.Pixels[row][column]
		}
	}
	return values
}

// NewCNNLiteSquareGraph builds the exact learned convolution/square/linear
// score graph. Every 2x2 kernel is shared across its nine spatial positions.
func NewCNNLiteSquareGraph(model CNNLiteSquareModel) *ir.Graph {
	graph := ir.NewGraph()
	for row := 0; row < CNNLiteInputSide; row++ {
		for column := 0; column < CNNLiteInputSide; column++ {
			id := ir.NodeID(fmt.Sprintf("pool%d%d", row, column))
			graph.MustAddNode(ir.NewInput(id, string(id)))
		}
	}

	outputTerms := make([]ir.NodeID, 0, CNNLiteFilters*CNNLiteConvSide*CNNLiteConvSide)
	for filter := 0; filter < CNNLiteFilters; filter++ {
		for row := 0; row < CNNLiteConvSide; row++ {
			for column := 0; column < CNNLiteConvSide; column++ {
				prefix := fmt.Sprintf("f%d_r%d_c%d", filter, row, column)
				terms := make([]ir.NodeID, 0, 4)
				for kernelRow := 0; kernelRow < CNNLiteFilterSide; kernelRow++ {
					for kernelColumn := 0; kernelColumn < CNNLiteFilterSide; kernelColumn++ {
						input := ir.NodeID(fmt.Sprintf(
							"pool%d%d",
							row+kernelRow,
							column+kernelColumn,
						))
						term := ir.NodeID(fmt.Sprintf(
							"%s_k%d%d",
							prefix,
							kernelRow,
							kernelColumn,
						))
						graph.MustAddNode(ir.NewMulConst(
							term,
							string(term),
							input,
							model.FilterWeights[filter][kernelRow][kernelColumn],
						))
						terms = append(terms, term)
					}
				}
				sum := addCNNLiteTermChain(graph, prefix+"_conv_sum", terms)
				bias := ir.NodeID(prefix + "_bias")
				hidden := ir.NodeID(prefix + "_hidden")
				squared := ir.NodeID(prefix + "_square")
				outputTerm := ir.NodeID(prefix + "_output")
				graph.MustAddNode(ir.NewConst(
					bias,
					string(bias),
					model.FilterBias[filter],
				))
				graph.MustAddNode(ir.NewBinary(
					hidden,
					string(hidden),
					ir.OpAdd,
					sum,
					bias,
				))
				graph.MustAddNode(ir.NewUnary(
					squared,
					string(squared),
					ir.OpPow2,
					hidden,
				))
				graph.MustAddNode(ir.NewMulConst(
					outputTerm,
					string(outputTerm),
					squared,
					model.OutputWeights[filter][row][column],
				))
				outputTerms = append(outputTerms, outputTerm)
			}
		}
	}
	outputSum := addCNNLiteTermChain(
		graph,
		"output_sum",
		outputTerms,
	)
	outputBias := ir.NodeID("output_bias")
	score := ir.NodeID("score")
	graph.MustAddNode(ir.NewConst(
		outputBias,
		string(outputBias),
		model.OutputBias,
	))
	graph.MustAddNode(ir.NewBinary(
		score,
		"CNN-lite binary score",
		ir.OpAdd,
		outputSum,
		outputBias,
	))
	graph.MustSetOutput(score)
	return graph
}

// CNNLiteSquareScore evaluates the same learned graph in floating point.
func CNNLiteSquareScore(
	sample CNNLiteSquareSample,
	model CNNLiteSquareModel,
) float64 {
	score := model.OutputBias
	for filter := 0; filter < CNNLiteFilters; filter++ {
		for row := 0; row < CNNLiteConvSide; row++ {
			for column := 0; column < CNNLiteConvSide; column++ {
				hidden := model.FilterBias[filter]
				for kernelRow := 0; kernelRow < CNNLiteFilterSide; kernelRow++ {
					for kernelColumn := 0; kernelColumn < CNNLiteFilterSide; kernelColumn++ {
						hidden += model.FilterWeights[filter][kernelRow][kernelColumn] *
							sample.Pixels[row+kernelRow][column+kernelColumn]
					}
				}
				score += model.OutputWeights[filter][row][column] *
					hidden * hidden
			}
		}
	}
	return score
}

func addCNNLiteTermChain(
	graph *ir.Graph,
	prefix string,
	terms []ir.NodeID,
) ir.NodeID {
	if len(terms) == 0 {
		panic("CNN-lite term chain is empty")
	}
	current := terms[0]
	for index := 1; index < len(terms); index++ {
		next := ir.NodeID(fmt.Sprintf("%s_%d", prefix, index))
		graph.MustAddNode(ir.NewBinary(
			next,
			string(next),
			ir.OpAdd,
			current,
			terms[index],
		))
		current = next
	}
	return current
}
