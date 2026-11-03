package ckksbackend

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"strconv"
	"time"
)

type CKKSDepthLadderConfig struct {
	DataPath  string
	Depth     int
	Threshold float64
}

type CKKSDepthLadderRecord struct {
	RowID           int     `json:"row_id"`
	PlainScore      float64 `json:"plain_score"`
	CKKSScore       float64 `json:"ckks_score"`
	AbsError        float64 `json:"abs_error"`
	PlainDecision   bool    `json:"plain_decision"`
	CKKSDecision    bool    `json:"ckks_decision"`
	DecisionFlip    bool    `json:"decision_flip"`
	EncodeEncryptMS float64 `json:"encode_encrypt_ms"`
	EvalOnlyMS      float64 `json:"eval_only_ms"`
	DecryptDecodeMS float64 `json:"decrypt_decode_ms"`
	TotalEvalMS     float64 `json:"total_eval_ms"`
	InitialLevel    int     `json:"initial_level"`
	FinalLevel      int     `json:"final_level"`
}

type depthLadderRow struct {
	rowID         int
	x             float64
	plainScore    float64
	plainDecision bool
}

func (c Context) RunCKKSDepthLadderInference(config CKKSDepthLadderConfig) ([]CKKSDepthLadderRecord, error) {
	if config.Depth <= 0 || config.Threshold != 1 || config.DataPath == "" {
		return nil, fmt.Errorf("invalid depth-ladder execution configuration")
	}
	rows, err := loadDepthLadderRows(config.DataPath)
	if err != nil {
		return nil, err
	}
	for _, row := range rows {
		replayed := math.Pow(row.x, math.Pow(2, float64(config.Depth)))
		if math.Abs(replayed-row.plainScore) > 1e-12 || (row.plainScore >= config.Threshold) != row.plainDecision {
			return nil, fmt.Errorf("depth-ladder row %d plaintext replay mismatch", row.rowID)
		}
	}
	runtimeState, err := c.newCKKSTimingRuntime()
	if err != nil {
		return nil, fmt.Errorf("create depth-ladder CKKS runtime: %w", err)
	}
	records := make([]CKKSDepthLadderRecord, 0, len(rows))
	for _, row := range rows {
		totalStart := time.Now()
		encryptStart := time.Now()
		value, err := c.encryptSingleFeature(runtimeState.encoder, runtimeState.encryptor, row.x)
		if err != nil {
			return nil, fmt.Errorf("row %d encrypt: %w", row.rowID, err)
		}
		encodeEncryptMS := durationMS(time.Since(encryptStart))
		evalStart := time.Now()
		for rung := 1; rung <= config.Depth; rung++ {
			value, err = c.squareTabularCiphertext(runtimeState, value, CKKSEvaluationModeRescale)
			if err != nil {
				return nil, fmt.Errorf("row %d depth rung %d: %w", row.rowID, rung, err)
			}
		}
		evalOnlyMS := durationMS(time.Since(evalStart))
		decryptStart := time.Now()
		decoded, err := c.decryptFirstSlot(runtimeState.encoder, runtimeState.decryptor, value)
		if err != nil {
			return nil, fmt.Errorf("row %d decrypt: %w", row.rowID, err)
		}
		decryptDecodeMS := durationMS(time.Since(decryptStart))
		decision := decoded >= config.Threshold
		records = append(records, CKKSDepthLadderRecord{
			RowID: row.rowID, PlainScore: row.plainScore, CKKSScore: decoded,
			AbsError: math.Abs(decoded - row.plainScore), PlainDecision: row.plainDecision,
			CKKSDecision: decision, DecisionFlip: decision != row.plainDecision,
			EncodeEncryptMS: encodeEncryptMS, EvalOnlyMS: evalOnlyMS,
			DecryptDecodeMS: decryptDecodeMS, TotalEvalMS: durationMS(time.Since(totalStart)),
			InitialLevel: c.MaxLevel(), FinalLevel: value.Level(),
		})
	}
	return records, nil
}

func loadDepthLadderRows(path string) ([]depthLadderRow, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()
	records, err := csv.NewReader(handle).ReadAll()
	if err != nil || len(records) < 2 {
		return nil, fmt.Errorf("read depth-ladder rows: %w", err)
	}
	header := make(map[string]int, len(records[0]))
	for index, name := range records[0] {
		header[name] = index
	}
	required := []string{"row_id", "x_0", "plaintext_score", "plaintext_decision"}
	for _, name := range required {
		if _, ok := header[name]; !ok {
			return nil, fmt.Errorf("depth-ladder data missing %s", name)
		}
	}
	rows := make([]depthLadderRow, 0, len(records)-1)
	for index, record := range records[1:] {
		rowID, err := strconv.Atoi(record[header["row_id"]])
		if err != nil {
			return nil, fmt.Errorf("row %d id: %w", index+2, err)
		}
		x, err := strconv.ParseFloat(record[header["x_0"]], 64)
		if err != nil {
			return nil, fmt.Errorf("row %d input: %w", index+2, err)
		}
		score, err := strconv.ParseFloat(record[header["plaintext_score"]], 64)
		if err != nil {
			return nil, fmt.Errorf("row %d score: %w", index+2, err)
		}
		decision, err := strconv.ParseBool(record[header["plaintext_decision"]])
		if err != nil {
			return nil, fmt.Errorf("row %d decision: %w", index+2, err)
		}
		rows = append(rows, depthLadderRow{rowID: rowID, x: x, plainScore: score, plainDecision: decision})
	}
	return rows, nil
}
