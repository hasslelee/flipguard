package ckksbackend

import (
	"fmt"
	"math"
	"sort"
	"time"
)

const PairedTabularLatencySchemaVersion = 1

// PairedTabularLatencyArm is one frozen configuration in a paired latency run.
// Each arm owns parameter-compatible key material that is reused for the
// entire run.
type PairedTabularLatencyArm struct {
	ID             string
	Role           string
	CandidateID    string
	Profile        CKKSProfile
	EvaluationMode string
}

// PairedTabularLatencyConfig fixes the workload and measurement schedule.
type PairedTabularLatencyConfig struct {
	ModelPath   string
	TestPath    string
	DatasetID   string
	ModelID     string
	MaxRows     int
	WarmupRuns  int
	MeasureRuns int
	Arms        []PairedTabularLatencyArm
}

// PairedTabularLatencyProtocol records the controls applied by the runner.
type PairedTabularLatencyProtocol struct {
	WarmupRuns       int    `json:"warmup_runs"`
	MeasurementRuns  int    `json:"measurement_runs"`
	RequestedMaxRows int    `json:"requested_max_rows"`
	SelectedRows     int    `json:"selected_rows"`
	SelectedRowIDs   []int  `json:"selected_row_ids"`
	OrderSchedule    string `json:"order_schedule"`
	KeyPolicy        string `json:"key_policy"`
	OutlierPolicy    string `json:"outlier_policy"`
	MeasurementUnit  string `json:"measurement_unit"`
}

// PairedTabularLatencyArmMetadata binds a role to its exact CKKS literal.
type PairedTabularLatencyArmMetadata struct {
	ID              string  `json:"id"`
	Role            string  `json:"role"`
	CandidateID     string  `json:"candidate_id"`
	ProfileName     string  `json:"profile_name"`
	EvaluationMode  string  `json:"evaluation_mode"`
	LogN            int     `json:"log_n"`
	LogQ            []int   `json:"log_q"`
	LogP            []int   `json:"log_p"`
	LogDefaultScale int     `json:"log_default_scale"`
	SetupMS         float64 `json:"setup_ms"`
}

// PairedTabularLatencyRecord is one timed observation in execution order.
type PairedTabularLatencyRecord struct {
	ObservationIndex int `json:"observation_index"`
	MeasurementRun   int `json:"measurement_run"`
	RowIndex         int `json:"row_index"`
	RowID            int `json:"row_id"`
	OrderIndex       int `json:"order_index"`
	OrderPosition    int `json:"order_position"`

	ArmID       string `json:"arm_id"`
	Role        string `json:"role"`
	CandidateID string `json:"candidate_id"`

	PlainY       float64 `json:"plain_y"`
	CKKSY        float64 `json:"ckks_y"`
	YError       float64 `json:"y_error"`
	DecisionFlip bool    `json:"decision_flip"`

	EncodeEncryptMS  float64 `json:"encode_encrypt_ms"`
	ModelEvalMS      float64 `json:"model_eval_ms"`
	PolynomialEvalMS float64 `json:"polynomial_eval_ms"`
	EvalOnlyMS       float64 `json:"eval_only_ms"`
	DecryptDecodeMS  float64 `json:"decrypt_decode_ms"`
	TotalMS          float64 `json:"total_ms"`
}

// PairedTabularLatencyArmSummary summarizes raw observations without removing
// outliers.
type PairedTabularLatencyArmSummary struct {
	ArmID       string `json:"arm_id"`
	Role        string `json:"role"`
	CandidateID string `json:"candidate_id"`

	Observations  int     `json:"observations"`
	DecisionFlips int     `json:"decision_flips"`
	MaxYError     float64 `json:"max_y_error"`

	MeanTotalMS   float64 `json:"mean_total_ms"`
	MedianTotalMS float64 `json:"median_total_ms"`
	P95TotalMS    float64 `json:"p95_total_ms"`
	StdDevTotalMS float64 `json:"stddev_total_ms"`
	IQRTotalMS    float64 `json:"iqr_total_ms"`

	MeanEvalOnlyMS   float64 `json:"mean_eval_only_ms"`
	MedianEvalOnlyMS float64 `json:"median_eval_only_ms"`
	P95EvalOnlyMS    float64 `json:"p95_eval_only_ms"`
	StdDevEvalOnlyMS float64 `json:"stddev_eval_only_ms"`
	IQREvalOnlyMS    float64 `json:"iqr_eval_only_ms"`
}

// PairedTabularLatencyPairSummary compares observations sharing the same
// measurement run and row. Ratio is numerator latency divided by denominator
// latency; values above one mean the denominator arm was faster.
type PairedTabularLatencyPairSummary struct {
	NumeratorArmID   string `json:"numerator_arm_id"`
	DenominatorArmID string `json:"denominator_arm_id"`
	Pairs            int    `json:"pairs"`

	GeometricMeanTotalRatio float64 `json:"geometric_mean_total_ratio"`
	MeanTotalDifferenceMS   float64 `json:"mean_paired_total_difference_ms"`
	MedianTotalDifferenceMS float64 `json:"median_paired_total_difference_ms"`
	P95TotalDifferenceMS    float64 `json:"p95_paired_total_difference_ms"`

	GeometricMeanEvalOnlyRatio float64 `json:"geometric_mean_eval_only_ratio"`
	MeanEvalOnlyDifferenceMS   float64 `json:"mean_paired_eval_only_difference_ms"`
	MedianEvalOnlyDifferenceMS float64 `json:"median_paired_eval_only_difference_ms"`
	P95EvalOnlyDifferenceMS    float64 `json:"p95_paired_eval_only_difference_ms"`
}

// PairedTabularLatencyResult preserves both the complete raw timing records and
// their summaries.
type PairedTabularLatencyResult struct {
	SchemaVersion int `json:"schema_version"`

	DatasetID   string `json:"dataset_id"`
	DatasetName string `json:"dataset_name"`
	ModelID     string `json:"model_id"`
	ModelType   string `json:"model_type"`

	Protocol PairedTabularLatencyProtocol      `json:"protocol"`
	Arms     []PairedTabularLatencyArmMetadata `json:"arms"`
	Records  []PairedTabularLatencyRecord      `json:"records"`

	ArmSummaries  []PairedTabularLatencyArmSummary  `json:"arm_summaries"`
	PairSummaries []PairedTabularLatencyPairSummary `json:"pair_summaries"`
}

type pairedTabularArmRuntime struct {
	arm     PairedTabularLatencyArm
	context Context
	runtime ckksTimingRuntime
}

// RunPairedTabularLatency executes all arms in one process using a balanced,
// deterministic order. Different CKKS parameter sets cannot share keys, so
// each arm creates one compatible key set and reuses it for warm-up and all
// measured observations.
func RunPairedTabularLatency(
	config PairedTabularLatencyConfig,
) (PairedTabularLatencyResult, error) {
	if config.WarmupRuns < 0 {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"warmup runs must be non-negative",
		)
	}
	if config.MeasureRuns <= 0 {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"measurement runs must be positive",
		)
	}
	if config.MaxRows < 0 {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"max rows must be non-negative",
		)
	}
	if len(config.Arms) < 2 {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"paired latency requires at least two arms",
		)
	}

	model, err := loadTabularModelArtifact(config.ModelPath)
	if err != nil {
		return PairedTabularLatencyResult{}, err
	}
	if model.DatasetID != config.DatasetID ||
		model.ModelID != config.ModelID {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"workload identity mismatch: model has %s/%s, requested %s/%s",
			model.DatasetID,
			model.ModelID,
			config.DatasetID,
			config.ModelID,
		)
	}
	if err := validateTabularDecisionThreshold(
		model.PolynomialScore.DecisionThreshold,
	); err != nil {
		return PairedTabularLatencyResult{}, err
	}

	rows, err := loadTabularTestRows(config.TestPath, model.InputDim)
	if err != nil {
		return PairedTabularLatencyResult{}, err
	}
	if err := validateTabularPlainDecisions(
		rows,
		model.PolynomialScore.DecisionThreshold,
	); err != nil {
		return PairedTabularLatencyResult{}, err
	}
	rows = selectPairedLatencyRows(rows, config.MaxRows)
	if len(rows) == 0 {
		return PairedTabularLatencyResult{}, fmt.Errorf(
			"no rows selected for paired latency",
		)
	}

	runtimes, metadata, err := preparePairedTabularArms(config.Arms)
	if err != nil {
		return PairedTabularLatencyResult{}, err
	}
	orders := balancedArmOrders(len(runtimes))

	for warmupRun := 0; warmupRun < config.WarmupRuns; warmupRun++ {
		for rowIndex, row := range rows {
			orderIndex := pairedArmOrderIndex(
				warmupRun,
				rowIndex,
				len(orders),
			)
			order := orders[orderIndex]
			for _, armIndex := range order {
				item := runtimes[armIndex]
				if _, err := item.context.runTabularTimedInference(
					item.runtime,
					row,
					model,
					item.arm.EvaluationMode,
					1,
					1,
				); err != nil {
					return PairedTabularLatencyResult{}, fmt.Errorf(
						"warm-up run %d row %d arm %s: %w",
						warmupRun+1,
						row.RowID,
						item.arm.ID,
						err,
					)
				}
			}
		}
	}

	recordCapacity :=
		config.MeasureRuns * len(rows) * len(runtimes)
	records := make(
		[]PairedTabularLatencyRecord,
		0,
		recordCapacity,
	)
	for measureRun := 0; measureRun < config.MeasureRuns; measureRun++ {
		for rowIndex, row := range rows {
			orderIndex := pairedArmOrderIndex(
				measureRun,
				rowIndex,
				len(orders),
			)
			for orderPosition, armIndex := range orders[orderIndex] {
				item := runtimes[armIndex]
				raw, err := item.context.runTabularTimedInference(
					item.runtime,
					row,
					model,
					item.arm.EvaluationMode,
					1,
					1,
				)
				if err != nil {
					return PairedTabularLatencyResult{}, fmt.Errorf(
						"measurement run %d row %d arm %s: %w",
						measureRun+1,
						row.RowID,
						item.arm.ID,
						err,
					)
				}
				records = append(records, PairedTabularLatencyRecord{
					ObservationIndex: len(records) + 1,
					MeasurementRun:   measureRun + 1,
					RowIndex:         rowIndex + 1,
					RowID:            row.RowID,
					OrderIndex:       orderIndex + 1,
					OrderPosition:    orderPosition + 1,
					ArmID:            item.arm.ID,
					Role:             item.arm.Role,
					CandidateID:      item.arm.CandidateID,
					PlainY:           raw.PlainY,
					CKKSY:            raw.CKKSY,
					YError:           raw.YError,
					DecisionFlip:     raw.DecisionFlip,
					EncodeEncryptMS:  raw.EncodeEncryptMS,
					ModelEvalMS:      raw.ModelEvalMS,
					PolynomialEvalMS: raw.PolynomialEvalMS,
					EvalOnlyMS:       raw.EvalOnlyMS,
					DecryptDecodeMS:  raw.DecryptDecodeMS,
					TotalMS:          raw.TotalEvalMS,
				})
			}
		}
	}

	armSummaries, err := summarizePairedTabularArms(
		config.Arms,
		records,
	)
	if err != nil {
		return PairedTabularLatencyResult{}, err
	}
	pairSummaries, err := summarizePairedTabularPairs(
		config.Arms,
		records,
	)
	if err != nil {
		return PairedTabularLatencyResult{}, err
	}

	rowIDs := make([]int, len(rows))
	for index, row := range rows {
		rowIDs[index] = row.RowID
	}

	return PairedTabularLatencyResult{
		SchemaVersion: PairedTabularLatencySchemaVersion,
		DatasetID:     model.DatasetID,
		DatasetName:   model.DatasetName,
		ModelID:       model.ModelID,
		ModelType:     model.ModelType,
		Protocol: PairedTabularLatencyProtocol{
			WarmupRuns:       config.WarmupRuns,
			MeasurementRuns:  config.MeasureRuns,
			RequestedMaxRows: config.MaxRows,
			SelectedRows:     len(rows),
			SelectedRowIDs:   rowIDs,
			OrderSchedule:    "balanced_cyclic_and_reverse_row_rotated_v1",
			KeyPolicy:        "one_parameter_compatible_keyset_per_arm_reused_within_workload",
			OutlierPolicy:    "none_all_raw_observations_preserved",
			MeasurementUnit:  "milliseconds",
		},
		Arms:          metadata,
		Records:       records,
		ArmSummaries:  armSummaries,
		PairSummaries: pairSummaries,
	}, nil
}

func preparePairedTabularArms(
	arms []PairedTabularLatencyArm,
) (
	[]pairedTabularArmRuntime,
	[]PairedTabularLatencyArmMetadata,
	error,
) {
	seenIDs := make(map[string]bool)
	runtimes := make([]pairedTabularArmRuntime, 0, len(arms))
	metadata := make(
		[]PairedTabularLatencyArmMetadata,
		0,
		len(arms),
	)
	for _, arm := range arms {
		if arm.ID == "" || arm.Role == "" || arm.CandidateID == "" {
			return nil, nil, fmt.Errorf(
				"paired latency arm identity fields must not be empty",
			)
		}
		if seenIDs[arm.ID] {
			return nil, nil, fmt.Errorf(
				"duplicate paired latency arm ID %q",
				arm.ID,
			)
		}
		seenIDs[arm.ID] = true

		mode, err := normalizeCKKSEvaluationMode(
			arm.EvaluationMode,
		)
		if err != nil {
			return nil, nil, fmt.Errorf(
				"arm %s evaluation mode: %w",
				arm.ID,
				err,
			)
		}
		arm.EvaluationMode = mode

		setupStart := time.Now()
		context, err := NewContextFromProfile(arm.Profile)
		if err != nil {
			return nil, nil, fmt.Errorf(
				"arm %s context: %w",
				arm.ID,
				err,
			)
		}
		runtimeState, err := context.newCKKSTimingRuntime()
		if err != nil {
			return nil, nil, fmt.Errorf(
				"arm %s key/runtime setup: %w",
				arm.ID,
				err,
			)
		}
		setupMS := durationMS(time.Since(setupStart))
		runtimes = append(runtimes, pairedTabularArmRuntime{
			arm:     arm,
			context: context,
			runtime: runtimeState,
		})
		metadata = append(metadata, PairedTabularLatencyArmMetadata{
			ID:             arm.ID,
			Role:           arm.Role,
			CandidateID:    arm.CandidateID,
			ProfileName:    arm.Profile.Name,
			EvaluationMode: mode,
			LogN:           arm.Profile.Literal.LogN,
			LogQ: append(
				[]int(nil),
				logQBitSizes(arm.Profile.Literal)...,
			),
			LogP: append(
				[]int(nil),
				logPBitSizes(arm.Profile.Literal)...,
			),
			LogDefaultScale: arm.Profile.Literal.LogDefaultScale,
			SetupMS:         setupMS,
		})
	}
	return runtimes, metadata, nil
}

func selectPairedLatencyRows(
	rows []tabularTestRow,
	maxRows int,
) []tabularTestRow {
	if maxRows == 0 || maxRows >= len(rows) {
		return append([]tabularTestRow(nil), rows...)
	}
	if maxRows == 1 {
		return []tabularTestRow{rows[len(rows)/2]}
	}

	selected := make([]tabularTestRow, 0, maxRows)
	for index := 0; index < maxRows; index++ {
		position := index * (len(rows) - 1) / (maxRows - 1)
		selected = append(selected, rows[position])
	}
	return selected
}

func balancedArmOrders(armCount int) [][]int {
	if armCount <= 0 {
		return nil
	}

	base := make([]int, armCount)
	for index := range base {
		base[index] = index
	}

	orders := make([][]int, 0, 2*armCount)
	for rotation := 0; rotation < armCount; rotation++ {
		order := make([]int, armCount)
		for position := range order {
			order[position] =
				base[(position+rotation)%armCount]
		}
		orders = append(orders, order)
	}
	for rotation := 0; rotation < armCount; rotation++ {
		order := make([]int, armCount)
		for position := range order {
			index :=
				(armCount - 1 - position + rotation) % armCount
			order[position] = base[index]
		}
		orders = append(orders, order)
	}
	return orders
}

func pairedArmOrderIndex(
	runIndex int,
	rowIndex int,
	orderCount int,
) int {
	if orderCount <= 0 {
		return 0
	}
	return (runIndex + rowIndex) % orderCount
}

func summarizePairedTabularArms(
	arms []PairedTabularLatencyArm,
	records []PairedTabularLatencyRecord,
) ([]PairedTabularLatencyArmSummary, error) {
	output := make(
		[]PairedTabularLatencyArmSummary,
		0,
		len(arms),
	)
	for _, arm := range arms {
		totalValues := make([]float64, 0)
		evalValues := make([]float64, 0)
		flips := 0
		maxError := 0.0
		for _, record := range records {
			if record.ArmID != arm.ID {
				continue
			}
			totalValues = append(totalValues, record.TotalMS)
			evalValues = append(evalValues, record.EvalOnlyMS)
			if record.DecisionFlip {
				flips++
			}
			maxError = math.Max(maxError, record.YError)
		}
		stats, err := summarizeLatencyValues(totalValues)
		if err != nil {
			return nil, fmt.Errorf(
				"summarize arm %s: %w",
				arm.ID,
				err,
			)
		}
		evalStats, err := summarizeLatencyValues(evalValues)
		if err != nil {
			return nil, fmt.Errorf(
				"summarize arm %s eval-only: %w",
				arm.ID,
				err,
			)
		}
		output = append(output, PairedTabularLatencyArmSummary{
			ArmID:            arm.ID,
			Role:             arm.Role,
			CandidateID:      arm.CandidateID,
			Observations:     len(totalValues),
			DecisionFlips:    flips,
			MaxYError:        maxError,
			MeanTotalMS:      stats.mean,
			MedianTotalMS:    stats.median,
			P95TotalMS:       stats.p95,
			StdDevTotalMS:    stats.stddev,
			IQRTotalMS:       stats.iqr,
			MeanEvalOnlyMS:   evalStats.mean,
			MedianEvalOnlyMS: evalStats.median,
			P95EvalOnlyMS:    evalStats.p95,
			StdDevEvalOnlyMS: evalStats.stddev,
			IQREvalOnlyMS:    evalStats.iqr,
		})
	}
	return output, nil
}

func summarizePairedTabularPairs(
	arms []PairedTabularLatencyArm,
	records []PairedTabularLatencyRecord,
) ([]PairedTabularLatencyPairSummary, error) {
	type observationKey struct {
		run int
		row int
	}
	type observation struct {
		totalMS    float64
		evalOnlyMS float64
	}
	byArm := make(
		map[string]map[observationKey]observation,
		len(arms),
	)
	for _, arm := range arms {
		byArm[arm.ID] = make(map[observationKey]observation)
	}
	for _, record := range records {
		key := observationKey{
			run: record.MeasurementRun,
			row: record.RowID,
		}
		if _, duplicate := byArm[record.ArmID][key]; duplicate {
			return nil, fmt.Errorf(
				"duplicate observation for arm %s run %d row %d",
				record.ArmID,
				key.run,
				key.row,
			)
		}
		byArm[record.ArmID][key] = observation{
			totalMS:    record.TotalMS,
			evalOnlyMS: record.EvalOnlyMS,
		}
	}

	output := make(
		[]PairedTabularLatencyPairSummary,
		0,
		len(arms)*(len(arms)-1)/2,
	)
	for numeratorIndex := 1; numeratorIndex < len(arms); numeratorIndex++ {
		for denominatorIndex := 0; denominatorIndex < numeratorIndex; denominatorIndex++ {
			numerator := arms[numeratorIndex]
			denominator := arms[denominatorIndex]
			totalDifferences := make([]float64, 0)
			evalDifferences := make([]float64, 0)
			totalLogRatioSum := 0.0
			evalLogRatioSum := 0.0
			for key, numeratorValue := range byArm[numerator.ID] {
				denominatorValue, ok :=
					byArm[denominator.ID][key]
				if !ok {
					return nil, fmt.Errorf(
						"missing paired observation for arms %s/%s run %d row %d",
						numerator.ID,
						denominator.ID,
						key.run,
						key.row,
					)
				}
				if numeratorValue.totalMS <= 0 ||
					denominatorValue.totalMS <= 0 ||
					numeratorValue.evalOnlyMS <= 0 ||
					denominatorValue.evalOnlyMS <= 0 {
					return nil, fmt.Errorf(
						"non-positive paired latency for arms %s/%s",
						numerator.ID,
						denominator.ID,
					)
				}
				totalDifferences = append(
					totalDifferences,
					numeratorValue.totalMS-
						denominatorValue.totalMS,
				)
				evalDifferences = append(
					evalDifferences,
					numeratorValue.evalOnlyMS-
						denominatorValue.evalOnlyMS,
				)
				totalLogRatioSum += math.Log(
					numeratorValue.totalMS /
						denominatorValue.totalMS,
				)
				evalLogRatioSum += math.Log(
					numeratorValue.evalOnlyMS /
						denominatorValue.evalOnlyMS,
				)
			}
			totalStats, err := summarizeLatencyValues(
				totalDifferences,
			)
			if err != nil {
				return nil, fmt.Errorf(
					"summarize pair %s/%s: %w",
					numerator.ID,
					denominator.ID,
					err,
				)
			}
			evalStats, err := summarizeLatencyValues(
				evalDifferences,
			)
			if err != nil {
				return nil, fmt.Errorf(
					"summarize eval-only pair %s/%s: %w",
					numerator.ID,
					denominator.ID,
					err,
				)
			}
			output = append(output, PairedTabularLatencyPairSummary{
				NumeratorArmID:   numerator.ID,
				DenominatorArmID: denominator.ID,
				Pairs:            len(totalDifferences),
				GeometricMeanTotalRatio: math.Exp(
					totalLogRatioSum /
						float64(len(totalDifferences)),
				),
				MeanTotalDifferenceMS:   totalStats.mean,
				MedianTotalDifferenceMS: totalStats.median,
				P95TotalDifferenceMS:    totalStats.p95,
				GeometricMeanEvalOnlyRatio: math.Exp(
					evalLogRatioSum /
						float64(len(evalDifferences)),
				),
				MeanEvalOnlyDifferenceMS:   evalStats.mean,
				MedianEvalOnlyDifferenceMS: evalStats.median,
				P95EvalOnlyDifferenceMS:    evalStats.p95,
			})
		}
	}
	return output, nil
}

type latencyValueSummary struct {
	mean   float64
	median float64
	p95    float64
	stddev float64
	iqr    float64
}

func summarizeLatencyValues(
	values []float64,
) (latencyValueSummary, error) {
	if len(values) == 0 {
		return latencyValueSummary{}, fmt.Errorf(
			"cannot summarize empty values",
		)
	}

	sorted := append([]float64(nil), values...)
	total := 0.0
	for index, value := range sorted {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return latencyValueSummary{}, fmt.Errorf(
				"value %d is not finite",
				index,
			)
		}
		total += value
	}
	sort.Float64s(sorted)
	mean := total / float64(len(sorted))
	variance := 0.0
	for _, value := range sorted {
		delta := value - mean
		variance += delta * delta
	}
	variance /= float64(len(sorted))

	return latencyValueSummary{
		mean:   mean,
		median: nearestRank(sorted, 0.50),
		p95:    nearestRank(sorted, 0.95),
		stddev: math.Sqrt(variance),
		iqr: nearestRank(sorted, 0.75) -
			nearestRank(sorted, 0.25),
	}, nil
}

func nearestRank(sorted []float64, fraction float64) float64 {
	index := int(math.Ceil(fraction*float64(len(sorted)))) - 1
	if index < 0 {
		index = 0
	}
	if index >= len(sorted) {
		index = len(sorted) - 1
	}
	return sorted[index]
}
