package ckksbackend

import (
	"fmt"
	"math"
	"runtime"
	"time"

	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/journalmnist"
)

const JournalMLPPairedLatencySchemaV1 = "flipguard_journal_mlp_paired_latency_v1"

// JournalMLPPairedLatencyArm binds one frozen candidate to its exact runtime
// profile. Profiles are supplied by the caller so catalog concrete primes are
// not silently regenerated from bit lengths.
type JournalMLPPairedLatencyArm struct {
	ID          string
	Role        string
	CandidateID string
	Profile     CKKSProfile
}

// JournalMLPPairedLatencyConfig fixes one fresh-key process block.
type JournalMLPPairedLatencyConfig struct {
	ModelPath       string
	AuditPath       string
	SelectedRowIDs  []int
	Keyset          int
	WarmupRuns      int
	MeasurementRuns int
	MarginFloor     float64
	UtilizationCap  float64
	Arms            []JournalMLPPairedLatencyArm
}

type JournalMLPPairedLatencyProtocol struct {
	Keyset                     int    `json:"keyset"`
	WarmupRuns                 int    `json:"warmup_runs"`
	MeasurementRuns            int    `json:"measurement_runs"`
	SelectedImages             int    `json:"selected_images"`
	OrderSchedule              string `json:"order_schedule"`
	KeyPolicy                  string `json:"key_policy"`
	OutlierPolicy              string `json:"outlier_policy"`
	LatencyMeasurementUnit     string `json:"latency_measurement_unit"`
	StatisticalObservationUnit string `json:"statistical_observation_unit"`
}

type JournalMLPPairedLatencyArmMetadata struct {
	ID              string  `json:"id"`
	Role            string  `json:"role"`
	CandidateID     string  `json:"candidate_id"`
	ProfileName     string  `json:"profile_name"`
	LogN            int     `json:"log_n"`
	LogQ            []int   `json:"log_q"`
	LogP            []int   `json:"log_p"`
	LogDefaultScale int     `json:"log_default_scale"`
	SetupKeygenMS   float64 `json:"setup_keygen_ms"`
}

type JournalMLPPairedLatencyRecord struct {
	ObservationIndex int `json:"observation_index"`
	Keyset           int `json:"keyset"`
	MeasurementRun   int `json:"measurement_run"`
	RowIndex         int `json:"row_index"`
	RowID            int `json:"row_id"`
	SourceIndex      int `json:"source_index"`
	Label            int `json:"label"`
	OrderIndex       int `json:"order_index"`
	OrderPosition    int `json:"order_position"`

	SampleID    string `json:"sample_id"`
	ArmID       string `json:"arm_id"`
	Role        string `json:"role"`
	CandidateID string `json:"candidate_id"`

	PlainLogits []float64 `json:"plaintext_logits"`
	CKKSLogits  []float64 `json:"ckks_logits"`
	AbsErrors   []float64 `json:"per_logit_absolute_error"`
	PlainTop1   int       `json:"plaintext_top_1"`
	PlainTop2   int       `json:"plaintext_top_2"`
	CKKSTop1    int       `json:"ckks_top_1"`
	TopTwoGap   float64   `json:"top_two_gap"`

	PairwiseDecisionBudget float64 `json:"pairwise_decision_budget"`
	MinimumCapRequired     float64 `json:"minimum_cap_required"`
	ArgmaxFlip             bool    `json:"argmax_flip"`
	ReservePolicyPass      bool    `json:"reserve_policy_pass"`
	ReservePolicyViolation bool    `json:"reserve_policy_violation"`

	EncodeEncryptMS  float64 `json:"encode_encrypt_ms"`
	EvaluationOnlyMS float64 `json:"evaluation_only_ms"`
	DecryptDecodeMS  float64 `json:"decrypt_decode_ms"`
	TotalMS          float64 `json:"total_ms"`
}

type JournalMLPPairedLatencyResult struct {
	SchemaVersion string `json:"schema_version"`
	DatasetID     string `json:"dataset_id"`
	ModelID       string `json:"model_id"`
	ModelType     string `json:"model_type"`

	Protocol JournalMLPPairedLatencyProtocol      `json:"protocol"`
	Arms     []JournalMLPPairedLatencyArmMetadata `json:"arms"`
	Records  []JournalMLPPairedLatencyRecord      `json:"records"`
}

type journalMLPPairedRuntime struct {
	arm     JournalMLPPairedLatencyArm
	context Context
	runtime ckksTimingRuntime
}

// RunJournalMLPPairedLatencyKeyset evaluates every selected image separately.
// It deliberately does not copy a packed-batch latency to multiple images.
// The callback supports an append-only, fsync'd ledger at the command layer.
func RunJournalMLPPairedLatencyKeyset(
	config JournalMLPPairedLatencyConfig,
	onRecord func(JournalMLPPairedLatencyRecord) error,
) (JournalMLPPairedLatencyResult, error) {
	if config.Keyset <= 0 || config.WarmupRuns < 0 || config.MeasurementRuns <= 0 {
		return JournalMLPPairedLatencyResult{}, fmt.Errorf("invalid paired-latency repetition policy")
	}
	if len(config.SelectedRowIDs) == 0 || len(config.Arms) < 2 {
		return JournalMLPPairedLatencyResult{}, fmt.Errorf("paired latency requires selected rows and at least two arms")
	}
	if config.MarginFloor < 0 || config.UtilizationCap <= 0 || config.UtilizationCap > 1 {
		return JournalMLPPairedLatencyResult{}, fmt.Errorf("invalid multiclass admission policy")
	}

	model, err := journalmnist.LoadModelArtifact(config.ModelPath)
	if err != nil {
		return JournalMLPPairedLatencyResult{}, err
	}
	if model.ModelType != journalmnist.MLPModelType {
		return JournalMLPPairedLatencyResult{}, fmt.Errorf("focused paired latency requires the frozen MLP-100 model")
	}
	allRows, err := journalmnist.LoadPartitionCSV(config.AuditPath, "locked_audit")
	if err != nil {
		return JournalMLPPairedLatencyResult{}, err
	}
	rows, err := selectJournalMNISTRows(allRows, config.SelectedRowIDs)
	if err != nil {
		return JournalMLPPairedLatencyResult{}, err
	}

	runtimes := make([]journalMLPPairedRuntime, 0, len(config.Arms))
	metadata := make([]JournalMLPPairedLatencyArmMetadata, 0, len(config.Arms))
	seenArms := make(map[string]bool)
	for _, arm := range config.Arms {
		if arm.ID == "" || arm.Role == "" || arm.CandidateID == "" || seenArms[arm.ID] {
			return JournalMLPPairedLatencyResult{}, fmt.Errorf("invalid or duplicate arm identity %q", arm.ID)
		}
		seenArms[arm.ID] = true
		setupStart := time.Now()
		context, err := NewContextFromProfile(arm.Profile)
		if err != nil {
			return JournalMLPPairedLatencyResult{}, fmt.Errorf("arm %s context: %w", arm.ID, err)
		}
		runtimeState, err := context.newCKKSTimingRuntime()
		if err != nil {
			return JournalMLPPairedLatencyResult{}, fmt.Errorf("arm %s setup/keygen: %w", arm.ID, err)
		}
		setupMS := durationMS(time.Since(setupStart))
		runtimes = append(runtimes, journalMLPPairedRuntime{arm: arm, context: context, runtime: runtimeState})
		metadata = append(metadata, JournalMLPPairedLatencyArmMetadata{
			ID: arm.ID, Role: arm.Role, CandidateID: arm.CandidateID,
			ProfileName: arm.Profile.Name, LogN: arm.Profile.Literal.LogN,
			LogQ:            append([]int(nil), logQBitSizes(arm.Profile.Literal)...),
			LogP:            append([]int(nil), logPBitSizes(arm.Profile.Literal)...),
			LogDefaultScale: arm.Profile.Literal.LogDefaultScale,
			SetupKeygenMS:   setupMS,
		})
	}
	orders := balancedArmOrders(len(runtimes))
	for warmup := 0; warmup < config.WarmupRuns; warmup++ {
		for rowIndex, row := range rows {
			order := orders[pairedArmOrderIndex((config.Keyset-1)*config.WarmupRuns+warmup, rowIndex, len(orders))]
			for _, armIndex := range order {
				item := runtimes[armIndex]
				if _, _, err := item.context.runJournalMLPSingleImage(item.runtime, model, row); err != nil {
					return JournalMLPPairedLatencyResult{}, fmt.Errorf("warm-up keyset %d row %d arm %s: %w", config.Keyset, row.RowID, item.arm.ID, err)
				}
			}
		}
	}

	capacity := config.MeasurementRuns * len(rows) * len(runtimes)
	records := make([]JournalMLPPairedLatencyRecord, 0, capacity)
	for measurementRun := 0; measurementRun < config.MeasurementRuns; measurementRun++ {
		for rowIndex, row := range rows {
			orderIndex := pairedArmOrderIndex((config.Keyset-1)*config.MeasurementRuns+measurementRun, rowIndex, len(orders))
			for orderPosition, armIndex := range orders[orderIndex] {
				item := runtimes[armIndex]
				backendRecord, summary, err := item.context.runJournalMLPSingleImage(item.runtime, model, row)
				if err != nil {
					return JournalMLPPairedLatencyResult{}, fmt.Errorf("measurement keyset %d run %d row %d arm %s: %w", config.Keyset, measurementRun+1, row.RowID, item.arm.ID, err)
				}
				aggregation, err := certify.AggregateObservedMulticlassCandidate(
					[]certify.MulticlassObservedSample{{ID: row.SampleID, PlainLogits: backendRecord.PlainLogits, ApproxLogits: [][]float64{backendRecord.CKKSLogits}}},
					0, config.MarginFloor, config.UtilizationCap,
				)
				if err != nil || len(aggregation.Observations) != 1 {
					return JournalMLPPairedLatencyResult{}, fmt.Errorf("certify row %d arm %s: %w", row.RowID, item.arm.ID, err)
				}
				observation := aggregation.Observations[0]
				record := JournalMLPPairedLatencyRecord{
					ObservationIndex: len(records) + 1, Keyset: config.Keyset,
					MeasurementRun: measurementRun + 1, RowIndex: rowIndex + 1,
					RowID: row.RowID, SourceIndex: row.SourceIndex, Label: row.Label,
					OrderIndex: orderIndex + 1, OrderPosition: orderPosition + 1,
					SampleID: row.SampleID, ArmID: item.arm.ID, Role: item.arm.Role,
					CandidateID: item.arm.CandidateID,
					PlainLogits: observation.PlainLogits, CKKSLogits: observation.CKKSLogits,
					AbsErrors: observation.AbsErrors, PlainTop1: observation.PlainTop1,
					PlainTop2: observation.PlainTop2, CKKSTop1: observation.CKKSTop1,
					TopTwoGap:              observation.TopTwoGap,
					PairwiseDecisionBudget: observation.PairwiseDecisionBudget,
					MinimumCapRequired:     observation.MinimumCapRequired,
					ArgmaxFlip:             observation.ArgmaxFlip,
					ReservePolicyPass:      observation.ReservePolicyPass,
					ReservePolicyViolation: observation.ReserveViolation,
					EncodeEncryptMS:        summary.EncodeEncryptMS,
					EvaluationOnlyMS:       summary.EvaluationOnlyMS,
					DecryptDecodeMS:        summary.DecryptDecodeMS, TotalMS: summary.TotalMS,
				}
				if err := onRecord(record); err != nil {
					return JournalMLPPairedLatencyResult{}, fmt.Errorf("persist observation %d: %w", record.ObservationIndex, err)
				}
				records = append(records, record)
			}
		}
	}

	return JournalMLPPairedLatencyResult{
		SchemaVersion: JournalMLPPairedLatencySchemaV1,
		DatasetID:     model.DatasetID, ModelID: model.ModelID, ModelType: model.ModelType,
		Protocol: JournalMLPPairedLatencyProtocol{
			Keyset: config.Keyset, WarmupRuns: config.WarmupRuns,
			MeasurementRuns: config.MeasurementRuns, SelectedImages: len(rows),
			OrderSchedule:              "balanced_cyclic_and_reverse_image_rotated_v1",
			KeyPolicy:                  "one_fresh_parameter_compatible_keyset_per_arm_per_process_block",
			OutlierPolicy:              "none_all_raw_observations_preserved",
			LatencyMeasurementUnit:     "milliseconds_per_single_image_encrypted_inference",
			StatisticalObservationUnit: "image_cluster_with_keyset_and_pass_repetitions",
		},
		Arms: metadata, Records: records,
	}, nil
}

func selectJournalMNISTRows(allRows []journalmnist.PartitionRow, selectedRowIDs []int) ([]journalmnist.PartitionRow, error) {
	byID := make(map[int]journalmnist.PartitionRow, len(allRows))
	for _, row := range allRows {
		byID[row.RowID] = row
	}
	seen := make(map[int]bool, len(selectedRowIDs))
	rows := make([]journalmnist.PartitionRow, 0, len(selectedRowIDs))
	for _, rowID := range selectedRowIDs {
		row, ok := byID[rowID]
		if !ok || seen[rowID] {
			return nil, fmt.Errorf("selected row ID %d is missing or duplicated", rowID)
		}
		seen[rowID] = true
		rows = append(rows, row)
	}
	return rows, nil
}

func (c Context) runJournalMLPSingleImage(
	runtimeState ckksTimingRuntime,
	model journalmnist.ModelArtifact,
	row journalmnist.PartitionRow,
) (JournalMNISTMulticlassRecord, JournalMNISTMulticlassSummary, error) {
	totalStart := time.Now()
	encodeStart := time.Now()
	inputs, err := c.encryptMNISTFeatureVectors(runtimeState, []journalmnist.PartitionRow{row})
	encodeMS := durationMS(time.Since(encodeStart))
	if err != nil {
		return JournalMNISTMulticlassRecord{}, JournalMNISTMulticlassSummary{}, err
	}
	evalStart := time.Now()
	output, err := c.evaluateMNISTMLP(runtimeState, journalmnist.MLPModel{Parameters: model.Parameters}, inputs)
	evalMS := durationMS(time.Since(evalStart))
	inputs = nil
	if err != nil {
		return JournalMNISTMulticlassRecord{}, JournalMNISTMulticlassSummary{}, err
	}
	decodeStart := time.Now()
	approximate := make([]float64, journalmnist.ClassCount)
	for classIndex, ciphertext := range output {
		values, err := c.decryptRealSlots(runtimeState.encoder, runtimeState.decryptor, ciphertext, 1)
		if err != nil {
			return JournalMNISTMulticlassRecord{}, JournalMNISTMulticlassSummary{}, err
		}
		approximate[classIndex] = values[0]
	}
	decodeMS := durationMS(time.Since(decodeStart))
	plainArray, err := model.Logits(row)
	if err != nil {
		return JournalMNISTMulticlassRecord{}, JournalMNISTMulticlassSummary{}, err
	}
	plain := append([]float64(nil), plainArray[:]...)
	plainTop, _, gap := topTwoJournalLogits(plain)
	approxTop, _, _ := topTwoJournalLogits(approximate)
	totalMS := durationMS(time.Since(totalStart))
	result := JournalMNISTMulticlassRecord{
		RowID: row.RowID, SampleID: row.SampleID, SourceIndex: row.SourceIndex,
		SourcePartition: row.SourcePartition, Role: row.Role, Label: row.Label,
		PlainLogits: plain, CKKSLogits: approximate, PlainTop1: plainTop,
		CKKSTop1: approxTop, TopTwoGap: gap, ArgmaxFlip: plainTop != approxTop,
	}
	summary := JournalMNISTMulticlassSummary{
		ExecutionAdapter: JournalMNISTMulticlassExecutionAdapterV1,
		DatasetID:        model.DatasetID, ModelID: model.ModelID, ModelType: model.ModelType,
		Role: row.Role, EvaluatedRows: 1, ClassCount: journalmnist.ClassCount,
		EncodeEncryptMS: encodeMS, EvaluationOnlyMS: evalMS,
		DecryptDecodeMS: decodeMS, TotalMS: totalMS, AmortizedMS: totalMS,
		InputCiphertexts: journalmnist.PixelCount, OutputCiphertexts: len(output),
		InitialLevel: c.MaxLevel(), FinalLevel: output[0].Level(),
		RequiredSlots: 1, AvailableSlots: c.Params.MaxSlots(),
	}
	if result.ArgmaxFlip {
		summary.ArgmaxFlips = 1
	}
	output = nil
	runtime.GC()
	return result, summary, nil
}

func finiteLatency(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value > 0
}
