//go:build externalv8

package main

import (
	"encoding/csv"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"strconv"
	"time"

	"github.com/hasslelee/flipguard/external/v8/generated/sharedpoly"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/providergate"
)

type splitManifest struct {
	LatencySubset struct {
		RowIDs []string `json:"row_ids"`
	} `json:"latency_subset"`
}

type inputRow struct {
	ID       int
	X        []float64
	Z        float64
	Y        float64
	Decision bool
}

type record struct {
	Keyset           int     `json:"keyset"`
	Pass             int     `json:"pass"`
	RowID            int     `json:"row_id"`
	OrderIndex       int     `json:"order_index"`
	OrderPosition    int     `json:"order_position"`
	Arm              string  `json:"arm"`
	CandidateID      string  `json:"candidate_id"`
	Plaintext        float64 `json:"plaintext"`
	Decrypted        float64 `json:"decrypted"`
	AbsoluteError    float64 `json:"absolute_error"`
	DecisionFlip     bool    `json:"decision_flip"`
	ReserveViolation bool    `json:"reserve_violation"`
	EncryptMS        float64 `json:"encrypt_ms"`
	EvaluateMS       float64 `json:"evaluate_ms"`
	DecryptMS        float64 `json:"decrypt_ms"`
	TotalMS          float64 `json:"total_ms"`
}

type output struct {
	SchemaVersion string           `json:"schema_version"`
	Workload      string           `json:"workload"`
	Protocol      map[string]any   `json:"protocol"`
	Arms          []map[string]any `json:"arms"`
	Setup         []map[string]any `json:"setup"`
	Records       []record         `json:"records"`
}

type heirRuntime struct {
	evaluator any
}

func mustFloat(value string) float64 {
	result, err := strconv.ParseFloat(value, 64)
	if err != nil {
		panic(err)
	}
	return result
}
func mustInt(value string) int {
	result, err := strconv.Atoi(value)
	if err != nil {
		panic(err)
	}
	return result
}

func loadRows(path string, manifestPath string) ([]inputRow, error) {
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, err
	}
	var manifest splitManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, err
	}
	wanted := map[int]bool{}
	for _, value := range manifest.LatencySubset.RowIDs {
		wanted[mustInt(value)] = true
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	all, err := csv.NewReader(file).ReadAll()
	if err != nil {
		return nil, err
	}
	header := map[string]int{}
	for index, name := range all[0] {
		header[name] = index
	}
	rows := make([]inputRow, 0, 100)
	for _, raw := range all[1:] {
		id := mustInt(raw[header["row_id"]])
		if !wanted[id] {
			continue
		}
		rows = append(rows, inputRow{ID: id, X: []float64{mustFloat(raw[header["x_0"]]), mustFloat(raw[header["x_1"]]), mustFloat(raw[header["x_2"]])}, Z: mustFloat(raw[header["scaled_logit"]]), Y: mustFloat(raw[header["polynomial_score"]]), Decision: raw[header["plaintext_decision"]] == "True" || raw[header["plaintext_decision"]] == "true"})
	}
	if len(rows) != 100 {
		return nil, fmt.Errorf("expected 100 frozen latency rows, got %d", len(rows))
	}
	for _, row := range rows {
		delete(wanted, row.ID)
	}
	if len(wanted) != 0 {
		return nil, fmt.Errorf("latency subset IDs missing")
	}
	return rows, nil
}

func orders() [][]int {
	return [][]int{{0, 1, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}, {0, 2, 1}, {1, 0, 2}}
}

func main() {
	directPath := flag.String("direct", "", "direct provider gate result")
	catalogPath := flag.String("catalog", "", "catalog provider gate result")
	modelPath := flag.String("model", "", "frozen model")
	auditPath := flag.String("audit", "", "frozen audit CSV")
	splitPath := flag.String("split-manifest", "", "frozen split manifest")
	outPath := flag.String("out", "", "output JSON")
	flag.Parse()
	if *directPath == "" || *catalogPath == "" || *modelPath == "" || *auditPath == "" || *splitPath == "" || *outPath == "" {
		panic("all arguments required")
	}
	rows, err := loadRows(*auditPath, *splitPath)
	if err != nil {
		panic(err)
	}
	direct, _, err := providergate.LoadProviderCandidateGateResult(*directPath)
	if err != nil {
		panic(err)
	}
	catalog, _, err := providergate.LoadProviderCandidateGateResult(*catalogPath)
	if err != nil {
		panic(err)
	}
	if direct.Outcome != "SELECTED" || catalog.Outcome != "SELECTED" || direct.Selected == nil || catalog.Selected == nil {
		panic("common executor arms must be SAFE")
	}
	directProfile, err := direct.Selected.Profile()
	if err != nil {
		panic(err)
	}
	catalogProfile, err := catalog.Selected.Profile()
	if err != nil {
		panic(err)
	}
	result := output{SchemaVersion: "flipguard_focused_external_v8_common_executor_v1", Workload: "shared_polynomial_threshold_v8", Protocol: map[string]any{"unique_inputs": 100, "fresh_keysets": 3, "warmup_passes": 1, "measurement_passes": 6, "order": "balanced_cyclic_and_reverse", "outlier_removal": false, "same_process": true, "same_lattigo_version": "v6.2.0"}, Arms: []map[string]any{{"arm": "heir_generated", "provider": "Google HEIR", "candidate_id": "heir_generated_lattigo_v8"}, {"arm": "flipguard_direct", "provider": "FlipGuard direct", "candidate_id": direct.Selected.ID}, {"arm": "bounded_catalog", "provider": "Security-V2 bounded catalog", "candidate_id": catalog.Selected.ID}}}
	armOrders := orders()
	for keyset := 1; keyset <= 3; keyset++ {
		heirSetup := time.Now()
		evaluator, params, encoder, encryptor, decryptor := sharedpoly.Shared_polynomial__configure()
		plains := sharedpoly.Shared_polynomial__preprocessing(params, encoder)
		heirSetupMS := float64(time.Since(heirSetup).Nanoseconds()) / 1e6
		directRuntime, directSetupMS, err := ckksbackend.NewExternalV8TabularRuntime(directProfile, *modelPath)
		if err != nil {
			panic(err)
		}
		catalogRuntime, catalogSetupMS, err := ckksbackend.NewExternalV8TabularRuntime(catalogProfile, *modelPath)
		if err != nil {
			panic(err)
		}
		result.Setup = append(result.Setup, map[string]any{"keyset": keyset, "arm": "heir_generated", "setup_ms": heirSetupMS}, map[string]any{"keyset": keyset, "arm": "flipguard_direct", "setup_ms": directSetupMS}, map[string]any{"keyset": keyset, "arm": "bounded_catalog", "setup_ms": catalogSetupMS})
		evaluate := func(arm int, row inputRow, pass int, orderIndex int, position int) record {
			if arm == 0 {
				total := time.Now()
				start := time.Now()
				a := sharedpoly.Shared_polynomial__encrypt__arg0(evaluator, params, encoder, encryptor, float32(row.X[0]))
				b := sharedpoly.Shared_polynomial__encrypt__arg1(evaluator, params, encoder, encryptor, float32(row.X[1]))
				c := sharedpoly.Shared_polynomial__encrypt__arg2(evaluator, params, encoder, encryptor, float32(row.X[2]))
				enc := float64(time.Since(start).Nanoseconds()) / 1e6
				start = time.Now()
				ct := sharedpoly.Shared_polynomial__preprocessed(evaluator, params, encoder, a, b, c, plains)
				eval := float64(time.Since(start).Nanoseconds()) / 1e6
				start = time.Now()
				actual := float64(sharedpoly.Shared_polynomial__decrypt__result0(evaluator, params, encoder, decryptor, ct))
				dec := float64(time.Since(start).Nanoseconds()) / 1e6
				error := math.Abs(actual - row.Y)
				margin := math.Abs(row.Y - 0.5)
				return record{keyset, pass, row.ID, orderIndex, position, "heir_generated", "heir_generated_lattigo_v8", row.Y, actual, error, (actual >= 0.5) != row.Decision, error >= 0.5*margin, enc, eval, dec, float64(time.Since(total).Nanoseconds()) / 1e6}
			}
			runtime := directRuntime
			armName := "flipguard_direct"
			candidate := direct.Selected.ID
			if arm == 2 {
				runtime = catalogRuntime
				armName = "bounded_catalog"
				candidate = catalog.Selected.ID
			}
			raw, err := runtime.Evaluate(row.ID, row.X, row.Z, row.Y, row.Decision)
			if err != nil {
				panic(err)
			}
			return record{keyset, pass, row.ID, orderIndex, position, armName, candidate, row.Y, raw.CKKSY, raw.YError, raw.DecisionFlip, raw.ErrorViolation, raw.EncodeEncryptMS, raw.EvalOnlyMS, raw.DecryptDecodeMS, raw.TotalEvalMS}
		}
		for index, row := range rows {
			order := armOrders[index%len(armOrders)]
			for position, arm := range order {
				_ = evaluate(arm, row, 0, index%len(armOrders)+1, position+1)
			}
		}
		for pass := 1; pass <= 6; pass++ {
			for index, row := range rows {
				oi := (pass - 1 + index) % len(armOrders)
				for position, arm := range armOrders[oi] {
					result.Records = append(result.Records, evaluate(arm, row, pass, oi+1, position+1))
				}
			}
		}
	}
	if len(result.Records) != 5400 {
		panic(fmt.Sprintf("expected 5400 records, got %d", len(result.Records)))
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		panic(err)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(*outPath, encoded, 0644); err != nil {
		panic(err)
	}
}
