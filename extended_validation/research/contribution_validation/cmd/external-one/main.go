// Independent original-policy selection on the preserved common cubic workload.
package main

import (
	"encoding/json"
	"flag"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
	"os"
	"path/filepath"
	"time"
)

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func save(p string, v any) {
	f, e := os.OpenFile(p, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644)
	must(e)
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	must(enc.Encode(v))
	must(f.Sync())
}
func main() {
	input := flag.String("input", "", "input root")
	out := flag.String("out", "", "exclusive output")
	flag.Parse()
	must(os.Mkdir(*out, 0755))
	o := ckksplanner.DefaultPrimaryTabularContractOptions()
	o.ModelPath = filepath.Join(*input, "model.json")
	o.ValidationPath = filepath.Join(*input, "configuration_validation.csv")
	o.SplitID = "shared_polynomial_v2/configuration_selection"
	start := time.Now()
	c, e := ckksplanner.BuildTabularWorkloadContract(o)
	must(e)
	p, e := ckksplanner.Synthesize(c, ckksplanner.DefaultPrimarySynthesisPolicy())
	must(e)
	r, e := ckksplanner.RunAdaptiveTabularAutotuneWithOptions(p, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
	must(e)
	save(filepath.Join(*out, "selection.json"), r)
	save(filepath.Join(*out, "selection_cost.json"), map[string]any{"wall_seconds": time.Since(start).Seconds()})
	if r.Selected == nil {
		save(filepath.Join(*out, "NO_SELECTION.json"), map[string]any{"status": r.Outcome})
		return
	}
	o.ValidationPath = filepath.Join(*input, "locked_audit.csv")
	o.SplitID = "shared_polynomial_v2/locked_audit"
	a, e := ckksplanner.BuildTabularWorkloadContract(o)
	must(e)
	a.Calibration = c.Calibration
	start = time.Now()
	t, e := ckksplanner.ExecuteTabularCandidateWithOptions(a, *r.Selected, 1, ckksplanner.TabularCandidateExecutionOptions{CaptureSampleLedger: true})
	must(e)
	save(filepath.Join(*out, "audit.json"), t)
	save(filepath.Join(*out, "audit_cost.json"), map[string]any{"wall_seconds": time.Since(start).Seconds(), "retuning": 0})
}
