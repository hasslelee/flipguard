package certify

import (
	"fmt"
	"math"
)

// BuildTabularLinearPoly3OperationGraph builds the exact analytical execution
// DAG corresponding to the current generic tabular backend for model_type
// linear_poly3.
//
// modelBias is used only to reproduce the backend branch that omits bias
// encoding and addition when bias == 0. The concrete bias and weight values are
// bound separately through ModelArtifactDigest.
func BuildTabularLinearPoly3OperationGraph(
	inputDim int,
	modelBias float64,
	executionPath string,
) (
	AnalyticalOperationGraph,
	error,
) {
	if inputDim <= 0 {
		return AnalyticalOperationGraph{}, fmt.Errorf(
			"linear_poly3 input dimension must be positive",
		)
	}

	if math.IsNaN(modelBias) ||
		math.IsInf(modelBias, 0) {
		return AnalyticalOperationGraph{}, fmt.Errorf(
			"linear_poly3 model bias must be finite",
		)
	}

	nodes := make(
		[]AnalyticalOperationNode,
		0,
		3*inputDim+16,
	)

	var accumulatorID string

	for featureIndex := 0; featureIndex < inputDim; featureIndex++ {
		inputID := fmt.Sprintf(
			"input_%d",
			featureIndex,
		)

		weightedID := fmt.Sprintf(
			"weighted_input_%d",
			featureIndex,
		)

		nodes = append(
			nodes,
			AnalyticalOperationNode{
				ID: inputID,
				Op: AnalyticalOpInput,

				InputSymbol: fmt.Sprintf(
					"x_%d",
					featureIndex,
				),
			},
			AnalyticalOperationNode{
				ID: weightedID,

				Op: AnalyticalOpMulModelScalar,

				Inputs: []string{
					inputID,
				},

				ModelParameter: fmt.Sprintf(
					"/scaled_model_for_ckks/weights/%d",
					featureIndex,
				),
			},
		)

		if accumulatorID == "" {
			accumulatorID = weightedID
			continue
		}

		sumID := fmt.Sprintf(
			"weighted_sum_%d",
			featureIndex,
		)

		nodes = append(
			nodes,
			AnalyticalOperationNode{
				ID: sumID,

				Op: AnalyticalOpAddCiphertexts,

				Inputs: []string{
					accumulatorID,
					weightedID,
				},
			},
		)

		accumulatorID = sumID
	}

	zID := accumulatorID

	if modelBias != 0 {
		const biasPlaintextID = "model_bias_plaintext"

		const biasedOutputID = "z"

		nodes = append(
			nodes,
			AnalyticalOperationNode{
				ID: biasPlaintextID,

				Op: AnalyticalOpEncodeModelPlaintextAtLevel,

				Inputs: []string{
					accumulatorID,
				},

				ModelParameter: "/scaled_model_for_ckks/bias",
			},
			AnalyticalOperationNode{
				ID: biasedOutputID,

				Op: AnalyticalOpAddCiphertextPlaintext,

				Inputs: []string{
					accumulatorID,
					biasPlaintextID,
				},
			},
		)

		zID = biasedOutputID
	}

	switch executionPath {
	case AnalyticalExecutionPathBaselineNonRescale:
		var err error

		nodes, err =
			appendLinearPoly3BaselineOutputGraph(
				nodes,
				zID,
			)
		if err != nil {
			return AnalyticalOperationGraph{}, err
		}

	case AnalyticalExecutionPathRescaleAware:
		var err error

		nodes, err =
			appendLinearPoly3RescaleOutputGraph(
				nodes,
				zID,
			)
		if err != nil {
			return AnalyticalOperationGraph{}, err
		}

	default:
		return AnalyticalOperationGraph{}, fmt.Errorf(
			"unsupported linear_poly3 execution path %q",
			executionPath,
		)
	}

	graph := NewAnalyticalOperationGraph(
		"linear_poly3",
		executionPath,
		nodes,
		"score",
	)

	if err := graph.Validate(); err != nil {
		return AnalyticalOperationGraph{}, fmt.Errorf(
			"validate linear_poly3 analytical graph: %w",
			err,
		)
	}

	return graph, nil
}

func appendLinearPoly3BaselineOutputGraph(
	nodes []AnalyticalOperationNode,
	zID string,
) (
	[]AnalyticalOperationNode,
	error,
) {
	linearBits, err :=
		AnalyticalFixedScalarBits(0.197)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 linear coefficient: %w",
			err,
		)
	}

	cubicBits, err :=
		AnalyticalFixedScalarBits(-0.004)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 cubic coefficient: %w",
			err,
		)
	}

	biasBits, err :=
		AnalyticalFixedScalarBits(0.5)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 output bias: %w",
			err,
		)
	}

	nodes = append(
		nodes,
		AnalyticalOperationNode{
			ID: "z_squared_product",

			Op: AnalyticalOpMulCiphertexts,

			Inputs: []string{
				zID,
				zID,
			},
		},
		AnalyticalOperationNode{
			ID: "z_squared",

			Op: AnalyticalOpRelinearize,

			Inputs: []string{
				"z_squared_product",
			},
		},
		AnalyticalOperationNode{
			ID: "z_cubed_product",

			Op: AnalyticalOpMulCiphertexts,

			Inputs: []string{
				"z_squared",
				zID,
			},
		},
		AnalyticalOperationNode{
			ID: "z_cubed",

			Op: AnalyticalOpRelinearize,

			Inputs: []string{
				"z_cubed_product",
			},
		},
		AnalyticalOperationNode{
			ID: "linear_term",

			Op: AnalyticalOpMulFixedScalar,

			Inputs: []string{
				zID,
			},

			ScalarBits: linearBits,
		},
		AnalyticalOperationNode{
			ID: "cubic_term",

			Op: AnalyticalOpMulFixedScalar,

			Inputs: []string{
				"z_cubed",
			},

			ScalarBits: cubicBits,
		},
		AnalyticalOperationNode{
			ID: "polynomial_terms",

			Op: AnalyticalOpAddCiphertexts,

			Inputs: []string{
				"linear_term",
				"cubic_term",
			},
		},
		AnalyticalOperationNode{
			ID: "output_bias_plaintext",

			Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

			Inputs: []string{
				"polynomial_terms",
			},

			ScalarBits: biasBits,
		},
		AnalyticalOperationNode{
			ID: "score",

			Op: AnalyticalOpAddCiphertextPlaintext,

			Inputs: []string{
				"polynomial_terms",
				"output_bias_plaintext",
			},
		},
	)

	return nodes, nil
}

func appendLinearPoly3RescaleOutputGraph(
	nodes []AnalyticalOperationNode,
	zID string,
) (
	[]AnalyticalOperationNode,
	error,
) {
	linearBits, err :=
		AnalyticalFixedScalarBits(0.197)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 linear coefficient: %w",
			err,
		)
	}

	cubicBits, err :=
		AnalyticalFixedScalarBits(-0.004)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 cubic coefficient: %w",
			err,
		)
	}

	biasBits, err :=
		AnalyticalFixedScalarBits(0.5)
	if err != nil {
		return nil, fmt.Errorf(
			"encode linear_poly3 output bias: %w",
			err,
		)
	}

	nodes = append(
		nodes,
		AnalyticalOperationNode{
			ID: "z_squared_product",

			Op: AnalyticalOpMulCiphertexts,

			Inputs: []string{
				zID,
				zID,
			},
		},
		AnalyticalOperationNode{
			ID: "z_squared_relinearized",

			Op: AnalyticalOpRelinearize,

			Inputs: []string{
				"z_squared_product",
			},
		},
		AnalyticalOperationNode{
			ID: "z_squared",

			Op: AnalyticalOpRescaleToDefault,

			Inputs: []string{
				"z_squared_relinearized",
			},
		},
		AnalyticalOperationNode{
			ID: "cubic_inner_term",

			Op: AnalyticalOpMulFixedScalar,

			Inputs: []string{
				"z_squared",
			},

			ScalarBits: cubicBits,
		},
		AnalyticalOperationNode{
			ID: "linear_coefficient_plaintext",

			Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

			Inputs: []string{
				"cubic_inner_term",
			},

			ScalarBits: linearBits,
		},
		AnalyticalOperationNode{
			ID: "horner_inner",

			Op: AnalyticalOpAddCiphertextPlaintext,

			Inputs: []string{
				"cubic_inner_term",
				"linear_coefficient_plaintext",
			},
		},
		AnalyticalOperationNode{
			ID: "z_aligned",

			Op: AnalyticalOpAlignLevelTo,

			Inputs: []string{
				zID,
				"horner_inner",
			},
		},
		AnalyticalOperationNode{
			ID: "horner_product",

			Op: AnalyticalOpMulCiphertexts,

			Inputs: []string{
				"horner_inner",
				"z_aligned",
			},
		},
		AnalyticalOperationNode{
			ID: "horner_relinearized",

			Op: AnalyticalOpRelinearize,

			Inputs: []string{
				"horner_product",
			},
		},
		AnalyticalOperationNode{
			ID: "polynomial_terms",

			Op: AnalyticalOpRescaleToDefault,

			Inputs: []string{
				"horner_relinearized",
			},
		},
		AnalyticalOperationNode{
			ID: "output_bias_plaintext",

			Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

			Inputs: []string{
				"polynomial_terms",
			},

			ScalarBits: biasBits,
		},
		AnalyticalOperationNode{
			ID: "score",

			Op: AnalyticalOpAddCiphertextPlaintext,

			Inputs: []string{
				"polynomial_terms",
				"output_bias_plaintext",
			},
		},
	)

	return nodes, nil
}
