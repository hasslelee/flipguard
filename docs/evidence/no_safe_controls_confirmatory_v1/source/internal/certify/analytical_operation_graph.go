package certify

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"strconv"
	"strings"
)

const analyticalOperationGraphSchemaVersion = 1

const analyticalOperationGraphKind = "ckks_analytical_execution_dag"

const (
	AnalyticalExecutionPathBaselineNonRescale = "baseline_non_rescale"

	AnalyticalExecutionPathRescaleAware = "rescale_aware"
)

// AnalyticalOperationKind identifies one operation relevant to CKKS error
// propagation.
//
// The graph deliberately records operations such as plaintext encoding,
// relinearization, rescaling, and level alignment instead of collapsing them
// into a mathematically equivalent polynomial node.
type AnalyticalOperationKind string

const (
	AnalyticalOpInput AnalyticalOperationKind = "input"

	AnalyticalOpMulModelScalar AnalyticalOperationKind = "mul_model_scalar"

	AnalyticalOpMulFixedScalar AnalyticalOperationKind = "mul_fixed_scalar"

	AnalyticalOpEncodeModelPlaintextAtLevel AnalyticalOperationKind = "encode_model_plaintext_at_level"

	AnalyticalOpEncodeFixedPlaintextAtLevel AnalyticalOperationKind = "encode_fixed_plaintext_at_level"

	AnalyticalOpAddCiphertexts AnalyticalOperationKind = "add_ciphertexts"

	AnalyticalOpAddCiphertextPlaintext AnalyticalOperationKind = "add_ciphertext_plaintext"

	AnalyticalOpMulCiphertexts AnalyticalOperationKind = "mul_ciphertexts"

	AnalyticalOpRelinearize AnalyticalOperationKind = "relinearize"

	AnalyticalOpRescaleToDefault AnalyticalOperationKind = "rescale_to_default"

	AnalyticalOpAlignLevelTo AnalyticalOperationKind = "align_level_to"
)

// AnalyticalOperationNode is one node in an ordered analytical execution DAG.
//
// ModelParameter is a JSON-pointer-like reference into the separately hashed
// model artifact. ScalarBits stores a fixed scalar as canonical IEEE-754
// binary64 hexadecimal bits.
type AnalyticalOperationNode struct {
	ID string `json:"id"`

	Op AnalyticalOperationKind `json:"op"`

	Inputs []string `json:"inputs,omitempty"`

	InputSymbol string `json:"input_symbol,omitempty"`

	ModelParameter string `json:"model_parameter,omitempty"`

	ScalarBits string `json:"scalar_bits,omitempty"`
}

// AnalyticalOperationGraph binds the exact ordered operation sequence used by
// an analytical error derivation.
//
// Model coefficients are referenced rather than duplicated because their
// concrete values are bound separately by ModelArtifactDigest.
type AnalyticalOperationGraph struct {
	SchemaVersion int `json:"schema_version"`

	GraphKind string `json:"graph_kind"`

	ModelType string `json:"model_type"`

	ExecutionPath string `json:"execution_path"`

	Nodes []AnalyticalOperationNode `json:"nodes"`

	OutputNode string `json:"output_node"`
}

// NewAnalyticalOperationGraph creates a graph with defensive copies.
func NewAnalyticalOperationGraph(
	modelType string,
	executionPath string,
	nodes []AnalyticalOperationNode,
	outputNode string,
) AnalyticalOperationGraph {
	copiedNodes := make(
		[]AnalyticalOperationNode,
		len(nodes),
	)

	for index, node := range nodes {
		copiedNodes[index] = node
		copiedNodes[index].Inputs = append(
			[]string(nil),
			node.Inputs...,
		)
	}

	return AnalyticalOperationGraph{
		SchemaVersion: analyticalOperationGraphSchemaVersion,

		GraphKind: analyticalOperationGraphKind,

		ModelType: modelType,

		ExecutionPath: executionPath,

		Nodes: copiedNodes,

		OutputNode: outputNode,
	}
}

// AnalyticalFixedScalarBits returns the canonical binary64 representation of a
// fixed scalar embedded in the operation graph.
func AnalyticalFixedScalarBits(
	value float64,
) (string, error) {
	if math.IsNaN(value) ||
		math.IsInf(value, 0) {
		return "", fmt.Errorf(
			"analytical fixed scalar must be finite",
		)
	}

	if value == 0 {
		value = 0
	}

	return fmt.Sprintf(
		"%016x",
		math.Float64bits(value),
	), nil
}

// Validate enforces a unique, topologically ordered, unambiguous execution DAG.
func (graph AnalyticalOperationGraph) Validate() error {
	if graph.SchemaVersion !=
		analyticalOperationGraphSchemaVersion {
		return fmt.Errorf(
			"unsupported analytical operation-graph schema version %d",
			graph.SchemaVersion,
		)
	}

	if graph.GraphKind !=
		analyticalOperationGraphKind {
		return fmt.Errorf(
			"unsupported analytical operation-graph kind %q",
			graph.GraphKind,
		)
	}

	if err := validateAnalyticalGraphIdentity(
		"model type",
		graph.ModelType,
	); err != nil {
		return err
	}

	switch graph.ExecutionPath {
	case AnalyticalExecutionPathBaselineNonRescale,
		AnalyticalExecutionPathRescaleAware:

	default:
		return fmt.Errorf(
			"unsupported analytical execution path %q",
			graph.ExecutionPath,
		)
	}

	if len(graph.Nodes) == 0 {
		return fmt.Errorf(
			"analytical operation graph has no nodes",
		)
	}

	seenNodes := make(
		map[string]AnalyticalOperationNode,
		len(graph.Nodes),
	)

	seenInputSymbols := make(
		map[string]struct{},
	)

	nodeValueKinds := make(
		map[string]analyticalOperationValueKind,
		len(graph.Nodes),
	)

	for index, node := range graph.Nodes {
		if err := validateAnalyticalGraphIdentity(
			fmt.Sprintf("node %d ID", index),
			node.ID,
		); err != nil {
			return err
		}

		if _, exists := seenNodes[node.ID]; exists {
			return fmt.Errorf(
				"analytical operation graph has duplicate node ID %q",
				node.ID,
			)
		}

		for inputIndex, inputID := range node.Inputs {
			if err := validateAnalyticalGraphIdentity(
				fmt.Sprintf(
					"node %q input %d",
					node.ID,
					inputIndex,
				),
				inputID,
			); err != nil {
				return err
			}

			if _, exists :=
				seenNodes[inputID]; !exists {
				return fmt.Errorf(
					"analytical operation node %q references input %q that is not topologically prior",
					node.ID,
					inputID,
				)
			}
		}

		if err := validateAnalyticalOperationNode(
			node,
			nodeValueKinds,
			seenInputSymbols,
		); err != nil {
			return fmt.Errorf(
				"validate analytical operation node %q: %w",
				node.ID,
				err,
			)
		}

		seenNodes[node.ID] = node
		nodeValueKinds[node.ID] =
			analyticalOperationOutputKind(node.Op)
	}

	if err := validateAnalyticalGraphIdentity(
		"output node",
		graph.OutputNode,
	); err != nil {
		return err
	}

	output, exists :=
		seenNodes[graph.OutputNode]
	if !exists {
		return fmt.Errorf(
			"analytical operation graph output node %q does not exist",
			graph.OutputNode,
		)
	}

	switch output.Op {
	case AnalyticalOpEncodeModelPlaintextAtLevel,
		AnalyticalOpEncodeFixedPlaintextAtLevel:
		return fmt.Errorf(
			"analytical operation graph output %q is a plaintext-encoding node",
			graph.OutputNode,
		)
	}

	return nil
}

// CanonicalJSON returns the deterministic representation used by Digest.
func (graph AnalyticalOperationGraph) CanonicalJSON() (
	[]byte,
	error,
) {
	if err := graph.Validate(); err != nil {
		return nil, err
	}

	encoded, err := json.Marshal(graph)
	if err != nil {
		return nil, fmt.Errorf(
			"marshal analytical operation graph: %w",
			err,
		)
	}

	return encoded, nil
}

// Digest returns the canonical SHA-256 operation-graph digest.
func (graph AnalyticalOperationGraph) Digest() (
	string,
	error,
) {
	canonical, err := graph.CanonicalJSON()
	if err != nil {
		return "", err
	}

	sum := sha256.Sum256(canonical)

	return "sha256:" +
		hex.EncodeToString(sum[:]), nil
}

type analyticalOperationValueKind uint8

const (
	analyticalOperationValueUnknown analyticalOperationValueKind = iota
	analyticalOperationValueCiphertext
	analyticalOperationValuePlaintext
)

func analyticalOperationOutputKind(
	op AnalyticalOperationKind,
) analyticalOperationValueKind {
	switch op {
	case AnalyticalOpEncodeModelPlaintextAtLevel,
		AnalyticalOpEncodeFixedPlaintextAtLevel:
		return analyticalOperationValuePlaintext

	case AnalyticalOpInput,
		AnalyticalOpMulModelScalar,
		AnalyticalOpMulFixedScalar,
		AnalyticalOpAddCiphertexts,
		AnalyticalOpAddCiphertextPlaintext,
		AnalyticalOpMulCiphertexts,
		AnalyticalOpRelinearize,
		AnalyticalOpRescaleToDefault,
		AnalyticalOpAlignLevelTo:
		return analyticalOperationValueCiphertext

	default:
		return analyticalOperationValueUnknown
	}
}

func validateAnalyticalOperationNode(
	node AnalyticalOperationNode,
	nodeValueKinds map[string]analyticalOperationValueKind,
	seenInputSymbols map[string]struct{},
) error {
	switch node.Op {
	case AnalyticalOpInput:
		if err := requireAnalyticalNodeArity(
			node,
			0,
		); err != nil {
			return err
		}

		if err := validateAnalyticalGraphIdentity(
			"input symbol",
			node.InputSymbol,
		); err != nil {
			return err
		}

		if _, exists :=
			seenInputSymbols[node.InputSymbol]; exists {
			return fmt.Errorf(
				"duplicate input symbol %q",
				node.InputSymbol,
			)
		}

		seenInputSymbols[node.InputSymbol] =
			struct{}{}

		if node.ModelParameter != "" ||
			node.ScalarBits != "" {
			return fmt.Errorf(
				"input node must not carry scalar payload",
			)
		}

	case AnalyticalOpMulModelScalar:
		if err := requireAnalyticalNodeArity(
			node,
			1,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := validateAnalyticalModelParameter(
			node.ModelParameter,
		); err != nil {
			return err
		}

		if node.InputSymbol != "" ||
			node.ScalarBits != "" {
			return fmt.Errorf(
				"model-scalar node has incompatible payload",
			)
		}

	case AnalyticalOpEncodeModelPlaintextAtLevel:
		if err := requireAnalyticalNodeArity(
			node,
			1,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := validateAnalyticalModelParameter(
			node.ModelParameter,
		); err != nil {
			return err
		}

		if node.InputSymbol != "" ||
			node.ScalarBits != "" {
			return fmt.Errorf(
				"model-plaintext encoding node has incompatible payload",
			)
		}

	case AnalyticalOpMulFixedScalar:
		if err := requireAnalyticalNodeArity(
			node,
			1,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := validateAnalyticalScalarBits(
			node.ScalarBits,
		); err != nil {
			return err
		}

		if node.InputSymbol != "" ||
			node.ModelParameter != "" {
			return fmt.Errorf(
				"fixed-scalar node has incompatible payload",
			)
		}

	case AnalyticalOpEncodeFixedPlaintextAtLevel:
		if err := requireAnalyticalNodeArity(
			node,
			1,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := validateAnalyticalScalarBits(
			node.ScalarBits,
		); err != nil {
			return err
		}

		if node.InputSymbol != "" ||
			node.ModelParameter != "" {
			return fmt.Errorf(
				"fixed-plaintext encoding node has incompatible payload",
			)
		}

	case AnalyticalOpAddCiphertexts,
		AnalyticalOpMulCiphertexts:
		if err := requireAnalyticalNodeArity(
			node,
			2,
		); err != nil {
			return err
		}

		for inputIndex := range node.Inputs {
			if err := requireAnalyticalInputValueKind(
				node,
				inputIndex,
				nodeValueKinds,
				analyticalOperationValueCiphertext,
			); err != nil {
				return err
			}
		}

		if err := requireAnalyticalNodeNoPayload(
			node,
		); err != nil {
			return err
		}

	case AnalyticalOpAddCiphertextPlaintext:
		if err := requireAnalyticalNodeArity(
			node,
			2,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			1,
			nodeValueKinds,
			analyticalOperationValuePlaintext,
		); err != nil {
			return err
		}

		if err := requireAnalyticalNodeNoPayload(
			node,
		); err != nil {
			return err
		}

	case AnalyticalOpRelinearize,
		AnalyticalOpRescaleToDefault:
		if err := requireAnalyticalNodeArity(
			node,
			1,
		); err != nil {
			return err
		}

		if err := requireAnalyticalInputValueKind(
			node,
			0,
			nodeValueKinds,
			analyticalOperationValueCiphertext,
		); err != nil {
			return err
		}

		if err := requireAnalyticalNodeNoPayload(
			node,
		); err != nil {
			return err
		}

	case AnalyticalOpAlignLevelTo:
		if err := requireAnalyticalNodeArity(
			node,
			2,
		); err != nil {
			return err
		}

		for inputIndex := range node.Inputs {
			if err := requireAnalyticalInputValueKind(
				node,
				inputIndex,
				nodeValueKinds,
				analyticalOperationValueCiphertext,
			); err != nil {
				return err
			}
		}

		if err := requireAnalyticalNodeNoPayload(
			node,
		); err != nil {
			return err
		}

	default:
		return fmt.Errorf(
			"unsupported analytical operation %q",
			node.Op,
		)
	}

	return nil
}

func requireAnalyticalInputValueKind(
	node AnalyticalOperationNode,
	inputIndex int,
	nodeValueKinds map[string]analyticalOperationValueKind,
	expected analyticalOperationValueKind,
) error {
	inputID := node.Inputs[inputIndex]

	actual, exists := nodeValueKinds[inputID]
	if !exists {
		return fmt.Errorf(
			"input %d node %q has no inferred value kind",
			inputIndex,
			inputID,
		)
	}

	if actual != expected {
		return fmt.Errorf(
			"operation %q input %d node %q must be %s; got %s",
			node.Op,
			inputIndex,
			inputID,
			analyticalOperationValueKindName(expected),
			analyticalOperationValueKindName(actual),
		)
	}

	return nil
}

func analyticalOperationValueKindName(
	kind analyticalOperationValueKind,
) string {
	switch kind {
	case analyticalOperationValueCiphertext:
		return "ciphertext"

	case analyticalOperationValuePlaintext:
		return "plaintext"

	default:
		return "unknown"
	}
}

func requireAnalyticalNodeArity(
	node AnalyticalOperationNode,
	expected int,
) error {
	if len(node.Inputs) != expected {
		return fmt.Errorf(
			"operation %q has %d inputs; expected %d",
			node.Op,
			len(node.Inputs),
			expected,
		)
	}

	return nil
}

func requireAnalyticalNodeNoPayload(
	node AnalyticalOperationNode,
) error {
	if node.InputSymbol != "" ||
		node.ModelParameter != "" ||
		node.ScalarBits != "" {
		return fmt.Errorf(
			"operation %q must not carry scalar payload",
			node.Op,
		)
	}

	return nil
}

func validateAnalyticalGraphIdentity(
	name string,
	value string,
) error {
	if value == "" {
		return fmt.Errorf(
			"analytical operation graph %s is empty",
			name,
		)
	}

	if strings.TrimSpace(value) != value {
		return fmt.Errorf(
			"analytical operation graph %s %q has surrounding whitespace",
			name,
			value,
		)
	}

	return nil
}

func validateAnalyticalModelParameter(
	value string,
) error {
	if err := validateAnalyticalGraphIdentity(
		"model parameter",
		value,
	); err != nil {
		return err
	}

	if !strings.HasPrefix(value, "/") {
		return fmt.Errorf(
			"analytical model parameter %q is not an absolute artifact reference",
			value,
		)
	}

	return nil
}

func validateAnalyticalScalarBits(
	value string,
) error {
	if len(value) != 16 ||
		strings.ToLower(value) != value {
		return fmt.Errorf(
			"analytical scalar bits %q must be 16 lowercase hexadecimal digits",
			value,
		)
	}

	bitsValue, err := strconv.ParseUint(
		value,
		16,
		64,
	)
	if err != nil {
		return fmt.Errorf(
			"parse analytical scalar bits %q: %w",
			value,
			err,
		)
	}

	if bitsValue == uint64(1)<<63 {
		return fmt.Errorf(
			"analytical scalar bits must normalize negative zero",
		)
	}

	scalar := math.Float64frombits(bitsValue)

	if math.IsNaN(scalar) ||
		math.IsInf(scalar, 0) {
		return fmt.Errorf(
			"analytical scalar bits encode a non-finite value",
		)
	}

	return nil
}
