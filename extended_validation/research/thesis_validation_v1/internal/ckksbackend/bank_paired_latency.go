package ckksbackend

import (
	"fmt"
	"runtime"
	"time"

	"github.com/hasslelee/flipguard/internal/bankadapter"
	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
)

const BankPrimaryPairedLatencySchema = "flipguard_bank_primary_paired_latency_v1"

const (
	BankPairedKindJournalMNIST = "journal_mnist_multiclass"
	BankPairedKindPackedCNN    = "packed_cnn_lite_binary01"
)

// BankPrimaryPairedLatencyArm binds one already selected candidate to its
// concrete Lattigo parameters. The runner never synthesizes or repairs arms.
type BankPrimaryPairedLatencyArm struct {
	ID          string
	Role        string
	CandidateID string
	Profile     CKKSProfile
}

// BankPrimaryPairedLatencyConfig fixes one fresh-keyset timing block.
type BankPrimaryPairedLatencyConfig struct {
	Kind            string
	ModelPath       string
	DataPath        string
	SelectedRowIDs  []int
	Keyset          int
	WarmupRuns      int
	MeasurementRuns int
	MarginFloor     float64
	UtilizationCap  float64
	Arms            []BankPrimaryPairedLatencyArm
}

type BankPrimaryPairedLatencyProtocol struct {
	Kind                    string `json:"kind"`
	Keyset                  int    `json:"keyset"`
	WarmupRuns              int    `json:"warmup_runs"`
	MeasurementRuns         int    `json:"measurement_runs"`
	SelectedInputs          int    `json:"selected_inputs"`
	OrderSchedule           string `json:"order_schedule"`
	KeyPolicy               string `json:"key_policy"`
	OutlierPolicy           string `json:"outlier_policy"`
	LatencyMeasurementUnit  string `json:"latency_measurement_unit"`
	StatisticalUnit         string `json:"statistical_unit"`
	ConfigurationSelection  string `json:"configuration_selection"`
	IndependentInputRole    string `json:"independent_input_role"`
	ConcurrentCKKSProcesses int    `json:"concurrent_ckks_processes"`
}

type BankPrimaryPairedLatencyArmMetadata struct {
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

// BankPrimaryPairedLatencyRecord is one arm execution over the complete frozen
// latency subset. It is deliberately a batch observation for LeNet because
// the implementation batches images across ciphertext slots.
type BankPrimaryPairedLatencyRecord struct {
	Keyset         int `json:"keyset"`
	MeasurementRun int `json:"measurement_run"`
	OrderIndex     int `json:"order_index"`
	OrderPosition  int `json:"order_position"`

	ArmID       string `json:"arm_id"`
	Role        string `json:"role"`
	CandidateID string `json:"candidate_id"`

	SelectedInputs   int                     `json:"selected_inputs"`
	VCert            int                     `json:"v_cert"`
	VAmb             int                     `json:"v_amb"`
	DecisionFlips    int                     `json:"decision_flips"`
	PolicyViolations int                     `json:"reserve_policy_violations"`
	Status           certify.CandidateStatus `json:"decision_stability_status"`

	EncodeEncryptMS  float64 `json:"encode_encrypt_ms"`
	EvaluationOnlyMS float64 `json:"evaluation_only_ms"`
	AdapterIOMS      float64 `json:"adapter_io_ms"`
	DecryptDecodeMS  float64 `json:"decrypt_decode_ms"`
	TotalMS          float64 `json:"total_ms"`
}

type BankPrimaryPairedLatencyResult struct {
	SchemaVersion string `json:"schema_version"`
	DatasetID     string `json:"dataset_id"`
	ModelID       string `json:"model_id"`
	ModelType     string `json:"model_type"`

	Protocol       BankPrimaryPairedLatencyProtocol      `json:"protocol"`
	SelectedRowIDs []int                                 `json:"selected_row_ids"`
	Arms           []BankPrimaryPairedLatencyArmMetadata `json:"arms"`
	Records        []BankPrimaryPairedLatencyRecord      `json:"records"`
}

type bankPrimaryPairedRuntime struct {
	arm     BankPrimaryPairedLatencyArm
	context Context
	runtime ckksTimingRuntime
}

// RunBankPairedLatencyKeyset executes a fixed two-arm comparison under
// one fresh keyset per arm. Results are emitted through onRecord so the command
// layer can fsync an append-only ledger.
func RunBankPairedLatencyKeyset(
	config BankPrimaryPairedLatencyConfig,
	onRecord func(BankPrimaryPairedLatencyRecord) error,
) (BankPrimaryPairedLatencyResult, error) {
	if config.Keyset <= 0 || config.WarmupRuns < 0 || config.MeasurementRuns <= 0 {
		return BankPrimaryPairedLatencyResult{}, fmt.Errorf("invalid paired-latency repetition policy")
	}
	if len(config.SelectedRowIDs) == 0 || len(config.Arms) != 2 {
		return BankPrimaryPairedLatencyResult{}, fmt.Errorf("Bank paired latency requires selected rows and exactly two frozen arms")
	}
	if config.MarginFloor < 0 || config.UtilizationCap <= 0 || config.UtilizationCap > 1 {
		return BankPrimaryPairedLatencyResult{}, fmt.Errorf("invalid decision-stability policy")
	}

	runtimes := make([]bankPrimaryPairedRuntime, 0, len(config.Arms))
	metadata := make([]BankPrimaryPairedLatencyArmMetadata, 0, len(config.Arms))
	seen := make(map[string]bool)
	for _, arm := range config.Arms {
		if arm.ID == "" || arm.Role == "" || arm.CandidateID == "" || seen[arm.ID] {
			return BankPrimaryPairedLatencyResult{}, fmt.Errorf("invalid or duplicate arm %q", arm.ID)
		}
		seen[arm.ID] = true
		setupStart := time.Now()
		context, err := NewContextFromProfile(arm.Profile)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, fmt.Errorf("arm %s context: %w", arm.ID, err)
		}
		var runtimeState ckksTimingRuntime
		if config.Kind == BankPairedKindPackedCNN {
			runtimeState, err = context.newCKKSTimingRuntimeWithRotations([]int{1, 2, 4, 5, 6, 8, 9, 10})
		} else {
			runtimeState, err = context.newCKKSTimingRuntime()
		}
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, fmt.Errorf("arm %s setup/keygen: %w", arm.ID, err)
		}
		runtimes = append(runtimes, bankPrimaryPairedRuntime{arm: arm, context: context, runtime: runtimeState})
		metadata = append(metadata, BankPrimaryPairedLatencyArmMetadata{
			ID: arm.ID, Role: arm.Role, CandidateID: arm.CandidateID,
			ProfileName: arm.Profile.Name, LogN: arm.Profile.Literal.LogN,
			LogQ:            append([]int(nil), logQBitSizes(arm.Profile.Literal)...),
			LogP:            append([]int(nil), logPBitSizes(arm.Profile.Literal)...),
			LogDefaultScale: arm.Profile.Literal.LogDefaultScale,
			SetupKeygenMS:   durationMS(time.Since(setupStart)),
		})
	}

	var datasetID, modelID, modelType string
	var runArm func(bankPrimaryPairedRuntime) (BankPrimaryPairedLatencyRecord, error)
	switch config.Kind {
	case BankPairedKindJournalMNIST:
		model, err := bankadapter.LoadModelArtifact(config.ModelPath)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		allRows, err := bankadapter.LoadPartitionCSV(config.DataPath, "locked_audit")
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		rows, err := selectBankRows(allRows, config.SelectedRowIDs)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		datasetID, modelID, modelType = model.DatasetID, model.ModelID, model.ModelType
		runArm = func(item bankPrimaryPairedRuntime) (BankPrimaryPairedLatencyRecord, error) {
			records, timing, err := item.context.runBankLogitBatch(item.runtime, model, rows)
			if err != nil {
				return BankPrimaryPairedLatencyRecord{}, err
			}
			samples := make([]certify.MulticlassObservedSample, len(records))
			for index, record := range records {
				samples[index] = certify.MulticlassObservedSample{ID: record.SampleID, PlainLogits: record.PlainLogits, ApproxLogits: [][]float64{record.CKKSLogits}}
			}
			aggregation, err := certify.AggregateObservedMulticlassCandidate(samples, 0, config.MarginFloor, config.UtilizationCap)
			if err != nil {
				return BankPrimaryPairedLatencyRecord{}, err
			}
			return BankPrimaryPairedLatencyRecord{
				ArmID: item.arm.ID, Role: item.arm.Role, CandidateID: item.arm.CandidateID,
				SelectedInputs: len(rows), VCert: aggregation.VCert, VAmb: aggregation.VAmb,
				DecisionFlips: aggregation.ArgmaxFlips, PolicyViolations: aggregation.ReserveViolations,
				Status: aggregation.Status, EncodeEncryptMS: timing.EncodeEncryptMS,
				EvaluationOnlyMS: timing.EvaluationOnlyMS, AdapterIOMS: timing.AdapterIOMS,
				DecryptDecodeMS: timing.DecryptDecodeMS, TotalMS: timing.TotalMS,
			}, nil
		}
	case BankPairedKindPackedCNN:
		model, err := loadCNNLiteModel(config.ModelPath)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		allRows, err := loadCNNLiteRows(config.DataPath, model)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		rows, err := selectBankCNNLiteRows(allRows, config.SelectedRowIDs)
		if err != nil {
			return BankPrimaryPairedLatencyResult{}, err
		}
		datasetID, modelID, modelType = model.DatasetID, "packed_cnn_lite_binary01_bank", model.ModelType
		runArm = func(item bankPrimaryPairedRuntime) (BankPrimaryPairedLatencyRecord, error) {
			record := BankPrimaryPairedLatencyRecord{ArmID: item.arm.ID, Role: item.arm.Role, CandidateID: item.arm.CandidateID, SelectedInputs: len(rows)}
			for _, row := range rows {
				observed, err := item.context.runPackedCNNLiteSample(item.runtime, row, model)
				if err != nil {
					return BankPrimaryPairedLatencyRecord{}, err
				}
				margin := bankAbsFloat(observed.PlainScore - model.DecisionThreshold)
				if margin > config.MarginFloor {
					record.VCert++
					if observed.DecisionFlip {
						record.DecisionFlips++
					}
					if !(observed.AbsError < config.UtilizationCap*margin) {
						record.PolicyViolations++
					}
				} else {
					record.VAmb++
				}
				record.EncodeEncryptMS += observed.EncodeEncryptMS
				record.EvaluationOnlyMS += observed.EvalOnlyMS
				record.DecryptDecodeMS += observed.DecryptDecodeMS
				record.TotalMS += observed.TotalEvalMS
			}
			record.Status = certify.StatusSafe
			if record.DecisionFlips > 0 || record.PolicyViolations > 0 {
				record.Status = certify.StatusRejected
			}
			return record, nil
		}
	default:
		return BankPrimaryPairedLatencyResult{}, fmt.Errorf("unknown Bank paired kind %q", config.Kind)
	}

	orders := balancedArmOrders(len(runtimes))
	for warmup := 0; warmup < config.WarmupRuns; warmup++ {
		order := orders[pairedArmOrderIndex((config.Keyset-1)*config.WarmupRuns+warmup, 0, len(orders))]
		for _, armIndex := range order {
			if _, err := runArm(runtimes[armIndex]); err != nil {
				return BankPrimaryPairedLatencyResult{}, fmt.Errorf("warm-up keyset %d arm %s: %w", config.Keyset, runtimes[armIndex].arm.ID, err)
			}
		}
	}

	records := make([]BankPrimaryPairedLatencyRecord, 0, config.MeasurementRuns*len(runtimes))
	for measurementRun := 0; measurementRun < config.MeasurementRuns; measurementRun++ {
		orderIndex := pairedArmOrderIndex((config.Keyset-1)*config.MeasurementRuns+measurementRun, 0, len(orders))
		for orderPosition, armIndex := range orders[orderIndex] {
			record, err := runArm(runtimes[armIndex])
			if err != nil {
				return BankPrimaryPairedLatencyResult{}, fmt.Errorf("measurement keyset %d run %d arm %s: %w", config.Keyset, measurementRun+1, runtimes[armIndex].arm.ID, err)
			}
			record.Keyset = config.Keyset
			record.MeasurementRun = measurementRun + 1
			record.OrderIndex = orderIndex + 1
			record.OrderPosition = orderPosition + 1
			if err := onRecord(record); err != nil {
				return BankPrimaryPairedLatencyResult{}, err
			}
			records = append(records, record)
		}
	}

	return BankPrimaryPairedLatencyResult{
		SchemaVersion: BankPrimaryPairedLatencySchema,
		DatasetID:     datasetID, ModelID: modelID, ModelType: modelType,
		Protocol: BankPrimaryPairedLatencyProtocol{
			Kind: config.Kind, Keyset: config.Keyset, WarmupRuns: config.WarmupRuns,
			MeasurementRuns: config.MeasurementRuns, SelectedInputs: len(config.SelectedRowIDs),
			OrderSchedule:           "balanced_cyclic_and_reverse_per_batch_v1",
			KeyPolicy:               "one_fresh_parameter_compatible_keyset_per_arm_per_keyset_block",
			OutlierPolicy:           "none_all_raw_observations_preserved",
			LatencyMeasurementUnit:  "milliseconds_per_frozen_input_batch",
			StatisticalUnit:         "frozen_input_batch_with_keyset_and_pass_repetitions",
			ConfigurationSelection:  "frozen_direct_and_Bank_B3_fastest_SAFE",
			IndependentInputRole:    "independent_evaluation",
			ConcurrentCKKSProcesses: 0,
		},
		SelectedRowIDs: append([]int(nil), config.SelectedRowIDs...), Arms: metadata, Records: records,
	}, nil
}

func (c Context) runBankLogitBatch(
	runtimeState ckksTimingRuntime,
	model bankadapter.ModelArtifact,
	rows []bankadapter.PartitionRow,
) ([]JournalMNISTMulticlassRecord, JournalMNISTMulticlassSummary, error) {
	totalStart := time.Now()
	evalStart := time.Now()
	var output []*rlwe.Ciphertext
	stats := journalMNISTExecutionStats{}
	var err error
	switch model.ModelType {
	case bankadapter.MLPModelType:
		encodeStart := time.Now()
		var inputs []*rlwe.Ciphertext
		inputs, err = c.encryptBankFeatureVectors(runtimeState, rows)
		stats.EncodeDuration = time.Since(encodeStart)
		stats.InputCiphertexts = len(inputs)
		if err == nil {
			output, err = c.evaluateBankMLP(runtimeState, model, inputs)
		}
		inputs = nil
	default:
		err = fmt.Errorf("unsupported journal multiclass model %q", model.ModelType)
	}
	if err != nil {
		return nil, JournalMNISTMulticlassSummary{}, err
	}
	evalWall := time.Since(evalStart)
	decodeStart := time.Now()
	decoded := make([][]float64, len(output))
	for classIndex, ciphertext := range output {
		decoded[classIndex], err = c.decryptRealSlots(runtimeState.encoder, runtimeState.decryptor, ciphertext, len(rows))
		if err != nil {
			return nil, JournalMNISTMulticlassSummary{}, err
		}
	}
	decodeDuration := time.Since(decodeStart)
	records := make([]JournalMNISTMulticlassRecord, 0, len(rows))
	flips := 0
	for rowIndex, row := range rows {
		plainArray, err := model.Logits(row)
		if err != nil {
			return nil, JournalMNISTMulticlassSummary{}, err
		}
		plain := append([]float64(nil), plainArray[:]...)
		approximate := make([]float64, bankadapter.ClassCount)
		for classIndex := range approximate {
			approximate[classIndex] = decoded[classIndex][rowIndex]
		}
		plainTop, _, gap := topTwoJournalLogits(plain)
		approxTop, _, _ := topTwoJournalLogits(approximate)
		if plainTop != approxTop {
			flips++
		}
		records = append(records, JournalMNISTMulticlassRecord{
			RowID: row.RowID, SampleID: row.SampleID, SourceIndex: row.SourceIndex,
			SourcePartition: row.SourcePartition, Role: row.Role, Label: row.Label,
			PlainLogits: plain, CKKSLogits: approximate, PlainTop1: plainTop,
			CKKSTop1: approxTop, TopTwoGap: gap, ArgmaxFlip: plainTop != approxTop,
		})
	}
	evalDuration := evalWall - stats.EncodeDuration - stats.AdapterIODuration
	if evalDuration < 0 {
		evalDuration = 0
	}
	finalLevel := -1
	if len(output) > 0 {
		finalLevel = output[0].Level()
	}
	output = nil
	runtime.GC()
	return records, JournalMNISTMulticlassSummary{
		ExecutionAdapter: JournalMNISTMulticlassExecutionAdapterV1,
		DatasetID:        model.DatasetID, ModelID: model.ModelID, ModelType: model.ModelType,
		Role: "locked_audit", EvaluatedRows: len(rows), ClassCount: bankadapter.ClassCount,
		EncodeEncryptMS: durationMS(stats.EncodeDuration), EvaluationOnlyMS: durationMS(evalDuration),
		AdapterIOMS: durationMS(stats.AdapterIODuration), DecryptDecodeMS: durationMS(decodeDuration),
		TotalMS: durationMS(time.Since(totalStart)), InputCiphertexts: stats.InputCiphertexts,
		OutputCiphertexts: len(decoded), InitialLevel: c.MaxLevel(), FinalLevel: finalLevel,
		RequiredSlots: len(rows), AvailableSlots: c.Params.MaxSlots(), ArgmaxFlips: flips,
		SpoolBytes: stats.SpoolBytes,
	}, nil
}

func selectBankCNNLiteRows(allRows []cnnLiteRow, selectedRowIDs []int) ([]cnnLiteRow, error) {
	byID := make(map[int]cnnLiteRow, len(allRows))
	for _, row := range allRows {
		byID[row.RowID] = row
	}
	seen := make(map[int]bool, len(selectedRowIDs))
	rows := make([]cnnLiteRow, 0, len(selectedRowIDs))
	for _, rowID := range selectedRowIDs {
		row, ok := byID[rowID]
		if !ok || seen[rowID] {
			return nil, fmt.Errorf("selected CNN-lite row ID %d is missing or duplicated", rowID)
		}
		seen[rowID] = true
		rows = append(rows, row)
	}
	return rows, nil
}

func bankAbsFloat(value float64) float64 {
	if value < 0 {
		return -value
	}
	return value
}

func selectBankRows(allRows []bankadapter.PartitionRow, selectedRowIDs []int) ([]bankadapter.PartitionRow, error) {
	byID := make(map[int]bankadapter.PartitionRow, len(allRows))
	for _, row := range allRows {
		byID[row.RowID] = row
	}
	seen := make(map[int]bool, len(selectedRowIDs))
	rows := make([]bankadapter.PartitionRow, 0, len(selectedRowIDs))
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
