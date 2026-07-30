package decisionactivation

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

func TestDecisionContractActivationControl(t *testing.T) {
	root := filepath.Join(t.TempDir(), "control")
	analysis, err := WriteAndAnalyze(root, "test-source-commit")
	if err != nil {
		t.Fatalf("write and analyze control: %v", err)
	}
	if analysis.StaticClaimState != "SUPPORTED" {
		t.Fatalf(
			"decision-contract activation not observed: %+v",
			analysis.Regimes,
		)
	}
	if len(analysis.Regimes) != 2 {
		t.Fatalf("unexpected regime count %d", len(analysis.Regimes))
	}
	narrow := analysis.Regimes[0]
	wide := analysis.Regimes[1]
	if narrow.AggregateSensitivity != wide.AggregateSensitivity {
		t.Fatal("aggregate sensitivity differs between regimes")
	}
	if narrow.GraphFixed.Parameters.LogDefaultScale !=
		wide.GraphFixed.Parameters.LogDefaultScale {
		t.Fatal("graph-fixed scale changed between regimes")
	}
	if narrow.DecisionContract.Parameters.LogDefaultScale <=
		narrow.GraphFixed.Parameters.LogDefaultScale {
		t.Fatalf(
			"narrow decision contract did not increase scale: full=%d graph=%d",
			narrow.DecisionContract.Parameters.LogDefaultScale,
			narrow.GraphFixed.Parameters.LogDefaultScale,
		)
	}
	if wide.DecisionContract.Parameters.LogDefaultScale !=
		wide.GraphFixed.Parameters.LogDefaultScale {
		t.Fatalf(
			"wide decision contract did not remain at the backend floor: full=%d graph=%d",
			wide.DecisionContract.Parameters.LogDefaultScale,
			wide.GraphFixed.Parameters.LogDefaultScale,
		)
	}
	for _, regime := range analysis.Regimes {
		if regime.GraphFixed.Security.AdmissionStatus !=
			ckksplanner.SecurityAdmissionPass ||
			regime.DecisionContract.Security.AdmissionStatus !=
				ckksplanner.SecurityAdmissionPass {
			t.Fatalf("security admission failed: %+v", regime)
		}
		if regime.Validation.Rows != 32 ||
			regime.LockedAudit.Rows != 32 {
			t.Fatalf("unexpected control row count: %+v", regime)
		}
	}
	if _, err := os.Stat(
		filepath.Join(root, "static_analysis.json"),
	); err != nil {
		t.Fatalf("static analysis artifact: %v", err)
	}
}

func TestDecisionContractActivationRefusesOverwrite(t *testing.T) {
	root := filepath.Join(t.TempDir(), "nested", "control")
	if _, err := WriteAndAnalyze(root, "first-source-commit"); err != nil {
		t.Fatalf("first control write: %v", err)
	}
	if _, err := WriteAndAnalyze(root, "second-source-commit"); err == nil {
		t.Fatal("control unexpectedly overwrote existing output")
	}
}
