package ckksbackend

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/benchmarks"
	"github.com/tuneinsight/lattigo/v6/core/rlwe"
)

type CKKSHarrisPatchConfig struct {
	ModelPath string
	DataPath  string
	MaxRows   int
}

type CKKSHarrisPatchRecord struct {
	RowID           int    `json:"row_id"`
	ImageID         string `json:"image_id"`
	SourcePartition string `json:"source_partition"`
	PatchIndex      int    `json:"patch_index"`
	CenterX         int    `json:"center_x"`
	CenterY         int    `json:"center_y"`

	PlainScore float64 `json:"plain_score"`
	CKKSScore  float64 `json:"ckks_score"`
	AbsError   float64 `json:"abs_error"`

	PlainDecision bool `json:"plain_decision"`
	CKKSDecision  bool `json:"ckks_decision"`
	DecisionFlip  bool `json:"decision_flip"`

	EncodeEncryptMS float64 `json:"encode_encrypt_ms"`
	EvalOnlyMS      float64 `json:"eval_only_ms"`
	DecryptDecodeMS float64 `json:"decrypt_decode_ms"`
	TotalEvalMS     float64 `json:"total_eval_ms"`

	InitialLevel int `json:"initial_level"`
	FinalLevel   int `json:"final_level"`
	FinalDegree  int `json:"final_degree"`
}

type harrisPatchModel struct {
	SchemaVersion     string  `json:"schema_version"`
	DatasetID         string  `json:"dataset_id"`
	ModelID           string  `json:"model_id"`
	ModelType         string  `json:"model_type"`
	InputDim          int     `json:"input_dim"`
	GraphFormula      string  `json:"graph_formula"`
	DecisionThreshold float64 `json:"decision_threshold"`
}

type harrisPatchRow struct {
	RowID           int
	ImageID         string
	SourcePartition string
	PatchIndex      int
	CenterX         int
	CenterY         int
	Pixels          [5][5]float64
	PlainScore      float64
	PlainDecision   bool
}

func (c Context) RunCKKSHarrisPatchInference(
	config CKKSHarrisPatchConfig,
) ([]CKKSHarrisPatchRecord, error) {
	model, err := loadHarrisPatchModel(config.ModelPath)
	if err != nil {
		return nil, err
	}
	rows, err := loadHarrisPatchRows(
		config.DataPath,
		model.DecisionThreshold,
	)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("Harris patch data has no rows")
	}
	if config.MaxRows > 0 && config.MaxRows < len(rows) {
		rows = rows[:config.MaxRows]
	}

	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, fmt.Errorf("create Harris CKKS runtime: %w", err)
	}
	records := make([]CKKSHarrisPatchRecord, 0, len(rows))
	for _, row := range rows {
		record, err := c.runHarrisPatch(
			runtimeState,
			row,
			model.DecisionThreshold,
		)
		if err != nil {
			return nil, fmt.Errorf(
				"Harris patch row %d: %w",
				row.RowID,
				err,
			)
		}
		records = append(records, record)
	}
	return records, nil
}

func (c Context) runHarrisPatch(
	runtimeState ckksTimingRuntime,
	row harrisPatchRow,
	threshold float64,
) (CKKSHarrisPatchRecord, error) {
	totalStart := time.Now()
	encryptStart := time.Now()
	var inputs [5][5]*rlwe.Ciphertext
	for r := 0; r < 5; r++ {
		for column := 0; column < 5; column++ {
			ciphertext, err := c.encryptSingleFeature(
				runtimeState.encoder,
				runtimeState.encryptor,
				row.Pixels[r][column],
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"encrypt p%d%d: %w",
					r,
					column,
					err,
				)
			}
			inputs[r][column] = ciphertext
		}
	}
	encodeEncryptMS := durationMS(time.Since(encryptStart))

	evalStart := time.Now()
	sxxTerms := make([]*rlwe.Ciphertext, 0, 9)
	syyTerms := make([]*rlwe.Ciphertext, 0, 9)
	twoSxyTerms := make([]*rlwe.Ciphertext, 0, 9)
	for r := 1; r <= 3; r++ {
		for column := 1; column <= 3; column++ {
			gx, err := evalSobelGX(
				runtimeState.evaluator,
				inputs[r-1][column-1],
				inputs[r-1][column+1],
				inputs[r][column-1],
				inputs[r][column+1],
				inputs[r+1][column-1],
				inputs[r+1][column+1],
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"evaluate gx at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			gy, err := evalSobelGY(
				runtimeState.evaluator,
				inputs[r-1][column-1],
				inputs[r-1][column],
				inputs[r-1][column+1],
				inputs[r+1][column-1],
				inputs[r+1][column],
				inputs[r+1][column+1],
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"evaluate gy at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			gx2, err := c.squareTabularCiphertext(
				runtimeState,
				gx,
				CKKSEvaluationModeRescale,
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"square gx at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			gy2, err := c.squareTabularCiphertext(
				runtimeState,
				gy,
				CKKSEvaluationModeRescale,
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"square gy at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			gxPlusGy, err := runtimeState.evaluator.AddNew(gx, gy)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"add gradients at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			gxPlusGy2, err := c.squareTabularCiphertext(
				runtimeState,
				gxPlusGy,
				CKKSEvaluationModeRescale,
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"square gradient sum at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			twoGxy, err := runtimeState.evaluator.SubNew(
				gxPlusGy2,
				gx2,
			)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"derive 2gxy at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			twoGxy, err = runtimeState.evaluator.SubNew(twoGxy, gy2)
			if err != nil {
				return CKKSHarrisPatchRecord{}, fmt.Errorf(
					"finish 2gxy at %d,%d: %w",
					r,
					column,
					err,
				)
			}
			sxxTerms = append(sxxTerms, gx2)
			syyTerms = append(syyTerms, gy2)
			twoSxyTerms = append(twoSxyTerms, twoGxy)
		}
	}

	sxx, err := addHarrisCipherChain(runtimeState, sxxTerms)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("accumulate Sxx: %w", err)
	}
	syy, err := addHarrisCipherChain(runtimeState, syyTerms)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("accumulate Syy: %w", err)
	}
	twoSxy, err := addHarrisCipherChain(runtimeState, twoSxyTerms)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("accumulate 2Sxy: %w", err)
	}
	trace, err := runtimeState.evaluator.AddNew(sxx, syy)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("compute trace: %w", err)
	}

	sxx2, err := c.squareTabularCiphertext(
		runtimeState,
		sxx,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("square Sxx: %w", err)
	}
	syy2, err := c.squareTabularCiphertext(
		runtimeState,
		syy,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("square Syy: %w", err)
	}
	twoSxy2, err := c.squareTabularCiphertext(
		runtimeState,
		twoSxy,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("square 2Sxy: %w", err)
	}
	trace2, err := c.squareTabularCiphertext(
		runtimeState,
		trace,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf("square trace: %w", err)
	}

	twoSxxSyy, err := runtimeState.evaluator.SubNew(trace2, sxx2)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"derive 2SxxSyy: %w",
			err,
		)
	}
	twoSxxSyy, err = runtimeState.evaluator.SubNew(twoSxxSyy, syy2)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"finish 2SxxSyy: %w",
			err,
		)
	}
	positiveDet, err := runtimeState.evaluator.MulNew(twoSxxSyy, 0.5)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"scale SxxSyy: %w",
			err,
		)
	}
	negativeSxy2, err := runtimeState.evaluator.MulNew(twoSxy2, -0.25)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"scale negative Sxy2: %w",
			err,
		)
	}
	determinant, err := runtimeState.evaluator.AddNew(
		positiveDet,
		negativeSxy2,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"compute determinant: %w",
			err,
		)
	}
	negativeKTrace2, err := runtimeState.evaluator.MulNew(
		trace2,
		-benchmarks.HarrisCornerK,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"scale negative k trace2: %w",
			err,
		)
	}
	score, err := runtimeState.evaluator.AddNew(
		determinant,
		negativeKTrace2,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"compute Harris score: %w",
			err,
		)
	}
	evalOnlyMS := durationMS(time.Since(evalStart))

	decryptStart := time.Now()
	decoded, err := c.decryptFirstSlot(
		runtimeState.encoder,
		runtimeState.decryptor,
		score,
	)
	if err != nil {
		return CKKSHarrisPatchRecord{}, fmt.Errorf(
			"decrypt Harris score: %w",
			err,
		)
	}
	decryptDecodeMS := durationMS(time.Since(decryptStart))
	ckksDecision := decoded >= threshold
	return CKKSHarrisPatchRecord{
		RowID:           row.RowID,
		ImageID:         row.ImageID,
		SourcePartition: row.SourcePartition,
		PatchIndex:      row.PatchIndex,
		CenterX:         row.CenterX,
		CenterY:         row.CenterY,
		PlainScore:      row.PlainScore,
		CKKSScore:       decoded,
		AbsError:        math.Abs(decoded - row.PlainScore),
		PlainDecision:   row.PlainDecision,
		CKKSDecision:    ckksDecision,
		DecisionFlip:    row.PlainDecision != ckksDecision,
		EncodeEncryptMS: encodeEncryptMS,
		EvalOnlyMS:      evalOnlyMS,
		DecryptDecodeMS: decryptDecodeMS,
		TotalEvalMS:     durationMS(time.Since(totalStart)),
		InitialLevel:    c.MaxLevel(),
		FinalLevel:      score.Level(),
		FinalDegree:     score.Degree(),
	}, nil
}

func addHarrisCipherChain(
	runtimeState ckksTimingRuntime,
	terms []*rlwe.Ciphertext,
) (*rlwe.Ciphertext, error) {
	if len(terms) == 0 {
		return nil, fmt.Errorf("cannot add empty Harris ciphertext chain")
	}
	current := terms[0]
	for index := 1; index < len(terms); index++ {
		next, err := runtimeState.evaluator.AddNew(current, terms[index])
		if err != nil {
			return nil, fmt.Errorf("add term %d: %w", index, err)
		}
		current = next
	}
	return current, nil
}

func loadHarrisPatchModel(path string) (harrisPatchModel, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return harrisPatchModel{}, fmt.Errorf(
			"read Harris model: %w",
			err,
		)
	}
	model := harrisPatchModel{}
	if err := json.Unmarshal(data, &model); err != nil {
		return harrisPatchModel{}, fmt.Errorf(
			"parse Harris model: %w",
			err,
		)
	}
	if model.SchemaVersion != "flipguard_bsds500_harris_holdout_v1" ||
		model.DatasetID != "bsds500" ||
		model.ModelID != "harris_corner_response" ||
		model.ModelType != "harris_corner_response" ||
		model.InputDim != 25 ||
		model.GraphFormula != "det(M)-0.04*trace(M)^2" ||
		!finiteHarrisValue(model.DecisionThreshold) ||
		model.DecisionThreshold <= 0 {
		return harrisPatchModel{}, fmt.Errorf(
			"unsupported Harris model artifact",
		)
	}
	return model, nil
}

func loadHarrisPatchRows(
	path string,
	threshold float64,
) ([]harrisPatchRow, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open Harris patch CSV: %w", err)
	}
	defer file.Close()
	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read Harris patch CSV: %w", err)
	}
	if len(records) < 2 {
		return nil, fmt.Errorf("Harris patch CSV has no rows")
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{
		"row_id", "image_id", "source_partition",
		"patch_index", "center_x", "center_y",
		"plaintext_score", "decision_threshold", "plaintext_decision",
	}
	for r := 0; r < 5; r++ {
		for column := 0; column < 5; column++ {
			required = append(required, fmt.Sprintf("p%d%d", r, column))
		}
	}
	for _, name := range required {
		if _, ok := header[name]; !ok {
			return nil, fmt.Errorf("Harris patch CSV missing %s", name)
		}
	}

	rows := make([]harrisPatchRow, 0, len(records)-1)
	for rowIndex, record := range records[1:] {
		value := func(name string) (string, error) {
			index := header[name]
			if index >= len(record) {
				return "", fmt.Errorf(
					"row %d missing %s",
					rowIndex+2,
					name,
				)
			}
			return strings.TrimSpace(record[index]), nil
		}
		parseInt := func(name string) (int, error) {
			raw, err := value(name)
			if err != nil {
				return 0, err
			}
			parsed, err := strconv.Atoi(raw)
			if err != nil {
				return 0, fmt.Errorf(
					"row %d invalid %s",
					rowIndex+2,
					name,
				)
			}
			return parsed, nil
		}
		parseFloat := func(name string) (float64, error) {
			raw, err := value(name)
			if err != nil {
				return 0, err
			}
			parsed, err := strconv.ParseFloat(raw, 64)
			if err != nil || !finiteHarrisValue(parsed) {
				return 0, fmt.Errorf(
					"row %d invalid %s",
					rowIndex+2,
					name,
				)
			}
			return parsed, nil
		}
		rowID, err := parseInt("row_id")
		if err != nil {
			return nil, err
		}
		imageID, err := value("image_id")
		if err != nil || imageID == "" {
			return nil, fmt.Errorf("row %d invalid image_id", rowIndex+2)
		}
		sourcePartition, err := value("source_partition")
		if err != nil || sourcePartition == "" {
			return nil, fmt.Errorf(
				"row %d invalid source_partition",
				rowIndex+2,
			)
		}
		patchIndex, err := parseInt("patch_index")
		if err != nil {
			return nil, err
		}
		centerX, err := parseInt("center_x")
		if err != nil {
			return nil, err
		}
		centerY, err := parseInt("center_y")
		if err != nil {
			return nil, err
		}
		var pixels [5][5]float64
		for r := 0; r < 5; r++ {
			for column := 0; column < 5; column++ {
				name := fmt.Sprintf("p%d%d", r, column)
				pixel, err := parseFloat(name)
				if err != nil || pixel < 0 || pixel > 1 {
					return nil, fmt.Errorf(
						"row %d invalid %s",
						rowIndex+2,
						name,
					)
				}
				pixels[r][column] = pixel
			}
		}
		plainScore, err := parseFloat("plaintext_score")
		if err != nil {
			return nil, err
		}
		recomputed := benchmarks.HarrisCornerScore(
			benchmarks.HarrisCornerWindowSample{Pixels: pixels},
		)
		if math.Abs(plainScore-recomputed) >
			1e-12*math.Max(1, math.Abs(recomputed)) {
			return nil, fmt.Errorf(
				"row %d plaintext score changed",
				rowIndex+2,
			)
		}
		rowThreshold, err := parseFloat("decision_threshold")
		if err != nil || math.Abs(rowThreshold-threshold) > 1e-15 {
			return nil, fmt.Errorf(
				"row %d threshold changed",
				rowIndex+2,
			)
		}
		rawDecision, err := value("plaintext_decision")
		if err != nil {
			return nil, err
		}
		plainDecision, err := strconv.ParseBool(rawDecision)
		if err != nil || plainDecision != (plainScore >= threshold) {
			return nil, fmt.Errorf(
				"row %d plaintext decision changed",
				rowIndex+2,
			)
		}
		rows = append(rows, harrisPatchRow{
			RowID:           rowID,
			ImageID:         imageID,
			SourcePartition: sourcePartition,
			PatchIndex:      patchIndex,
			CenterX:         centerX,
			CenterY:         centerY,
			Pixels:          pixels,
			PlainScore:      plainScore,
			PlainDecision:   plainDecision,
		})
	}
	return rows, nil
}

func finiteHarrisValue(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
