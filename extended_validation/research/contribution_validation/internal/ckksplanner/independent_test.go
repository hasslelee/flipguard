package ckksplanner

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestIndependentGeneratorHasNoDecisionFields(t *testing.T) {
	typ := reflect.TypeOf(IndependentFacts{})
	want := map[string]bool{"ModelDigest": true, "InputDigest": true, "RequiredQPrimes": true, "RescaleLevels": true, "RequiredSlots": true, "MaxOutputAbs": true}
	for i := 0; i < typ.NumField(); i++ {
		if !want[typ.Field(i).Name] {
			t.Fatalf("unexpected information channel %s", typ.Field(i).Name)
		}
	}
	f := IndependentFacts{RequiredQPrimes: 5, RescaleLevels: 4, RequiredSlots: 500, MaxOutputAbs: 64}
	a, e := GenerateIndependentCandidate(f, 30, 0)
	if e != nil {
		t.Fatal(e)
	}
	f.ModelDigest = "changed identity"
	f.InputDigest = "another identity"
	b, e := GenerateIndependentCandidate(f, 30, 0)
	if e != nil {
		t.Fatal(e)
	}
	if !reflect.DeepEqual(a.Parameters, b.Parameters) {
		t.Fatal("identity affected numerical configuration")
	}
	if a.Parameters.LogDefaultScale != 30 {
		t.Fatal("hidden scale lifting")
	}
}

func TestIndependentRejectsInsteadOfHiddenRepair(t *testing.T) {
	f := IndependentFacts{RequiredQPrimes: 5, RescaleLevels: 4, RequiredSlots: 500, MaxOutputAbs: 1 << 20}
	if _, e := GenerateIndependentCandidate(f, 40, 0); e == nil {
		t.Fatal("invalid first prime silently accepted")
	}
}

// The same graph/range with a changed threshold must produce the same facts
// relevant to generation, although artifact digests change.
func TestIndependentTabularThresholdInvariance(t *testing.T) {
	if testing.Short() {
		t.Skip("workspace fixture")
	}
	root := filepath.Join("..", "..", "..", "..")
	model := filepath.Join(root, "results/fg_expand_v1_20260905_run01/plaintext/spambase__linear_poly3__split0_seed0/model.json")
	data := filepath.Join(root, "results/fg_expand_v1_20260905_run01/run/spambase__linear_poly3__split0_seed0/configuration_selection.prepared.csv")
	if _, e := os.Stat(model); os.IsNotExist(e) {
		t.Skip("fixture not in standalone module")
	}
	a, e := BuildIndependentFacts(model, data, false)
	if e != nil {
		t.Fatal(e)
	}
	raw, e := os.ReadFile(model)
	if e != nil {
		t.Fatal(e)
	}
	var m map[string]any
	if e = json.Unmarshal(raw, &m); e != nil {
		t.Fatal(e)
	}
	m["polynomial_score"].(map[string]any)["decision_threshold"] = 0.7
	raw, _ = json.Marshal(m)
	p := filepath.Join(t.TempDir(), "model.json")
	if e = os.WriteFile(p, raw, 0600); e != nil {
		t.Fatal(e)
	}
	b, e := BuildIndependentFacts(p, data, false)
	if e != nil {
		t.Fatal(e)
	}
	ca, e := GenerateIndependentCandidate(a, 30, 0)
	if e != nil {
		t.Fatal(e)
	}
	cb, e := GenerateIndependentCandidate(b, 30, 0)
	if e != nil {
		t.Fatal(e)
	}
	if !reflect.DeepEqual(ca.Parameters, cb.Parameters) {
		t.Fatal("decision threshold affected independent generation")
	}
}
