// Bounded comparison orchestration. C uses the preserved synthesis, repair and
// certification functions. A/B share only independent graph/range generation.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/hasslelee/flipguard/internal/certify"
	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"math"
	"os"
	"path/filepath"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func load(p string, v any) { b, e := os.ReadFile(p); must(e); must(json.Unmarshal(b, v)) }

var ioMS float64
var thesisDelta = .001
var thesisRho = .5
var thesisSlack bool
var thesisBSlack bool

func ms(t time.Time) float64 { return float64(time.Since(t).Nanoseconds()) / 1e6 }
func save(p string, v any) {
	s := time.Now()
	must(os.MkdirAll(filepath.Dir(p), 0755))
	f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
	must(e)
	en := json.NewEncoder(f)
	en.SetIndent("", "  ")
	must(en.Encode(v))
	must(f.Sync())
	must(f.Close())
	ioMS += ms(s)
}

type Numeric struct {
	Key    int     `json:"key"`
	Count  int     `json:"count"`
	MaxAbs float64 `json:"max_abs"`
	RMSE   float64 `json:"rmse"`
}
type Trial struct {
	Candidate    ckksplanner.SynthesizedCandidate `json:"candidate"`
	Status       certify.CandidateStatus          `json:"status"`
	Failure      string                           `json:"failure,omitempty"`
	Signal       ckksplanner.RepairSignal         `json:"failure_signal,omitempty"`
	Keys         int                              `json:"keys"`
	Numeric      []Numeric                        `json:"numeric"`
	DecisionMS   float64                          `json:"decision_ms"`
	NumericMS    float64                          `json:"numeric_ms"`
	NativeWallMS float64                          `json:"native_wall_ms"`
}

func scalarNumeric(key int, rs []ckksbackend.CKKSTabularInferenceRecord) Numeric {
	n := Numeric{Key: key}
	sum := 0.
	for _, r := range rs {
		e := math.Abs(r.CKKSY - r.PlainY)
		n.MaxAbs = math.Max(n.MaxAbs, e)
		sum += e * e
		n.Count++
	}
	if n.Count > 0 {
		n.RMSE = math.Sqrt(sum / float64(n.Count))
	}
	return n
}
func multiNumeric(key int, rs []ckksbackend.JournalMNISTMulticlassRecord) Numeric {
	n := Numeric{Key: key}
	sum := 0.
	for _, r := range rs {
		for j, v := range r.CKKSLogits {
			e := math.Abs(v - r.PlainLogits[j])
			n.MaxAbs = math.Max(n.MaxAbs, e)
			sum += e * e
			n.Count++
		}
	}
	if n.Count > 0 {
		n.RMSE = math.Sqrt(sum / float64(n.Count))
	}
	return n
}
func execute(c ckksplanner.WorkloadContract, cand ckksplanner.SynthesizedCandidate, idx int, out string) Trial {
	started := time.Now()
	t := Trial{Candidate: cand, Numeric: []Numeric{}}
	if c.MulticlassDecision != nil {
		r, e := ckksplanner.ExecuteJournalMNISTMulticlassCandidateWithOptions(c, cand, idx, ckksplanner.MulticlassCandidateExecutionOptions{OnKeyRun: func(ev ckksplanner.MulticlassKeyRunEvidence) error {
			s := time.Now()
			n := multiNumeric(ev.KeyRun, ev.Records)
			t.NumericMS += ms(s)
			t.Numeric = append(t.Numeric, n)
			save(filepath.Join(out, fmt.Sprintf("key_%d.json", ev.KeyRun)), ev)
			fmt.Printf("key_complete %s %d\n", cand.ID, ev.KeyRun)
			return nil
		}})
		must(e)
		t.Status = r.Status
		t.Signal = r.FailureSignal
		t.Failure = r.Failure
		t.Keys = r.KeyRepeatsCompleted
		t.DecisionMS = r.DecisionEvaluationMS
		save(filepath.Join(out, "native_trial.json"), r)
	} else {
		r, e := ckksplanner.ExecuteTabularCandidateWithOptions(c, cand, idx, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true, OnKeyRun: func(ev ckksplanner.TabularKeyRunEvidence) error {
			s := time.Now()
			n := scalarNumeric(ev.KeyRun, ev.Records)
			t.NumericMS += ms(s)
			t.Numeric = append(t.Numeric, n)
			save(filepath.Join(out, fmt.Sprintf("key_%d.json", ev.KeyRun)), ev)
			fmt.Printf("key_complete %s %d\n", cand.ID, ev.KeyRun)
			return nil
		}})
		must(e)
		t.Status = r.Status
		t.Signal = r.FailureSignal
		t.Failure = r.Failure
		t.Keys = r.KeyRepeatsCompleted
		t.DecisionMS = r.DecisionEvaluationMS
		save(filepath.Join(out, "native_trial.json"), r)
	}
	t.NativeWallMS = ms(started)
	save(filepath.Join(out, "trial.json"), t)
	return t
}
func freshContract(old ckksplanner.WorkloadContract, data, role string) ckksplanner.WorkloadContract {
	if old.MulticlassDecision != nil {
		o := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()
		o.MarginFloor = thesisDelta
		o.MarginUtilizationCap = thesisRho
		o.ModelPath = old.ModelArtifact.Path
		o.ValidationPath = data
		o.SourcePath = old.SourceData.Path
		o.SplitID = old.SplitID
		o.ExpectedRole = role
		if role == "locked_audit" {
			o.SplitID = "contribution/locked_audit"
		}
		c, _, e := ckksplanner.BuildJournalMNISTMulticlassContract(o)
		must(e)
		return c
	}
	o := ckksplanner.DefaultPrimaryTabularContractOptions()
	o.MarginFloor = thesisDelta
	o.SafetyFactor = thesisRho
	o.ModelPath = old.ModelArtifact.Path
	o.ValidationPath = data
	o.SplitID = old.SplitID
	// The supplied prepared file already binds the exact raw source/model.
	if data == old.ValidationData.Path && old.SourceData != nil {
		o.SourceDataPath = old.SourceData.Path
	}
	if role == "locked_audit" {
		o.SplitID = "contribution/locked_audit"
	}
	c, e := ckksplanner.BuildTabularWorkloadContract(o)
	must(e)
	return c
}
func main() {
	mode := flag.String("mode", "generate", "generate|select|candidate|audit|timing")
	legacy := flag.String("legacy-plan", "", "preserved evaluation plan")
	out := flag.String("out", "", "fresh directory")
	role := flag.String("role", "C", "A|B|C")
	startScale := flag.Int("start-scale", 30, "independent fixed start")
	scale := flag.Int("scale", 30, "diagnostic scale")
	guard := flag.Int("q-guard", 0, "diagnostic extra Q primes")
	threshold := flag.Float64("threshold", 0, "development max-absolute-error threshold")
	candidate := flag.String("candidate", "", "frozen candidate")
	other := flag.String("other", "", "paired candidate")
	data := flag.String("data", "", "prepared evaluation CSV")
	modelPath := flag.String("model", "", "model for materialization/new-plan")
	keyset := flag.Int("keyset", 1, "fresh key block ordinal")
	flag.Float64Var(&thesisDelta, "delta", .001, "sensitivity margin floor")
	flag.Float64Var(&thesisRho, "rho", .5, "sensitivity error fraction")
	flag.BoolVar(&thesisSlack, "cprime", false, "isolated existing optional precision slack")
	flag.BoolVar(&thesisBSlack, "b-slack", false, "independent auxiliary slack")
	flag.Parse()
	if thesisSlack && *role != "C" {
		panic("Cprime only for C")
	}
	if thesisBSlack && *role != "B" {
		panic("B slack only for B")
	}
	if (thesisSlack || thesisBSlack) && (thesisDelta != .001 || thesisRho != .5) {
		panic("no compound policy variants")
	}
	must(os.MkdirAll(*out, 0755))
	if _, e := os.Stat(filepath.Join(*out, "result.json")); e == nil {
		panic("completed output exists")
	}
	start := time.Now()
	defer func() {
		if r := recover(); r != nil {
			save(filepath.Join(*out, fmt.Sprintf("failure_%d.json", time.Now().UnixNano())), map[string]any{"error": fmt.Sprint(r), "mode": *mode, "utc": time.Now().UTC(), "wall_ms": ms(start)})
			fmt.Fprintln(os.Stderr, r)
			os.Exit(1)
		}
	}()
	if *mode == "materialize" {
		r, e := ckksplanner.MaterializeTabularValidationWithOptions(*modelPath, *data, filepath.Join(*out, "prepared.csv"), ckksplanner.TabularMaterializationOptions{DataSpace: ckksplanner.TabularDataSpaceRaw})
		must(e)
		save(filepath.Join(*out, "result.json"), r)
		return
	}
	if *mode == "new-plan" {
		o := ckksplanner.DefaultPrimaryTabularContractOptions()
		o.MarginFloor = thesisDelta
		o.SafetyFactor = thesisRho
		o.ModelPath = *modelPath
		o.ValidationPath = *data
		o.SplitID = "external/configuration_selection"
		c, e := ckksplanner.BuildTabularWorkloadContract(o)
		must(e)
		p, e := ckksplanner.Synthesize(c, ckksplanner.DefaultPrimarySynthesisPolicy())
		must(e)
		save(filepath.Join(*out, "plan.json"), p)
		save(filepath.Join(*out, "result.json"), map[string]any{"wall_ms": ms(start)})
		return
	}
	var old ckksplanner.SynthesisPlan
	load(*legacy, &old)
	c := old.Contract
	if *data != "" && (*mode == "select" || *mode == "plan") {
		c = freshContract(c, *data, "configuration_validation")
	}
	if *mode == "generate" {
		s := time.Now()
		f, e := ckksplanner.BuildIndependentFacts(c.ModelArtifact.Path, c.ValidationData.Path, c.MulticlassDecision != nil)
		must(e)
		analysisMS := ms(s)
		cand, e := ckksplanner.GenerateIndependentCandidate(f, *scale, *guard)
		errText := ""
		if e != nil {
			errText = e.Error()
		}
		save(filepath.Join(*out, "result.json"), map[string]any{"facts": f, "candidate": cand, "failure": errText, "analysis_ms": analysisMS, "wall_ms": ms(start)})
		return
	}
	if *mode == "plan" {
		c = freshContract(c, c.ValidationData.Path, "configuration_validation")
		p, e := ckksplanner.ThesisInitialPlan(c, thesisSlack)
		must(e)
		cr, e := ckksplanner.ThesisConcreteRecord(p.InitialCandidates[0])
		must(e)
		save(filepath.Join(*out, "plan.json"), p)
		save(filepath.Join(*out, "result.json"), map[string]any{"plan": p, "concrete": cr, "wall_ms": ms(start), "new_encrypted_calls": 0})
		return
	}
	if *mode == "select" {
		if *role != "A" && *role != "B" && *role != "C" {
			panic("invalid role")
		}
		if *role == "A" && *threshold <= 0 {
			panic("positive numeric threshold required")
		}
		s := time.Now()
		var plan ckksplanner.SynthesisPlan
		var facts ckksplanner.IndependentFacts
		var e error
		if *role == "C" {
			c = freshContract(c, c.ValidationData.Path, "configuration_validation")
			plan, e = ckksplanner.ThesisInitialPlan(c, thesisSlack)
			must(e)
		} else {
			facts, e = ckksplanner.BuildIndependentFacts(c.ModelArtifact.Path, c.ValidationData.Path, c.MulticlassDecision != nil)
			must(e)
		}
		analysisMS := ms(s)
		save(filepath.Join(*out, "analysis.json"), map[string]any{"role": *role, "facts": facts, "plan": plan, "analysis_ms": analysisMS, "evaluation_contract": c, "generator_does_not_receive_evaluation_contract": *role != "C"})
		trials := []Trial{}
		generations := []map[string]any{}
		var selected *ckksplanner.SynthesizedCandidate
		var cand ckksplanner.SynthesizedCandidate
		if *role == "C" {
			cand = plan.InitialCandidates[0]
		}
		for idx := 1; idx <= 4; idx++ {
			if *role != "C" {
				s = time.Now()
				cand, e = ckksplanner.GenerateIndependentCandidate(facts, *startScale+4*(idx-1), 0)
				errText := ""
				if e != nil {
					errText = e.Error()
				}
				generations = append(generations, map[string]any{"ordinal": idx, "requested_scale": *startScale + 4*(idx-1), "failure": errText, "ms": ms(s)})
				if e != nil {
					continue
				}
			}
			if thesisBSlack {
				var at []map[string]any
				cand, at, e = ckksplanner.ThesisIndependentSlack(facts, cand)
				must(e)
				save(filepath.Join(*out, fmt.Sprintf("slack_static_%d.json", idx)), at)
			}
			concrete, e := ckksplanner.ThesisConcreteRecord(cand)
			must(e)
			save(filepath.Join(*out, fmt.Sprintf("concrete_%d.json", idx)), concrete)
			t := execute(c, cand, idx, filepath.Join(*out, fmt.Sprintf("trial_%d", idx)))
			trials = append(trials, t)
			accept := t.Keys == 3 && t.Failure == "" && t.Status == certify.StatusSafe
			if *role == "A" {
				accept = t.Keys == 3 && t.Failure == "" && len(t.Numeric) == 3
				for _, n := range t.Numeric {
					accept = accept && n.Count > 0 && n.MaxAbs <= *threshold
				}
			}
			if accept {
				cp := cand
				selected = &cp
				break
			}
			if *role == "C" {
				if idx == 4 || t.Signal == "" {
					break
				}
				cand, e = ckksplanner.RepairCandidate(plan, cand, t.Signal, idx)
				if errors.Is(e, ckksplanner.ErrRepairExhausted) {
					break
				}
				must(e)
			}
		}
		outcome := "NO_SELECTION"
		if selected != nil {
			outcome = "SELECTED"
		}
		save(filepath.Join(*out, "result.json"), map[string]any{"role": *role, "outcome": outcome, "selected": selected, "trials": trials, "generation_attempts": generations, "analysis_ms": analysisMS, "wall_ms": ms(start), "evidence_write_ms": ioMS, "threshold": *threshold, "start_scale": *startScale, "candidate_cap": 4, "actual_encrypted_candidates": len(trials), "key_block": *keyset, "protocol": "FG_THESIS_V1_20260908", "cprime": thesisSlack, "b_slack": thesisBSlack, "rho": thesisRho, "delta": thesisDelta, "numeric_posthoc_for_B_C": true, "decision_posthoc_for_A": true})
		return
	}
	var cand ckksplanner.SynthesizedCandidate
	load(*candidate, &cand)
	if *mode == "raw-stress" {
		p, e := cand.Profile()
		must(e)
		for k := 1; k <= 3; k++ {
			s := time.Now()
			ctx, e := ckksbackend.NewContextFromProfile(p)
			must(e)
			parameterMS := ms(s)
			s = time.Now()
			if c.MulticlassDecision != nil {
				ids := make([]int, 16)
				for i := range ids {
					ids[i] = i
				}
				rs, su, e := ctx.RunCKKSJournalMNISTMulticlassInference(ckksbackend.JournalMNISTMulticlassConfig{ModelPath: c.ModelArtifact.Path, DataPath: *data, Role: "locked_audit", SelectedRowIDs: ids})
				must(e)
				ev := ckksplanner.MulticlassKeyRunEvidence{SchemaVersion: "contribution_stress_no_labels_asserted_v1", KeyRun: k, CandidateID: cand.ID, Records: rs, Summary: su, ParameterMS: parameterMS, BackendMS: ms(s), Q: ctx.Params.Q(), P: ctx.Params.P()}
				save(filepath.Join(*out, fmt.Sprintf("key_%d.json", k)), ev)
			} else {
				cfg := ckksbackend.DefaultCKKSTabularInferenceConfig(c.DatasetID, c.ModelID)
				cfg.ModelPath = c.ModelArtifact.Path
				cfg.TestPath = *data
				cfg.MaxRows = 16
				cfg.EvaluationMode = "rescale"
				cfg.ScoreAbsErrorCap = 1
				cfg.ScoreRelErrorCap = 1
				rs, su, e := ctx.RunCKKSTabularInference(cfg)
				must(e)
				ev := ckksplanner.TabularKeyRunEvidence{KeyRun: k, CandidateID: cand.ID, Records: rs, Summary: su, ParameterMS: parameterMS, BackendMS: ms(s), Q: ctx.Params.Q(), P: ctx.Params.P()}
				save(filepath.Join(*out, fmt.Sprintf("key_%d.json", k)), ev)
			}
		}
		save(filepath.Join(*out, "result.json"), map[string]any{"candidate": cand, "keys": 3, "inputs": 16, "wall_ms": ms(start), "synthetic_labels_asserted": false, "status": "RAW_COMPLETED_NO_RISK_CLAIM"})
		return
	}
	if *mode == "candidate" || *mode == "audit" {
		if *mode == "audit" {
			c = freshContract(c, *data, "locked_audit")
			c.Calibration = old.Contract.Calibration
			save(filepath.Join(*out, "audit_contract.json"), c)
		}
		cr, e := ckksplanner.ThesisConcreteRecord(cand)
		must(e)
		save(filepath.Join(*out, "concrete.json"), cr)
		t := execute(c, cand, 1, *out)
		save(filepath.Join(*out, "result.json"), t)
		return
	}
	if *mode == "timing" {
		var comp ckksplanner.SynthesizedCandidate
		load(*other, &comp)
		p, e := cand.Profile()
		must(e)
		q, e := comp.Profile()
		must(e)
		if c.MulticlassDecision != nil {
			rows := make([]int, 20)
			for i := range rows {
				rows[i] = i * 499 / 19
			}
			cfg := ckksbackend.V17PrimaryPairedLatencyConfig{Kind: ckksbackend.V17PairedKindJournalMNIST, ModelPath: c.ModelArtifact.Path, DataPath: *data, SelectedRowIDs: rows, Keyset: *keyset, WarmupRuns: 1, MeasurementRuns: 6, MarginFloor: .001, UtilizationCap: .5, Arms: []ckksbackend.V17PrimaryPairedLatencyArm{{ID: "reference_C", Role: "frozen_C", CandidateID: cand.ID, Profile: p}, {ID: "comparator", Role: "frozen_comparator", CandidateID: comp.ID, Profile: q}}}
			f, e := os.OpenFile(filepath.Join(*out, "records.jsonl"), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
			must(e)
			en := json.NewEncoder(f)
			r, e := ckksbackend.RunV17PrimaryPairedLatencyKeyset(cfg, func(v ckksbackend.V17PrimaryPairedLatencyRecord) error {
				if e := en.Encode(v); e != nil {
					return e
				}
				return f.Sync()
			})
			must(e)
			must(f.Close())
			save(filepath.Join(*out, "result.json"), r)
		} else {
			r, e := ckksbackend.RunPairedTabularLatency(ckksbackend.PairedTabularLatencyConfig{ModelPath: c.ModelArtifact.Path, TestPath: *data, DatasetID: c.DatasetID, ModelID: c.ModelID, MaxRows: 20, WarmupRuns: 1, MeasureRuns: 6, Arms: []ckksbackend.PairedTabularLatencyArm{{ID: "reference_C", Role: "frozen_C", CandidateID: cand.ID, Profile: p, EvaluationMode: "rescale"}, {ID: "comparator", Role: "frozen_comparator", CandidateID: comp.ID, Profile: q, EvaluationMode: "rescale"}}})
			must(e)
			save(filepath.Join(*out, "result.json"), r)
		}
		save(filepath.Join(*out, "wall.json"), map[string]any{"wall_ms": ms(start), "key_block": *keyset})
		return
	}
	panic("invalid mode")
}
