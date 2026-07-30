package analyticalv2

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
)

const (
	derivationSchemaVersion = 1
	derivationMethod        = "conditional_ckks_operation_graph_envelope"
	derivationVersion       = "v2"
)

// BoundSourceKind distinguishes absolute primitive bounds from diagnostics
// that must never be promoted to an analytical certificate.
type BoundSourceKind string

const (
	SourceDeterministicAbsolute BoundSourceKind = "DETERMINISTIC_ABSOLUTE_BOUND"
	SourceProbabilisticAbsolute BoundSourceKind = "PROBABILISTIC_ABSOLUTE_BOUND"
	SourceEmpiricalDiagnostic   BoundSourceKind = "EMPIRICAL_DIAGNOSTIC"
	SourceStdDevDiagnostic      BoundSourceKind = "STANDARD_DEVIATION_DIAGNOSTIC"
)

// Envelope bounds an exact scalar and the error of its approximate value.
type Envelope struct {
	ExactAbsBound float64 `json:"exact_abs_bound"`
	ErrorAbsBound float64 `json:"error_abs_bound"`
}

// ModelScalar binds the binary64 value used for a model-parameter reference.
// The model artifact remains the authority; this value makes the arithmetic
// derivation independently replayable.
type ModelScalar struct {
	Reference string `json:"reference"`
	ValueBits string `json:"value_bits"`
}

// NodeAssumption supplies every primitive bound used at one graph node.
//
// Input nodes use InputExactAbsBound and InputErrorAbsBound. Scalar multiply
// and plaintext-encoding nodes use CoefficientEncodingAbsBound. Every
// non-input operation may use OperationResidualAbsBound. Fields that do not
// apply to a node must be zero.
type NodeAssumption struct {
	NodeID string `json:"node_id"`

	InputExactAbsBound float64 `json:"input_exact_abs_bound"`
	InputErrorAbsBound float64 `json:"input_error_abs_bound"`

	CoefficientEncodingAbsBound float64 `json:"coefficient_encoding_abs_bound"`
	OperationResidualAbsBound   float64 `json:"operation_residual_abs_bound"`

	SourceKind   BoundSourceKind `json:"source_kind"`
	SourceDigest string          `json:"source_digest"`

	FailureProbability float64 `json:"failure_probability"`
}

// NodeEnvelope records the replayed envelope at one ordered graph node.
type NodeEnvelope struct {
	NodeID string `json:"node_id"`
	Envelope
}

// Derivation is a canonical, replayable conditional error derivation.
//
// CertificateEligible is false when any primitive source is empirical or a
// standard-deviation diagnostic. Such derivations remain useful for debugging
// but Proof refuses to promote them.
type Derivation struct {
	SchemaVersion int `json:"schema_version"`

	Method  string `json:"method"`
	Version string `json:"version"`

	ScopeDigest string `json:"scope_digest"`

	Graph certify.AnalyticalOperationGraph `json:"graph"`

	ModelScalars  []ModelScalar    `json:"model_scalars"`
	Assumptions   []NodeAssumption `json:"assumptions"`
	NodeEnvelopes []NodeEnvelope   `json:"node_envelopes"`

	OutputNode    string  `json:"output_node"`
	MaxErrorBound float64 `json:"max_error_bound"`

	Guarantee          certify.AnalyticalGuaranteeKind `json:"guarantee"`
	FailureProbability float64                         `json:"failure_probability"`

	CertificateEligible bool     `json:"certificate_eligible"`
	BlockReasons        []string `json:"block_reasons,omitempty"`
}

// Build constructs and validates a conditional derivation. It performs no
// CKKS execution and never estimates missing primitive bounds.
func Build(
	scopeDigest string,
	graph certify.AnalyticalOperationGraph,
	modelScalars []ModelScalar,
	assumptions []NodeAssumption,
) (Derivation, error) {
	if err := validateDigest(
		"scope",
		scopeDigest,
	); err != nil {
		return Derivation{}, err
	}
	if err := graph.Validate(); err != nil {
		return Derivation{}, fmt.Errorf(
			"validate operation graph: %w",
			err,
		)
	}

	copiedScalars := append(
		[]ModelScalar(nil),
		modelScalars...,
	)
	sort.Slice(
		copiedScalars,
		func(left, right int) bool {
			return copiedScalars[left].Reference <
				copiedScalars[right].Reference
		},
	)

	copiedAssumptions := append(
		[]NodeAssumption(nil),
		assumptions...,
	)

	envelopes, guarantee, probability, eligible, reasons, err :=
		evaluate(
			graph,
			copiedScalars,
			copiedAssumptions,
		)
	if err != nil {
		return Derivation{}, err
	}

	output := envelopes[len(envelopes)-1]
	if output.NodeID != graph.OutputNode {
		return Derivation{}, fmt.Errorf(
			"graph output %q is not the final evaluated node %q",
			graph.OutputNode,
			output.NodeID,
		)
	}

	derivation := Derivation{
		SchemaVersion:       derivationSchemaVersion,
		Method:              derivationMethod,
		Version:             derivationVersion,
		ScopeDigest:         scopeDigest,
		Graph:               graph,
		ModelScalars:        copiedScalars,
		Assumptions:         copiedAssumptions,
		NodeEnvelopes:       envelopes,
		OutputNode:          output.NodeID,
		MaxErrorBound:       output.ErrorAbsBound,
		Guarantee:           guarantee,
		FailureProbability:  probability,
		CertificateEligible: eligible,
		BlockReasons:        reasons,
	}

	if err := derivation.Validate(); err != nil {
		return Derivation{}, fmt.Errorf(
			"validate built derivation: %w",
			err,
		)
	}

	return derivation, nil
}

// Validate replays the graph and rejects any altered result or eligibility
// metadata.
func (derivation Derivation) Validate() error {
	if derivation.SchemaVersion != derivationSchemaVersion {
		return fmt.Errorf(
			"unsupported derivation schema version %d",
			derivation.SchemaVersion,
		)
	}
	if derivation.Method != derivationMethod ||
		derivation.Version != derivationVersion {
		return fmt.Errorf(
			"unsupported derivation method/version %q/%q",
			derivation.Method,
			derivation.Version,
		)
	}
	if err := validateDigest(
		"scope",
		derivation.ScopeDigest,
	); err != nil {
		return err
	}
	if err := derivation.Graph.Validate(); err != nil {
		return fmt.Errorf(
			"validate derivation graph: %w",
			err,
		)
	}

	replayed, guarantee, probability, eligible, reasons, err :=
		evaluate(
			derivation.Graph,
			derivation.ModelScalars,
			derivation.Assumptions,
		)
	if err != nil {
		return err
	}

	if !sameNodeEnvelopes(
		derivation.NodeEnvelopes,
		replayed,
	) {
		return fmt.Errorf(
			"stored node envelopes do not match deterministic replay",
		)
	}
	if len(replayed) == 0 {
		return fmt.Errorf(
			"derivation has no replayed node envelopes",
		)
	}

	output := replayed[len(replayed)-1]
	if derivation.OutputNode != output.NodeID ||
		derivation.OutputNode !=
			derivation.Graph.OutputNode {
		return fmt.Errorf(
			"derivation output identity mismatch",
		)
	}
	if derivation.MaxErrorBound !=
		output.ErrorAbsBound {
		return fmt.Errorf(
			"derivation maximum error bound does not match replay",
		)
	}
	if derivation.Guarantee != guarantee ||
		derivation.FailureProbability != probability {
		return fmt.Errorf(
			"derivation guarantee metadata does not match replay",
		)
	}
	if derivation.CertificateEligible != eligible ||
		!sameStrings(
			derivation.BlockReasons,
			reasons,
		) {
		return fmt.Errorf(
			"derivation eligibility metadata does not match replay",
		)
	}

	return nil
}

// CanonicalJSON returns the deterministic representation bound by Digest.
func (derivation Derivation) CanonicalJSON() ([]byte, error) {
	if err := derivation.Validate(); err != nil {
		return nil, err
	}

	encoded, err := json.Marshal(derivation)
	if err != nil {
		return nil, fmt.Errorf(
			"marshal conditional analytical derivation: %w",
			err,
		)
	}

	return encoded, nil
}

// Digest returns the SHA-256 of the replay-validated derivation.
func (derivation Derivation) Digest() (string, error) {
	canonical, err := derivation.CanonicalJSON()
	if err != nil {
		return "", err
	}

	sum := sha256.Sum256(canonical)
	return "sha256:" +
		hex.EncodeToString(sum[:]), nil
}

// Proof promotes an eligible derivation into the existing certificate proof
// metadata. Diagnostic or incompletely bounded inputs fail closed.
func (derivation Derivation) Proof() (
	certify.AnalyticalBoundProof,
	error,
) {
	if err := derivation.Validate(); err != nil {
		return certify.AnalyticalBoundProof{}, err
	}
	if !derivation.CertificateEligible {
		return certify.AnalyticalBoundProof{}, fmt.Errorf(
			"conditional derivation is not certificate eligible: %s",
			strings.Join(
				derivation.BlockReasons,
				"; ",
			),
		)
	}

	digest, err := derivation.Digest()
	if err != nil {
		return certify.AnalyticalBoundProof{}, err
	}

	proof := certify.AnalyticalBoundProof{
		Method:             derivation.Method,
		Version:            derivation.Version,
		Guarantee:          derivation.Guarantee,
		ScopeDigest:        derivation.ScopeDigest,
		DerivationDigest:   digest,
		MaxErrorBound:      derivation.MaxErrorBound,
		FailureProbability: derivation.FailureProbability,
	}

	if err := proof.Validate(); err != nil {
		return certify.AnalyticalBoundProof{}, fmt.Errorf(
			"validate promoted analytical proof: %w",
			err,
		)
	}

	return proof, nil
}

func evaluate(
	graph certify.AnalyticalOperationGraph,
	modelScalars []ModelScalar,
	assumptions []NodeAssumption,
) (
	[]NodeEnvelope,
	certify.AnalyticalGuaranteeKind,
	float64,
	bool,
	[]string,
	error,
) {
	scalars, err := validateModelScalars(
		graph,
		modelScalars,
	)
	if err != nil {
		return nil, "", 0, false, nil, err
	}
	if len(assumptions) != len(graph.Nodes) {
		return nil, "", 0, false, nil, fmt.Errorf(
			"assumption count %d does not match graph node count %d",
			len(assumptions),
			len(graph.Nodes),
		)
	}

	values := make(
		map[string]Envelope,
		len(graph.Nodes),
	)
	envelopes := make(
		[]NodeEnvelope,
		0,
		len(graph.Nodes),
	)
	guarantee := certify.AnalyticalGuaranteeDeterministic
	failureProbability := 0.0
	eligible := true
	reasons := make([]string, 0)

	for index, node := range graph.Nodes {
		assumption := assumptions[index]
		if assumption.NodeID != node.ID {
			return nil, "", 0, false, nil, fmt.Errorf(
				"assumption %d binds node %q; expected %q",
				index,
				assumption.NodeID,
				node.ID,
			)
		}
		if err := validateAssumption(
			node,
			assumption,
		); err != nil {
			return nil, "", 0, false, nil, fmt.Errorf(
				"validate assumption for node %q: %w",
				node.ID,
				err,
			)
		}

		switch assumption.SourceKind {
		case SourceProbabilisticAbsolute:
			guarantee =
				certify.AnalyticalGuaranteeProbabilistic
			failureProbability = addUp(
				failureProbability,
				assumption.FailureProbability,
			)

		case SourceEmpiricalDiagnostic,
			SourceStdDevDiagnostic:
			eligible = false
			reasons = append(
				reasons,
				fmt.Sprintf(
					"node %s uses %s rather than an absolute primitive derivation",
					node.ID,
					assumption.SourceKind,
				),
			)
		}

		value, err := evaluateNode(
			node,
			assumption,
			values,
			scalars,
		)
		if err != nil {
			return nil, "", 0, false, nil, fmt.Errorf(
				"evaluate analytical node %q: %w",
				node.ID,
				err,
			)
		}

		values[node.ID] = value
		envelopes = append(
			envelopes,
			NodeEnvelope{
				NodeID:   node.ID,
				Envelope: value,
			},
		)
	}

	if failureProbability >= 1 ||
		math.IsInf(failureProbability, 0) {
		eligible = false
		reasons = append(
			reasons,
			"union-bound failure probability is not below one",
		)
	}

	return envelopes,
		guarantee,
		failureProbability,
		eligible,
		reasons,
		nil
}

func evaluateNode(
	node certify.AnalyticalOperationNode,
	assumption NodeAssumption,
	values map[string]Envelope,
	modelScalars map[string]float64,
) (Envelope, error) {
	input := func(index int) (Envelope, error) {
		if index >= len(node.Inputs) {
			return Envelope{}, fmt.Errorf(
				"missing input %d",
				index,
			)
		}
		value, exists := values[node.Inputs[index]]
		if !exists {
			return Envelope{}, fmt.Errorf(
				"input %q is unavailable",
				node.Inputs[index],
			)
		}
		return value, nil
	}

	var result Envelope

	switch node.Op {
	case certify.AnalyticalOpInput:
		result = Envelope{
			ExactAbsBound: assumption.InputExactAbsBound,
			ErrorAbsBound: assumption.InputErrorAbsBound,
		}

	case certify.AnalyticalOpMulModelScalar:
		value, err := input(0)
		if err != nil {
			return Envelope{}, err
		}
		scalar, exists :=
			modelScalars[node.ModelParameter]
		if !exists {
			return Envelope{}, fmt.Errorf(
				"model scalar %q is unavailable",
				node.ModelParameter,
			)
		}
		result = scale(
			value,
			scalar,
			assumption.CoefficientEncodingAbsBound,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpMulFixedScalar:
		value, err := input(0)
		if err != nil {
			return Envelope{}, err
		}
		scalar, err := scalarFromBits(
			node.ScalarBits,
		)
		if err != nil {
			return Envelope{}, err
		}
		result = scale(
			value,
			scalar,
			assumption.CoefficientEncodingAbsBound,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpEncodeModelPlaintextAtLevel:
		scalar, exists :=
			modelScalars[node.ModelParameter]
		if !exists {
			return Envelope{}, fmt.Errorf(
				"model scalar %q is unavailable",
				node.ModelParameter,
			)
		}
		result = constant(
			scalar,
			assumption.CoefficientEncodingAbsBound,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpEncodeFixedPlaintextAtLevel:
		scalar, err := scalarFromBits(
			node.ScalarBits,
		)
		if err != nil {
			return Envelope{}, err
		}
		result = constant(
			scalar,
			assumption.CoefficientEncodingAbsBound,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpAddCiphertexts,
		certify.AnalyticalOpAddCiphertextPlaintext:
		left, err := input(0)
		if err != nil {
			return Envelope{}, err
		}
		right, err := input(1)
		if err != nil {
			return Envelope{}, err
		}
		result = add(
			left,
			right,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpMulCiphertexts:
		left, err := input(0)
		if err != nil {
			return Envelope{}, err
		}
		right, err := input(1)
		if err != nil {
			return Envelope{}, err
		}
		result = multiply(
			left,
			right,
			assumption.OperationResidualAbsBound,
		)

	case certify.AnalyticalOpRelinearize,
		certify.AnalyticalOpRescaleToDefault,
		certify.AnalyticalOpAlignLevelTo:
		value, err := input(0)
		if err != nil {
			return Envelope{}, err
		}
		result = Envelope{
			ExactAbsBound: value.ExactAbsBound,
			ErrorAbsBound: addUp(
				value.ErrorAbsBound,
				assumption.OperationResidualAbsBound,
			),
		}

	default:
		return Envelope{}, fmt.Errorf(
			"unsupported operation %q",
			node.Op,
		)
	}

	if err := validateEnvelope(result); err != nil {
		return Envelope{}, err
	}

	return result, nil
}

func validateAssumption(
	node certify.AnalyticalOperationNode,
	assumption NodeAssumption,
) error {
	values := []struct {
		name  string
		value float64
	}{
		{"input exact bound", assumption.InputExactAbsBound},
		{"input error bound", assumption.InputErrorAbsBound},
		{"coefficient encoding bound", assumption.CoefficientEncodingAbsBound},
		{"operation residual bound", assumption.OperationResidualAbsBound},
	}
	for _, value := range values {
		if !nonNegativeFinite(value.value) {
			return fmt.Errorf(
				"%s must be finite and non-negative",
				value.name,
			)
		}
	}
	if err := validateDigest(
		"primitive source",
		assumption.SourceDigest,
	); err != nil {
		return err
	}

	switch assumption.SourceKind {
	case SourceDeterministicAbsolute:
		if assumption.FailureProbability != 0 {
			return fmt.Errorf(
				"deterministic source must have zero failure probability",
			)
		}

	case SourceProbabilisticAbsolute:
		if !finite(
			assumption.FailureProbability,
		) || assumption.FailureProbability <= 0 ||
			assumption.FailureProbability >= 1 {
			return fmt.Errorf(
				"probabilistic source failure probability must lie in (0, 1)",
			)
		}

	case SourceEmpiricalDiagnostic,
		SourceStdDevDiagnostic:
		if assumption.FailureProbability != 0 {
			return fmt.Errorf(
				"diagnostic source must not assert a failure probability",
			)
		}

	default:
		return fmt.Errorf(
			"unsupported primitive source kind %q",
			assumption.SourceKind,
		)
	}

	switch node.Op {
	case certify.AnalyticalOpInput:
		if assumption.CoefficientEncodingAbsBound != 0 ||
			assumption.OperationResidualAbsBound != 0 {
			return fmt.Errorf(
				"input node has inapplicable coefficient or operation residual",
			)
		}

	case certify.AnalyticalOpMulModelScalar,
		certify.AnalyticalOpMulFixedScalar,
		certify.AnalyticalOpEncodeModelPlaintextAtLevel,
		certify.AnalyticalOpEncodeFixedPlaintextAtLevel:
		if assumption.InputExactAbsBound != 0 ||
			assumption.InputErrorAbsBound != 0 {
			return fmt.Errorf(
				"scalar node has inapplicable input bounds",
			)
		}

	default:
		if assumption.InputExactAbsBound != 0 ||
			assumption.InputErrorAbsBound != 0 ||
			assumption.CoefficientEncodingAbsBound != 0 {
			return fmt.Errorf(
				"operation node has inapplicable input or coefficient bounds",
			)
		}
	}

	return nil
}

func validateModelScalars(
	graph certify.AnalyticalOperationGraph,
	values []ModelScalar,
) (map[string]float64, error) {
	required := make(map[string]struct{})
	for _, node := range graph.Nodes {
		if node.ModelParameter != "" {
			required[node.ModelParameter] = struct{}{}
		}
	}

	result := make(
		map[string]float64,
		len(values),
	)
	previous := ""
	for index, value := range values {
		if strings.TrimSpace(value.Reference) == "" {
			return nil, fmt.Errorf(
				"model scalar %d reference is empty",
				index,
			)
		}
		if index > 0 &&
			value.Reference <= previous {
			return nil, fmt.Errorf(
				"model scalars are not in strict canonical order",
			)
		}
		scalar, err := scalarFromBits(
			value.ValueBits,
		)
		if err != nil {
			return nil, fmt.Errorf(
				"model scalar %q: %w",
				value.Reference,
				err,
			)
		}
		if _, exists := required[value.Reference]; !exists {
			return nil, fmt.Errorf(
				"model scalar %q is not referenced by the graph",
				value.Reference,
			)
		}
		result[value.Reference] = scalar
		previous = value.Reference
	}

	if len(result) != len(required) {
		missing := make([]string, 0)
		for reference := range required {
			if _, exists := result[reference]; !exists {
				missing = append(
					missing,
					reference,
				)
			}
		}
		sort.Strings(missing)
		return nil, fmt.Errorf(
			"missing model scalars: %s",
			strings.Join(missing, ", "),
		)
	}

	return result, nil
}

func scalarFromBits(
	value string,
) (float64, error) {
	if len(value) != 16 ||
		value != strings.ToLower(value) {
		return 0, fmt.Errorf(
			"scalar bits must be 16 lowercase hexadecimal digits",
		)
	}
	bits, err := strconv.ParseUint(
		value,
		16,
		64,
	)
	if err != nil {
		return 0, fmt.Errorf(
			"parse scalar bits: %w",
			err,
		)
	}
	scalar := math.Float64frombits(bits)
	if !finite(scalar) {
		return 0, fmt.Errorf(
			"scalar bits encode a non-finite value",
		)
	}
	canonical, err :=
		certify.AnalyticalFixedScalarBits(scalar)
	if err != nil {
		return 0, err
	}
	if canonical != value {
		return 0, fmt.Errorf(
			"scalar bits are not canonical",
		)
	}
	return scalar, nil
}

func constant(
	value float64,
	encodingError float64,
	residual float64,
) Envelope {
	return Envelope{
		ExactAbsBound: math.Abs(value),
		ErrorAbsBound: sumUp(
			encodingError,
			residual,
		),
	}
}

func add(
	left Envelope,
	right Envelope,
	residual float64,
) Envelope {
	return Envelope{
		ExactAbsBound: addUp(
			left.ExactAbsBound,
			right.ExactAbsBound,
		),
		ErrorAbsBound: sumUp(
			left.ErrorAbsBound,
			right.ErrorAbsBound,
			residual,
		),
	}
}

func multiply(
	left Envelope,
	right Envelope,
	residual float64,
) Envelope {
	return Envelope{
		ExactAbsBound: multiplyUp(
			left.ExactAbsBound,
			right.ExactAbsBound,
		),
		ErrorAbsBound: sumUp(
			multiplyUp(
				left.ExactAbsBound,
				right.ErrorAbsBound,
			),
			multiplyUp(
				right.ExactAbsBound,
				left.ErrorAbsBound,
			),
			multiplyUp(
				left.ErrorAbsBound,
				right.ErrorAbsBound,
			),
			residual,
		),
	}
}

func scale(
	input Envelope,
	coefficient float64,
	coefficientError float64,
	residual float64,
) Envelope {
	coefficientAbs := math.Abs(coefficient)
	return Envelope{
		ExactAbsBound: multiplyUp(
			coefficientAbs,
			input.ExactAbsBound,
		),
		ErrorAbsBound: sumUp(
			multiplyUp(
				coefficientAbs,
				input.ErrorAbsBound,
			),
			multiplyUp(
				coefficientError,
				input.ExactAbsBound,
			),
			multiplyUp(
				coefficientError,
				input.ErrorAbsBound,
			),
			residual,
		),
	}
}

func multiplyUp(
	left float64,
	right float64,
) float64 {
	if left == 0 || right == 0 {
		return 0
	}
	return math.Nextafter(
		left*right,
		math.Inf(1),
	)
}

func addUp(
	left float64,
	right float64,
) float64 {
	if left == 0 {
		return right
	}
	if right == 0 {
		return left
	}
	return math.Nextafter(
		left+right,
		math.Inf(1),
	)
}

func sumUp(
	values ...float64,
) float64 {
	total := 0.0
	for _, value := range values {
		total = addUp(
			total,
			value,
		)
	}
	return total
}

func validateEnvelope(
	value Envelope,
) error {
	if !nonNegativeFinite(value.ExactAbsBound) {
		return fmt.Errorf(
			"exact absolute bound must be finite and non-negative",
		)
	}
	if !nonNegativeFinite(value.ErrorAbsBound) {
		return fmt.Errorf(
			"error absolute bound must be finite and non-negative",
		)
	}
	return nil
}

func validateDigest(
	name string,
	value string,
) error {
	const prefix = "sha256:"
	if !strings.HasPrefix(value, prefix) {
		return fmt.Errorf(
			"%s digest must use sha256 prefix",
			name,
		)
	}
	decoded, err := hex.DecodeString(
		strings.TrimPrefix(
			value,
			prefix,
		),
	)
	if err != nil || len(decoded) != sha256.Size {
		return fmt.Errorf(
			"%s digest must contain 32 hexadecimal bytes",
			name,
		)
	}
	return nil
}

func sameNodeEnvelopes(
	left []NodeEnvelope,
	right []NodeEnvelope,
) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func sameStrings(
	left []string,
	right []string,
) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func nonNegativeFinite(
	value float64,
) bool {
	return finite(value) && value >= 0
}

func finite(
	value float64,
) bool {
	return !math.IsNaN(value) &&
		!math.IsInf(value, 0)
}
