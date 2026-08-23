package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const schema = "flipguard_v17_primary_paired_latency_combined_v1"

type selectedEnvelope struct {
	Selected *ckksplanner.SynthesizedCandidate `json:"selected"`
	Result   *struct {
		Selected *ckksplanner.SynthesizedCandidate `json:"selected"`
	} `json:"result"`
}

type finiteEnvelope struct {
	FastestSafe *ckksplanner.SynthesizedCandidate `json:"fastest_safe"`
}

type subsetManifest struct {
	SchemaVersion string `json:"schema_version"`
	Subsets       []struct {
		ID       string `json:"id"`
		Kind     string `json:"kind"`
		ModelID  string `json:"model_id"`
		RowIDs   []int  `json:"row_ids"`
		Rule     string `json:"selection_rule"`
		DataPath string `json:"data_path"`
		SHA256   string `json:"data_sha256"`
	} `json:"subsets"`
}

type combinedResult struct {
	SchemaVersion        string                                      `json:"schema_version"`
	Kind                 string                                      `json:"kind"`
	ModelID              string                                      `json:"model_id"`
	SubsetID             string                                      `json:"subset_id"`
	SubsetSHA256         string                                      `json:"subset_manifest_sha256"`
	BinarySHA256         string                                      `json:"binary_sha256"`
	ModelSHA256          string                                      `json:"model_sha256"`
	DataSHA256           string                                      `json:"data_sha256"`
	DirectSourceSHA256   string                                      `json:"direct_source_sha256"`
	FiniteSourceSHA256   string                                      `json:"finite_source_sha256"`
	DirectAuditSHA256    string                                      `json:"direct_audit_sha256"`
	FiniteAuditSHA256    string                                      `json:"finite_audit_sha256"`
	Direct               ckksplanner.SynthesizedCandidate            `json:"direct_candidate"`
	FastestSafe          ckksplanner.SynthesizedCandidate            `json:"finite_fastest_safe_candidate"`
	FreshKeysets         int                                         `json:"fresh_keysets"`
	WarmupRuns           int                                         `json:"warmup_runs"`
	MeasureRuns          int                                         `json:"measurement_runs"`
	KeysetResults        []ckksbackend.V17PrimaryPairedLatencyResult `json:"keyset_results"`
	Records              []ckksbackend.V17PrimaryPairedLatencyRecord `json:"records"`
	PairSummary          map[string]float64                          `json:"pair_summary"`
	NoRetuning           bool                                        `json:"no_retuning"`
	SafeToSafeEligible   bool                                        `json:"safe_to_safe_eligible"`
	NonSafeTimingRecords int                                         `json:"non_safe_timing_records"`
}

func main() {
	kind := flag.String("kind", "", "journal_mnist_multiclass or packed_cnn_lite_binary01")
	model := flag.String("model", "", "frozen model artifact")
	data := flag.String("data", "", "frozen independent-evaluation CSV")
	directSource := flag.String("direct-source", "", "JSON containing the frozen direct selected candidate")
	finiteSource := flag.String("finite-source", "", "V17 B3 exhaustive JSON")
	directAuditSource := flag.String("direct-audit-source", "", "independent-evaluation JSON for the direct arm")
	finiteAuditSource := flag.String("finite-audit-source", "", "independent-evaluation JSON for the finite fastest-SAFE arm")
	subsetPath := flag.String("subset-manifest", "", "frozen V17 latency subset manifest")
	subsetID := flag.String("subset-id", "", "subset identity")
	outRoot := flag.String("out-root", "", "new resumable result root")
	stopRequest := flag.String("stop-request", "", "optional stop request checked after a complete keyset")
	preflightOnly := flag.Bool("preflight-only", false, "validate frozen inputs and arm materialization without CKKS execution")
	flag.Parse()
	if *kind == "" || *model == "" || *data == "" || *directSource == "" || *finiteSource == "" || *directAuditSource == "" || *finiteAuditSource == "" || *subsetPath == "" || *subsetID == "" || *outRoot == "" {
		fatalf("all flags are required")
	}
	if *kind != ckksbackend.V17PairedKindJournalMNIST && *kind != ckksbackend.V17PairedKindPackedCNN {
		fatalf("unsupported kind %q", *kind)
	}
	direct := loadDirectCandidate(*directSource)
	fastest := loadFastestCandidate(*finiteSource)
	for role, candidate := range map[string]ckksplanner.SynthesizedCandidate{"direct": direct, "finite_fastest_safe": fastest} {
		if candidate.Security.FinalAdmission != ckksplanner.SecurityAdmissionPass {
			fatalf("%s candidate is not Security-V2 admitted", role)
		}
	}
	requireSafeAudit(*directAuditSource, direct.ID, "direct")
	requireSafeAudit(*finiteAuditSource, fastest.ID, "finite_fastest_safe")
	rows := loadSubset(*subsetPath, *subsetID, *kind, *data)
	profiles := make([]ckksbackend.V17PrimaryPairedLatencyArm, 0, 2)
	for _, item := range []struct {
		id, role  string
		candidate ckksplanner.SynthesizedCandidate
	}{
		{id: "direct", role: "DIRECT_SELECTED", candidate: direct},
		{id: "finite_fastest_safe", role: "V17_B3_FASTEST_SAFE", candidate: fastest},
	} {
		profile, err := item.candidate.Profile()
		if err != nil {
			fatalf("materialize %s: %v", item.role, err)
		}
		profiles = append(profiles, ckksbackend.V17PrimaryPairedLatencyArm{ID: item.id, Role: item.role, CandidateID: item.candidate.ID, Profile: profile})
	}
	if *preflightOnly {
		fmt.Printf("v17_primary_paired_latency_preflight=PASS kind=%s subset=%s rows=%d arms=%d\n", *kind, *subsetID, len(rows), len(profiles))
		return
	}
	finalPath := filepath.Join(*outRoot, "paired_latency.json")
	if _, err := os.Stat(finalPath); err == nil {
		fmt.Printf("paired latency already complete: %s\n", finalPath)
		return
	}
	if err := os.MkdirAll(*outRoot, 0o755); err != nil {
		fatalf("create output: %v", err)
	}

	keysetResults := make([]ckksbackend.V17PrimaryPairedLatencyResult, 0, 3)
	allRecords := make([]ckksbackend.V17PrimaryPairedLatencyRecord, 0, 36)
	for keyset := 1; keyset <= 3; keyset++ {
		keysetPath := filepath.Join(*outRoot, fmt.Sprintf("keyset_%02d.json", keyset))
		result, created, err := loadOrRunKeyset(keysetPath, func() (ckksbackend.V17PrimaryPairedLatencyResult, error) {
			return ckksbackend.RunV17PrimaryPairedLatencyKeyset(
				ckksbackend.V17PrimaryPairedLatencyConfig{
					Kind: *kind, ModelPath: *model, DataPath: *data, SelectedRowIDs: rows,
					Keyset: keyset, WarmupRuns: 1, MeasurementRuns: 6,
					MarginFloor: 0.001, UtilizationCap: 0.5, Arms: profiles,
				},
				func(record ckksbackend.V17PrimaryPairedLatencyRecord) error { return nil },
			)
		})
		if err != nil {
			fatalf("keyset %d: %v", keyset, err)
		}
		if created {
			writeExclusiveJSON(keysetPath, result)
		}
		keysetResults = append(keysetResults, result)
		allRecords = append(allRecords, result.Records...)
		if *stopRequest != "" {
			if _, err := os.Stat(*stopRequest); err == nil {
				fmt.Printf("checkpoint_after_keyset=%d output=%s\n", keyset, keysetPath)
				os.Exit(75)
			} else if !os.IsNotExist(err) {
				fatalf("inspect stop request: %v", err)
			}
		}
	}
	modelID := "packed_cnn_lite_binary01_v17"
	if len(keysetResults) > 0 && keysetResults[0].ModelID != "" {
		modelID = keysetResults[0].ModelID
	}
	nonSafe := 0
	for _, record := range allRecords {
		if record.Status != "SAFE" {
			nonSafe++
		}
	}
	combined := combinedResult{
		SchemaVersion: schema, Kind: *kind, ModelID: modelID, SubsetID: *subsetID,
		SubsetSHA256: digestFile(*subsetPath), BinarySHA256: digestSelf(),
		ModelSHA256: digestFile(*model), DataSHA256: digestFile(*data),
		DirectSourceSHA256: digestFile(*directSource), FiniteSourceSHA256: digestFile(*finiteSource),
		DirectAuditSHA256: digestFile(*directAuditSource), FiniteAuditSHA256: digestFile(*finiteAuditSource),
		Direct: direct, FastestSafe: fastest,
		FreshKeysets: 3, WarmupRuns: 1, MeasureRuns: 6,
		KeysetResults: keysetResults, Records: allRecords,
		PairSummary: summarizePairs(allRecords), NoRetuning: true,
		SafeToSafeEligible: nonSafe == 0, NonSafeTimingRecords: nonSafe,
	}
	writeExclusiveJSON(finalPath, combined)
	fmt.Printf("kind=%s model=%s keysets=3 records=%d output=%s\n", *kind, modelID, len(allRecords), finalPath)
}

func loadOrRunKeyset(path string, run func() (ckksbackend.V17PrimaryPairedLatencyResult, error)) (ckksbackend.V17PrimaryPairedLatencyResult, bool, error) {
	var result ckksbackend.V17PrimaryPairedLatencyResult
	if loadJSON(path, &result) {
		return result, false, nil
	}
	var err error
	result, err = run()
	if err != nil {
		return ckksbackend.V17PrimaryPairedLatencyResult{}, false, err
	}
	return result, true, nil
}

func loadDirectCandidate(path string) ckksplanner.SynthesizedCandidate {
	var envelope selectedEnvelope
	readJSON(path, &envelope)
	if envelope.Selected != nil {
		return *envelope.Selected
	}
	if envelope.Result != nil && envelope.Result.Selected != nil {
		return *envelope.Result.Selected
	}
	fatalf("direct source has no selected candidate: %s", path)
	return ckksplanner.SynthesizedCandidate{}
}

func loadFastestCandidate(path string) ckksplanner.SynthesizedCandidate {
	var envelope finiteEnvelope
	readJSON(path, &envelope)
	if envelope.FastestSafe == nil {
		fatalf("finite source has no fastest SAFE candidate: %s", path)
	}
	return *envelope.FastestSafe
}

func loadSubset(path, subsetID, kind, dataPath string) []int {
	var manifest subsetManifest
	readJSON(path, &manifest)
	for _, subset := range manifest.Subsets {
		if subset.ID != subsetID {
			continue
		}
		if subset.Kind != kind || subset.DataPath != dataPath || subset.SHA256 != digestFile(dataPath) || len(subset.RowIDs) != 20 {
			fatalf("latency subset binding mismatch for %s", subsetID)
		}
		return append([]int(nil), subset.RowIDs...)
	}
	fatalf("latency subset not found: %s", subsetID)
	return nil
}

func requireSafeAudit(path, candidateID, role string) {
	var document any
	readJSON(path, &document)
	if !containsSafeCandidateAudit(document, candidateID) {
		fatalf("%s arm lacks matching SAFE independent-evaluation evidence in %s", role, path)
	}
}

func containsSafeCandidateAudit(value any, candidateID string) bool {
	switch item := value.(type) {
	case map[string]any:
		if status, ok := item["status"].(string); ok && status == "SAFE" {
			if candidate, ok := item["candidate"].(map[string]any); ok && candidate["id"] == candidateID {
				return true
			}
		}
		for _, child := range item {
			if containsSafeCandidateAudit(child, candidateID) {
				return true
			}
		}
	case []any:
		for _, child := range item {
			if containsSafeCandidateAudit(child, candidateID) {
				return true
			}
		}
	}
	return false
}

func summarizePairs(records []ckksbackend.V17PrimaryPairedLatencyRecord) map[string]float64 {
	type pair struct{ directTotal, finiteTotal, directEval, finiteEval float64 }
	pairs := make(map[[2]int]*pair)
	for _, record := range records {
		key := [2]int{record.Keyset, record.MeasurementRun}
		if pairs[key] == nil {
			pairs[key] = &pair{}
		}
		if record.ArmID == "direct" {
			pairs[key].directTotal = record.TotalMS
			pairs[key].directEval = record.EvaluationOnlyMS
		} else if record.ArmID == "finite_fastest_safe" {
			pairs[key].finiteTotal = record.TotalMS
			pairs[key].finiteEval = record.EvaluationOnlyMS
		}
	}
	totalRatios := make([]float64, 0, len(pairs))
	evalRatios := make([]float64, 0, len(pairs))
	for _, item := range pairs {
		if item.directTotal > 0 && item.finiteTotal > 0 && item.directEval > 0 && item.finiteEval > 0 {
			totalRatios = append(totalRatios, item.finiteTotal/item.directTotal)
			evalRatios = append(evalRatios, item.finiteEval/item.directEval)
		}
	}
	if len(totalRatios) == 0 {
		return map[string]float64{"pairs": 0}
	}
	sort.Float64s(totalRatios)
	sort.Float64s(evalRatios)
	totalLogSum, evalLogSum := 0.0, 0.0
	for index := range totalRatios {
		totalLogSum += math.Log(totalRatios[index])
		evalLogSum += math.Log(evalRatios[index])
	}
	return map[string]float64{
		"pairs": float64(len(totalRatios)),
		"finite_over_direct_geometric_mean_total_ratio":     math.Exp(totalLogSum / float64(len(totalRatios))),
		"finite_over_direct_geometric_mean_eval_only_ratio": math.Exp(evalLogSum / float64(len(evalRatios))),
		"minimum_total_ratio":                               totalRatios[0], "median_total_ratio": totalRatios[len(totalRatios)/2], "maximum_total_ratio": totalRatios[len(totalRatios)-1],
		"minimum_eval_only_ratio": evalRatios[0], "median_eval_only_ratio": evalRatios[len(evalRatios)/2], "maximum_eval_only_ratio": evalRatios[len(evalRatios)-1],
	}
}

func loadJSON(path string, target any) bool {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return false
	}
	if err != nil {
		fatalf("read %s: %v", path, err)
	}
	if err := json.Unmarshal(data, target); err != nil {
		fatalf("parse %s: %v", path, err)
	}
	return true
}

func readJSON(path string, target any) { _ = loadJSON(path, target) }

func writeExclusiveJSON(path string, value any) {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fatalf("marshal %s: %v", path, err)
	}
	handle, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o644)
	if err != nil {
		fatalf("create %s: %v", path, err)
	}
	if _, err := handle.Write(append(data, '\n')); err != nil {
		_ = handle.Close()
		fatalf("write %s: %v", path, err)
	}
	if err := handle.Sync(); err != nil {
		_ = handle.Close()
		fatalf("sync %s: %v", path, err)
	}
	if err := handle.Close(); err != nil {
		fatalf("close %s: %v", path, err)
	}
}

func digestFile(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		fatalf("digest %s: %v", path, err)
	}
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func digestSelf() string {
	path, err := os.Executable()
	if err != nil {
		fatalf("resolve executable: %v", err)
	}
	return digestFile(path)
}

func fatalf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "flipguard-v17-primary-paired-latency: "+format+"\n", args...)
	os.Exit(1)
}
