package certify

import (
	"math"
	"strings"
	"testing"
)

func TestBuildTabularLinearPoly3BaselineMatchesBackendSequence(
	t *testing.T,
) {
	graph, err :=
		BuildTabularLinearPoly3OperationGraph(
			2,
			-0.25,
			AnalyticalExecutionPathBaselineNonRescale,
		)
	if err != nil {
		t.Fatalf(
			"build baseline linear_poly3 graph: %v",
			err,
		)
	}

	requireOperationSequence(
		t,
		graph,
		[]AnalyticalOperationKind{
			AnalyticalOpInput,
			AnalyticalOpMulModelScalar,
			AnalyticalOpInput,
			AnalyticalOpMulModelScalar,
			AnalyticalOpAddCiphertexts,
			AnalyticalOpEncodeModelPlaintextAtLevel,
			AnalyticalOpAddCiphertextPlaintext,
			AnalyticalOpMulCiphertexts,
			AnalyticalOpRelinearize,
			AnalyticalOpMulCiphertexts,
			AnalyticalOpRelinearize,
			AnalyticalOpMulFixedScalar,
			AnalyticalOpMulFixedScalar,
			AnalyticalOpAddCiphertexts,
			AnalyticalOpEncodeFixedPlaintextAtLevel,
			AnalyticalOpAddCiphertextPlaintext,
		},
	)

	if graph.OutputNode != "score" {
		t.Fatalf(
			"unexpected baseline output node %q",
			graph.OutputNode,
		)
	}

	requireNodeInputs(
		t,
		graph,
		"z_cubed_product",
		[]string{
			"z_squared",
			"z",
		},
	)
}

func TestBuildTabularLinearPoly3RescaleMatchesBackendSequence(
	t *testing.T,
) {
	graph, err :=
		BuildTabularLinearPoly3OperationGraph(
			2,
			-0.25,
			AnalyticalExecutionPathRescaleAware,
		)
	if err != nil {
		t.Fatalf(
			"build rescale linear_poly3 graph: %v",
			err,
		)
	}

	requireOperationSequence(
		t,
		graph,
		[]AnalyticalOperationKind{
			AnalyticalOpInput,
			AnalyticalOpMulModelScalar,
			AnalyticalOpInput,
			AnalyticalOpMulModelScalar,
			AnalyticalOpAddCiphertexts,
			AnalyticalOpEncodeModelPlaintextAtLevel,
			AnalyticalOpAddCiphertextPlaintext,
			AnalyticalOpMulCiphertexts,
			AnalyticalOpRelinearize,
			AnalyticalOpRescaleToDefault,
			AnalyticalOpMulFixedScalar,
			AnalyticalOpEncodeFixedPlaintextAtLevel,
			AnalyticalOpAddCiphertextPlaintext,
			AnalyticalOpAlignLevelTo,
			AnalyticalOpMulCiphertexts,
			AnalyticalOpRelinearize,
			AnalyticalOpRescaleToDefault,
			AnalyticalOpEncodeFixedPlaintextAtLevel,
			AnalyticalOpAddCiphertextPlaintext,
		},
	)

	requireNodeInputs(
		t,
		graph,
		"z_aligned",
		[]string{
			"z",
			"horner_inner",
		},
	)

	requireNodeInputs(
		t,
		graph,
		"horner_product",
		[]string{
			"horner_inner",
			"z_aligned",
		},
	)
}

func TestBuildTabularLinearPoly3OmitsZeroModelBias(
	t *testing.T,
) {
	graph, err :=
		BuildTabularLinearPoly3OperationGraph(
			1,
			0,
			AnalyticalExecutionPathBaselineNonRescale,
		)
	if err != nil {
		t.Fatalf(
			"build zero-bias linear_poly3 graph: %v",
			err,
		)
	}

	for _, node := range graph.Nodes {
		if node.ID == "model_bias_plaintext" ||
			node.ID == "z" {
			t.Fatalf(
				"zero-bias graph unexpectedly contains node %q",
				node.ID,
			)
		}
	}

	requireNodeInputs(
		t,
		graph,
		"z_squared_product",
		[]string{
			"weighted_input_0",
			"weighted_input_0",
		},
	)
}

func TestBuildTabularLinearPoly3UsesOrderedModelReferences(
	t *testing.T,
) {
	graph, err :=
		BuildTabularLinearPoly3OperationGraph(
			3,
			1,
			AnalyticalExecutionPathBaselineNonRescale,
		)
	if err != nil {
		t.Fatalf(
			"build model-reference graph: %v",
			err,
		)
	}

	for index := 0; index < 3; index++ {
		node := requireOperationNode(
			t,
			graph,
			"weighted_input_"+
				string(rune('0'+index)),
		)

		expected :=
			"/scaled_model_for_ckks/weights/" +
				string(rune('0'+index))

		if node.ModelParameter != expected {
			t.Fatalf(
				"weight %d model reference: got %q, expected %q",
				index,
				node.ModelParameter,
				expected,
			)
		}
	}

	biasNode := requireOperationNode(
		t,
		graph,
		"model_bias_plaintext",
	)

	if biasNode.ModelParameter !=
		"/scaled_model_for_ckks/bias" {
		t.Fatalf(
			"unexpected bias model reference %q",
			biasNode.ModelParameter,
		)
	}
}

func TestBuildTabularLinearPoly3PathsHaveDifferentDigests(
	t *testing.T,
) {
	baseline, err :=
		BuildTabularLinearPoly3OperationGraph(
			4,
			-0.1,
			AnalyticalExecutionPathBaselineNonRescale,
		)
	if err != nil {
		t.Fatalf(
			"build baseline graph: %v",
			err,
		)
	}

	rescale, err :=
		BuildTabularLinearPoly3OperationGraph(
			4,
			-0.1,
			AnalyticalExecutionPathRescaleAware,
		)
	if err != nil {
		t.Fatalf(
			"build rescale graph: %v",
			err,
		)
	}

	baselineDigest, err :=
		baseline.Digest()
	if err != nil {
		t.Fatalf(
			"digest baseline graph: %v",
			err,
		)
	}

	rescaleDigest, err :=
		rescale.Digest()
	if err != nil {
		t.Fatalf(
			"digest rescale graph: %v",
			err,
		)
	}

	if baselineDigest == rescaleDigest {
		t.Fatal(
			"baseline and rescale graphs produced identical digests",
		)
	}
}

func TestBuildTabularLinearPoly3RejectsInvalidInputDimension(
	t *testing.T,
) {
	for _, inputDim := range []int{
		0,
		-1,
	} {
		_, err :=
			BuildTabularLinearPoly3OperationGraph(
				inputDim,
				0,
				AnalyticalExecutionPathBaselineNonRescale,
			)

		if err == nil {
			t.Fatalf(
				"expected input dimension %d to fail",
				inputDim,
			)
		}

		if !strings.Contains(
			err.Error(),
			"input dimension must be positive",
		) {
			t.Fatalf(
				"unexpected input-dimension error: %v",
				err,
			)
		}
	}
}

func TestBuildTabularLinearPoly3RejectsNonFiniteBias(
	t *testing.T,
) {
	for _, bias := range []float64{
		math.NaN(),
		math.Inf(1),
		math.Inf(-1),
	} {
		_, err :=
			BuildTabularLinearPoly3OperationGraph(
				1,
				bias,
				AnalyticalExecutionPathBaselineNonRescale,
			)

		if err == nil {
			t.Fatalf(
				"expected non-finite bias %v to fail",
				bias,
			)
		}

		if !strings.Contains(
			err.Error(),
			"model bias must be finite",
		) {
			t.Fatalf(
				"unexpected non-finite-bias error: %v",
				err,
			)
		}
	}
}

func TestBuildTabularLinearPoly3RejectsUnsupportedPath(
	t *testing.T,
) {
	_, err :=
		BuildTabularLinearPoly3OperationGraph(
			1,
			0,
			"unknown_path",
		)

	if err == nil {
		t.Fatal(
			"expected unsupported path to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"unsupported linear_poly3 execution path",
	) {
		t.Fatalf(
			"unexpected execution-path error: %v",
			err,
		)
	}
}

func requireOperationSequence(
	t *testing.T,
	graph AnalyticalOperationGraph,
	expected []AnalyticalOperationKind,
) {
	t.Helper()

	if len(graph.Nodes) != len(expected) {
		t.Fatalf(
			"operation count: got %d, expected %d",
			len(graph.Nodes),
			len(expected),
		)
	}

	for index, expectedOperation := range expected {
		if graph.Nodes[index].Op !=
			expectedOperation {
			t.Fatalf(
				"operation %d: got %q, expected %q",
				index,
				graph.Nodes[index].Op,
				expectedOperation,
			)
		}
	}
}

func requireNodeInputs(
	t *testing.T,
	graph AnalyticalOperationGraph,
	nodeID string,
	expected []string,
) {
	t.Helper()

	node := requireOperationNode(
		t,
		graph,
		nodeID,
	)

	if len(node.Inputs) != len(expected) {
		t.Fatalf(
			"node %q input count: got %d, expected %d",
			nodeID,
			len(node.Inputs),
			len(expected),
		)
	}

	for index, expectedInput := range expected {
		if node.Inputs[index] !=
			expectedInput {
			t.Fatalf(
				"node %q input %d: got %q, expected %q",
				nodeID,
				index,
				node.Inputs[index],
				expectedInput,
			)
		}
	}
}

func requireOperationNode(
	t *testing.T,
	graph AnalyticalOperationGraph,
	nodeID string,
) AnalyticalOperationNode {
	t.Helper()

	for _, node := range graph.Nodes {
		if node.ID == nodeID {
			return node
		}
	}

	t.Fatalf(
		"operation node %q not found",
		nodeID,
	)

	return AnalyticalOperationNode{}
}

func TestBuildTabularLinearPoly3MatchesVersion1GoldenDigests(
	t *testing.T,
) {
	testCases := []struct {
		name     string
		path     string
		expected string
	}{
		{
			name:     "baseline",
			path:     AnalyticalExecutionPathBaselineNonRescale,
			expected: "sha256:1a1e64847d3887fb5ec1a753f9920fe320fe86ba146b31649459579dcb135f8a",
		},
		{
			name:     "rescale",
			path:     AnalyticalExecutionPathRescaleAware,
			expected: "sha256:84b55e61a5cfe96ff1fd079c0d4901d8d59bda92947caf8cd971a54c86b6b045",
		},
	}

	for _, testCase := range testCases {
		t.Run(
			testCase.name,
			func(t *testing.T) {
				graph, err :=
					BuildTabularLinearPoly3OperationGraph(
						4,
						-1,
						testCase.path,
					)
				if err != nil {
					t.Fatalf(
						"build graph: %v",
						err,
					)
				}

				got, err := graph.Digest()
				if err != nil {
					t.Fatalf(
						"digest graph: %v",
						err,
					)
				}

				if got != testCase.expected {
					t.Fatalf(
						"linear_poly3 schema-v1 %s digest changed: got %s, expected %s",
						testCase.name,
						got,
						testCase.expected,
					)
				}
			},
		)
	}
}

func TestBuildTabularLinearPoly3SupportsMultiDigitFeatureIndex(
	t *testing.T,
) {
	graph, err :=
		BuildTabularLinearPoly3OperationGraph(
			12,
			1,
			AnalyticalExecutionPathBaselineNonRescale,
		)
	if err != nil {
		t.Fatalf(
			"build twelve-feature graph: %v",
			err,
		)
	}

	inputNode := requireOperationNode(
		t,
		graph,
		"input_10",
	)

	if inputNode.InputSymbol != "x_10" {
		t.Fatalf(
			"feature 10 input symbol: got %q, expected %q",
			inputNode.InputSymbol,
			"x_10",
		)
	}

	weightNode := requireOperationNode(
		t,
		graph,
		"weighted_input_10",
	)

	if weightNode.ModelParameter !=
		"/scaled_model_for_ckks/weights/10" {
		t.Fatalf(
			"feature 10 model reference: got %q",
			weightNode.ModelParameter,
		)
	}

	requireNodeInputs(
		t,
		graph,
		"weighted_sum_10",
		[]string{
			"weighted_sum_9",
			"weighted_input_10",
		},
	)
}
