package analyticalv2

import (
	"math"
	"math/rand"
	"strings"
	"testing"

	"github.com/hasslelee/flipguard/internal/certify"
)

const testDigest = "sha256:" +
	"0123456789abcdef0123456789abcdef" +
	"0123456789abcdef0123456789abcdef"

func TestConditionalDerivationBuildsReplayableProof(
	t *testing.T,
) {
	graph, scalars, assumptions :=
		testDerivationInputs(
			t,
			SourceDeterministicAbsolute,
		)

	derivation, err := Build(
		testDigest,
		graph,
		scalars,
		assumptions,
	)
	if err != nil {
		t.Fatalf(
			"build derivation: %v",
			err,
		)
	}
	if !derivation.CertificateEligible {
		t.Fatalf(
			"deterministic derivation unexpectedly blocked: %v",
			derivation.BlockReasons,
		)
	}
	if derivation.Guarantee !=
		certify.AnalyticalGuaranteeDeterministic {
		t.Fatalf(
			"unexpected guarantee %q",
			derivation.Guarantee,
		)
	}
	if derivation.MaxErrorBound <= 0 {
		t.Fatal(
			"expected a positive propagated error bound",
		)
	}

	proof, err := derivation.Proof()
	if err != nil {
		t.Fatalf(
			"promote proof: %v",
			err,
		)
	}
	if proof.MaxErrorBound !=
		derivation.MaxErrorBound {
		t.Fatal(
			"proof bound does not match derivation",
		)
	}
	if err := proof.Validate(); err != nil {
		t.Fatalf(
			"proof validation failed: %v",
			err,
		)
	}

	first, err := derivation.Digest()
	if err != nil {
		t.Fatalf(
			"first digest: %v",
			err,
		)
	}
	second, err := derivation.Digest()
	if err != nil {
		t.Fatalf(
			"second digest: %v",
			err,
		)
	}
	if first != second {
		t.Fatalf(
			"derivation digest is not deterministic: %s != %s",
			first,
			second,
		)
	}
}

func TestDiagnosticPrimitiveCannotProduceProof(
	t *testing.T,
) {
	graph, scalars, assumptions :=
		testDerivationInputs(
			t,
			SourceDeterministicAbsolute,
		)
	assumptions[0].SourceKind =
		SourceStdDevDiagnostic

	derivation, err := Build(
		testDigest,
		graph,
		scalars,
		assumptions,
	)
	if err != nil {
		t.Fatalf(
			"build diagnostic derivation: %v",
			err,
		)
	}
	if derivation.CertificateEligible {
		t.Fatal(
			"standard-deviation diagnostic became certificate eligible",
		)
	}
	if len(derivation.BlockReasons) != 1 ||
		!strings.Contains(
			derivation.BlockReasons[0],
			"STANDARD_DEVIATION_DIAGNOSTIC",
		) {
		t.Fatalf(
			"unexpected block reasons: %v",
			derivation.BlockReasons,
		)
	}

	_, err = derivation.Proof()
	if err == nil {
		t.Fatal(
			"expected diagnostic proof promotion to fail",
		)
	}
}

func TestProbabilisticPrimitiveUsesUnionBound(
	t *testing.T,
) {
	graph, scalars, assumptions :=
		testDerivationInputs(
			t,
			SourceProbabilisticAbsolute,
		)
	for index := range assumptions {
		assumptions[index].FailureProbability =
			1e-12
	}

	derivation, err := Build(
		testDigest,
		graph,
		scalars,
		assumptions,
	)
	if err != nil {
		t.Fatalf(
			"build probabilistic derivation: %v",
			err,
		)
	}
	if derivation.Guarantee !=
		certify.AnalyticalGuaranteeProbabilistic {
		t.Fatalf(
			"unexpected guarantee %q",
			derivation.Guarantee,
		)
	}

	expected := float64(
		len(assumptions),
	) * 1e-12
	if derivation.FailureProbability < expected {
		t.Fatalf(
			"outward union bound %.17g is below exact sum %.17g",
			derivation.FailureProbability,
			expected,
		)
	}

	proof, err := derivation.Proof()
	if err != nil {
		t.Fatalf(
			"promote probabilistic proof: %v",
			err,
		)
	}
	if proof.FailureProbability !=
		derivation.FailureProbability {
		t.Fatal(
			"proof probability mismatch",
		)
	}
}

func TestAssumptionOrderFailsClosed(
	t *testing.T,
) {
	graph, scalars, assumptions :=
		testDerivationInputs(
			t,
			SourceDeterministicAbsolute,
		)
	assumptions[0], assumptions[1] =
		assumptions[1], assumptions[0]

	_, err := Build(
		testDigest,
		graph,
		scalars,
		assumptions,
	)
	if err == nil {
		t.Fatal(
			"expected reordered assumptions to fail",
		)
	}
	if !strings.Contains(
		err.Error(),
		"expected",
	) {
		t.Fatalf(
			"unexpected assumption-order error: %v",
			err,
		)
	}
}

func TestStoredEnvelopeMutationFailsReplay(
	t *testing.T,
) {
	graph, scalars, assumptions :=
		testDerivationInputs(
			t,
			SourceDeterministicAbsolute,
		)
	derivation, err := Build(
		testDigest,
		graph,
		scalars,
		assumptions,
	)
	if err != nil {
		t.Fatalf(
			"build derivation: %v",
			err,
		)
	}

	derivation.NodeEnvelopes[len(derivation.NodeEnvelopes)-1].
		ErrorAbsBound += 1e-9

	err = derivation.Validate()
	if err == nil {
		t.Fatal(
			"expected stored-envelope mutation to fail",
		)
	}
}

func TestOutwardArithmeticRejectsOverflow(
	t *testing.T,
) {
	graph := certify.NewAnalyticalOperationGraph(
		"overflow_test",
		certify.AnalyticalExecutionPathRescaleAware,
		[]certify.AnalyticalOperationNode{
			{
				ID:          "left",
				Op:          certify.AnalyticalOpInput,
				InputSymbol: "x_0",
			},
			{
				ID:          "right",
				Op:          certify.AnalyticalOpInput,
				InputSymbol: "x_1",
			},
			{
				ID:     "score",
				Op:     certify.AnalyticalOpMulCiphertexts,
				Inputs: []string{"left", "right"},
			},
		},
		"score",
	)

	assumptions := []NodeAssumption{
		testAssumption("left", SourceDeterministicAbsolute),
		testAssumption("right", SourceDeterministicAbsolute),
		testAssumption("score", SourceDeterministicAbsolute),
	}
	assumptions[0].InputExactAbsBound =
		math.MaxFloat64
	assumptions[1].InputExactAbsBound = 2

	_, err := Build(
		testDigest,
		graph,
		nil,
		assumptions,
	)
	if err == nil {
		t.Fatal(
			"expected overflow to fail closed",
		)
	}
	if !strings.Contains(
		err.Error(),
		"must be finite",
	) {
		t.Fatalf(
			"unexpected overflow error: %v",
			err,
		)
	}
}

func TestLinearPoly3DerivationBoundsRandomPerturbations(
	t *testing.T,
) {
	random := rand.New(
		rand.NewSource(20260730),
	)

	graph, err :=
		certify.BuildTabularLinearPoly3OperationGraph(
			1,
			0,
			certify.AnalyticalExecutionPathRescaleAware,
		)
	if err != nil {
		t.Fatalf(
			"build property-test graph: %v",
			err,
		)
	}

	for caseIndex := 0; caseIndex < 2000; caseIndex++ {
		exactInput := random.Float64()*8 - 4
		inputErrorBound := random.Float64() * 0.02
		inputDelta := randomSignedWithin(
			random,
			inputErrorBound,
		)

		exactWeight := random.Float64()*4 - 2
		coefficientErrorBound :=
			random.Float64() * 0.00002
		weightDelta := randomSignedWithin(
			random,
			coefficientErrorBound,
		)
		linearDelta := randomSignedWithin(
			random,
			coefficientErrorBound,
		)
		cubicDelta := randomSignedWithin(
			random,
			coefficientErrorBound,
		)
		outputBiasDelta := randomSignedWithin(
			random,
			coefficientErrorBound,
		)

		weightBits, err :=
			certify.AnalyticalFixedScalarBits(
				exactWeight,
			)
		if err != nil {
			t.Fatalf(
				"case %d encode weight: %v",
				caseIndex,
				err,
			)
		}

		assumptions := make(
			[]NodeAssumption,
			len(graph.Nodes),
		)
		for index, node := range graph.Nodes {
			assumption := testAssumption(
				node.ID,
				SourceDeterministicAbsolute,
			)
			switch node.Op {
			case certify.AnalyticalOpInput:
				assumption.InputExactAbsBound =
					math.Abs(exactInput)
				assumption.InputErrorAbsBound =
					inputErrorBound

			case certify.AnalyticalOpMulModelScalar,
				certify.AnalyticalOpMulFixedScalar,
				certify.AnalyticalOpEncodeModelPlaintextAtLevel,
				certify.AnalyticalOpEncodeFixedPlaintextAtLevel:
				assumption.CoefficientEncodingAbsBound =
					coefficientErrorBound
			}
			assumptions[index] = assumption
		}

		derivation, err := Build(
			testDigest,
			graph,
			[]ModelScalar{
				{
					Reference: "/scaled_model_for_ckks/weights/0",
					ValueBits: weightBits,
				},
			},
			assumptions,
		)
		if err != nil {
			t.Fatalf(
				"case %d build derivation: %v",
				caseIndex,
				err,
			)
		}

		exactZ := exactWeight * exactInput
		approxZ :=
			(exactWeight + weightDelta) *
				(exactInput + inputDelta)

		exactScore :=
			0.5 +
				0.197*exactZ -
				0.004*exactZ*exactZ*exactZ
		approxScore :=
			(0.5 + outputBiasDelta) +
				(0.197+linearDelta)*approxZ +
				(-0.004+cubicDelta)*
					approxZ*approxZ*approxZ

		actualError := math.Abs(
			approxScore - exactScore,
		)
		if actualError >
			derivation.MaxErrorBound {
			t.Fatalf(
				"case %d actual error %.17g exceeds derived bound %.17g",
				caseIndex,
				actualError,
				derivation.MaxErrorBound,
			)
		}
	}
}

func testDerivationInputs(
	t *testing.T,
	source BoundSourceKind,
) (
	certify.AnalyticalOperationGraph,
	[]ModelScalar,
	[]NodeAssumption,
) {
	t.Helper()

	graph, err :=
		certify.BuildTabularLinearPoly3OperationGraph(
			1,
			0,
			certify.AnalyticalExecutionPathRescaleAware,
		)
	if err != nil {
		t.Fatalf(
			"build test graph: %v",
			err,
		)
	}

	weightBits, err :=
		certify.AnalyticalFixedScalarBits(0.8)
	if err != nil {
		t.Fatalf(
			"encode weight bits: %v",
			err,
		)
	}

	scalars := []ModelScalar{
		{
			Reference: "/scaled_model_for_ckks/weights/0",
			ValueBits: weightBits,
		},
	}

	assumptions := make(
		[]NodeAssumption,
		len(graph.Nodes),
	)
	for index, node := range graph.Nodes {
		assumption := testAssumption(
			node.ID,
			source,
		)

		switch node.Op {
		case certify.AnalyticalOpInput:
			assumption.InputExactAbsBound = 1.2
			assumption.InputErrorAbsBound = 0.01

		case certify.AnalyticalOpMulModelScalar,
			certify.AnalyticalOpMulFixedScalar,
			certify.AnalyticalOpEncodeModelPlaintextAtLevel,
			certify.AnalyticalOpEncodeFixedPlaintextAtLevel:
			assumption.CoefficientEncodingAbsBound =
				0.00001
			assumption.OperationResidualAbsBound =
				0.000001

		default:
			assumption.OperationResidualAbsBound =
				0.000001
		}

		assumptions[index] = assumption
	}

	return graph, scalars, assumptions
}

func testAssumption(
	nodeID string,
	source BoundSourceKind,
) NodeAssumption {
	return NodeAssumption{
		NodeID:       nodeID,
		SourceKind:   source,
		SourceDigest: testDigest,
	}
}

func randomSignedWithin(
	random *rand.Rand,
	bound float64,
) float64 {
	return (2*random.Float64() - 1) * bound
}
