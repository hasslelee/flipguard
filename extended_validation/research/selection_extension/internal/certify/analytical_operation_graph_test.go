package certify

import (
	"math"
	"strings"
	"testing"
)

func TestAnalyticalOperationGraphMatchesVersion1GoldenVector(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	got, err := graph.Digest()
	if err != nil {
		t.Fatalf(
			"operation-graph digest failed: %v",
			err,
		)
	}

	const expected = "sha256:" +
		"239b0a4efcacb497c1f1d44278dc8787" +
		"b4c8c8a490f7e0d30e85c598edccbb01"

	if got != expected {
		t.Fatalf(
			"operation-graph schema-v1 digest changed: got %s, expected %s",
			got,
			expected,
		)
	}
}

func TestAnalyticalOperationGraphDigestIsDeterministic(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	first, err := graph.Digest()
	if err != nil {
		t.Fatalf(
			"first operation-graph digest failed: %v",
			err,
		)
	}

	second, err := graph.Digest()
	if err != nil {
		t.Fatalf(
			"second operation-graph digest failed: %v",
			err,
		)
	}

	if first != second {
		t.Fatalf(
			"operation-graph digest is not deterministic: %s != %s",
			first,
			second,
		)
	}
}

func TestAnalyticalOperationGraphDigestChangesWithExecutionPath(
	t *testing.T,
) {
	first := testAnalyticalOperationGraph(t)
	second := testAnalyticalOperationGraph(t)

	second.ExecutionPath =
		AnalyticalExecutionPathRescaleAware

	requireDifferentOperationGraphDigest(
		t,
		first,
		second,
		"execution path",
	)
}

func TestAnalyticalOperationGraphDigestChangesWithModelReference(
	t *testing.T,
) {
	first := testAnalyticalOperationGraph(t)
	second := testAnalyticalOperationGraph(t)

	second.Nodes[1].ModelParameter =
		"/scaled_model_for_ckks/weights/1"

	requireDifferentOperationGraphDigest(
		t,
		first,
		second,
		"model parameter reference",
	)
}

func TestAnalyticalOperationGraphDigestChangesWithFixedScalar(
	t *testing.T,
) {
	first := testAnalyticalOperationGraph(t)
	second := testAnalyticalOperationGraph(t)

	second.Nodes[4].ScalarBits =
		mustAnalyticalScalarBits(t, 0.198)

	requireDifferentOperationGraphDigest(
		t,
		first,
		second,
		"fixed scalar",
	)
}

func TestAnalyticalOperationGraphDigestChangesWithDependency(
	t *testing.T,
) {
	first := testAnalyticalOperationGraph(t)
	second := testAnalyticalOperationGraph(t)

	second.Nodes[4].Inputs =
		[]string{"wx0"}

	requireDifferentOperationGraphDigest(
		t,
		first,
		second,
		"operation dependency",
	)
}

func TestAnalyticalOperationGraphRejectsForwardReference(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	graph.Nodes[0], graph.Nodes[1] =
		graph.Nodes[1], graph.Nodes[0]

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected forward reference to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"not topologically prior",
	) {
		t.Fatalf(
			"unexpected forward-reference error: %v",
			err,
		)
	}
}

func TestAnalyticalOperationGraphRejectsDuplicateInputSymbol(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	graph.Nodes = append(
		graph.Nodes,
		AnalyticalOperationNode{
			ID:          "x1",
			Op:          AnalyticalOpInput,
			InputSymbol: "x_0",
		},
	)

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected duplicate input symbol to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"duplicate input symbol",
	) {
		t.Fatalf(
			"unexpected duplicate-input error: %v",
			err,
		)
	}
}

func TestAnalyticalOperationGraphRejectsInvalidPlaintextAddition(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	graph.Nodes[3].Inputs =
		[]string{
			"wx0",
			"wx0",
		}

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected invalid plaintext addition to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"must be plaintext; got ciphertext",
	) {
		t.Fatalf(
			"unexpected plaintext-input error: %v",
			err,
		)
	}
}

func TestAnalyticalOperationGraphRejectsNonFiniteScalarBits(
	t *testing.T,
) {
	graph := testAnalyticalOperationGraph(t)

	graph.Nodes[4].ScalarBits =
		"7ff0000000000000"

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected infinite fixed scalar to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"non-finite",
	) {
		t.Fatalf(
			"unexpected non-finite scalar error: %v",
			err,
		)
	}
}

func TestAnalyticalFixedScalarBitsNormalizesNegativeZero(
	t *testing.T,
) {
	positive, err :=
		AnalyticalFixedScalarBits(0)
	if err != nil {
		t.Fatalf(
			"positive zero conversion failed: %v",
			err,
		)
	}

	negative, err :=
		AnalyticalFixedScalarBits(
			math.Copysign(0, -1),
		)
	if err != nil {
		t.Fatalf(
			"negative zero conversion failed: %v",
			err,
		)
	}

	if positive !=
		"0000000000000000" {
		t.Fatalf(
			"unexpected positive-zero bits %q",
			positive,
		)
	}

	if positive != negative {
		t.Fatalf(
			"positive and negative zero produced different scalar bits: %s != %s",
			positive,
			negative,
		)
	}
}

func TestNewAnalyticalOperationGraphDefensivelyCopiesNodes(
	t *testing.T,
) {
	nodes := []AnalyticalOperationNode{
		{
			ID:          "x0",
			Op:          AnalyticalOpInput,
			InputSymbol: "x_0",
		},
		{
			ID:     "square",
			Op:     AnalyticalOpMulCiphertexts,
			Inputs: []string{"x0", "x0"},
		},
	}

	graph := NewAnalyticalOperationGraph(
		"test_model",
		AnalyticalExecutionPathBaselineNonRescale,
		nodes,
		"square",
	)

	before, err := graph.Digest()
	if err != nil {
		t.Fatalf(
			"digest before source mutation failed: %v",
			err,
		)
	}

	nodes[0].ID = "mutated"
	nodes[1].Inputs[0] = "mutated"

	after, err := graph.Digest()
	if err != nil {
		t.Fatalf(
			"digest after source mutation failed: %v",
			err,
		)
	}

	if before != after {
		t.Fatalf(
			"source mutation changed defensive graph copy: %s != %s",
			before,
			after,
		)
	}

	if graph.Nodes[0].ID != "x0" {
		t.Fatalf(
			"node ID was not defensively copied: %q",
			graph.Nodes[0].ID,
		)
	}

	if graph.Nodes[1].Inputs[0] != "x0" {
		t.Fatalf(
			"node inputs were not defensively copied: %q",
			graph.Nodes[1].Inputs[0],
		)
	}
}

func testAnalyticalOperationGraph(
	t *testing.T,
) AnalyticalOperationGraph {
	t.Helper()

	return NewAnalyticalOperationGraph(
		"linear_poly3",
		AnalyticalExecutionPathBaselineNonRescale,
		[]AnalyticalOperationNode{
			{
				ID:          "x0",
				Op:          AnalyticalOpInput,
				InputSymbol: "x_0",
			},
			{
				ID:     "wx0",
				Op:     AnalyticalOpMulModelScalar,
				Inputs: []string{"x0"},

				ModelParameter: "/scaled_model_for_ckks/weights/0",
			},
			{
				ID: "bias_pt",

				Op: AnalyticalOpEncodeModelPlaintextAtLevel,

				Inputs: []string{"wx0"},

				ModelParameter: "/scaled_model_for_ckks/bias",
			},
			{
				ID: "z",

				Op: AnalyticalOpAddCiphertextPlaintext,

				Inputs: []string{
					"wx0",
					"bias_pt",
				},
			},
			{
				ID:     "y_linear",
				Op:     AnalyticalOpMulFixedScalar,
				Inputs: []string{"z"},

				ScalarBits: mustAnalyticalScalarBits(
					t,
					0.197,
				),
			},
			{
				ID: "y_bias_pt",

				Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

				Inputs: []string{"y_linear"},

				ScalarBits: mustAnalyticalScalarBits(
					t,
					0.5,
				),
			},
			{
				ID: "y",

				Op: AnalyticalOpAddCiphertextPlaintext,

				Inputs: []string{
					"y_linear",
					"y_bias_pt",
				},
			},
		},
		"y",
	)
}

func mustAnalyticalScalarBits(
	t *testing.T,
	value float64,
) string {
	t.Helper()

	bits, err :=
		AnalyticalFixedScalarBits(value)
	if err != nil {
		t.Fatalf(
			"convert analytical scalar %.12g: %v",
			value,
			err,
		)
	}

	return bits
}

func requireDifferentOperationGraphDigest(
	t *testing.T,
	first AnalyticalOperationGraph,
	second AnalyticalOperationGraph,
	changedField string,
) {
	t.Helper()

	firstDigest, err := first.Digest()
	if err != nil {
		t.Fatalf(
			"first digest for %s failed: %v",
			changedField,
			err,
		)
	}

	secondDigest, err := second.Digest()
	if err != nil {
		t.Fatalf(
			"second digest for %s failed: %v",
			changedField,
			err,
		)
	}

	if firstDigest == secondDigest {
		t.Fatalf(
			"%s change did not alter operation-graph digest",
			changedField,
		)
	}
}

func TestAnalyticalOperationGraphRejectsPlaintextCiphertextMultiply(
	t *testing.T,
) {
	scalarBits :=
		mustAnalyticalScalarBits(t, 0.5)

	graph := NewAnalyticalOperationGraph(
		"invalid_value_flow",
		AnalyticalExecutionPathBaselineNonRescale,
		[]AnalyticalOperationNode{
			{
				ID:          "x0",
				Op:          AnalyticalOpInput,
				InputSymbol: "x_0",
			},
			{
				ID: "plain",

				Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

				Inputs: []string{"x0"},

				ScalarBits: scalarBits,
			},
			{
				ID: "bad_multiply",

				Op: AnalyticalOpMulFixedScalar,

				Inputs: []string{"plain"},

				ScalarBits: scalarBits,
			},
		},
		"bad_multiply",
	)

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected plaintext-as-ciphertext input to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"must be ciphertext; got plaintext",
	) {
		t.Fatalf(
			"unexpected plaintext value-flow error: %v",
			err,
		)
	}
}

func TestAnalyticalOperationGraphRejectsCiphertextPlaintextPosition(
	t *testing.T,
) {
	graph := NewAnalyticalOperationGraph(
		"invalid_value_flow",
		AnalyticalExecutionPathBaselineNonRescale,
		[]AnalyticalOperationNode{
			{
				ID:          "x0",
				Op:          AnalyticalOpInput,
				InputSymbol: "x_0",
			},
			{
				ID:          "x1",
				Op:          AnalyticalOpInput,
				InputSymbol: "x_1",
			},
			{
				ID: "bad_add",

				Op: AnalyticalOpAddCiphertextPlaintext,

				Inputs: []string{
					"x0",
					"x1",
				},
			},
		},
		"bad_add",
	)

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected ciphertext in plaintext position to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"must be plaintext; got ciphertext",
	) {
		t.Fatalf(
			"unexpected ciphertext value-flow error: %v",
			err,
		)
	}
}

func TestAnalyticalOperationGraphRejectsPlaintextAlignmentTarget(
	t *testing.T,
) {
	scalarBits :=
		mustAnalyticalScalarBits(t, 0.5)

	graph := NewAnalyticalOperationGraph(
		"invalid_value_flow",
		AnalyticalExecutionPathRescaleAware,
		[]AnalyticalOperationNode{
			{
				ID:          "x0",
				Op:          AnalyticalOpInput,
				InputSymbol: "x_0",
			},
			{
				ID: "plain",

				Op: AnalyticalOpEncodeFixedPlaintextAtLevel,

				Inputs: []string{"x0"},

				ScalarBits: scalarBits,
			},
			{
				ID: "bad_align",

				Op: AnalyticalOpAlignLevelTo,

				Inputs: []string{
					"x0",
					"plain",
				},
			},
		},
		"bad_align",
	)

	err := graph.Validate()
	if err == nil {
		t.Fatal(
			"expected plaintext alignment target to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"must be ciphertext; got plaintext",
	) {
		t.Fatalf(
			"unexpected alignment value-flow error: %v",
			err,
		)
	}
}
