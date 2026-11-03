package ckksplanner

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"

	"github.com/hasslelee/flipguard/internal/analysis"
	"github.com/hasslelee/flipguard/internal/ir"
	fgruntime "github.com/hasslelee/flipguard/internal/runtime"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const V17DepthLadderSchema = "flipguard_v17_depth_ladder_v1"

type V17DepthLadderOptions struct {
	ModelPath string
	DataPath  string
	SplitID   string
	Depth     int
}

type v17DepthModel struct {
	SchemaVersion string  `json:"schema_version"`
	ModelID       string  `json:"model_id"`
	Depth         int     `json:"multiplicative_depth"`
	Threshold     float64 `json:"decision_threshold"`
}

// BuildV17DepthLadderContract creates one result-independent repeated-square
// stress graph. Unsupported depth is represented by synthesis/execution state,
// never rewritten as NO_SAFE.
func BuildV17DepthLadderContract(options V17DepthLadderOptions) (WorkloadContract, error) {
	if options.Depth <= 0 || options.ModelPath == "" || options.DataPath == "" || options.SplitID == "" {
		return WorkloadContract{}, fmt.Errorf("depth, model, data, and split identity are required")
	}
	modelBytes, err := os.ReadFile(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, err
	}
	var model v17DepthModel
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		return WorkloadContract{}, err
	}
	if model.SchemaVersion != V17DepthLadderSchema || model.Depth != options.Depth ||
		model.ModelID != fmt.Sprintf("v17_depth_ladder_d%d", options.Depth) || model.Threshold != 1 {
		return WorkloadContract{}, fmt.Errorf("depth-ladder model identity mismatch")
	}
	dataBytes, err := os.ReadFile(options.DataPath)
	if err != nil {
		return WorkloadContract{}, err
	}
	reader := csv.NewReader(bytes.NewReader(dataBytes))
	records, err := reader.ReadAll()
	if err != nil || len(records) < 2 {
		return WorkloadContract{}, fmt.Errorf("invalid depth-ladder data: %w", err)
	}
	header := make(map[string]int)
	for index, field := range records[0] {
		header[field] = index
	}
	required := []string{"row_id", "x_0", "plaintext_score", "plaintext_decision"}
	for _, field := range required {
		if _, ok := header[field]; !ok {
			return WorkloadContract{}, fmt.Errorf("depth-ladder data missing %s", field)
		}
	}
	graph := ir.NewGraph()
	graph.MustAddNode(ir.NewInput("x_0", "x_0"))
	previous := ir.NodeID("x_0")
	for level := 1; level <= options.Depth; level++ {
		id := ir.NodeID(fmt.Sprintf("square_%d", level))
		graph.MustAddNode(ir.NewBinary(id, string(id), ir.OpMul, previous, previous))
		previous = id
	}
	graph.MustSetOutput(previous)
	if err := graph.Validate(); err != nil {
		return WorkloadContract{}, err
	}
	sampleOrder := make([]string, 0, len(records)-1)
	plainScores := make(map[string]float64, len(records)-1)
	analysisSamples := make([]map[ir.NodeID]float64, 0, len(records)-1)
	protectedMargin := math.Inf(1)
	maxInput, maxOutput := 0.0, 0.0
	vCert, vAmb := 0, 0
	for rowIndex, record := range records[1:] {
		id := record[header["row_id"]]
		x, parseErr := strconv.ParseFloat(record[header["x_0"]], 64)
		if parseErr != nil {
			return WorkloadContract{}, parseErr
		}
		score, parseErr := strconv.ParseFloat(record[header["plaintext_score"]], 64)
		if parseErr != nil {
			return WorkloadContract{}, parseErr
		}
		decision, parseErr := strconv.ParseBool(record[header["plaintext_decision"]])
		if parseErr != nil {
			return WorkloadContract{}, parseErr
		}
		plain, evalErr := fgruntime.EvalPlain(graph, map[ir.NodeID]float64{"x_0": x})
		if evalErr != nil || !closeFloatAtTolerance(plain.Output, score, 1e-12) || decision != (score >= model.Threshold) {
			return WorkloadContract{}, fmt.Errorf("depth-ladder row %d plaintext replay mismatch", rowIndex+2)
		}
		margin := math.Abs(score - model.Threshold)
		if margin <= 0.001 {
			vAmb++
		} else {
			vCert++
			protectedMargin = math.Min(protectedMargin, margin)
		}
		maxInput = math.Max(maxInput, math.Abs(x))
		maxOutput = math.Max(maxOutput, math.Abs(score))
		sampleOrder = append(sampleOrder, id)
		plainScores[id] = score
		analysisSamples = append(analysisSamples, map[ir.NodeID]float64{"x_0": x})
	}
	if vCert == 0 {
		return WorkloadContract{}, fmt.Errorf("depth-ladder scope has no certifiable row")
	}
	bounds, err := analysis.AnalyzeBoundsAndSensitivity(graph, analysisSamples, model.Threshold, 0.05)
	if err != nil {
		return WorkloadContract{}, err
	}
	sensitivity := aggregateOperationSensitivity(graph, bounds)
	graphSummary, err := summarizeTabularGraph(graph)
	if err != nil {
		return WorkloadContract{}, err
	}
	graphSummary.Notes = []string{
		"predeclared repeated-square depth stress graph",
		"identical bounded input domain and threshold rule at every depth",
	}
	// The depth-ladder backend rescales after every repeated ciphertext
	// square. Its schedule therefore consumes exactly one Q level per rung and
	// leaves the output at the default scale.
	demand := lattigoScaleDemand{
		LevelsConsumed:  options.Depth,
		ScaleExponent:   1,
		RequiredQPrimes: options.Depth + 1,
	}
	contract := WorkloadContract{
		SchemaVersion: WorkloadContractSchemaVersion,
		WorkloadID:    options.SplitID + "/depth_ladder/" + model.ModelID,
		DatasetID:     "v17_bounded_scalar_domain", ModelID: model.ModelID,
		ModelType: "v17_repeated_square_depth", SplitID: options.SplitID,
		ModelArtifact:  ArtifactBinding{Path: options.ModelPath, SHA256: digestBytes(modelBytes)},
		ValidationData: ArtifactBinding{Path: options.DataPath, SHA256: digestBytes(dataBytes)},
		Graph:          graphSummary,
		Decision: DecisionStabilityContract{
			Threshold: model.Threshold, MarginFloor: 0.001, SafetyFactor: 0.5,
			ProtectedMargin: protectedMargin, OutputErrorBudget: 0.5 * protectedMargin,
			ValidationDigest:  digestValidationScores(sampleOrder, plainScores),
			ValidationSamples: len(sampleOrder), CertifiableSamples: vCert, AmbiguousSamples: vAmb,
		},
		Calibration: NumericalCalibration{
			MaxInputAbs: maxInput, MaxPlaintextOutputAbs: maxOutput,
			AggregateSensitivity: sensitivity, SensitivityMethod: EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope: "predeclared_bounded_depth_ladder:" + digestBytes(dataBytes),
		},
		Deployment: DeploymentContract{
			SecurityBits: 128, RequiredSlots: 1, MaxEncryptedTrials: 4,
			ValidationKeyRepeats: 3, PackingStrategy: ScalarReplicatedPackingV1,
			AllowedPaths:          []tuner.ExecutionPath{tuner.PathRescale},
			ScaleTraceMethod:      LattigoRescaleScaleTraceV1,
			RescaleLevelsConsumed: demand.LevelsConsumed,
			TerminalScaleExponent: demand.ScaleExponent, RequiredQPrimes: demand.RequiredQPrimes,
		},
	}
	if err := contract.Validate(); err != nil {
		return WorkloadContract{}, err
	}
	return contract, nil
}
