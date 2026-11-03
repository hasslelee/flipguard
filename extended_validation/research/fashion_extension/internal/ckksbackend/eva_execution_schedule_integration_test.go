package ckksbackend

import (
	"encoding/json"
	"math"
	"os"
	"testing"

	"github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

func TestEVAScheduleIntegrationDiagnostic(t *testing.T) {
	if os.Getenv("FLIPGUARD_RUN_EVA_SCHEDULE_DIAGNOSTIC") != "1" {
		t.Skip("set FLIPGUARD_RUN_EVA_SCHEDULE_DIAGNOSTIC=1")
	}
	profile, err := NewCKKSProfileFromLiteral(
		"eva_schedule_diagnostic",
		"pinned EVA v1.0.1 schedule diagnostic",
		ckks.ParametersLiteral{
			LogN: 14,
			Q: []uint64{
				1152921504605962241,
				1152921504606584833,
				1152921504606683137,
			},
			P:               []uint64{1152921504606748673},
			LogDefaultScale: 20,
		},
	)
	if err != nil {
		t.Fatalf("create EVA profile: %v", err)
	}
	context, err := NewContextFromProfile(profile)
	if err != nil {
		t.Fatalf("create EVA context: %v", err)
	}
	config := DefaultCKKSTabularInferenceConfig(
		"iris_binary",
		"linear_poly3",
	)
	config.ModelPath =
		"../../datasets/tabular_suite/iris_binary/linear_poly3/model.json"
	config.TestPath = "../../results/thesis_grade_protocol/" +
		"tabular_splits_v1/split_seed_0/iris_binary/linear_poly3/" +
		"configuration_validation.csv"
	config.MaxRows = 1
	config.EvaluationMode =
		CKKSEvaluationModeEVAV101LinearPoly3
	config.ScoreAbsErrorCap = 1
	config.ScoreRelErrorCap = 1

	records, summary, err := context.RunCKKSTabularInference(config)
	if err != nil {
		t.Fatalf("run EVA schedule diagnostic: %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("got %d records, expected one", len(records))
	}
	encoded, err := json.Marshal(records[0])
	if err != nil {
		t.Fatalf("marshal diagnostic record: %v", err)
	}
	t.Logf("EVA_DIAGNOSTIC_RECORD=%s", encoded)
	t.Logf(
		"EVA_DIAGNOSTIC_SUMMARY mode=%s initial=%d final=%d",
		summary.EvaluationMode,
		summary.InitialLevel,
		summary.FinalYLevel,
	)
	if math.Abs(records[0].CKKSZ-records[0].PlainZ) > 0.01 {
		t.Fatalf(
			"EVA linear score mismatch: plain=%g ckks=%g",
			records[0].PlainZ,
			records[0].CKKSZ,
		)
	}
	if math.IsNaN(records[0].CKKSY) ||
		math.IsInf(records[0].CKKSY, 0) {
		t.Fatalf(
			"EVA output score is not finite: %g",
			records[0].CKKSY,
		)
	}
	if records[0].InitialLevel != 2 ||
		records[0].ZLevel != 2 ||
		records[0].YLevel != 0 ||
		records[0].ZDegree != 1 ||
		records[0].YDegree != 1 {
		t.Fatalf(
			"unexpected EVA terminal state: %+v",
			records[0],
		)
	}
}
