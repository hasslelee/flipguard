package ckksplanner

import (
	"fmt"
	"github.com/hasslelee/flipguard/internal/bankadapter"
	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/tuner"
	"math"
)

func BankIndependentFacts(modelPath, dataPath string) (IndependentFacts, error) {
	m, e := bankadapter.LoadModelArtifact(modelPath)
	if e != nil {
		return IndependentFacts{}, e
	}
	rows, e := bankadapter.LoadPartitionCSV(dataPath, "configuration_selection")
	if e != nil {
		return IndependentFacts{}, e
	}
	maxZ := 0.
	for _, r := range rows {
		z, _ := m.Logits(r)
		for _, v := range z {
			maxZ = math.Max(maxZ, math.Abs(v))
		}
	}
	md, e := sha256FileWithPrefix(modelPath)
	if e != nil {
		return IndependentFacts{}, e
	}
	dd, e := sha256FileWithPrefix(dataPath)
	if e != nil {
		return IndependentFacts{}, e
	}
	return IndependentFacts{ModelDigest: md, InputDigest: dd, RequiredQPrimes: 5, RescaleLevels: 3, RequiredSlots: len(rows), MaxOutputAbs: maxZ}, nil
}

// Model adapter only. Synthesize, Direct Policy V2, repair, security and
// multiclass acceptance are called unchanged in this isolated module.
func BuildBankContract(modelPath, dataPath, role string) (WorkloadContract, error) {
	m, e := bankadapter.LoadModelArtifact(modelPath)
	if e != nil {
		return WorkloadContract{}, e
	}
	rows, e := bankadapter.LoadPartitionCSV(dataPath, role)
	if e != nil {
		return WorkloadContract{}, e
	}
	ids := []string{}
	logits := [][]float64{}
	protected := 0.
	vc := 0
	for _, r := range rows {
		z, _ := m.Logits(r)
		v := append([]float64{}, z[:]...)
		ids = append(ids, r.SampleID)
		logits = append(logits, v)
		gap := math.Abs(z[0] - z[1])
		if gap > .001 {
			vc++
			if protected == 0 || gap < protected {
				protected = gap
			}
		}
	}
	if vc == 0 {
		return WorkloadContract{}, fmt.Errorf("Bank has no applicable selection inputs")
	}
	cal, e := bankadapter.CalibrateModel(m, rows)
	if e != nil {
		return WorkloadContract{}, e
	}
	md, e := sha256FileWithPrefix(modelPath)
	if e != nil {
		return WorkloadContract{}, e
	}
	dd, e := sha256FileWithPrefix(dataPath)
	if e != nil {
		return WorkloadContract{}, e
	}
	c := WorkloadContract{SchemaVersion: WorkloadContractSchemaVersion, WorkloadID: m.DatasetID + "__" + m.ModelID + "__" + role, DatasetID: m.DatasetID, ModelID: m.ModelID, ModelType: m.ModelType, SplitID: role, ModelArtifact: ArtifactBinding{Path: modelPath, SHA256: md}, ValidationData: ArtifactBinding{Path: dataPath, SHA256: dd},
		Graph:              tuner.GraphSummary{MultiplicativeDepth: 1, AddOps: 5632, MulOps: 5888, RotOps: 0, RescaleOps: 1, Notes: []string{"20-256-2 affine/square graph; exact t*t+t=(t+.5)^2-.25; original two logits", "same feature-ciphertext sample-slots and scalar/rescale schedule as journal MLP; three levels, terminal exponent2, Q5"}},
		MulticlassDecision: &MulticlassDecisionStabilityContract{SchemaVersion: certify.MulticlassDecisionContractSchemaV2, ClassCount: 2, TieBreak: certify.DeterministicLowestIndexTieBreak, BoundMode: "uniform_per_logit_v1", MarginFloor: .001, MarginUtilizationCap: .5, ProtectedTopTwoGap: protected, PerLogitErrorBudget: .5 * protected / 2, ValidationDigest: DigestMulticlassPlaintextLogits(ids, logits), ValidationSamples: len(rows), CertifiableSamples: vc, AmbiguousSamples: len(rows) - vc},
		Calibration:        NumericalCalibration{MaxInputAbs: cal.MaxInputAbs, MaxPlaintextOutputAbs: cal.MaxPlaintextLogitAbs, AggregateSensitivity: cal.AggregateSensitivity, SensitivityMethod: EmpiricalIntervalDAGSensitivityV1, CalibrationScope: role + ":" + dd + ";underlying_method=" + cal.Method},
		Deployment:         DeploymentContract{SecurityBits: 128, RequiredSlots: len(rows), MaxEncryptedTrials: 4, ValidationKeyRepeats: 3, PackingStrategy: FeatureCiphertextSampleSlotsV1, AllowedPaths: []tuner.ExecutionPath{tuner.PathRescale}, ScaleTraceMethod: LattigoRescaleScaleTraceV1, RescaleLevelsConsumed: 3, TerminalScaleExponent: 2, RequiredQPrimes: 5}}
	return c, c.Validate()
}
