package ckksplanner

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"io"
	"math"
	"os"
	"strings"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/journalmnist"
	"github.com/hasslelee/flipguard/internal/tuner"
)

const (
	JournalMNISTGraphAdapterV1 = "mnist_multiclass_feature_ciphertext_batch_adapter_v1"
	JournalMNISTDatasetID      = "mnist_10class"
)

type MulticlassContractOptions struct {
	ModelPath      string
	ValidationPath string
	SourcePath     string
	SplitID        string
	ExpectedRole   string

	MarginFloor          float64
	MarginUtilizationCap float64
	SecurityBits         int
	MaxEncryptedTrials   int
	ValidationKeyRepeats int
	AllowedPaths         []tuner.ExecutionPath
}

type MulticlassPlaintextScope struct {
	SampleIDs        []string
	Labels           []int
	Logits           [][]float64
	TopTwoGaps       []float64
	ValidationDigest string
	VCert            int
	VAmb             int
	ProtectedGap     float64
	MinimumGap       float64
	MaximumGap       float64
	Calibration      journalmnist.CalibrationSummary
}

func DefaultJournalMNISTMulticlassContractOptions() MulticlassContractOptions {
	return MulticlassContractOptions{
		MarginFloor:          0.001,
		MarginUtilizationCap: 0.5,
		SecurityBits:         128,
		MaxEncryptedTrials:   4,
		ValidationKeyRepeats: 3,
		AllowedPaths:         []tuner.ExecutionPath{tuner.PathRescale},
	}
}

// BuildJournalMNISTMulticlassContract replays one frozen 500-image role and
// derives a multiclass workload contract without consulting encrypted output.
func BuildJournalMNISTMulticlassContract(
	options MulticlassContractOptions,
) (WorkloadContract, MulticlassPlaintextScope, error) {
	normalizeMulticlassOptions(&options)
	model, err := journalmnist.LoadModelArtifact(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	if err := validateJournalModelIdentity(model); err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	rows, err := journalmnist.LoadPartitionCSV(options.ValidationPath, options.ExpectedRole)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	modelDigest, err := sha256FileWithPrefix(options.ModelPath)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	validationDigest, err := sha256FileWithPrefix(options.ValidationPath)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	sourceDigest, err := sha256FileWithPrefix(options.SourcePath)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	if sourceDigest != model.Source.SHA256 {
		return WorkloadContract{}, MulticlassPlaintextScope{}, fmt.Errorf(
			"MNIST source digest %s does not match model binding %s",
			sourceDigest,
			model.Source.SHA256,
		)
	}
	scope, err := deriveMulticlassPlaintextScope(model, rows, options.MarginFloor)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	graph, levels, terminalExponent, requiredQ, err := journalMNISTGraphFacts(model.ModelType)
	if err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, err
	}
	contract := WorkloadContract{
		SchemaVersion: WorkloadContractSchemaVersion,
		WorkloadID: strings.Join(
			[]string{JournalMNISTDatasetID, model.ModelID, options.SplitID},
			"__",
		),
		DatasetID: JournalMNISTDatasetID,
		ModelID:   model.ModelID,
		ModelType: model.ModelType,
		SplitID:   options.SplitID,
		ModelArtifact: ArtifactBinding{
			Path: options.ModelPath, SHA256: modelDigest,
		},
		ValidationData: ArtifactBinding{
			Path: options.ValidationPath, SHA256: validationDigest,
		},
		SourceData: &ArtifactBinding{
			Path: options.SourcePath, SHA256: sourceDigest,
		},
		InputMaterialization: &InputMaterializationContract{
			SchemaVersion:        MNISTMulticlassMaterializationSchemaV1,
			SourceFeatureSpace:   MNISTMulticlassSourceFeatureSpaceV1,
			PreprocessingMethod:  MNISTMulticlassExtractionPolicyV1,
			SourceReplayVerified: true,
		},
		Graph: graph,
		MulticlassDecision: &MulticlassDecisionStabilityContract{
			SchemaVersion:        certify.MulticlassDecisionContractSchemaV2,
			ClassCount:           journalmnist.ClassCount,
			TieBreak:             certify.DeterministicLowestIndexTieBreak,
			BoundMode:            "uniform_per_logit_v1",
			MarginFloor:          options.MarginFloor,
			MarginUtilizationCap: options.MarginUtilizationCap,
			ProtectedTopTwoGap:   scope.ProtectedGap,
			PerLogitErrorBudget:  options.MarginUtilizationCap * scope.ProtectedGap / 2,
			ValidationDigest:     scope.ValidationDigest,
			ValidationSamples:    len(rows),
			CertifiableSamples:   scope.VCert,
			AmbiguousSamples:     scope.VAmb,
		},
		Calibration: NumericalCalibration{
			MaxInputAbs:           scope.Calibration.MaxInputAbs,
			MaxPlaintextOutputAbs: scope.Calibration.MaxPlaintextLogitAbs,
			AggregateSensitivity:  scope.Calibration.AggregateSensitivity,
			SensitivityMethod:     EmpiricalIntervalDAGSensitivityV1,
			CalibrationScope: fmt.Sprintf(
				"%s:%s;underlying_method=%s",
				options.ExpectedRole,
				validationDigest,
				scope.Calibration.Method,
			),
		},
		Deployment: DeploymentContract{
			SecurityBits:          options.SecurityBits,
			RequiredSlots:         len(rows),
			MaxEncryptedTrials:    options.MaxEncryptedTrials,
			ValidationKeyRepeats:  options.ValidationKeyRepeats,
			PackingStrategy:       FeatureCiphertextSampleSlotsV1,
			AllowedPaths:          append([]tuner.ExecutionPath(nil), options.AllowedPaths...),
			ScaleTraceMethod:      LattigoRescaleScaleTraceV1,
			RescaleLevelsConsumed: levels,
			TerminalScaleExponent: terminalExponent,
			RequiredQPrimes:       requiredQ,
		},
	}
	if err := contract.Validate(); err != nil {
		return WorkloadContract{}, MulticlassPlaintextScope{}, fmt.Errorf(
			"validate journal multiclass contract: %w",
			err,
		)
	}
	return contract, scope, nil
}

func normalizeMulticlassOptions(options *MulticlassContractOptions) {
	defaults := DefaultJournalMNISTMulticlassContractOptions()
	options.ModelPath = strings.TrimSpace(options.ModelPath)
	options.ValidationPath = strings.TrimSpace(options.ValidationPath)
	options.SourcePath = strings.TrimSpace(options.SourcePath)
	options.SplitID = strings.TrimSpace(options.SplitID)
	options.ExpectedRole = strings.TrimSpace(options.ExpectedRole)
	if options.MarginFloor < 0 || !finite(options.MarginFloor) {
		options.MarginFloor = defaults.MarginFloor
	}
	if options.MarginUtilizationCap <= 0 || options.MarginUtilizationCap > 1 ||
		!finite(options.MarginUtilizationCap) {
		options.MarginUtilizationCap = defaults.MarginUtilizationCap
	}
	if options.SecurityBits <= 0 {
		options.SecurityBits = defaults.SecurityBits
	}
	if options.MaxEncryptedTrials <= 0 {
		options.MaxEncryptedTrials = defaults.MaxEncryptedTrials
	}
	if options.ValidationKeyRepeats <= 0 {
		options.ValidationKeyRepeats = defaults.ValidationKeyRepeats
	}
	if len(options.AllowedPaths) == 0 {
		options.AllowedPaths = append([]tuner.ExecutionPath(nil), defaults.AllowedPaths...)
	}
}

func validateJournalModelIdentity(model journalmnist.ModelArtifact) error {
	if model.DatasetID != JournalMNISTDatasetID ||
		model.GraphAdapterID != JournalMNISTGraphAdapterV1 {
		return fmt.Errorf("journal MNIST model identity is outside the frozen adapter")
	}
	expectedFormula := ""
	switch model.ModelType {
	case journalmnist.MLPModelType:
		expectedFormula = "affine_100(square(affine_784(input)))->10_logits"
	case journalmnist.LeNetModelType:
		expectedFormula = "conv5x5_6->square->avgpool2->conv5x5_16->square->avgpool2->fc120->square->fc64->square->10_logits"
	default:
		return fmt.Errorf("unsupported journal MNIST model type %q", model.ModelType)
	}
	if model.GraphFormula != expectedFormula {
		return fmt.Errorf("journal MNIST graph formula changed")
	}
	return nil
}

func deriveMulticlassPlaintextScope(
	model journalmnist.ModelArtifact,
	rows []journalmnist.PartitionRow,
	marginFloor float64,
) (MulticlassPlaintextScope, error) {
	scope := MulticlassPlaintextScope{
		SampleIDs:  make([]string, 0, len(rows)),
		Labels:     make([]int, 0, len(rows)),
		Logits:     make([][]float64, 0, len(rows)),
		TopTwoGaps: make([]float64, 0, len(rows)),
		MinimumGap: math.Inf(1),
	}
	for _, row := range rows {
		logitsArray, err := model.Logits(row)
		if err != nil {
			return MulticlassPlaintextScope{}, err
		}
		logits := append([]float64(nil), logitsArray[:]...)
		_, _, gap, tied, err := multiclassTopTwo(logits)
		if err != nil {
			return MulticlassPlaintextScope{}, fmt.Errorf("sample %s: %w", row.SampleID, err)
		}
		scope.SampleIDs = append(scope.SampleIDs, row.SampleID)
		scope.Labels = append(scope.Labels, row.Label)
		scope.Logits = append(scope.Logits, logits)
		scope.TopTwoGaps = append(scope.TopTwoGaps, gap)
		scope.MinimumGap = math.Min(scope.MinimumGap, gap)
		scope.MaximumGap = math.Max(scope.MaximumGap, gap)
		if !tied && gap > marginFloor {
			scope.VCert++
			if scope.ProtectedGap == 0 || gap < scope.ProtectedGap {
				scope.ProtectedGap = gap
			}
		} else {
			scope.VAmb++
		}
	}
	if scope.VCert == 0 {
		return MulticlassPlaintextScope{}, fmt.Errorf("multiclass scope has no certifiable samples")
	}
	scope.ValidationDigest = DigestMulticlassPlaintextLogits(scope.SampleIDs, scope.Logits)
	calibration, err := journalmnist.CalibrateModel(model, rows)
	if err != nil {
		return MulticlassPlaintextScope{}, err
	}
	scope.Calibration = calibration
	return scope, nil
}

func journalMNISTGraphFacts(modelType string) (tuner.GraphSummary, int, int, int, error) {
	switch modelType {
	case journalmnist.MLPModelType:
		return tuner.GraphSummary{
			MultiplicativeDepth: 1,
			AddOps:              79400,
			MulOps:              79500,
			RotOps:              0,
			RescaleOps:          1,
			Notes: []string{
				"exact affine/square operation inventory for 784-100-10 MLP",
				"feature ciphertexts use sample slots; no rotation",
				"one square consumes three Q levels and the terminal affine has scale exponent two under the Lattigo v6 scalar/rescale trace",
			},
		}, 3, 2, 5, nil
	case journalmnist.LeNetModelType:
		return tuner.GraphSummary{
			MultiplicativeDepth: 4,
			AddOps:              418648,
			MulOps:              421984,
			RotOps:              0,
			RescaleOps:          4,
			Notes: []string{
				"exact convolution/average-pool/affine/square inventory for the frozen LeNet-5-small adapter",
				"feature ciphertexts use sample slots; no rotation",
				"pool scalars raise the next affine scale; four squares consume sixteen Q levels and the terminal affine has scale exponent two",
			},
		}, 16, 2, 18, nil
	default:
		return tuner.GraphSummary{}, 0, 0, 0, fmt.Errorf("unsupported journal model type %q", modelType)
	}
}

// DigestMulticlassPlaintextLogits binds ordered sample IDs to every
// full-precision plaintext logit. It is reused before validation and audit.
func DigestMulticlassPlaintextLogits(sampleIDs []string, logits [][]float64) string {
	hasher := sha256.New()
	var encoded [8]byte
	for index, sampleID := range sampleIDs {
		binary.BigEndian.PutUint64(encoded[:], uint64(len(sampleID)))
		_, _ = hasher.Write(encoded[:])
		_, _ = hasher.Write([]byte(sampleID))
		binary.BigEndian.PutUint64(encoded[:], uint64(len(logits[index])))
		_, _ = hasher.Write(encoded[:])
		for _, value := range logits[index] {
			binary.BigEndian.PutUint64(encoded[:], math.Float64bits(value))
			_, _ = hasher.Write(encoded[:])
		}
	}
	return "sha256:" + hex.EncodeToString(hasher.Sum(nil))
}

func multiclassTopTwo(logits []float64) (top, runner int, gap float64, tied bool, err error) {
	if len(logits) < 2 {
		return 0, 0, 0, false, fmt.Errorf("requires at least two logits")
	}
	for index, value := range logits {
		if !finite(value) {
			return 0, 0, 0, false, fmt.Errorf("logit %d is non-finite", index)
		}
	}
	top = 0
	for index := 1; index < len(logits); index++ {
		if logits[index] > logits[top] {
			top = index
		}
	}
	runner = -1
	for index := range logits {
		if index == top {
			continue
		}
		if runner == -1 || logits[index] > logits[runner] {
			runner = index
		}
	}
	gap = logits[top] - logits[runner]
	tied = gap == 0
	return top, runner, gap, tied, nil
}

func sha256FileWithPrefix(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("open %s for digest: %w", path, err)
	}
	defer file.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", fmt.Errorf("digest %s: %w", path, err)
	}
	return "sha256:" + hex.EncodeToString(hasher.Sum(nil)), nil
}

// WorkloadContractDigest exposes the canonical contract identity to resumable
// journal tooling without exposing the internal canonicalization helper.
func WorkloadContractDigest(contract WorkloadContract) (string, error) {
	return digestContract(contract)
}
