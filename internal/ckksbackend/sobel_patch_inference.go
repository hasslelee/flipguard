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

	"github.com/tuneinsight/lattigo/v6/core/rlwe"
)

type CKKSSobelPatchConfig struct {
	ModelPath string
	DataPath  string
}

type CKKSSobelPatchRecord struct {
	RowID      int    `json:"row_id"`
	ImageID    string `json:"image_id"`
	PatchIndex int    `json:"patch_index"`
	CenterX    int    `json:"center_x"`
	CenterY    int    `json:"center_y"`

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

type sobelPatchModel struct {
	SchemaVersion     string  `json:"schema_version"`
	DatasetID         string  `json:"dataset_id"`
	ModelID           string  `json:"model_id"`
	ModelType         string  `json:"model_type"`
	InputDim          int     `json:"input_dim"`
	GraphFormula      string  `json:"graph_formula"`
	DecisionThreshold float64 `json:"decision_threshold"`
}

type sobelPatchRow struct {
	RowID         int
	ImageID       string
	PatchIndex    int
	CenterX       int
	CenterY       int
	Pixels        [9]float64
	PlainScore    float64
	PlainDecision bool
}

func (c Context) RunCKKSSobelPatchInference(
	config CKKSSobelPatchConfig,
) ([]CKKSSobelPatchRecord, error) {
	model, err := loadSobelPatchModel(config.ModelPath)
	if err != nil {
		return nil, err
	}
	rows, err := loadSobelPatchRows(
		config.DataPath,
		model.DecisionThreshold,
	)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("Sobel patch data has no rows")
	}

	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, fmt.Errorf("create Sobel CKKS runtime: %w", err)
	}
	records := make([]CKKSSobelPatchRecord, 0, len(rows))
	for _, row := range rows {
		record, err := c.runSobelPatch(
			runtimeState,
			row,
			model.DecisionThreshold,
		)
		if err != nil {
			return nil, fmt.Errorf(
				"Sobel patch row %d: %w",
				row.RowID,
				err,
			)
		}
		records = append(records, record)
	}
	return records, nil
}

func (c Context) runSobelPatch(
	runtimeState ckksTimingRuntime,
	row sobelPatchRow,
	threshold float64,
) (CKKSSobelPatchRecord, error) {
	totalStart := time.Now()
	encryptStart := time.Now()
	var inputs [9]*rlwe.Ciphertext
	for index, pixel := range row.Pixels {
		ciphertext, err := c.encryptSingleFeature(
			runtimeState.encoder,
			runtimeState.encryptor,
			pixel,
		)
		if err != nil {
			return CKKSSobelPatchRecord{}, fmt.Errorf(
				"encrypt p%d: %w",
				index,
				err,
			)
		}
		inputs[index] = ciphertext
	}
	encodeEncryptMS := durationMS(time.Since(encryptStart))

	evalStart := time.Now()
	gx, err := evalSobelGX(
		runtimeState.evaluator,
		inputs[0],
		inputs[2],
		inputs[3],
		inputs[5],
		inputs[6],
		inputs[8],
	)
	if err != nil {
		return CKKSSobelPatchRecord{}, fmt.Errorf("evaluate gx: %w", err)
	}
	gy, err := evalSobelGY(
		runtimeState.evaluator,
		inputs[0],
		inputs[1],
		inputs[2],
		inputs[6],
		inputs[7],
		inputs[8],
	)
	if err != nil {
		return CKKSSobelPatchRecord{}, fmt.Errorf("evaluate gy: %w", err)
	}
	gx2, err := c.squareTabularCiphertext(
		runtimeState,
		gx,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSSobelPatchRecord{}, fmt.Errorf("square gx: %w", err)
	}
	gy2, err := c.squareTabularCiphertext(
		runtimeState,
		gy,
		CKKSEvaluationModeRescale,
	)
	if err != nil {
		return CKKSSobelPatchRecord{}, fmt.Errorf("square gy: %w", err)
	}
	if gy2.Level() != gx2.Level() {
		gy2, err = alignCiphertextToLevel(
			runtimeState.evaluator,
			gy2,
			gx2.Level(),
		)
		if err != nil {
			return CKKSSobelPatchRecord{}, fmt.Errorf(
				"align squared responses: %w",
				err,
			)
		}
	}
	score, err := runtimeState.evaluator.AddNew(gx2, gy2)
	if err != nil {
		return CKKSSobelPatchRecord{}, fmt.Errorf(
			"add squared responses: %w",
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
		return CKKSSobelPatchRecord{}, fmt.Errorf(
			"decrypt score: %w",
			err,
		)
	}
	decryptDecodeMS := durationMS(time.Since(decryptStart))
	ckksDecision := decoded >= threshold
	return CKKSSobelPatchRecord{
		RowID:           row.RowID,
		ImageID:         row.ImageID,
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

func loadSobelPatchModel(path string) (sobelPatchModel, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return sobelPatchModel{}, fmt.Errorf(
			"read Sobel model: %w",
			err,
		)
	}
	model := sobelPatchModel{}
	if err := json.Unmarshal(data, &model); err != nil {
		return sobelPatchModel{}, fmt.Errorf(
			"parse Sobel model: %w",
			err,
		)
	}
	if model.SchemaVersion != "flipguard_bsds500_sobel_holdout_v1" ||
		model.DatasetID != "bsds500" ||
		model.ModelID != "sobel_edge_score" ||
		model.ModelType != "sobel_edge_score" ||
		model.InputDim != 9 ||
		model.GraphFormula != "Gx^2 + Gy^2" ||
		!finiteSobelValue(model.DecisionThreshold) ||
		model.DecisionThreshold <= 0 {
		return sobelPatchModel{}, fmt.Errorf(
			"unsupported Sobel model artifact",
		)
	}
	return model, nil
}

func loadSobelPatchRows(
	path string,
	threshold float64,
) ([]sobelPatchRow, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open Sobel patch CSV: %w", err)
	}
	defer file.Close()
	records, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, fmt.Errorf("read Sobel patch CSV: %w", err)
	}
	if len(records) < 2 {
		return nil, fmt.Errorf("Sobel patch CSV has no rows")
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{
		"row_id", "image_id", "patch_index", "center_x", "center_y",
		"p00", "p01", "p02", "p10", "p11", "p12", "p20", "p21", "p22",
		"plaintext_score", "decision_threshold", "plaintext_decision",
	}
	for _, name := range required {
		if _, ok := header[name]; !ok {
			return nil, fmt.Errorf("Sobel patch CSV missing %s", name)
		}
	}
	rows := make([]sobelPatchRow, 0, len(records)-1)
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
			if err != nil || !finiteSobelValue(parsed) {
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
			return nil, fmt.Errorf(
				"row %d invalid image_id",
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
		var pixels [9]float64
		for index, name := range required[5:14] {
			pixel, err := parseFloat(name)
			if err != nil || pixel < 0 || pixel > 1 {
				return nil, fmt.Errorf(
					"row %d invalid %s",
					rowIndex+2,
					name,
				)
			}
			pixels[index] = pixel
		}
		plainScore, err := parseFloat("plaintext_score")
		if err != nil {
			return nil, err
		}
		rowThreshold, err := parseFloat("decision_threshold")
		if err != nil ||
			math.Abs(rowThreshold-threshold) > 1e-15 {
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
		if err != nil ||
			plainDecision != (plainScore >= threshold) {
			return nil, fmt.Errorf(
				"row %d plaintext decision changed",
				rowIndex+2,
			)
		}
		rows = append(rows, sobelPatchRow{
			RowID:         rowID,
			ImageID:       imageID,
			PatchIndex:    patchIndex,
			CenterX:       centerX,
			CenterY:       centerY,
			Pixels:        pixels,
			PlainScore:    plainScore,
			PlainDecision: plainDecision,
		})
	}
	return rows, nil
}

func finiteSobelValue(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}
