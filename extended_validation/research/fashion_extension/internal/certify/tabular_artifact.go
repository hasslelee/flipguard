package certify

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"fmt"
	"io"
	"math"
	"math/bits"
	"os"
	"strconv"
	"strings"
)

// TabularArtifactRun identifies one successful repeated CKKS inference run.
type TabularArtifactRun struct {
	RecordsPath string
	SummaryPath string
}

// TabularArtifactCandidateInput describes the repeated artifacts belonging to
// one dataset-model-configuration candidate.
type TabularArtifactCandidateInput struct {
	Candidate CandidateDescriptor

	WorkloadID string
	DatasetID  string
	ModelID    string
	SplitID    string

	Threshold float64

	Runs       []TabularArtifactRun
	FailedRuns int

	AnalyticalBoundProvided bool
	MaxErrorBound           float64
	AnalyticalProof         *AnalyticalBoundProof
}

// TabularArtifactAggregation is the importer output consumed by the generic
// certification engine.
type TabularArtifactAggregation struct {
	Scope ClaimScope

	RunMeanTotalMS []float64

	Aggregation ObservedAggregation
}

type tabularArtifactMetadata struct {
	DatasetID string
	ModelID   string

	EvaluatedRows int
	MeanTotalMS   float64

	ChainLength int
	ScaleBits   int
	Slots       int
	LogN        int
}

type tabularArtifactScore struct {
	PlainScore  float64
	ApproxScore float64
}

// LoadAndAggregateTabularCandidate imports repeated tabular records, verifies
// that all runs refer to the same validation samples, and applies the common
// V_cert/V_amb observation aggregator.
func LoadAndAggregateTabularCandidate(
	input TabularArtifactCandidateInput,
	marginFloor float64,
	safetyFactor float64,
) (TabularArtifactAggregation, error) {
	if strings.TrimSpace(input.Candidate.ID) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate ID is empty",
		)
	}
	if strings.TrimSpace(input.Candidate.Path) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s path is empty",
			input.Candidate.ID,
		)
	}
	if strings.TrimSpace(input.WorkloadID) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s workload ID is empty",
			input.Candidate.ID,
		)
	}
	if strings.TrimSpace(input.DatasetID) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s dataset ID is empty",
			input.Candidate.ID,
		)
	}
	if strings.TrimSpace(input.ModelID) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s model ID is empty",
			input.Candidate.ID,
		)
	}
	if strings.TrimSpace(input.SplitID) == "" {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s split ID is empty",
			input.Candidate.ID,
		)
	}
	if !isFinite(input.Threshold) {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s threshold must be finite",
			input.Candidate.ID,
		)
	}
	if len(input.Runs) == 0 {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s has no successful artifact run",
			input.Candidate.ID,
		)
	}
	if input.FailedRuns < 0 {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s has negative failed runs",
			input.Candidate.ID,
		)
	}

	var referenceMetadata *tabularArtifactMetadata

	var sampleOrder []string
	referencePlain := make(map[string]float64)
	approxBySample := make(map[string][]float64)

	runLatencies := make([]float64, 0, len(input.Runs))

	for runIndex, run := range input.Runs {
		if strings.TrimSpace(run.RecordsPath) == "" {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d records path is empty",
				input.Candidate.ID,
				runIndex,
			)
		}
		if strings.TrimSpace(run.SummaryPath) == "" {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d summary path is empty",
				input.Candidate.ID,
				runIndex,
			)
		}

		metadata, err := loadTabularArtifactMetadata(
			run.SummaryPath,
		)
		if err != nil {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d summary: %w",
				input.Candidate.ID,
				runIndex,
				err,
			)
		}

		if metadata.DatasetID != input.DatasetID {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d dataset mismatch: got %q, expected %q",
				input.Candidate.ID,
				runIndex,
				metadata.DatasetID,
				input.DatasetID,
			)
		}
		if metadata.ModelID != input.ModelID {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d model mismatch: got %q, expected %q",
				input.Candidate.ID,
				runIndex,
				metadata.ModelID,
				input.ModelID,
			)
		}

		if referenceMetadata == nil {
			copied := metadata
			referenceMetadata = &copied
		} else if err := compareTabularArtifactMetadata(
			*referenceMetadata,
			metadata,
		); err != nil {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d parameter mismatch: %w",
				input.Candidate.ID,
				runIndex,
				err,
			)
		}

		order, scores, err := loadTabularArtifactScores(
			run.RecordsPath,
		)
		if err != nil {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d records: %w",
				input.Candidate.ID,
				runIndex,
				err,
			)
		}

		if len(scores) != metadata.EvaluatedRows {
			return TabularArtifactAggregation{}, fmt.Errorf(
				"candidate %s run %d record count mismatch: records=%d evaluated_rows=%d",
				input.Candidate.ID,
				runIndex,
				len(scores),
				metadata.EvaluatedRows,
			)
		}

		if runIndex == 0 {
			sampleOrder = append(sampleOrder, order...)

			for _, sampleID := range sampleOrder {
				score := scores[sampleID]

				referencePlain[sampleID] = score.PlainScore
				approxBySample[sampleID] = []float64{
					score.ApproxScore,
				}
			}
		} else {
			if len(scores) != len(referencePlain) {
				return TabularArtifactAggregation{}, fmt.Errorf(
					"candidate %s run %d sample count mismatch: got %d, expected %d",
					input.Candidate.ID,
					runIndex,
					len(scores),
					len(referencePlain),
				)
			}

			for _, sampleID := range sampleOrder {
				score, exists := scores[sampleID]
				if !exists {
					return TabularArtifactAggregation{}, fmt.Errorf(
						"candidate %s run %d is missing sample %q",
						input.Candidate.ID,
						runIndex,
						sampleID,
					)
				}

				expectedPlain := referencePlain[sampleID]
				if !sameArtifactFloat(
					score.PlainScore,
					expectedPlain,
				) {
					return TabularArtifactAggregation{}, fmt.Errorf(
						"candidate %s run %d sample %q plaintext score mismatch: got %.12g, expected %.12g",
						input.Candidate.ID,
						runIndex,
						sampleID,
						score.PlainScore,
						expectedPlain,
					)
				}

				approxBySample[sampleID] = append(
					approxBySample[sampleID],
					score.ApproxScore,
				)
			}
		}

		runLatencies = append(
			runLatencies,
			metadata.MeanTotalMS,
		)
	}

	if referenceMetadata == nil {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s produced no artifact metadata",
			input.Candidate.ID,
		)
	}

	candidate, err := mergeTabularCandidateMetadata(
		input.Candidate,
		*referenceMetadata,
	)
	if err != nil {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s metadata: %w",
			input.Candidate.ID,
			err,
		)
	}

	samples := make([]ObservedSample, 0, len(sampleOrder))

	for _, sampleID := range sampleOrder {
		samples = append(samples, ObservedSample{
			ID:           sampleID,
			PlainScore:   referencePlain[sampleID],
			Threshold:    input.Threshold,
			ApproxScores: approxBySample[sampleID],
		})
	}

	meanTotalMS := meanArtifactFloat(runLatencies)

	validationDigest := buildTabularValidationDigest(
		sampleOrder,
		referencePlain,
	)

	observed, err := AggregateObservedCandidate(
		ObservedCandidateInput{
			Candidate: candidate,
			Samples:   samples,

			FailedRuns: input.FailedRuns,

			MeanTotalMS: meanTotalMS,

			AnalyticalBoundProvided: input.AnalyticalBoundProvided,
			MaxErrorBound:           input.MaxErrorBound,
			AnalyticalProof: cloneAnalyticalBoundProof(
				input.AnalyticalProof,
			),
		},
		marginFloor,
		safetyFactor,
	)
	if err != nil {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"aggregate candidate %s artifacts: %w",
			input.Candidate.ID,
			err,
		)
	}

	scope := ClaimScope{
		WorkloadID: input.WorkloadID,
		DatasetID:  input.DatasetID,
		ModelID:    input.ModelID,
		SplitID:    input.SplitID,

		ValidationDigest: validationDigest,

		Threshold:    input.Threshold,
		MarginFloor:  marginFloor,
		SafetyFactor: safetyFactor,

		SampleCount: observed.Coverage.Total,
	}

	if err := scope.Validate(); err != nil {
		return TabularArtifactAggregation{}, fmt.Errorf(
			"candidate %s claim scope: %w",
			input.Candidate.ID,
			err,
		)
	}

	return TabularArtifactAggregation{
		Scope: scope,

		RunMeanTotalMS: append(
			[]float64(nil),
			runLatencies...,
		),

		Aggregation: observed,
	}, nil
}

func loadTabularArtifactMetadata(
	path string,
) (tabularArtifactMetadata, error) {
	rows, err := readTabularArtifactCSV(path)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}
	if len(rows) != 1 {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"summary CSV must contain exactly one data row: got %d",
			len(rows),
		)
	}

	row := rows[0]

	datasetID, err := requiredTabularArtifactValue(
		row,
		"dataset_id",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}

	modelID, err := requiredTabularArtifactValue(
		row,
		"model_id",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}

	evaluatedRows, err := parseTabularArtifactInt(
		row,
		"evaluated_rows",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}
	if evaluatedRows <= 0 {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"%s: evaluated_rows must be positive",
			path,
		)
	}

	meanTotalMS, err := parseTabularArtifactFloat(
		row,
		"mean_total_eval_ms",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}
	if meanTotalMS <= 0 {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"%s: mean_total_eval_ms must be positive",
			path,
		)
	}

	initialLevel, err := parseTabularArtifactInt(
		row,
		"initial_level",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}
	if initialLevel < 0 {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"%s: initial_level must be non-negative",
			path,
		)
	}

	scaleBits, err := parseTabularArtifactInt(
		row,
		"log_default_scale",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}
	if scaleBits <= 0 {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"%s: log_default_scale must be positive",
			path,
		)
	}

	slots, err := parseTabularArtifactInt(
		row,
		"max_slots",
		path,
	)
	if err != nil {
		return tabularArtifactMetadata{}, err
	}

	logN, err := tabularArtifactLogNFromSlots(slots)
	if err != nil {
		return tabularArtifactMetadata{}, fmt.Errorf(
			"%s: %w",
			path,
			err,
		)
	}

	return tabularArtifactMetadata{
		DatasetID: datasetID,
		ModelID:   modelID,

		EvaluatedRows: evaluatedRows,
		MeanTotalMS:   meanTotalMS,

		ChainLength: initialLevel + 1,
		ScaleBits:   scaleBits,
		Slots:       slots,
		LogN:        logN,
	}, nil
}

func loadTabularArtifactScores(
	path string,
) ([]string, map[string]tabularArtifactScore, error) {
	rows, err := readTabularArtifactCSV(path)
	if err != nil {
		return nil, nil, err
	}
	if len(rows) == 0 {
		return nil, nil, fmt.Errorf(
			"records CSV contains no data row",
		)
	}

	order := make([]string, 0, len(rows))
	scores := make(
		map[string]tabularArtifactScore,
		len(rows),
	)

	for rowIndex, row := range rows {
		sampleID, err := requiredTabularArtifactValue(
			row,
			"row_id",
			path,
		)
		if err != nil {
			return nil, nil, fmt.Errorf(
				"row %d: %w",
				rowIndex,
				err,
			)
		}

		if _, exists := scores[sampleID]; exists {
			return nil, nil, fmt.Errorf(
				"duplicate row_id %q",
				sampleID,
			)
		}

		plainScore, err := parseTabularArtifactFloat(
			row,
			"plain_y",
			path,
		)
		if err != nil {
			return nil, nil, fmt.Errorf(
				"row %d: %w",
				rowIndex,
				err,
			)
		}

		approxScore, err := parseTabularArtifactFloat(
			row,
			"ckks_y",
			path,
		)
		if err != nil {
			return nil, nil, fmt.Errorf(
				"row %d: %w",
				rowIndex,
				err,
			)
		}

		order = append(order, sampleID)
		scores[sampleID] = tabularArtifactScore{
			PlainScore:  plainScore,
			ApproxScore: approxScore,
		}
	}

	return order, scores, nil
}

func compareTabularArtifactMetadata(
	expected tabularArtifactMetadata,
	actual tabularArtifactMetadata,
) error {
	switch {
	case actual.DatasetID != expected.DatasetID:
		return fmt.Errorf(
			"dataset_id=%q; expected %q",
			actual.DatasetID,
			expected.DatasetID,
		)

	case actual.ModelID != expected.ModelID:
		return fmt.Errorf(
			"model_id=%q; expected %q",
			actual.ModelID,
			expected.ModelID,
		)

	case actual.EvaluatedRows != expected.EvaluatedRows:
		return fmt.Errorf(
			"evaluated_rows=%d; expected %d",
			actual.EvaluatedRows,
			expected.EvaluatedRows,
		)

	case actual.ChainLength != expected.ChainLength:
		return fmt.Errorf(
			"chain_length=%d; expected %d",
			actual.ChainLength,
			expected.ChainLength,
		)

	case actual.ScaleBits != expected.ScaleBits:
		return fmt.Errorf(
			"scale_bits=%d; expected %d",
			actual.ScaleBits,
			expected.ScaleBits,
		)

	case actual.Slots != expected.Slots:
		return fmt.Errorf(
			"slots=%d; expected %d",
			actual.Slots,
			expected.Slots,
		)

	case actual.LogN != expected.LogN:
		return fmt.Errorf(
			"logN=%d; expected %d",
			actual.LogN,
			expected.LogN,
		)
	}

	return nil
}

func mergeTabularCandidateMetadata(
	candidate CandidateDescriptor,
	metadata tabularArtifactMetadata,
) (CandidateDescriptor, error) {
	if candidate.ChainLength == 0 {
		candidate.ChainLength = metadata.ChainLength
	} else if candidate.ChainLength != metadata.ChainLength {
		return CandidateDescriptor{}, fmt.Errorf(
			"chain length=%d; artifact reports %d",
			candidate.ChainLength,
			metadata.ChainLength,
		)
	}

	if candidate.ScaleBits == 0 {
		candidate.ScaleBits = metadata.ScaleBits
	} else if candidate.ScaleBits != metadata.ScaleBits {
		return CandidateDescriptor{}, fmt.Errorf(
			"scale bits=%d; artifact reports %d",
			candidate.ScaleBits,
			metadata.ScaleBits,
		)
	}

	if candidate.Slots == 0 {
		candidate.Slots = metadata.Slots
	} else if candidate.Slots != metadata.Slots {
		return CandidateDescriptor{}, fmt.Errorf(
			"slots=%d; artifact reports %d",
			candidate.Slots,
			metadata.Slots,
		)
	}

	if candidate.LogN == 0 {
		candidate.LogN = metadata.LogN
	} else if candidate.LogN != metadata.LogN {
		return CandidateDescriptor{}, fmt.Errorf(
			"logN=%d; artifact reports %d",
			candidate.LogN,
			metadata.LogN,
		)
	}

	return candidate, nil
}

func readTabularArtifactCSV(
	path string,
) ([]map[string]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf(
			"open %s: %w",
			path,
			err,
		)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	reader.FieldsPerRecord = -1

	header, err := reader.Read()
	if err != nil {
		return nil, fmt.Errorf(
			"read header from %s: %w",
			path,
			err,
		)
	}
	if len(header) == 0 {
		return nil, fmt.Errorf(
			"%s contains an empty CSV header",
			path,
		)
	}

	seenHeader := make(map[string]struct{}, len(header))

	for index := range header {
		header[index] = strings.TrimSpace(header[index])

		if header[index] == "" {
			return nil, fmt.Errorf(
				"%s contains an empty header at column %d",
				path,
				index,
			)
		}
		if _, exists := seenHeader[header[index]]; exists {
			return nil, fmt.Errorf(
				"%s contains duplicate header %q",
				path,
				header[index],
			)
		}
		seenHeader[header[index]] = struct{}{}
	}

	rows := make([]map[string]string, 0)

	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf(
				"read %s: %w",
				path,
				err,
			)
		}
		if len(record) != len(header) {
			return nil, fmt.Errorf(
				"%s contains %d fields; expected %d",
				path,
				len(record),
				len(header),
			)
		}

		row := make(map[string]string, len(header))
		for index, key := range header {
			row[key] = strings.TrimSpace(record[index])
		}

		rows = append(rows, row)
	}

	return rows, nil
}

func requiredTabularArtifactValue(
	row map[string]string,
	key string,
	path string,
) (string, error) {
	value, exists := row[key]
	if !exists {
		return "", fmt.Errorf(
			"%s is missing required column %q",
			path,
			key,
		)
	}

	value = strings.TrimSpace(value)
	if value == "" {
		return "", fmt.Errorf(
			"%s has an empty value for %q",
			path,
			key,
		)
	}

	return value, nil
}

func parseTabularArtifactFloat(
	row map[string]string,
	key string,
	path string,
) (float64, error) {
	value, err := requiredTabularArtifactValue(
		row,
		key,
		path,
	)
	if err != nil {
		return 0, err
	}

	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, fmt.Errorf(
			"%s: parse %s=%q as float: %w",
			path,
			key,
			value,
			err,
		)
	}
	if !isFinite(parsed) {
		return 0, fmt.Errorf(
			"%s: %s must be finite",
			path,
			key,
		)
	}

	return parsed, nil
}

func parseTabularArtifactInt(
	row map[string]string,
	key string,
	path string,
) (int, error) {
	value, err := requiredTabularArtifactValue(
		row,
		key,
		path,
	)
	if err != nil {
		return 0, err
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf(
			"%s: parse %s=%q as int: %w",
			path,
			key,
			value,
			err,
		)
	}

	return parsed, nil
}

func tabularArtifactLogNFromSlots(
	slots int,
) (int, error) {
	if slots <= 0 {
		return 0, fmt.Errorf(
			"max_slots must be positive: %d",
			slots,
		)
	}
	if slots&(slots-1) != 0 {
		return 0, fmt.Errorf(
			"max_slots must be a power of two: %d",
			slots,
		)
	}

	// CKKS has N/2 complex slots, so logN = log2(slots) + 1.
	return bits.Len(uint(slots)), nil
}

func sameArtifactFloat(
	left float64,
	right float64,
) bool {
	scale := math.Max(
		1,
		math.Max(math.Abs(left), math.Abs(right)),
	)

	return math.Abs(left-right) <= 1e-12*scale
}

func buildTabularValidationDigest(
	sampleOrder []string,
	plainScores map[string]float64,
) string {
	hasher := sha256.New()

	var encoded [8]byte

	for _, sampleID := range sampleOrder {
		binary.BigEndian.PutUint64(
			encoded[:],
			uint64(len(sampleID)),
		)
		_, _ = hasher.Write(encoded[:])
		_, _ = hasher.Write([]byte(sampleID))

		binary.BigEndian.PutUint64(
			encoded[:],
			math.Float64bits(plainScores[sampleID]),
		)
		_, _ = hasher.Write(encoded[:])
	}

	return "sha256:" + hex.EncodeToString(
		hasher.Sum(nil),
	)
}

func meanArtifactFloat(
	values []float64,
) float64 {
	if len(values) == 0 {
		return 0
	}

	var total float64
	for _, value := range values {
		total += value
	}

	return total / float64(len(values))
}
